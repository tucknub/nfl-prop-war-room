from __future__ import annotations

from datetime import datetime, timezone
import re

import pandas as pd

from src.common import load_config, output_path, raw_path


PROFILE_COLUMNS = [
    "player_id",
    "player_name",
    "team",
    "opponent",
    "position",
    "primary_market_family",
    "all_families_count",
    "best_signal_score",
    "overall_signal_score",
    "signal_tier",
    "recommended_user_action",
    "signal_explanation",
    "top_signal_reason",
    "review_reason",
    "blocked_reason",
    "top_positive_driver_1",
    "top_positive_driver_2",
    "top_positive_driver_3",
    "top_negative_driver_1",
    "top_negative_driver_2",
    "top_negative_driver_3",
    "green_signal_count",
    "yellow_signal_count",
    "red_flag_count",
    "missing_signal_count",
    "data_quality_score",
    "readiness_status",
    "roster_status",
    "role_status",
    "injury_status",
    "usage_status",
    "final_readiness",
]
MARKET_FAMILIES = ["receiving", "rushing", "passing"]
FAMILY_FLAGS = {
    "receiving": "receiving_market_available",
    "rushing": "rushing_market_available",
    "passing": "passing_market_available",
}
MARKET_COLUMNS = [
    "player_id",
    "player_name",
    "team",
    "opponent",
    "position",
    "market_family",
    "receptions_projection",
    "receiving_yards_projection",
    "rushing_yards_projection",
    "carries_projection",
    "pass_attempts_projection",
    "completions_projection",
    "passing_yards_projection",
    "overall_signal_score",
    "signal_tier",
    "recommended_user_action",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
    "signal_explanation",
    "top_positive_driver_1",
    "top_negative_driver_1",
]
CONTEXT_COLUMNS = [
    "player_id",
    "player_name",
    "team",
    "opponent",
    "position",
    "spread_line",
    "total_line",
    "team_implied_total",
    "favorite_status",
    "spread_bucket",
    "game_total_bucket",
    "pass_volume_environment",
    "rush_volume_environment",
    "opp_receiving_fit_score",
    "opp_rushing_fit_score",
    "opp_passing_fit_score",
    "defense_fit_reliability",
    "defense_fit_sample_games",
    "recent_form_reliability",
    "game_environment_reliability",
    "context_data_quality",
    "context_notes",
]
WEEKLY_RENAME = {
    "opponent_team": "opponent",
    "attempts": "pass_attempts",
}
RECENT_HISTORY_COLUMNS = [
    "player_id",
    "player_name",
    "season",
    "week",
    "team",
    "opponent",
    "position",
    "targets",
    "receptions",
    "receiving_yards",
    "carries",
    "rushing_yards",
    "pass_attempts",
    "completions",
    "passing_yards",
    "touchdowns_if_available",
]


def read_output(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def read_raw(filename: str) -> pd.DataFrame:
    path = raw_path(filename)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def normalize_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value).lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def row_families(row: pd.Series) -> list[str]:
    families = []
    for family, flag in FAMILY_FLAGS.items():
        if str(row.get(flag, "")).lower() in {"true", "1", "yes"}:
            families.append(family)
    if families:
        return families
    raw = str(row.get("market_family", "") or "")
    return [family for family in MARKET_FAMILIES if family in raw] or ["unknown"]


def serious_text(series: pd.Series) -> str:
    values = [str(value).strip() for value in series.dropna().tolist() if str(value).strip()]
    return "; ".join(dict.fromkeys(values))


def build_market_summary(master: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, source in master.iterrows():
        for family in row_families(source):
            record = source.to_dict()
            record["market_family"] = family
            rows.append(record)
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=MARKET_COLUMNS)
    return out[[col for col in MARKET_COLUMNS if col in out.columns]]


