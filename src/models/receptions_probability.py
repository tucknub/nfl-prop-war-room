from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.common import output_path


PROBABILITY_COLUMNS = [
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
    "usage_status",
    "notes",
]


def normal_over_probability(mean: float, sd: float, line: float) -> float:
    if sd <= 0:
        sd = 1.0
    z = (line - mean) / sd
    cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return max(0.0, min(1.0, 1 - cdf))


def calibration_error_sd() -> float:
    path = output_path("receptions_backtest_summary_candidates.csv")
    if not path.exists():
        return 1.0
    df = pd.read_csv(path, low_memory=False)
    if df.empty or "calibrated_rmse" not in df.columns:
        return 1.0
    value = pd.to_numeric(df["calibrated_rmse"].iloc[0], errors="coerce")
    if pd.isna(value):
        return 1.0
    return max(float(value), 0.75)


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _usage_status(row: pd.Series, final_readiness: str) -> str:
    if row.get("projection_mode") == "historical_test":
        return "HISTORICAL TEST ONLY"
    if final_readiness != "GO":
        return "DO NOT USE"
    return "MODEL REVIEW"


def _final_readiness() -> str:
    readiness = _read(output_path("google_sheets/live_readiness_export.csv"))
    if readiness.empty:
        return "NO-GO"
    row = readiness[readiness["Gate"] == "Final Betting Use"]
    return "NO-GO" if row.empty else str(row["Status"].iloc[0])


def build_receptions_market_probability() -> pd.DataFrame:
    model = _read(output_path("google_sheets_receptions_historical_test.csv"))
    odds = _read(output_path("gate_inputs_normalized/market_odds_gate_normalized.csv"))
    sd = calibration_error_sd()
    method = f"Normal approximation: mean=calibrated_projection, sd=max(calibrated_rmse,{0.75})"
    final_readiness = _final_readiness()
    if model.empty or odds.empty:
        out = pd.DataFrame(columns=PROBABILITY_COLUMNS)
        out.to_csv(output_path("market_edges/receptions_market_probability.csv"), index=False)
        return out

    merged = odds.merge(
        model,
        left_on=["Player ID", "Team"],
        right_on=["player_id", "team"],
        how="inner",
        suffixes=("_odds", "_model"),
    )
    rows = []
    for _, row in merged.iterrows():
        line = pd.to_numeric(row.get("Line"), errors="coerce")
        raw = pd.to_numeric(row.get("projected_receptions_raw"), errors="coerce")
        calibrated = pd.to_numeric(row.get("projected_receptions_calibrated"), errors="coerce")
        if pd.isna(line) or pd.isna(calibrated):
            over = pd.NA
            under = pd.NA
            notes = "Missing line or calibrated projection."
        else:
            over = normal_over_probability(float(calibrated), sd, float(line))
            under = 1 - over
            notes = "Research probability only unless Live Readiness is GO."
        rows.append(
            {
                "player_name": row.get("player_name", row.get("Player Name")),
                "player_id": row.get("player_id", row.get("Player ID")),
                "team": row.get("team", row.get("Team")),
                "opponent": row.get("Opponent", ""),
                "position": row.get("position", row.get("Position")),
                "line": line,
                "raw_projection": raw,
                "calibrated_projection": calibrated,
                "projection_sd": sd,
                "model_over_probability": over,
                "model_under_probability": under,
                "probability_method": method,
                "usage_status": _usage_status(row, final_readiness),
                "notes": notes,
            }
        )
    out = pd.DataFrame(rows, columns=PROBABILITY_COLUMNS)
    out.to_csv(output_path("market_edges/receptions_market_probability.csv"), index=False)
    return out


def main() -> None:
    out = build_receptions_market_probability()
    print(f"receptions_market_probability: {len(out):,} rows")
    print(f"calibration_error_used: {calibration_error_sd():.6f}")


if __name__ == "__main__":
    main()
