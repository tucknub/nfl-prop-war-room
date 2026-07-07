from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path, raw_path
from src.export.signal_scoring import (
    assign_signal_tier,
    count_signal_colors,
    score_data_quality,
    score_game_script,
    score_opponent_fit,
    score_percentile_series,
    score_recent_form,
)


SEASONS = [2023, 2024]
BASE_COLUMNS = ["season", "week", "game_id", "player_id", "player_name", "team", "opponent", "position"]
FAMILIES = {
    "receiving": {
        "actual": "actual_receiving_yards",
        "metric": "receiving_yards",
        "usage": "targets",
        "recent": ["l3_receiving_yards", "l5_receiving_yards", "l8_receiving_yards", "l3_targets"],
        "fit": "opp_allowed_rec_yards_per_game_to_position",
    },
    "rushing": {
        "actual": "actual_rushing_yards",
        "metric": "rushing_yards",
        "usage": "carries",
        "recent": ["l3_rushing_yards", "l5_rushing_yards", "l8_rushing_yards", "l3_carries"],
        "fit": "opp_allowed_rush_yards_per_game_to_position",
    },
    "passing": {
        "actual": "actual_passing_yards",
        "metric": "passing_yards",
        "usage": "attempts",
        "recent": ["l3_passing_yards", "l5_passing_yards", "l8_passing_yards", "l3_pass_attempts"],
        "fit": "opp_allowed_passing_yards_per_game",
    },
}
SCORE_BUCKETS = [0, 40, 55, 70, 85, 101]
SCORE_BUCKET_LABELS = ["0-39", "40-54", "55-69", "70-84", "85-100"]
COMPONENTS = [
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
]


