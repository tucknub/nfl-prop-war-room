from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common import load_config, output_path
from src.models.receptions_model import get_projection_target


SHEETS_COLUMNS = [
    "projection_mode",
    "season",
    "week",
    "overall_rank",
    "team_rank",
    "position_rank",
    "team",
    "player_name",
    "position",
    "projected_receptions_calibrated",
    "projected_receptions_raw",
    "projected_team_pass_attempts",
    "projected_target_share",
    "projected_catch_rate",
    "estimated_routes",
    "confidence_score",
    "confidence_bucket",
    "quality_flags",
    "current_team_verified",
    "team_verify_flag",
    "team_source",
    "team_context_note",
    "calibration_bucket",
    "calibration_multiplier",
    "usage_status",
]


def _usage_status(row: pd.Series) -> str:
    if row.get("team_verify_flag") == "TEAM_VERIFY":
        return "DO NOT USE"
    if row.get("projection_mode") == "historical_test":
        return "HISTORICAL TEST ONLY"
    return "MODEL REVIEW"


def export_google_sheet_receptions(csv_path: str | Path | None = None) -> pd.DataFrame:
    cfg = load_config()
    _, _, week = get_projection_target(cfg)
    path = Path(csv_path) if csv_path else output_path(f"receptions_projection_week_{week:02d}_candidates.csv", cfg)
    if not path.exists():
        fallback = output_path(f"receptions_projection_week_{week:02d}.csv", cfg)
        path = fallback
    df = pd.read_csv(path, low_memory=False)
    if "is_prop_candidate" in df.columns:
        df = df[df["is_prop_candidate"]].copy()
    df["usage_status"] = df.apply(_usage_status, axis=1)
    df = df.sort_values("projected_receptions_calibrated", ascending=False)
    missing = [column for column in SHEETS_COLUMNS if column not in df.columns]
    if missing:
        raise RuntimeError(f"Cannot create Google Sheets export. Missing columns: {missing}")
    export = df[SHEETS_COLUMNS].copy()
    export.to_csv(output_path("google_sheets_receptions_historical_test.csv", cfg), index=False)
    return export


def main() -> None:
    df = export_google_sheet_receptions()
    print(f"Prepared Google Sheets CSV export with {len(df):,} rows")


if __name__ == "__main__":
    main()
