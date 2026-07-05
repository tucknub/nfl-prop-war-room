from __future__ import annotations

from datetime import datetime, timezone
from math import erf, sqrt

import pandas as pd

from src.common import load_config, output_path


LINES = [9.5, 14.5, 19.5, 24.5, 29.5, 34.5, 39.5, 44.5, 49.5, 54.5, 59.5, 64.5, 69.5, 74.5, 79.5, 84.5, 89.5, 99.5]
METHOD = "Normal approximation: mean=calibrated_projection, sd=rushing_yards_backtest_calibrated_RMSE"


def error_sd(config: dict | None = None) -> float:
    cfg = config or load_config()
    path = output_path("rushing_yards_backtest_summary_candidates.csv", cfg)
    if path.exists():
        df = pd.read_csv(path, low_memory=False)
        if not df.empty:
            return float(df["calibrated_rmse"].iloc[0])
    return 20.0


def over_probability(mean: float, sd: float, line: float) -> float:
    cdf = .5 * (1 + erf(((line - mean) / max(sd, 1e-6)) / sqrt(2)))
    return min(max(1 - cdf, 0.0), 1.0)


def export_ladder() -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = load_config()
    path = output_path("google_sheets_rushing_yards_historical_test.csv", cfg)
    model = pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()
    sd = error_sd(cfg)
    rows = []
    for _, player in model.iterrows():
        mean = pd.to_numeric(player.get("projected_rushing_yards_calibrated"), errors="coerce")
        if pd.isna(mean):
            continue
        for line in LINES:
            over = over_probability(float(mean), sd, line)
            rows.append({"player_name": player.get("player_name"), "team": player.get("team"), "opponent": player.get("opponent_team"),
                         "position": player.get("position"), "line": line, "raw_projection": player.get("projected_rushing_yards_raw"),
                         "calibrated_projection": mean, "projection_sd": sd, "model_over_probability": over,
                         "model_under_probability": 1 - over, "probability_method": METHOD, "confidence_tier": player.get("confidence_bucket"),
                         "flags": player.get("quality_flags"), "usage_status": "HISTORICAL TEST ONLY",
                         "notes": "Research only - no odds, edge, or betting recommendation."})
    ladder = pd.DataFrame(rows)
    top = pd.DataFrame()
    if not ladder.empty:
        top = ladder.sort_values(["line", "model_over_probability"], ascending=[True, False]).groupby("line", as_index=False, group_keys=False).head(25).copy()
        top["rank"] = top.groupby("line")["model_over_probability"].rank(method="first", ascending=False).astype(int)
        top = top[["line", "rank", "player_name", "team", "opponent", "position", "calibrated_projection", "model_over_probability", "confidence_tier", "flags", "usage_status", "notes"]]
    ladder.to_csv(output_path("market_edges/rushing_yards_line_ladder.csv", cfg), index=False)
    top.to_csv(output_path("market_edges/rushing_yards_line_ladder_top_by_line.csv", cfg), index=False)
    summary_path = output_path("rushing_yards_backtest_summary_candidates.csv", cfg)
    summary = pd.read_csv(summary_path, low_memory=False) if summary_path.exists() else pd.DataFrame()
    metrics = "Backtest metrics unavailable."
    if not summary.empty:
        r = summary.iloc[0]
        metrics = f"Rows scored: `{int(r['rows_scored'])}`\n\nCalibrated MAE/RMSE/bias: `{r['calibrated_mae']:.6f}` / `{r['calibrated_rmse']:.6f}` / `{r['calibrated_bias']:.6f}`"
    report = f"""# Rushing Yards V1 Pipeline Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Formula: `projected_carries x projected_yards_per_carry = projected_rushing_yards`

Probability method: `{METHOD}`

Calibration/error SD used: `{sd:.6f}`

{metrics}

Line ladder rows: `{len(ladder)}`

Top-by-line rows: `{len(top)}`

Usage status: `HISTORICAL TEST ONLY`
"""
    output_path("run_reports/latest_rushing_yards_pipeline_report.md", cfg).write_text(report, encoding="utf-8")
    return ladder, top


def main() -> None:
    ladder, top = export_ladder()
    print(f"rushing_yards_line_ladder: {len(ladder):,} rows")
    print(f"rushing_yards_line_ladder_top_by_line: {len(top):,} rows")
    print(f"rushing_yards_error_sd: {error_sd():.6f}")


if __name__ == "__main__":
    main()
