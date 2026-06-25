from __future__ import annotations

from datetime import datetime, timezone
from math import erf, sqrt

import pandas as pd

from src.common import load_config, output_path


LINES = [9.5, 14.5, 19.5, 24.5, 29.5, 34.5, 39.5, 44.5, 49.5, 54.5, 59.5, 64.5, 69.5, 74.5, 79.5, 84.5, 89.5, 99.5]
METHOD = "Normal approximation: mean=calibrated_projection, sd=receiving_yards_backtest_calibrated_RMSE"


def normal_over_probability(mean: float, sd: float, line: float) -> float:
    sd = max(float(sd), 1e-6)
    z = (float(line) - float(mean)) / sd
    cdf = 0.5 * (1 + erf(z / sqrt(2)))
    return min(max(1 - cdf, 0.0), 1.0)


def calibration_error_sd(config: dict | None = None) -> float:
    cfg = config or load_config()
    path = output_path("receiving_yards_backtest_summary_candidates.csv", cfg)
    if path.exists():
        df = pd.read_csv(path, low_memory=False)
        if not df.empty and "calibrated_rmse" in df.columns:
            return float(pd.to_numeric(df["calibrated_rmse"], errors="coerce").dropna().iloc[0])
    return 18.0


def export_ladder() -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = load_config()
    path = output_path("google_sheets_receiving_yards_historical_test.csv", cfg)
    model = pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()
    sd = calibration_error_sd(cfg)
    rows = []
    for _, player in model.iterrows():
        mean = pd.to_numeric(player.get("projected_receiving_yards_calibrated"), errors="coerce")
        if pd.isna(mean):
            continue
        for line in LINES:
            over = normal_over_probability(float(mean), sd, line)
            rows.append(
                {
                    "player_name": player.get("player_name"),
                    "team": player.get("team"),
                    "opponent": "",
                    "position": player.get("position"),
                    "line": line,
                    "raw_projection": player.get("projected_receiving_yards_raw"),
                    "calibrated_projection": mean,
                    "projection_sd": sd,
                    "model_over_probability": over,
                    "model_under_probability": 1 - over,
                    "probability_method": METHOD,
                    "confidence_tier": player.get("confidence_bucket"),
                    "flags": player.get("quality_flags"),
                    "usage_status": "HISTORICAL TEST ONLY",
                    "notes": "Research only - no odds, edge, or betting recommendation.",
                }
            )
    ladder = pd.DataFrame(rows)
    if ladder.empty:
        top = pd.DataFrame()
    else:
        top = ladder.sort_values(["line", "model_over_probability"], ascending=[True, False]).groupby("line", as_index=False, group_keys=False).head(25).copy()
        top["rank"] = top.groupby("line")["model_over_probability"].rank(method="first", ascending=False).astype(int)
        top = top[["line", "rank", "player_name", "team", "opponent", "position", "calibrated_projection", "model_over_probability", "confidence_tier", "flags", "usage_status", "notes"]]
    ladder.to_csv(output_path("market_edges/receiving_yards_line_ladder.csv", cfg), index=False)
    top.to_csv(output_path("market_edges/receiving_yards_line_ladder_top_by_line.csv", cfg), index=False)
    summary_path = output_path("receiving_yards_backtest_summary_candidates.csv", cfg)
    summary = pd.read_csv(summary_path, low_memory=False) if summary_path.exists() else pd.DataFrame()
    metric_text = "Backtest metrics unavailable."
    if not summary.empty:
        row = summary.iloc[0]
        metric_text = (
            f"Rows scored: `{int(row.get('rows_scored', 0))}`\n\n"
            f"Raw MAE/RMSE/bias: `{row.get('raw_mae'):.6f}` / `{row.get('raw_rmse'):.6f}` / `{row.get('raw_bias'):.6f}`\n\n"
            f"Calibrated MAE/RMSE/bias: `{row.get('calibrated_mae'):.6f}` / `{row.get('calibrated_rmse'):.6f}` / `{row.get('calibrated_bias'):.6f}`"
        )
    report = f"""# Receiving Yards Line Ladder Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Formula: `projected_receptions_calibrated x projected_yards_per_reception = projected_receiving_yards`

Formula choice: Receptions V1 already provides leakage-safe projected reception volume, while Receiving Yards V1 adds historical yards-per-reception efficiency from entering-week receiving yards/receptions.

Probability method: `{METHOD}`

Calibration/error SD used: `{sd:.6f}`

## Backtest Metrics

{metric_text}

Line ladder rows: `{len(ladder)}`

Top-by-line rows: `{len(top)}`

Usage status: `HISTORICAL TEST ONLY`
"""
    output_path("run_reports/latest_receiving_yards_pipeline_report.md", cfg).write_text(report, encoding="utf-8")
    return ladder, top


def main() -> None:
    ladder, top = export_ladder()
    print(f"receiving_yards_line_ladder: {len(ladder):,} rows")
    print(f"receiving_yards_line_ladder_top_by_line: {len(top):,} rows")
    print(f"receiving_yards_error_sd: {calibration_error_sd():.6f}")


if __name__ == "__main__":
    main()