def read_csv(path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add_shifted_rolling(weekly: pd.DataFrame) -> pd.DataFrame:
    data = weekly.sort_values(["player_id", "season", "week"]).copy()
    stat_map = {
        "targets": "targets",
        "receptions": "receptions",
        "receiving_yards": "receiving_yards",
        "carries": "carries",
        "rushing_yards": "rushing_yards",
        "attempts": "pass_attempts",
        "completions": "completions",
        "passing_yards": "passing_yards",
    }
    for source, out_name in stat_map.items():
        if source not in data.columns:
            continue
        values = pd.to_numeric(data[source], errors="coerce")
        shifted = values.groupby(data["player_id"]).shift(1)
        for window in [3, 5, 8]:
            data[f"l{window}_{out_name}"] = shifted.groupby(data["player_id"]).rolling(window, min_periods=1).mean().reset_index(level=0, drop=True)
    data["pregame_sample_games"] = data.groupby("player_id").cumcount().clip(upper=8)
    return data


def add_schedule_context(rows: pd.DataFrame, schedules: pd.DataFrame) -> pd.DataFrame:
    if schedules.empty or not {"season", "week", "home_team", "away_team"}.issubset(schedules.columns):
        rows["game_environment_reliability"] = "MISSING"
        return rows
    games = schedules.copy()
    games["season"] = pd.to_numeric(games["season"], errors="coerce")
    games["week"] = pd.to_numeric(games["week"], errors="coerce")
    expanded = []
    for _, game in games.iterrows():
        spread = pd.to_numeric(game.get("spread_line"), errors="coerce")
        total = pd.to_numeric(game.get("total_line"), errors="coerce")
        for team_col, opp_col, is_home in [("home_team", "away_team", True), ("away_team", "home_team", False)]:
            team_spread = spread if is_home else (-spread if pd.notna(spread) else pd.NA)
            expanded.append(
                {
                    "season": game["season"],
                    "week": game["week"],
                    "team": str(game.get(team_col, "")),
                    "opponent": str(game.get(opp_col, "")),
                    "game_id_schedule": game.get("game_id", ""),
                    "home_team": game.get("home_team", ""),
                    "away_team": game.get("away_team", ""),
                    "is_home": is_home,
                    "spread_line": team_spread,
                    "total_line": total,
                    "game_environment_reliability": "MEDIUM" if pd.notna(team_spread) and pd.notna(total) else "MISSING",
                }
            )
    env = pd.DataFrame(expanded)
    out = rows.merge(env, on=["season", "week", "team", "opponent"], how="left")
    out["game_environment_reliability"] = out["game_environment_reliability"].fillna("MISSING")
    out["game_script_score"] = score_game_script(out)
    return out


def add_defense_fit(rows: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
    data = weekly.copy()
    data["_game_order"] = pd.to_numeric(data["season"], errors="coerce") * 100 + pd.to_numeric(data["week"], errors="coerce")
    out = rows.copy()
    out["_game_order"] = pd.to_numeric(out["season"], errors="coerce") * 100 + pd.to_numeric(out["week"], errors="coerce")
    specs = [
        ("receiving", ["WR", "TE", "RB", "FB"], "receiving_yards", "opp_allowed_rec_yards_per_game_to_position"),
        ("rushing", ["RB", "FB", "QB", "WR", "TE"], "rushing_yards", "opp_allowed_rush_yards_per_game_to_position"),
        ("passing", ["QB"], "passing_yards", "opp_allowed_passing_yards_per_game"),
    ]
    for family, positions, source_col, out_col in specs:
        if source_col not in data.columns:
            out[out_col] = pd.NA
            continue
        allowed = data[data["position"].astype(str).isin(positions)].copy()
        allowed[source_col] = pd.to_numeric(allowed[source_col], errors="coerce").fillna(0)
        weekly_allowed = allowed.groupby(["opponent_team", "position", "_game_order"], as_index=False)[source_col].sum()
        weekly_allowed = weekly_allowed.sort_values(["opponent_team", "position", "_game_order"])
        weekly_allowed[out_col] = weekly_allowed.groupby(["opponent_team", "position"])[source_col].transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
        weekly_allowed[f"{family}_defense_fit_sample_games"] = weekly_allowed.groupby(["opponent_team", "position"]).cumcount()
        merge_cols = ["opponent_team", "position", "_game_order", out_col, f"{family}_defense_fit_sample_games"]
        out = out.merge(
            weekly_allowed[merge_cols].rename(columns={"opponent_team": "opponent"}),
            on=["opponent", "position", "_game_order"],
            how="left",
        )
    sample_cols = [col for col in out.columns if col.endswith("_defense_fit_sample_games")]
    out["defense_fit_sample_games"] = out[sample_cols].max(axis=1) if sample_cols else pd.NA
    out["defense_fit_reliability"] = pd.cut(
        pd.to_numeric(out["defense_fit_sample_games"], errors="coerce").fillna(0),
        bins=[-1, 0, 2, 4, 999],
        labels=["MISSING", "LOW", "MEDIUM", "HIGH"],
    ).astype(str)
    return out.drop(columns=["_game_order"], errors="ignore")


def build_family_rows(base: pd.DataFrame, family: str) -> pd.DataFrame:
    spec = FAMILIES[family]
    required = [spec["metric"], spec["usage"]]
    if not set(required).issubset(base.columns):
        return pd.DataFrame()
    actual_metric = pd.to_numeric(base[spec["metric"]], errors="coerce").fillna(0)
    usage_metric = pd.to_numeric(base[spec["usage"]], errors="coerce").fillna(0)
    active = (actual_metric > 0) | (usage_metric > 0)
    rows = base[active].copy()
    if rows.empty:
        return rows
    rows["market_family"] = family
    rows["actual_receptions"] = pd.to_numeric(rows.get("receptions"), errors="coerce")
    rows["actual_receiving_yards"] = pd.to_numeric(rows.get("receiving_yards"), errors="coerce")
    rows["actual_carries"] = pd.to_numeric(rows.get("carries"), errors="coerce")
    rows["actual_rushing_yards"] = pd.to_numeric(rows.get("rushing_yards"), errors="coerce")
    rows["actual_pass_attempts"] = pd.to_numeric(rows.get("attempts"), errors="coerce")
    rows["actual_completions"] = pd.to_numeric(rows.get("completions"), errors="coerce")
    rows["actual_passing_yards"] = pd.to_numeric(rows.get("passing_yards"), errors="coerce")
    rows["actual_primary_value"] = rows[spec["actual"]]
    rows["actual_primary_metric"] = spec["actual"].replace("actual_", "")
    rows["pregame_projection_proxy"] = rows[[col for col in spec["recent"] if col in rows.columns]].mean(axis=1)
    rows["usage_proxy"] = pd.to_numeric(rows.get(f"l3_{'pass_attempts' if family == 'passing' else spec['usage']}"), errors="coerce")
    rows["opponent_fit_raw"] = pd.to_numeric(rows.get(spec["fit"]), errors="coerce")
    return rows


def score_rows(rows: pd.DataFrame) -> pd.DataFrame:
    scored = []
    for (_, week, family), group in rows.groupby(["season", "week", "market_family"], dropna=False):
        frame = group.copy()
        frame["projection_score"] = score_percentile_series(frame["pregame_projection_proxy"])
        frame["usage_foundation_score"] = score_percentile_series(frame["usage_proxy"])
        frame["recent_form_score"] = score_recent_form(frame, FAMILIES[family]["recent"])
        frame["opponent_fit_score"] = score_opponent_fit(frame, [FAMILIES[family]["fit"]])
        frame["role_availability_score"] = 60
        frame["volatility_score"] = pd.to_numeric(frame["pregame_sample_games"], errors="coerce").clip(0, 8) / 8 * 35 + 35
        frame["missing_signal_count"] = (
            frame[["pregame_projection_proxy", "usage_proxy", "opponent_fit_raw", "game_script_score"]]
            .isna()
            .sum(axis=1)
        )
        frame["data_quality_score"] = score_data_quality(frame)
        parts = [
            ("projection_score", 0.35),
            ("usage_foundation_score", 0.20),
            ("recent_form_score", 0.15),
            ("opponent_fit_score", 0.10),
            ("game_script_score", 0.10),
            ("role_availability_score", 0.05),
            ("data_quality_score", 0.05),
        ]
        numerator = pd.Series(0.0, index=frame.index)
        denominator = pd.Series(0.0, index=frame.index)
        for column, weight in parts:
            values = pd.to_numeric(frame[column], errors="coerce")
            mask = values.notna()
            numerator += values.fillna(0) * weight
            denominator += mask.astype(float) * weight
        frame["overall_signal_score"] = (numerator / denominator.replace(0, pd.NA)).round(2)
        frame = count_signal_colors(frame)
        frame["signal_tier"] = frame.apply(assign_signal_tier, axis=1)
        frame["backtest_usage_status"] = "HISTORICAL SIGNAL BACKTEST ONLY"
        frame["data_limitations"] = "Pregame proxy scores only; no sportsbook prices, no live role/injury gates, no weather source."
        frame["feature_source_max_game_order"] = pd.to_numeric(frame["season"], errors="coerce") * 100 + pd.to_numeric(frame["week"], errors="coerce") - 1
        frame["target_game_order"] = pd.to_numeric(frame["season"], errors="coerce") * 100 + pd.to_numeric(frame["week"], errors="coerce")
        scored.append(frame)
    return pd.concat(scored, ignore_index=True, sort=False) if scored else pd.DataFrame()


def score_bucket(score: object) -> str:
    number = pd.to_numeric(score, errors="coerce")
    if pd.isna(number):
        return "MISSING"
    return pd.cut(pd.Series([number]), SCORE_BUCKETS, labels=SCORE_BUCKET_LABELS, right=False).iloc[0]


def tier_lift(rows: pd.DataFrame) -> pd.DataFrame:
    out = []
    for family, group in rows.groupby("market_family"):
        baseline = pd.to_numeric(group["actual_primary_value"], errors="coerce").mean()
        top_cut = pd.to_numeric(group["actual_primary_value"], errors="coerce").quantile(0.75)
        bottom_cut = pd.to_numeric(group["actual_primary_value"], errors="coerce").quantile(0.25)
        for tier, tier_rows in group.groupby("signal_tier"):
            actual = pd.to_numeric(tier_rows["actual_primary_value"], errors="coerce")
            out.append(
                {
                    "market_family": family,
                    "signal_tier": tier,
                    "row_count": len(tier_rows),
                    "average_signal_score": pd.to_numeric(tier_rows["overall_signal_score"], errors="coerce").mean(),
                    "average_actual_primary_value": actual.mean(),
                    "median_actual_primary_value": actual.median(),
                    "baseline_average_actual": baseline,
                    "lift_vs_baseline": actual.mean() - baseline,
                    "top_quartile_actual_rate": float((actual >= top_cut).mean()) if pd.notna(top_cut) else pd.NA,
                    "bottom_quartile_actual_rate": float((actual <= bottom_cut).mean()) if pd.notna(bottom_cut) else pd.NA,
                    "notes": "Research-only tier separation audit.",
                }
            )
    return pd.DataFrame(out)


def bucket_summary(rows: pd.DataFrame) -> pd.DataFrame:
    data = rows.copy()
    data["score_bucket"] = data["overall_signal_score"].map(score_bucket)
    out = []
    for family, group in data.groupby("market_family"):
        baseline = pd.to_numeric(group["actual_primary_value"], errors="coerce").mean()
        previous = None
        for bucket in SCORE_BUCKET_LABELS:
            bucket_rows = group[group["score_bucket"].astype(str).eq(bucket)]
            actual = pd.to_numeric(bucket_rows["actual_primary_value"], errors="coerce")
            avg = actual.mean()
            flags = []
            if len(bucket_rows) < 30:
                flags.append("LOW_SAMPLE_BUCKET")
            if previous is not None and pd.notna(avg) and avg < previous:
                flags.append("NON_MONOTONIC_SIGNAL")
            if pd.notna(avg):
                previous = avg
            out.append(
                {
                    "market_family": family,
                    "score_bucket": bucket,
                    "row_count": len(bucket_rows),
                    "average_actual_primary_value": avg,
                    "median_actual_primary_value": actual.median(),
                    "lift_vs_baseline": avg - baseline if pd.notna(avg) else pd.NA,
                    "bucket_flags": "; ".join(flags) if flags else "OK",
                }
            )
    return pd.DataFrame(out)


def component_audit(rows: pd.DataFrame) -> pd.DataFrame:
    out = []
    for family, group in rows.groupby("market_family"):
        actual = pd.to_numeric(group["actual_primary_value"], errors="coerce")
        baseline = actual.mean()
        for component in COMPONENTS:
            if component not in group.columns:
                continue
            comp = pd.to_numeric(group[component], errors="coerce")
            valid = comp.notna() & actual.notna()
            if valid.sum() < 50:
                flag = "LOW_SAMPLE"
                corr = pd.NA
                spearman = pd.NA
                top_lift = pd.NA
                bottom_lift = pd.NA
            elif comp[valid].nunique(dropna=True) <= 1 or actual[valid].nunique(dropna=True) <= 1:
                flag = "NOISY"
                corr = pd.NA
                spearman = pd.NA
                top_lift = pd.NA
                bottom_lift = pd.NA
            else:
                corr = comp[valid].corr(actual[valid])
                spearman = comp[valid].corr(actual[valid], method="spearman")
                top = actual[valid & (comp >= comp[valid].quantile(0.75))].mean()
                bottom = actual[valid & (comp <= comp[valid].quantile(0.25))].mean()
                top_lift = top - baseline
                bottom_lift = bottom - baseline
                if pd.notna(spearman) and spearman < -0.05:
                    flag = "INVERTED"
                elif pd.notna(spearman) and abs(spearman) >= 0.18:
                    flag = "USEFUL"
                elif pd.notna(spearman) and abs(spearman) >= 0.08:
                    flag = "WEAK"
                else:
                    flag = "NOISY"
            out.append(
                {
                    "market_family": family,
                    "component_name": component,
                    "correlation_with_actual": corr,
                    "spearman_correlation_with_actual": spearman,
                    "top_quartile_lift": top_lift,
                    "bottom_quartile_lift": bottom_lift,
                    "row_count": int(valid.sum()),
                    "usefulness_flag": flag,
                    "notes": "Candidate for later review only; no production weight changed.",
                }
            )
    return pd.DataFrame(out)


def market_family_audit(rows: pd.DataFrame, buckets: pd.DataFrame) -> pd.DataFrame:
    out = []
    for family, group in rows.groupby("market_family"):
        actual = pd.to_numeric(group["actual_primary_value"], errors="coerce")
        baseline = actual.mean()
        strong = actual[group["signal_tier"].isin(["ELITE_SIGNAL", "STRONG_SIGNAL"])]
        watch = actual[group["signal_tier"].isin(["WATCH", "REVIEW", "INSUFFICIENT_DATA", "BLOCKED"])]
        family_buckets = buckets[buckets["market_family"].eq(family)]
        monotonic = "PASS" if not family_buckets["bucket_flags"].astype(str).str.contains("NON_MONOTONIC_SIGNAL", na=False).any() else "CHECK"
        out.append(
            {
                "market_family": family,
                "rows": len(group),
                "baseline_actual_average": baseline,
                "elite_or_strong_average_actual": strong.mean(),
                "watch_or_review_average_actual": watch.mean(),
                "tier_lift": strong.mean() - watch.mean() if len(strong) and len(watch) else pd.NA,
                "score_actual_correlation": pd.to_numeric(group["overall_signal_score"], errors="coerce").corr(actual),
                "monotonicity_status": monotonic,
                "data_quality_notes": "Historical player-week actuals from weekly.csv; pregame features shifted before target row.",
            }
        )
    return pd.DataFrame(out)


def export_historical_signal_backtest() -> dict[str, pd.DataFrame]:
    weekly = read_csv(raw_path("weekly.csv"))
    schedules = read_csv(raw_path("schedules.csv"))
    if weekly.empty:
        raise RuntimeError("Cannot build historical signal backtest: data/raw/weekly.csv is missing or empty.")
    required = ["season", "week", "player_id", "player_name", "team", "opponent_team", "position"]
    missing = [column for column in required if column not in weekly.columns]
    if missing:
        raise RuntimeError(f"Cannot build historical signal backtest: weekly.csv missing columns {missing}.")
    data = weekly.copy()
    data["season"] = pd.to_numeric(data["season"], errors="coerce")
    data["week"] = pd.to_numeric(data["week"], errors="coerce")
    data = data[data["season"].isin(SEASONS)].copy()
    data["opponent"] = data["opponent_team"].fillna("").astype(str)
    data["player_id"] = data["player_id"].fillna("").astype(str)
    data = add_shifted_rolling(data)
    base = add_schedule_context(data, schedules)
    base = add_defense_fit(base, data)
    family_rows = [build_family_rows(base, family) for family in FAMILIES]
    rows = pd.concat([frame for frame in family_rows if not frame.empty], ignore_index=True, sort=False)
    rows = score_rows(rows)
    selected = [
        *BASE_COLUMNS,
        "market_family",
        "pregame_projection_proxy",
        "projection_score",
        "usage_foundation_score",
        "recent_form_score",
        "opponent_fit_score",
        "game_script_score",
        "role_availability_score",
        "volatility_score",
        "data_quality_score",
        "overall_signal_score",
        "signal_tier",
        "green_signal_count",
        "red_flag_count",
        "missing_signal_count",
        "actual_receptions",
        "actual_receiving_yards",
        "actual_carries",
        "actual_rushing_yards",
        "actual_pass_attempts",
        "actual_completions",
        "actual_passing_yards",
        "actual_primary_value",
        "actual_primary_metric",
        "backtest_usage_status",
        "data_limitations",
        "feature_source_max_game_order",
        "target_game_order",
    ]
    rows = rows[[column for column in selected if column in rows.columns]].copy()
    tiers = tier_lift(rows)
    buckets = bucket_summary(rows)
    components = component_audit(rows)
    family = market_family_audit(rows, buckets)
    outcome = buckets.rename(
        columns={
            "average_actual_primary_value": "average_actual",
            "bucket_flags": "notes",
        }
    ).copy()
    outcome["average_projection"] = pd.NA
    outcome["projection_error"] = pd.NA
    outcome["hit_rate_over_common_line_if_available"] = pd.NA
    outcome["score_bucket"] = outcome["score_bucket"].astype(str)
    outcome["notes"] = "PARTIAL_HISTORICAL_SIGNAL_BACKTEST: " + outcome["notes"].astype(str)
    rows.to_csv(output_path("signal_boards/historical_signal_backtest_rows.csv"), index=False)
    buckets.to_csv(output_path("signal_boards/historical_signal_backtest_summary.csv"), index=False)
    tiers.to_csv(output_path("signal_boards/historical_signal_tier_lift.csv"), index=False)
    components.to_csv(output_path("signal_boards/historical_signal_component_audit.csv"), index=False)
    family.to_csv(output_path("signal_boards/historical_signal_market_family_audit.csv"), index=False)
    outcome[["score_bucket", "row_count", "average_projection", "average_actual", "projection_error", "hit_rate_over_common_line_if_available", "notes"]].to_csv(output_path("signal_boards/signal_score_outcome_audit.csv"), index=False)
    write_report(weekly, schedules, rows, tiers, buckets, components, family)
    return {"rows": rows, "summary": buckets, "tiers": tiers, "components": components, "family": family}


def write_report(weekly: pd.DataFrame, schedules: pd.DataFrame, rows: pd.DataFrame, tiers: pd.DataFrame, buckets: pd.DataFrame, components: pd.DataFrame, family: pd.DataFrame) -> None:
    seasons = sorted(pd.to_numeric(rows["season"], errors="coerce").dropna().astype(int).unique().tolist()) if not rows.empty else []
    weeks = sorted(pd.to_numeric(rows["week"], errors="coerce").dropna().astype(int).unique().tolist()) if not rows.empty else []
    text = f"""# Historical Signal Backtest Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Audit type: `RESEARCH ONLY / HISTORICAL SIGNAL BACKTEST`

## Source Inspection

- `data/raw/weekly.csv`: `{len(weekly)}` rows; columns used include player/team/week identifiers and actual receptions, receiving yards, carries, rushing yards, attempts, completions, and passing yards.
- `data/raw/schedules.csv`: `{len(schedules)}` rows; columns used when present include game_id, home_team, away_team, spread_line, and total_line.

## Coverage

- Backtest rows: `{len(rows)}`
- Seasons tested: `{', '.join(map(str, seasons))}`
- Weeks tested: `{min(weeks) if weeks else 'n/a'}-{max(weeks) if weeks else 'n/a'}`
- Market families: `{', '.join(sorted(rows['market_family'].dropna().unique())) if not rows.empty else 'none'}`

## Outputs

- Tier lift rows: `{len(tiers)}`
- Score bucket rows: `{len(buckets)}`
- Component audit rows: `{len(components)}`
- Market-family audit rows: `{len(family)}`

## Limitations

Pregame scores use shifted historical player rows and do not use target-week actuals. This is a proxy signal backtest, not a sportsbook profitability test, and it does not change production weights.
"""
    output_path("run_reports/latest_historical_signal_backtest_report.md").write_text(text, encoding="utf-8")


def main() -> None:
    outputs = export_historical_signal_backtest()
    print(f"historical_signal_backtest_rows: {len(outputs['rows']):,} rows")
    print(f"historical_signal_backtest_summary: {len(outputs['summary']):,} rows")
    print(f"historical_signal_tier_lift: {len(outputs['tiers']):,} rows")
    print(f"historical_signal_component_audit: {len(outputs['components']):,} rows")
    print(f"historical_signal_market_family_audit: {len(outputs['family']):,} rows")


if __name__ == "__main__":
    main()
