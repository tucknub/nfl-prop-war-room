from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from src.common import output_path
from src.export.signal_explainability import add_explainability_columns


MARKET_FILES = {
    "receptions": ("google_sheets_receptions_historical_test.csv", "projected_receptions_calibrated", "receptions_projection"),
    "receiving_yards": ("google_sheets_receiving_yards_historical_test.csv", "projected_receiving_yards_calibrated", "receiving_yards_projection"),
    "rushing_yards": ("google_sheets_rushing_yards_historical_test.csv", "projected_rushing_yards_calibrated", "rushing_yards_projection"),
    "carries": ("google_sheets_carries_historical_test.csv", "projected_carries_calibrated", "carries_projection"),
    "pass_attempts": ("google_sheets_pass_attempts_historical_test.csv", "projected_pass_attempts_calibrated", "pass_attempts_projection"),
    "completions": ("google_sheets_completions_historical_test.csv", "projected_completions_calibrated", "completions_projection"),
    "passing_yards": ("google_sheets_passing_yards_historical_test.csv", "projected_passing_yards_calibrated", "passing_yards_projection"),
}

BASE_COLS = ["season", "week", "player_id", "player_name", "team", "opponent", "position", "usage_status"]
CONTEXT_JOIN_KEYS = ["season", "week", "player_id"]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def gate_status(relative: str) -> str:
    frame = read_csv(relative)
    if frame.empty or "status" not in frame.columns:
        return "MISSING"
    return str(frame["status"].iloc[0])


def final_readiness() -> tuple[str, str]:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    final = "NO-GO"
    live = "False"
    if not status.empty and {"check_name", "value"}.issubset(status.columns):
        final_row = status[status["check_name"].astype(str).eq("final_live_readiness")]
        live_row = status[status["check_name"].astype(str).eq("live_betting_output_created")]
        if not final_row.empty:
            final = str(final_row["value"].iloc[0])
        if not live_row.empty:
            live = str(live_row["value"].iloc[0])
    return final, live


def normalize_market_frame(market_key: str, file_name: str, source_col: str, out_col: str) -> pd.DataFrame:
    frame = read_csv(file_name)
    if frame.empty:
        return pd.DataFrame(columns=BASE_COLS + [out_col])
    out = pd.DataFrame()
    out["season"] = frame.get("season", pd.Series([pd.NA] * len(frame)))
    out["week"] = frame.get("week", pd.Series([pd.NA] * len(frame)))
    out["player_id"] = frame.get("player_id", pd.Series([""] * len(frame))).fillna("").astype(str)
    out["player_name"] = frame.get("player_name", pd.Series([""] * len(frame))).fillna("").astype(str)
    out["team"] = frame.get("team", pd.Series([""] * len(frame))).fillna("").astype(str)
    opponent = frame.get("opponent", frame.get("opponent_team", pd.Series([""] * len(frame))))
    out["opponent"] = opponent.fillna("").astype(str)
    out["position"] = frame.get("position", pd.Series([""] * len(frame))).fillna("").astype(str)
    out["usage_status"] = frame.get("usage_status", pd.Series(["HISTORICAL TEST ONLY"] * len(frame))).fillna("HISTORICAL TEST ONLY").astype(str)
    out[out_col] = pd.to_numeric(frame.get(source_col), errors="coerce") if source_col in frame.columns else pd.NA
    out[f"{market_key}_confidence_bucket"] = frame.get("confidence_bucket", pd.Series([""] * len(frame))).fillna("").astype(str)
    out[f"{market_key}_quality_flags"] = frame.get("quality_flags", pd.Series([""] * len(frame))).fillna("").astype(str)
    out["_merge_key"] = out.apply(lambda row: row["player_id"] if row["player_id"] else f"{row['player_name']}|{row['team']}|{row['position']}", axis=1)
    return out


