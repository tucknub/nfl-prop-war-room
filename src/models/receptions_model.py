from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.common import load_config, output_path, raw_path
from src.features.build_receptions_feature_table import build_receptions_feature_table


RECEIVING_POSITIONS = {"WR", "TE", "RB", "FB"}
EXCLUDED_POSITIONS = {
    "QB",
    "OL",
    "C",
    "G",
    "T",
    "DE",
    "DT",
    "DL",
    "LB",
    "OLB",
    "ILB",
    "CB",
    "S",
    "SAF",
    "DB",
    "K",
    "P",
    "LS",
}
CALIBRATION_BUCKETS = ["0-1", "1-2", "2-3", "3-4", "4-6", "6+"]
CALIBRATION_BINS = [-0.01, 1, 2, 3, 4, 6, 99]
PROJECTION_COLUMNS = [
    "projection_mode",
    "history_start_season",
    "history_end_season",
    "max_training_season",
    "max_training_week",
    "target_season",
    "target_week",
    "leakage_check",
    "leakage_status",
    "season",
    "week",
    "team",
    "player_id",
    "player_name",
    "position",
    "projected_team_pass_attempts",
    "projected_target_share",
    "projected_catch_rate",
    "projected_receptions_raw",
    "calibration_bucket",
    "calibration_multiplier",
    "projected_receptions_calibrated",
    "projected_receptions",
    "estimated_routes",
    "is_prop_candidate",
    "overall_rank",
    "team_rank",
    "position_rank",
    "current_team_verified",
    "team_verify_flag",
    "team_source",
    "team_context_note",
    "route_proxy_status",
    "confidence_score",
    "confidence_bucket",
    "quality_flags",
]


def get_projection_target(config: dict) -> tuple[str, int, int]:
    data_cfg = config["data"]
    mode = data_cfg.get("projection_mode", "historical_test")
    if mode not in {"historical_test", "forward_projection"}:
        raise ValueError("projection_mode must be historical_test or forward_projection.")
    season = int(data_cfg.get("target_season", data_cfg.get("projection_season")))
    week = int(data_cfg.get("target_week", data_cfg.get("projection_week")))
    return mode, season, week


def validate_projection_mode(config: dict) -> None:
    mode, season, week = get_projection_target(config)
    if mode != "forward_projection":
        return

    schedules_path = raw_path("schedules.csv", config)
    rosters_path = raw_path("rosters.csv", config)
    if not schedules_path.exists() or not rosters_path.exists():
        raise RuntimeError("Cannot produce true forward projection: missing schedule/roster for target season/week.")

    schedules = pd.read_csv(schedules_path, low_memory=False)
    rosters = pd.read_csv(rosters_path, low_memory=False)
    schedule_ok = {"season", "week"}.issubset(schedules.columns) and not schedules[
        (schedules["season"] == season) & (schedules["week"] == week)
    ].empty
    roster_season_col = "season" if "season" in rosters.columns else None
    roster_ok = roster_season_col is not None and not rosters[rosters[roster_season_col] == season].empty
    if not schedule_ok or not roster_ok:
        raise RuntimeError("Cannot produce true forward projection: missing schedule/roster for target season/week.")


def _normalized_position(df: pd.DataFrame) -> pd.Series:
    return df.get("position", "").fillna("").astype(str).str.upper().str.strip()


def _historical_receiving_usage(df: pd.DataFrame) -> pd.Series:
    usage_cols = [
        "prior_targets",
        "targets_last_4",
        "targets_last_8",
        "player_week_targets_last_4",
        "player_week_targets_last_8",
        "career_targets_entering",
    ]
    usage = pd.Series(False, index=df.index)
    for col in usage_cols:
        if col in df.columns:
            usage = usage | (pd.to_numeric(df[col], errors="coerce").fillna(0) > 0)
    return usage


def _append_flag(existing: pd.Series, flag: str) -> pd.Series:
    values = existing.fillna("").astype(str)
    return values.where(values.str.contains(flag, regex=False), values.where(values == "", values + "|") + flag)


