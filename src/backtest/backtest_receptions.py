from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_receptions_feature_table import build_receptions_feature_table
from src.models.receptions_model import (
    add_projection_ranks,
    apply_calibration,
    build_calibration_multipliers,
    get_projection_target,
    project_receptions,
)
from src.features.history_window import get_history_config


def _eligible_for_scoring(df: pd.DataFrame) -> pd.Series:
    has_prior = df.get("prior_targets", pd.Series(0, index=df.index)).fillna(0) > 0
    has_current = df["current_season_games_entering"].fillna(0) >= 3
    return has_prior | has_current


def summarize_backtest(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    scoreable = scored[scored["scoreable"]].copy()
    scoreable["raw_abs_error"] = (scoreable["projected_receptions_raw"] - scoreable["actual_receptions"]).abs()
    scoreable["raw_sq_error"] = (scoreable["projected_receptions_raw"] - scoreable["actual_receptions"]) ** 2
    scoreable["calibrated_abs_error"] = (
        scoreable["projected_receptions_calibrated"] - scoreable["actual_receptions"]
    ).abs()
    scoreable["calibrated_sq_error"] = (
        scoreable["projected_receptions_calibrated"] - scoreable["actual_receptions"]
    ) ** 2
    return pd.DataFrame(
        {
            "rows_scored": [len(scoreable)],
            "raw_mae": [scoreable["raw_abs_error"].mean()],
            "raw_rmse": [np.sqrt(scoreable["raw_sq_error"].mean())],
            "raw_bias": [(scoreable["projected_receptions_raw"] - scoreable["actual_receptions"]).mean()],
            "calibrated_mae": [scoreable["calibrated_abs_error"].mean()],
            "calibrated_rmse": [np.sqrt(scoreable["calibrated_sq_error"].mean())],
            "calibrated_bias": [
                (scoreable["projected_receptions_calibrated"] - scoreable["actual_receptions"]).mean()
            ],
            "walk_forward_rule": ["Week N uses features available through Week N-1"],
        }
    )


def run_walk_forward_backtest(
    features: pd.DataFrame,
    season: int | None = None,
    candidates_only: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = features.copy()
    if season is not None:
        df = df[df["season"] == season]
    scored_weeks: list[pd.DataFrame] = []
    for week in sorted(df["week"].dropna().unique()):
        # Features are already shifted to entering-week values; selecting Week N is walk-forward safe.
        test = df[(df["week"] == week) & (df["confidence_bucket"] != "unusable")].copy()
        if test.empty:
            continue
        projections = project_receptions(test, load_config())
        if candidates_only:
            projections = projections[projections["is_prop_candidate"]].copy()
            projections = add_projection_ranks(projections)
        projections["actual_receptions"] = projections["player_week_receptions"]
        projections["scoreable"] = _eligible_for_scoring(projections)
        scored_weeks.append(projections)

    scored = pd.concat(scored_weeks, ignore_index=True) if scored_weeks else pd.DataFrame()
    summary = summarize_backtest(scored)
    return scored, summary


def apply_candidate_calibration_to_backtests(
    scored_all: pd.DataFrame,
    scored_candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    multipliers = build_calibration_multipliers(scored_candidates)
    multiplier_map = dict(zip(multipliers["calibration_bucket"], multipliers["calibration_multiplier"]))
    return (
        apply_calibration(scored_all, multiplier_map),
        apply_calibration(scored_candidates, multiplier_map),
        multipliers,
    )


def main() -> None:
    cfg = load_config()
    history_start, history_end, target_season, target_week, _ = get_history_config(cfg)
    path = output_path("receptions_feature_table.csv", cfg)
    features = pd.read_csv(path, low_memory=False) if path.exists() else build_receptions_feature_table(cfg)
    scored, summary = run_walk_forward_backtest(features, history_end)
    scored_candidates, summary_candidates = run_walk_forward_backtest(
        features,
        history_end,
        candidates_only=True,
    )
    scored, scored_candidates, multipliers = apply_candidate_calibration_to_backtests(scored, scored_candidates)
    summary = summarize_backtest(scored)
    summary_candidates = summarize_backtest(scored_candidates)
    scored.to_csv(output_path("receptions_backtest_rows.csv", cfg), index=False)
    summary.to_csv(output_path("receptions_backtest_summary.csv", cfg), index=False)
    summary.to_csv(output_path("receptions_backtest_summary_all.csv", cfg), index=False)
    scored_candidates.to_csv(output_path("receptions_backtest_rows_candidates.csv", cfg), index=False)
    summary_candidates.to_csv(output_path("receptions_backtest_summary_candidates.csv", cfg), index=False)
    multipliers.to_csv(output_path("receptions_calibration_multipliers.csv", cfg), index=False)
    print(f"Wrote all backtest summary with {0 if summary.empty else int(summary['rows_scored'].iloc[0])} scored rows")
    print(
        "Wrote candidate backtest summary with "
        f"{0 if summary_candidates.empty else int(summary_candidates['rows_scored'].iloc[0])} scored rows"
    )


if __name__ == "__main__":
    main()