def percentile_score(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series([pd.NA] * len(series), index=series.index)
    return (numeric.rank(pct=True) * 100).round(2)


def context_score_from_columns(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    scores = []
    for column in columns:
        if column in df.columns:
            scores.append(percentile_score(df[column]))
    if not scores:
        return pd.Series([pd.NA] * len(df), index=df.index)
    return pd.to_numeric(pd.concat(scores, axis=1).max(axis=1), errors="coerce").round(2)


def reliability_available(series: pd.Series) -> pd.Series:
    return series.fillna("MISSING").astype(str).isin(["HIGH", "MEDIUM", "LOW"])


def load_context_features() -> pd.DataFrame:
    context = read_csv("signal_boards/signal_context_features.csv")
    if context.empty:
        return context
    for key in CONTEXT_JOIN_KEYS:
        if key not in context.columns:
            return pd.DataFrame()
    context = context.copy()
    context["player_id"] = context["player_id"].fillna("").astype(str)
    context["season"] = pd.to_numeric(context["season"], errors="coerce")
    context["week"] = pd.to_numeric(context["week"], errors="coerce")
    return context.drop_duplicates(subset=CONTEXT_JOIN_KEYS)


def projection_family_score(df: pd.DataFrame) -> pd.Series:
    projection_cols = [
        "receptions_projection",
        "receiving_yards_projection",
        "rushing_yards_projection",
        "carries_projection",
        "pass_attempts_projection",
        "completions_projection",
        "passing_yards_projection",
    ]
    scores = []
    for col in projection_cols:
        if col in df.columns:
            scores.append(percentile_score(df[col]))
    if not scores:
        return pd.Series([pd.NA] * len(df), index=df.index)
    return pd.concat(scores, axis=1).max(axis=1).round(2)


def usage_foundation_score(df: pd.DataFrame) -> pd.Series:
    receiving = df[["receptions_projection", "receiving_yards_projection"]].notna().sum(axis=1) if {"receptions_projection", "receiving_yards_projection"}.issubset(df.columns) else 0
    rushing = df[["carries_projection", "rushing_yards_projection"]].notna().sum(axis=1) if {"carries_projection", "rushing_yards_projection"}.issubset(df.columns) else 0
    passing = df[["pass_attempts_projection", "completions_projection", "passing_yards_projection"]].notna().sum(axis=1) if {"pass_attempts_projection", "completions_projection", "passing_yards_projection"}.issubset(df.columns) else 0
    raw = pd.concat([pd.Series(receiving, index=df.index), pd.Series(rushing, index=df.index), pd.Series(passing, index=df.index)], axis=1).max(axis=1)
    return (raw / 3 * 100).round(2)


def tier(score: float, red_flags: int, missing: int) -> str:
    if red_flags > 0:
        return "REVIEW"
    if pd.isna(score):
        return "INSUFFICIENT_DATA"
    if missing >= 4 and score >= 80:
        return "STRONG_SIGNAL"
    if score >= 85:
        return "ELITE_SIGNAL"
    if score >= 72:
        return "STRONG_SIGNAL"
    if score >= 58:
        return "GOOD_SIGNAL"
    if score >= 40:
        return "WATCH"
    return "REVIEW"


def signal_tier(row: pd.Series) -> str:
    red_flags = int(row.get("red_flag_count", 0))
    missing = int(row.get("missing_signal_count", 0))
    score = row.get("overall_signal_score")
    if red_flags > 0:
        return "REVIEW"
    if pd.isna(score):
        return "INSUFFICIENT_DATA"
    context_available = bool(row.get("recent_context_available", False) or row.get("defense_context_available", False) or row.get("game_context_available", False))
    if score >= 85 and row.get("projection_score", 0) >= 75 and row.get("data_quality_score", 0) >= 65 and context_available:
        return "ELITE_SIGNAL"
    if missing >= 5 and score >= 80:
        return "STRONG_SIGNAL"
    if score >= 72:
        return "STRONG_SIGNAL"
    if score >= 58:
        return "GOOD_SIGNAL"
    if score >= 40:
        return "WATCH"
    return "REVIEW"


def export_player_week_signal_master() -> pd.DataFrame:
    frames = [normalize_market_frame(key, *spec) for key, spec in MARKET_FILES.items()]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        master = pd.DataFrame(columns=BASE_COLS)
    else:
        combined = pd.concat(frames, ignore_index=True, sort=False)
        agg: dict[str, str] = {}
        for col in combined.columns:
            if col == "_merge_key":
                continue
            agg[col] = "first"
        projection_cols = [spec[2] for spec in MARKET_FILES.values()]
        for col in projection_cols:
            if col in combined.columns:
                agg[col] = "max"
        master = combined.groupby("_merge_key", as_index=False).agg(agg)
        master = master.drop(columns=["_merge_key"], errors="ignore")

    final, live_output = final_readiness()
    roster_status = gate_status("roster/current_roster_map_status.csv")
    role_status = gate_status("roles/current_role_map_status.csv")
    injury_status = gate_status("injuries/current_injury_map_status.csv")
    intake = gate_status("data_intake/live_data_intake_status.csv",) if False else "NO-GO"

    context = load_context_features()
    if not context.empty and not master.empty:
        master["season"] = pd.to_numeric(master["season"], errors="coerce")
        master["week"] = pd.to_numeric(master["week"], errors="coerce")
        master["player_id"] = master["player_id"].fillna("").astype(str)
        context_cols = [col for col in context.columns if col not in {"player_name", "team", "opponent", "position"}]
        master = master.merge(context[context_cols], on=CONTEXT_JOIN_KEYS, how="left")

    projection_cols = [col for col in MARKET_FILES.values() if col[2] in master.columns]
    master["receiving_market_available"] = master[["receptions_projection", "receiving_yards_projection"]].notna().any(axis=1)
    master["rushing_market_available"] = master[["rushing_yards_projection", "carries_projection"]].notna().any(axis=1)
    master["passing_market_available"] = master[["pass_attempts_projection", "completions_projection", "passing_yards_projection"]].notna().any(axis=1)
    master["projection_score"] = projection_family_score(master)
    master["usage_foundation_score"] = usage_foundation_score(master)
    master["recent_form_score"] = context_score_from_columns(
        master,
        [
            "l3_targets",
            "l3_receptions",
            "l3_receiving_yards",
            "l3_carries",
            "l3_rushing_yards",
            "l3_pass_attempts",
            "l3_completions",
            "l3_passing_yards",
        ],
    )
    master["opponent_fit_score"] = context_score_from_columns(master, ["opp_receiving_fit_score", "opp_rushing_fit_score", "opp_passing_fit_score"])
    if "game_script_score" not in master.columns:
        master["game_script_score"] = pd.NA
    master["weather_score"] = pd.NA
    master["role_availability_score"] = 35 if any(status != "READY" for status in [roster_status, role_status, injury_status]) else 85
    flags = " ".join(master.filter(like="quality_flags").fillna("").astype(str).agg(" ".join, axis=1).tolist()) if not master.empty else ""
    confidence_text = master.filter(like="confidence_bucket").apply(lambda row: " ".join(str(value) for value in row.fillna("").tolist()), axis=1) if not master.empty else pd.Series(dtype=str)
    master["volatility_score"] = confidence_text.map(lambda text: 75 if "High" in text else (55 if "Medium" in text else 40))
    missing_id = master["player_id"].fillna("").astype(str).eq("") if "player_id" in master.columns else True
    missing_context = master["team"].fillna("").astype(str).eq("") | master["position"].fillna("").astype(str).eq("")
    missing_family = ~(master["receiving_market_available"] | master["rushing_market_available"] | master["passing_market_available"])
    live_context_missing = any(status != "READY" for status in [roster_status, role_status, injury_status])
    master["recent_context_available"] = reliability_available(master.get("recent_form_reliability", pd.Series(["MISSING"] * len(master), index=master.index)))
    master["defense_context_available"] = reliability_available(master.get("defense_fit_reliability", pd.Series(["MISSING"] * len(master), index=master.index)))
    master["game_context_available"] = reliability_available(master.get("game_environment_reliability", pd.Series(["MISSING"] * len(master), index=master.index)))
    unavailable_context_count = (~master["recent_context_available"]).astype(int) + (~master["defense_context_available"]).astype(int) + (~master["game_context_available"]).astype(int) + 1
    master["missing_signal_count"] = unavailable_context_count + missing_id.astype(int) + missing_context.astype(int) + missing_family.astype(int) + int(live_context_missing)
    context_quality = pd.to_numeric(master.get("context_data_quality", pd.Series([55] * len(master), index=master.index)), errors="coerce").fillna(55)
    base_quality = (100 - master["missing_signal_count"] * 7).clip(lower=20)
    master["data_quality_score"] = ((base_quality * 0.65) + (context_quality * 0.35)).clip(lower=20, upper=95).round(2)
    score_parts = [
        ("projection_score", 0.35),
        ("usage_foundation_score", 0.20),
        ("recent_form_score", 0.15),
        ("opponent_fit_score", 0.10),
        ("game_script_score", 0.10),
        ("role_availability_score", 0.05),
        ("data_quality_score", 0.05),
    ]
    numerator = pd.Series(0.0, index=master.index)
    denominator = pd.Series(0.0, index=master.index)
    for column, weight in score_parts:
        if column not in master.columns:
            continue
        values = pd.to_numeric(master[column], errors="coerce")
        mask = values.notna()
        numerator = numerator + values.fillna(0) * weight
        denominator = denominator + mask.astype(float) * weight
    master["overall_signal_score"] = (numerator / denominator.replace(0, pd.NA)).round(2)
    master["red_flag_count"] = missing_family.astype(int) + (master["usage_status"].astype(str).ne("HISTORICAL TEST ONLY")).astype(int)
    master["green_signal_count"] = (
        (master["projection_score"] >= 75).astype(int)
        + (master["usage_foundation_score"] >= 60).astype(int)
        + (pd.to_numeric(master["recent_form_score"], errors="coerce") >= 65).astype(int)
        + (pd.to_numeric(master["opponent_fit_score"], errors="coerce") >= 65).astype(int)
    )
    master["yellow_signal_count"] = ((master["projection_score"] >= 45) & (master["projection_score"] < 75)).astype(int)
    master["signal_tier"] = master.apply(signal_tier, axis=1)
    master["top_signal_reason"] = "Projection-led signal with pre-target recent form, schedule game environment, and shrinkage-adjusted defense fit where sourced."
    context_gaps = []
    if not master["recent_context_available"].all():
        context_gaps.append("recent form missing for some players")
    if not master["defense_context_available"].all():
        context_gaps.append("defense fit missing/low reliability for some players")
    if not master["game_context_available"].all():
        context_gaps.append("game environment missing for some players")
    context_gap_text = "; ".join(context_gaps) if context_gaps else "context features sourced"
    master["review_reason"] = "Context V1: " + context_gap_text + "; weather, route share, first-read share, and coverage are not sourced."
    master["blocked_reason"] = master.apply(lambda row: "Missing projection family." if not (row["receiving_market_available"] or row["rushing_market_available"] or row["passing_market_available"]) else "", axis=1)
    master["roster_status"] = roster_status
    master["role_status"] = role_status
    master["injury_status"] = injury_status
    master["readiness_status"] = "DATA_NEEDS_LIVE_CONTEXT" if final != "GO" else "READY"
    master["final_readiness"] = final
    master["live_betting_output_created"] = live_output
    master = add_explainability_columns(master)

    ordered = [
        "season", "week", "player_id", "player_name", "team", "opponent", "position",
        "receptions_projection", "receiving_yards_projection", "rushing_yards_projection", "carries_projection",
        "pass_attempts_projection", "completions_projection", "passing_yards_projection",
        "l3_targets", "l5_targets", "l8_targets", "l3_receptions", "l5_receptions", "l8_receptions",
        "l3_receiving_yards", "l5_receiving_yards", "l8_receiving_yards",
        "l3_carries", "l5_carries", "l8_carries", "l3_rushing_yards", "l5_rushing_yards", "l8_rushing_yards",
        "l3_pass_attempts", "l5_pass_attempts", "l8_pass_attempts", "l3_completions", "l5_completions", "l8_completions",
        "l3_passing_yards", "l5_passing_yards", "l8_passing_yards",
        "spread_line", "total_line", "team_implied_total", "opponent_implied_total", "favorite_status",
        "spread_bucket", "game_total_bucket", "pass_volume_environment", "rush_volume_environment",
        "opp_receiving_fit_score", "opp_rushing_fit_score", "opp_passing_fit_score",
        "defense_fit_sample_games", "defense_fit_reliability", "recent_form_reliability",
        "game_environment_reliability", "context_data_quality",
        "receiving_market_available", "rushing_market_available", "passing_market_available",
        "projection_score", "usage_foundation_score", "recent_form_score", "opponent_fit_score", "game_script_score",
        "weather_score", "role_availability_score", "volatility_score", "data_quality_score", "overall_signal_score",
        "signal_tier", "green_signal_count", "yellow_signal_count", "red_flag_count", "missing_signal_count",
        "top_signal_reason", "review_reason", "blocked_reason", "roster_status", "role_status", "injury_status",
        "readiness_status", "usage_status", "final_readiness", "live_betting_output_created",
        "signal_explanation", "recommended_user_action", "top_positive_driver_1", "top_positive_driver_2",
        "top_negative_driver_1", "top_negative_driver_2",
    ]
    for col in ordered:
        if col not in master.columns:
            master[col] = pd.NA
    master = master[ordered + [col for col in master.columns if col not in ordered]]
    master = master.sort_values("overall_signal_score", ascending=False)
    master.to_csv(output_path("signal_boards/player_week_signal_master.csv"), index=False)
    write_report(master, roster_status, role_status, injury_status, final, live_output)
    return master


def write_report(master: pd.DataFrame, roster: str, role: str, injury: str, final: str, live_output: str) -> None:
    text = f"""# Player Week Signal Master Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Rows: `{len(master)}`

Final readiness: `{final}`

Live betting output created: `{live_output}`

Live context: roster `{roster}`, role `{role}`, injury `{injury}`

Scoring status: `CONTEXT_ENRICHED_V1`

Available context: `pre-target recent form, schedules.csv game environment, shrinkage-adjusted defense fit`

Unavailable context: `weather, route share, first-read share, shadow coverage, CB matchup, practice trend`

Next required action: Source real live context and unavailable matchup data before treating signal tiers as full slate confidence.
"""
    output_path("run_reports/latest_player_week_signal_master_report.md").write_text(text, encoding="utf-8")


def main() -> None:
    master = export_player_week_signal_master()
    print(f"player_week_signal_master: {len(master):,} rows")
    print(f"signal_tiers: {', '.join(sorted(master['signal_tier'].dropna().astype(str).unique())) if not master.empty else 'None'}")


if __name__ == "__main__":
    main()