def add_team_verification(features: pd.DataFrame, config: dict) -> pd.DataFrame:
    mode, season, week = get_projection_target(config)
    df = features.copy()
    has_team = df.get("team", pd.Series("", index=df.index)).fillna("").astype(str).str.strip() != ""
    in_target_context = (df["season"] == season) & (df["week"] == week)
    if mode == "historical_test":
        verified = has_team
        source = "weekly_stats_historical"
        note = "Historical test mode: team is from loaded weekly/player stats context, not live roster confirmation."
    else:
        verified = has_team & in_target_context
        source = "target_schedule_roster"
        note = "Forward projection mode: team must be confirmed by target season/week schedule and roster data."

    df["current_team_verified"] = verified
    df["team_verify_flag"] = np.where(verified, "", "TEAM_VERIFY")
    df["team_source"] = source
    df["team_context_note"] = note
    stale = ~verified
    if stale.any():
        df.loc[stale, "quality_flags"] = _append_flag(df.loc[stale, "quality_flags"], "TEAM_VERIFY")
        df.loc[stale, "confidence_score"] = np.nan
        df.loc[stale, "confidence_bucket"] = "Unusable"
    return df


def filter_eligible_receivers(features: pd.DataFrame) -> pd.DataFrame:
    df = features.copy()
    pos = _normalized_position(df)
    historical_usage = _historical_receiving_usage(df)
    eligible = pos.isin(RECEIVING_POSITIONS)
    missing_position_with_usage = (pos == "") & historical_usage
    df = df[(eligible | missing_position_with_usage) & ~pos.isin(EXCLUDED_POSITIONS)].copy()
    return df


def add_prop_candidate_flags(projection: pd.DataFrame) -> pd.DataFrame:
    df = projection.copy()
    recent_or_prior_targets = _historical_receiving_usage(df)
    df["is_prop_candidate"] = (
        (df["projected_receptions_raw"] >= 0.75)
        | (df["projected_target_share"] >= 0.025)
        | (df["estimated_routes"] >= 8)
        | recent_or_prior_targets
    )
    return df


def add_projection_ranks(projection: pd.DataFrame) -> pd.DataFrame:
    df = projection.copy()
    df["position"] = df["position"].fillna("UNK")
    df = df.sort_values("projected_receptions_calibrated", ascending=False)
    df["overall_rank"] = range(1, len(df) + 1)
    df["team_rank"] = df.groupby(["season", "week", "team"])["projected_receptions_calibrated"].rank(
        method="first", ascending=False
    ).astype(int)
    df["position_rank"] = df.groupby(["season", "week", "position"])["projected_receptions_calibrated"].rank(
        method="first", ascending=False
    ).astype(int)
    return df


def assign_calibration_bucket(raw_projection: pd.Series) -> pd.Series:
    return pd.cut(raw_projection, bins=CALIBRATION_BINS, labels=CALIBRATION_BUCKETS).astype(str)


def neutral_calibration_multipliers() -> dict[str, float]:
    return {bucket: 1.0 for bucket in CALIBRATION_BUCKETS}


def load_calibration_multipliers(config: dict) -> dict[str, float]:
    multipliers = neutral_calibration_multipliers()
    path = output_path("receptions_calibration_multipliers.csv", config)
    report_path = output_path("receptions_calibration_report_candidates.csv", config)
    if path.exists():
        report = pd.read_csv(path, low_memory=False)
        for _, row in report.iterrows():
            multipliers[str(row["calibration_bucket"])] = float(row["calibration_multiplier"])
        return multipliers
    if report_path.exists():
        report = pd.read_csv(report_path, low_memory=False)
        for bucket, grouped in report.groupby("projection_bucket", dropna=False):
            projected = (grouped["avg_projected_receptions"] * grouped["rows"]).sum()
            actual = (grouped["avg_actual_receptions"] * grouped["rows"]).sum()
            if projected > 0:
                multipliers[str(bucket)] = float(actual / projected)
    return multipliers


