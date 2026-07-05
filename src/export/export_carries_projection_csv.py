from __future__ import annotations

import pandas as pd
from src.common import load_config, output_path
from src.models.carries_model import build_week_projection, output_columns


COLS = ["projection_mode", "season", "week", "overall_rank", "team_rank", "position_rank", "team", "opponent_team", "player_name", "position",
        "projected_carries_calibrated", "projected_carries_raw", "projected_team_rush_attempts", "projected_player_rush_attempt_share",
        "confidence_score", "confidence_bucket", "quality_flags", "calibration_bucket", "calibration_multiplier", "usage_status"]


def export_google_sheet() -> pd.DataFrame:
    cfg = load_config(); df = output_columns(build_week_projection(cfg, True))
    for col in COLS:
        if col not in df.columns: df[col] = ""
    out = df[COLS].sort_values("projected_carries_calibrated", ascending=False)
    out.to_csv(output_path("google_sheets_carries_historical_test.csv", cfg), index=False)
    return out


def main() -> None:
    out = export_google_sheet(); print(f"Exported carries Google Sheets CSV with {len(out):,} rows")


if __name__ == "__main__": main()