def build_profiles(master: pd.DataFrame, market_summary: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame(columns=PROFILE_COLUMNS)
    rows = []
    for _, row in master.iterrows():
        player_key = str(row.get("player_id", "") or "").strip()
        player_name = str(row.get("player_name", "") or "")
        team = str(row.get("team", "") or "")
        if player_key:
            player_markets = market_summary[market_summary["player_id"].fillna("").astype(str).eq(player_key)]
        else:
            player_markets = market_summary[
                market_summary["player_name"].fillna("").astype(str).eq(player_name)
                & market_summary["team"].fillna("").astype(str).eq(team)
            ]
        if player_markets.empty:
            families = row_families(row)
            primary = families[0] if families else "unknown"
            best_score = row.get("overall_signal_score")
        else:
            scores = pd.to_numeric(player_markets["overall_signal_score"], errors="coerce")
            idx = scores.idxmax() if scores.notna().any() else player_markets.index[0]
            primary = str(player_markets.loc[idx, "market_family"])
            best_score = player_markets.loc[idx, "overall_signal_score"]
        record = {col: row.get(col, "NOT_AVAILABLE") for col in PROFILE_COLUMNS if col in row.index}
        record["primary_market_family"] = primary
        record["all_families_count"] = len(set(player_markets["market_family"].dropna().astype(str))) if not player_markets.empty else len(row_families(row))
        record["best_signal_score"] = best_score
        if not player_markets.empty:
            record["review_reason"] = serious_text(player_markets.get("review_reason", pd.Series(dtype=str))) or row.get("review_reason", "")
            record["blocked_reason"] = serious_text(player_markets.get("blocked_reason", pd.Series(dtype=str))) or row.get("blocked_reason", "")
            red_flags = pd.to_numeric(player_markets.get("red_flag_count", pd.Series(dtype=float)), errors="coerce").fillna(0)
            record["red_flag_count"] = int(red_flags.max()) if not red_flags.empty else 0
        rows.append(record)
    out = pd.DataFrame(rows)
    for col in PROFILE_COLUMNS:
        if col not in out.columns:
            out[col] = "NOT_AVAILABLE"
    return out[PROFILE_COLUMNS].sort_values("best_signal_score", ascending=False, na_position="last")


def build_context_summary(master: pd.DataFrame) -> pd.DataFrame:
    if master.empty:
        return pd.DataFrame(columns=CONTEXT_COLUMNS)
    cols = [col for col in CONTEXT_COLUMNS if col in master.columns]
    out = master[cols].copy()
    for col in CONTEXT_COLUMNS:
        if col not in out.columns:
            out[col] = "NOT_AVAILABLE"
    return out[CONTEXT_COLUMNS]


def current_player_keys(master: pd.DataFrame) -> tuple[set[str], set[str]]:
    ids = set(master.get("player_id", pd.Series(dtype=str)).dropna().astype(str))
    ids = {value for value in ids if value and value.lower() != "nan"}
    names = set(master.get("player_name", pd.Series(dtype=str)).map(normalize_name))
    return ids, {value for value in names if value}


def build_recent_history(master: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    weekly = read_raw("weekly.csv")
    cfg = load_config()
    target_order = int(cfg["data"]["target_season"]) * 100 + int(cfg["data"]["target_week"])
    metadata = {"weekly_available": not weekly.empty, "target_or_future_rows_excluded": 0, "history_status": "AVAILABLE"}
    if weekly.empty:
        metadata["history_status"] = "NOT_AVAILABLE"
        return pd.DataFrame(columns=RECENT_HISTORY_COLUMNS + ["history_notes"]), metadata
    data = weekly.rename(columns=WEEKLY_RENAME).copy()
    data["season"] = pd.to_numeric(data.get("season"), errors="coerce")
    data["week"] = pd.to_numeric(data.get("week"), errors="coerce")
    data["_game_order"] = data["season"] * 100 + data["week"]
    metadata["target_or_future_rows_excluded"] = int((data["_game_order"] >= target_order).sum())
    data = data[data["_game_order"] < target_order].copy()
    ids, names = current_player_keys(master)
    id_match = data.get("player_id", pd.Series([""] * len(data))).fillna("").astype(str).isin(ids) if ids else pd.Series(False, index=data.index)
    name_match = data.get("player_name", data.get("player_display_name", pd.Series([""] * len(data)))).map(normalize_name).isin(names)
    data = data[id_match | name_match].copy()
    if "player_name" not in data.columns and "player_display_name" in data.columns:
        data["player_name"] = data["player_display_name"]
    td_cols = [col for col in ["receiving_tds", "rushing_tds", "passing_tds", "special_teams_tds"] if col in data.columns]
    data["touchdowns_if_available"] = data[td_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) if td_cols else "NOT_AVAILABLE"
    extra_cols = [col for col in data.columns if "snap" in col.lower() or "route" in col.lower()]
    cols = [col for col in RECENT_HISTORY_COLUMNS if col in data.columns] + extra_cols
    out = data[cols].copy() if cols else pd.DataFrame(columns=RECENT_HISTORY_COLUMNS)
    for col in RECENT_HISTORY_COLUMNS:
        if col not in out.columns:
            out[col] = "NOT_AVAILABLE"
    out["history_notes"] = "Prior games only; target week and future rows excluded from drilldown history."
    sort_cols = [col for col in ["player_name", "season", "week"] if col in out.columns]
    return out.sort_values(sort_cols, ascending=[True, False, False] if len(sort_cols) == 3 else True), metadata


def write_report(profiles: pd.DataFrame, market: pd.DataFrame, history: pd.DataFrame, context: pd.DataFrame, metadata: dict[str, object]) -> None:
    text = f"""# Player Signal Profiles Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Report status: `RESEARCH_ONLY`

Player profiles rows: `{len(profiles)}`

Market summary rows: `{len(market)}`

Recent history rows: `{len(history)}`

Context summary rows: `{len(context)}`

Weekly history status: `{metadata.get('history_status')}`

Target/future weekly rows excluded: `{metadata.get('target_or_future_rows_excluded')}`

Safety note: `Drilldown outputs explain signal strength only. They do not create live output or change production scoring.`
"""
    output_path("run_reports/latest_player_signal_profiles_report.md").write_text(text, encoding="utf-8")


def export_player_signal_profiles() -> dict[str, pd.DataFrame]:
    master = read_output("signal_boards/player_week_signal_master.csv")
    if master.empty:
        raise RuntimeError("player_week_signal_master.csv is required before player signal drilldown profiles.")
    market = build_market_summary(master)
    profiles = build_profiles(master, market)
    context = build_context_summary(master)
    history, metadata = build_recent_history(master)
    profiles.to_csv(output_path("signal_boards/player_signal_profiles.csv"), index=False)
    market.to_csv(output_path("signal_boards/player_signal_market_summary.csv"), index=False)
    context.to_csv(output_path("signal_boards/player_signal_context_summary.csv"), index=False)
    history.to_csv(output_path("signal_boards/player_signal_recent_history.csv"), index=False)
    write_report(profiles, market, history, context, metadata)
    return {"profiles": profiles, "market": market, "context": context, "history": history}


def main() -> None:
    outputs = export_player_signal_profiles()
    print(f"player_signal_profiles: {len(outputs['profiles']):,} rows")
    print(f"player_signal_market_summary: {len(outputs['market']):,} rows")
    print(f"player_signal_context_summary: {len(outputs['context']):,} rows")
    print(f"player_signal_recent_history: {len(outputs['history']):,} rows")


if __name__ == "__main__":
    main()
