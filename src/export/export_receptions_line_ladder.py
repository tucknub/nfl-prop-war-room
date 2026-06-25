from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path
from src.models.receptions_probability import calibration_error_sd, normal_over_probability


LINES = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5]
LADDER_COLUMNS = [
    "player_name",
    "player_id",
    "team",
    "opponent",
    "position",
    "line",
    "raw_projection",
    "calibrated_projection",
    "projection_sd",
    "model_over_probability",
    "model_under_probability",
    "probability_method",
    "confidence_tier",
    "flags",
    "usage_status",
    "notes",
]
TOP_COLUMNS = [
    "line",
    "rank",
    "player_name",
    "team",
    "opponent",
    "position",
    "calibrated_projection",
    "model_over_probability",
    "confidence_tier",
    "flags",
    "usage_status",
    "notes",
]


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _usage_status(row: pd.Series) -> str:
    if row.get("projection_mode") == "historical_test":
        return "HISTORICAL TEST ONLY"
    return "MODEL REVIEW"


def _confidence_tier(row: pd.Series) -> str:
    bucket = str(row.get("confidence_bucket", ""))
    if bucket:
        return bucket
    score = pd.to_numeric(row.get("confidence_score"), errors="coerce")
    if pd.isna(score):
        return "Unknown"
    if score >= 80:
        return "High"
    if score >= 55:
        return "Medium"
    return "Low"


def export_receptions_line_ladder() -> tuple[pd.DataFrame, pd.DataFrame]:
    model = _read(output_path("google_sheets_receptions_historical_test.csv"))
    sd = calibration_error_sd()
    method = "Normal approximation: mean=calibrated_projection, sd=calibrated_RMSE"
    rows = []
    for _, player in model.iterrows():
        calibrated = pd.to_numeric(player.get("projected_receptions_calibrated"), errors="coerce")
        raw = pd.to_numeric(player.get("projected_receptions_raw"), errors="coerce")
        if pd.isna(calibrated):
            continue
        flags = str(player.get("quality_flags", ""))
        if player.get("route_proxy_status") == "ROUTE_PROXY_UNVALIDATED" and "ROUTE_PROXY_UNVALIDATED" not in flags:
            flags = f"{flags}|ROUTE_PROXY_UNVALIDATED".strip("|")
        for line in LINES:
            over = normal_over_probability(float(calibrated), sd, line)
            under = 1 - over
            rows.append(
                {
                    "player_name": player.get("player_name"),
                    "player_id": player.get("player_id"),
                    "team": player.get("team"),
                    "opponent": "",
                    "position": player.get("position"),
                    "line": line,
                    "raw_projection": raw,
                    "calibrated_projection": calibrated,
                    "projection_sd": sd,
                    "model_over_probability": over,
                    "model_under_probability": under,
                    "probability_method": method,
                    "confidence_tier": _confidence_tier(player),
                    "flags": flags,
                    "usage_status": _usage_status(player),
                    "notes": "Research line ladder only. No odds, edge, or betting recommendation.",
                }
            )
    ladder = pd.DataFrame(rows, columns=LADDER_COLUMNS)
    if ladder.empty:
        top = pd.DataFrame(columns=TOP_COLUMNS)
    else:
        top = (
            ladder.sort_values(["line", "model_over_probability"], ascending=[True, False])
            .groupby("line", as_index=False, group_keys=False)
            .head(25)
            .copy()
        )
        top["rank"] = top.groupby("line")["model_over_probability"].rank(method="first", ascending=False).astype(int)
        top = top[TOP_COLUMNS]

    ladder.to_csv(output_path("market_edges/receptions_line_ladder.csv"), index=False)
    top.to_csv(output_path("market_edges/receptions_line_ladder_top_by_line.csv"), index=False)
    write_report(ladder, top, sd, method)
    return ladder, top


def write_report(ladder: pd.DataFrame, top: pd.DataFrame, sd: float, method: str) -> None:
    usage = ", ".join(sorted(ladder["usage_status"].dropna().unique())) if not ladder.empty else "No rows"
    text = f"""# Receptions Line Ladder Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Probability method: `{method}`

Calibration error used: `{sd:.6f}`

Line ladder rows: `{len(ladder)}`

Top-by-line rows: `{len(top)}`

Usage status: `{usage}`

Live betting output status: `NOT CREATED`

Warnings/errors: `None`

Next required action: `Use this for research only until Live Readiness is GO and market odds are matched.`
"""
    output_path("run_reports/latest_line_ladder_report.md").write_text(text, encoding="utf-8")


def main() -> None:
    ladder, top = export_receptions_line_ladder()
    print(f"receptions_line_ladder: {len(ladder):,} rows")
    print(f"receptions_line_ladder_top_by_line: {len(top):,} rows")
    print(f"calibration_error_used: {calibration_error_sd():.6f}")


if __name__ == "__main__":
    main()