def build_calibration_multipliers(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame(
            {"calibration_bucket": CALIBRATION_BUCKETS, "calibration_multiplier": [1.0] * len(CALIBRATION_BUCKETS)}
        )
    df = scored[scored["scoreable"]].copy()
    if df.empty:
        return pd.DataFrame(
            {"calibration_bucket": CALIBRATION_BUCKETS, "calibration_multiplier": [1.0] * len(CALIBRATION_BUCKETS)}
        )
    raw_col = "projected_receptions_raw" if "projected_receptions_raw" in df.columns else "projected_receptions"
    df["calibration_bucket"] = assign_calibration_bucket(df[raw_col])
    rows = []
    for bucket in CALIBRATION_BUCKETS:
        bucket_df = df[df["calibration_bucket"] == bucket]
        projected = bucket_df[raw_col].sum()
        actual = bucket_df["actual_receptions"].sum()
        multiplier = float(actual / projected) if projected > 0 else 1.0
        rows.append(
            {
                "calibration_bucket": bucket,
                "rows": len(bucket_df),
                "raw_projected_total": projected,
                "actual_total": actual,
                "calibration_multiplier": multiplier,
            }
        )
    return pd.DataFrame(rows)


def apply_calibration(projection: pd.DataFrame, multipliers: dict[str, float] | None = None) -> pd.DataFrame:
    df = projection.copy()
    multipliers = multipliers or neutral_calibration_multipliers()
    df["calibration_bucket"] = assign_calibration_bucket(df["projected_receptions_raw"])
    df["calibration_multiplier"] = df["calibration_bucket"].map(multipliers).fillna(1.0).astype(float)
    df["projected_receptions_calibrated"] = df["projected_receptions_raw"] * df["calibration_multiplier"]
    df["projected_receptions"] = df["projected_receptions_calibrated"]
    return df


def project_receptions(
    features: pd.DataFrame,
    config: dict | None = None,
    calibration_multipliers: dict[str, float] | None = None,
) -> pd.DataFrame:
    cfg = config or load_config()
    usable = add_team_verification(filter_eligible_receivers(features), cfg)
    usable = usable[usable["confidence_bucket"].astype(str).str.lower() != "unusable"].copy()
    usable["projected_receptions_raw"] = (
        usable["projected_team_pass_attempts"]
        * usable["projected_target_share"]
        * usable["projected_catch_rate"]
    )
    usable = apply_calibration(usable, calibration_multipliers)
    usable = add_prop_candidate_flags(usable)
    usable = add_projection_ranks(usable)
    return usable.sort_values(["season", "week", "team", "projected_receptions_calibrated"], ascending=[True, True, True, False])


def build_week_projection(config: dict | None = None, candidates_only: bool = True) -> pd.DataFrame:
    cfg = config or load_config()
    validate_projection_mode(cfg)
    mode, season, week = get_projection_target(cfg)
    features_path = output_path("receptions_feature_table.csv", cfg)
    features = pd.read_csv(features_path, low_memory=False) if features_path.exists() else build_receptions_feature_table(cfg)
    projection = project_receptions(features, cfg, load_calibration_multipliers(cfg))
    week_projection = projection[(projection["season"] == season) & (projection["week"] == week)].copy()
    week_projection["projection_mode"] = mode
    week_projection["target_season"] = season
    week_projection["target_week"] = week
    if candidates_only:
        week_projection = week_projection[
            week_projection["is_prop_candidate"]
            & week_projection["current_team_verified"]
            & (week_projection["confidence_bucket"].astype(str).str.lower() != "unusable")
        ].copy()
        week_projection = add_projection_ranks(week_projection)
    return week_projection[PROJECTION_COLUMNS]


def main() -> None:
    cfg = load_config()
    mode, _, week = get_projection_target(cfg)
    projection_all = build_week_projection(cfg, candidates_only=False)
    projection_candidates = build_week_projection(cfg, candidates_only=True)
    all_path = output_path(f"receptions_projection_week_{week:02d}_all.csv", cfg)
    candidates_path = output_path(f"receptions_projection_week_{week:02d}_candidates.csv", cfg)
    legacy_path = output_path(f"receptions_projection_week_{week:02d}.csv", cfg)
    mode_all_path = output_path(f"receptions_projection_{mode}_week_{week:02d}_all.csv", cfg)
    mode_candidates_path = output_path(f"receptions_projection_{mode}_week_{week:02d}_candidates.csv", cfg)
    projection_all.to_csv(all_path, index=False)
    projection_candidates.to_csv(candidates_path, index=False)
    projection_candidates.to_csv(legacy_path, index=False)
    projection_all.to_csv(mode_all_path, index=False)
    projection_candidates.to_csv(mode_candidates_path, index=False)
    print(f"Wrote {all_path} with {len(projection_all):,} rows")
    print(f"Wrote {candidates_path} with {len(projection_candidates):,} rows")


if __name__ == "__main__":
    main()
