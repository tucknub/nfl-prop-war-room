from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path, project_path
from src.export.signal_explainability import SCORE_FAMILY_COLUMNS, add_explainability_columns


BOARD_FILES = {
    "slate": "signal_boards/slate_signal_board.csv",
    "receiving": "signal_boards/receiving_signal_board.csv",
    "rushing": "signal_boards/rushing_signal_board.csv",
    "passing": "signal_boards/passing_signal_board.csv",
}

TIER_VALUES = ["ELITE_SIGNAL", "STRONG_SIGNAL", "GOOD_SIGNAL", "WATCH", "REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]
FORBIDDEN_WORDS = ["BET", "EDGE", "CLV", "ODDS"]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def score_flags(frame: pd.DataFrame) -> list[str]:
    flags = []
    if frame.empty:
        return ["EMPTY_BOARD"]
    tiers = frame.get("signal_tier", pd.Series(dtype=str)).fillna("").astype(str)
    elite_share = tiers.eq("ELITE_SIGNAL").mean() if len(tiers) else 0
    review_share = tiers.isin(["REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]).mean() if len(tiers) else 0
    scores = pd.to_numeric(frame.get("overall_signal_score", pd.Series(dtype=float)), errors="coerce")
    missing = pd.to_numeric(frame.get("missing_signal_count", pd.Series(dtype=float)), errors="coerce")
    if elite_share > 0.08:
        flags.append("Too many ELITE_SIGNAL rows")
    if review_share == 0:
        flags.append("No red/review rows")
    if scores.notna().any() and scores.std(skipna=True) < 6:
        flags.append("Scores clustered too tightly")
    if scores.notna().any() and scores.mean(skipna=True) >= 75:
        flags.append("Scores clustered too high")
    if scores.notna().any() and missing.notna().any():
        high_missing = frame[(missing >= 5) & (scores >= scores.quantile(0.8))]
        if len(high_missing) > 0:
            flags.append("Missing-data rows still ranking too high")
    return flags or ["No structural distribution flags"]


def distribution_summary(board_name: str, frame: pd.DataFrame) -> dict[str, object]:
    scores = pd.to_numeric(frame.get("overall_signal_score", pd.Series(dtype=float)), errors="coerce")
    tiers = frame.get("signal_tier", pd.Series(dtype=str)).fillna("").astype(str)
    row = {
        "board": board_name,
        "row_count": len(frame),
        "average_overall_signal_score": round(float(scores.mean()), 4) if scores.notna().any() else pd.NA,
        "median_overall_signal_score": round(float(scores.median()), 4) if scores.notna().any() else pd.NA,
        "min_score": round(float(scores.min()), 4) if scores.notna().any() else pd.NA,
        "max_score": round(float(scores.max()), 4) if scores.notna().any() else pd.NA,
        "average_green_signal_count": round(float(pd.to_numeric(frame.get("green_signal_count", pd.Series(dtype=float)), errors="coerce").mean()), 4) if "green_signal_count" in frame.columns else pd.NA,
        "average_red_flag_count": round(float(pd.to_numeric(frame.get("red_flag_count", pd.Series(dtype=float)), errors="coerce").mean()), 4) if "red_flag_count" in frame.columns else pd.NA,
        "average_missing_signal_count": round(float(pd.to_numeric(frame.get("missing_signal_count", pd.Series(dtype=float)), errors="coerce").mean()), 4) if "missing_signal_count" in frame.columns else pd.NA,
        "audit_flags": "; ".join(score_flags(frame)),
    }
    for tier in TIER_VALUES:
        row[f"{tier}_count"] = int(tiers.eq(tier).sum())
    return row


def component_correlations(master: pd.DataFrame) -> pd.DataFrame:
    cols = [column for column in [*SCORE_FAMILY_COLUMNS, "overall_signal_score"] if column in master.columns]
    numeric = master[cols].apply(pd.to_numeric, errors="coerce")
    corr = numeric.corr()
    rows = []
    for left in corr.columns:
        for right in corr.columns:
            if left >= right:
                continue
            value = corr.loc[left, right]
            if pd.isna(value):
                continue
            risk = abs(float(value)) >= 0.75
            note = ""
            if risk:
                note = f"Possible double-count risk: {left} and {right} are highly correlated."
            rows.append(
                {
                    "component_a": left,
                    "component_b": right,
                    "correlation": round(float(value), 6),
                    "abs_correlation": round(abs(float(value)), 6),
                    "double_count_risk": risk,
                    "notes": note,
                }
            )
    return pd.DataFrame(rows).sort_values("abs_correlation", ascending=False) if rows else pd.DataFrame(columns=["component_a", "component_b", "correlation", "abs_correlation", "double_count_risk", "notes"])


def driver_audit(master: pd.DataFrame) -> pd.DataFrame:
    explained = add_explainability_columns(master)
    cols = [
        "player_id",
        "player_name",
        "team",
        "opponent",
        "position",
        "overall_signal_score",
        "signal_tier",
        "top_positive_driver_1",
        "top_positive_driver_2",
        "top_positive_driver_3",
        "top_negative_driver_1",
        "top_negative_driver_2",
        "top_negative_driver_3",
        "driver_notes",
    ]
    return explained[[col for col in cols if col in explained.columns]].copy()


def explainability(master: pd.DataFrame) -> pd.DataFrame:
    explained = add_explainability_columns(master)
    cols = [
        "player_id",
        "player_name",
        "team",
        "opponent",
        "position",
        "market_family",
        "overall_signal_score",
        "signal_tier",
        "plain_english_summary",
        "why_green",
        "why_yellow_or_review",
        "why_red_or_blocked",
        "data_limitations",
        "recommended_user_action",
    ]
    return explained[[col for col in cols if col in explained.columns]].copy()


def find_outcome_sources() -> list[str]:
    roots = [project_path("outputs"), project_path("outputs/run_reports"), project_path("src/backtest")]
    matches = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and any(token in path.name.lower() for token in ["backtest", "actual", "outcome"]):
                matches.append(str(path.relative_to(project_path())))
    return sorted(set(matches))[:50]


def outcome_audit(master: pd.DataFrame) -> pd.DataFrame:
    actual_columns = [col for col in master.columns if col.startswith("actual_") or col.endswith("_actual")]
    if not actual_columns:
        return pd.DataFrame(
            [
                {
                    "score_bucket": "NEEDS HISTORICAL SIGNAL BACKTEST DATA",
                    "row_count": len(master),
                    "average_projection": pd.NA,
                    "average_actual": pd.NA,
                    "projection_error": pd.NA,
                    "hit_rate_over_common_line_if_available": pd.NA,
                    "notes": "Outcome audit not generated because current signal master is target-week projection only and does not contain actual outcome columns.",
                }
            ]
        )
    return pd.DataFrame()


def forbidden_language(frame: pd.DataFrame) -> list[str]:
    text = " ".join(frame.fillna("").astype(str).agg(" ".join, axis=1).tolist()).upper() if not frame.empty else ""
    return [word for word in FORBIDDEN_WORDS if word in text]


def export_signal_score_audit() -> dict[str, pd.DataFrame]:
    master = read_csv("signal_boards/player_week_signal_master.csv")
    context = read_csv("signal_boards/signal_context_features.csv")
    boards = {name: read_csv(path) for name, path in BOARD_FILES.items()}

    summary = pd.DataFrame([distribution_summary(name, frame) for name, frame in boards.items()])
    correlations = component_correlations(master)
    drivers = driver_audit(master)
    explain = explainability(master)
    outcome = outcome_audit(master)

    summary.to_csv(output_path("signal_boards/signal_score_audit_summary.csv"), index=False)
    correlations.to_csv(output_path("signal_boards/signal_score_component_correlations.csv"), index=False)
    summary[["board", *[f"{tier}_count" for tier in TIER_VALUES]]].to_csv(output_path("signal_boards/signal_score_tier_distribution.csv"), index=False)
    drivers.to_csv(output_path("signal_boards/signal_score_driver_audit.csv"), index=False)
    explain.to_csv(output_path("signal_boards/signal_score_explainability.csv"), index=False)
    outcome.to_csv(output_path("signal_boards/signal_score_outcome_audit.csv"), index=False)

    write_report(summary, correlations, drivers, explain, outcome, context, find_outcome_sources())
    return {
        "summary": summary,
        "correlations": correlations,
        "drivers": drivers,
        "explainability": explain,
        "outcome": outcome,
    }


def write_report(summary: pd.DataFrame, correlations: pd.DataFrame, drivers: pd.DataFrame, explain: pd.DataFrame, outcome: pd.DataFrame, context: pd.DataFrame, outcome_sources: list[str]) -> None:
    high_corr = correlations[correlations["double_count_risk"].astype(str).str.lower().eq("true")] if not correlations.empty else pd.DataFrame()
    outcome_status = "NEEDS HISTORICAL SIGNAL BACKTEST DATA" if not outcome.empty and "NEEDS HISTORICAL SIGNAL BACKTEST DATA" in str(outcome.iloc[0].get("score_bucket", "")) else "AVAILABLE"
    forbidden = sorted(set(forbidden_language(explain) + forbidden_language(drivers)))
    text = f"""# Signal Score Audit Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Audit type: `HISTORICAL TEST / RESEARCH ONLY`

Master/context rows: `{len(context)}`

Distribution boards audited: `{len(summary)}`

High-correlation risk pairs: `{len(high_corr)}`

Driver audit rows: `{len(drivers)}`

Explainability rows: `{len(explain)}`

Outcome audit status: `{outcome_status}`

Forbidden action language hits in audit outputs: `{', '.join(forbidden) if forbidden else 'None'}`

Outcome source files inspected:

{chr(10).join(f"- `{item}`" for item in outcome_sources) if outcome_sources else "- None found"}

Notes:

- This audit checks score structure, component behavior, driver labels, and explanation quality.
- It does not prove profitability.
- It does not change projection math or signal score weights.
- Outcome validation requires a historical signal table with actual outcome columns.
"""
    output_path("run_reports/latest_signal_score_audit_report.md").write_text(text, encoding="utf-8")


def main() -> None:
    outputs = export_signal_score_audit()
    print(f"signal_score_audit_summary: {len(outputs['summary']):,} rows")
    print(f"signal_score_component_correlations: {len(outputs['correlations']):,} rows")
    print(f"signal_score_driver_audit: {len(outputs['drivers']):,} rows")
    print(f"signal_score_explainability: {len(outputs['explainability']):,} rows")
    print(f"signal_score_outcome_audit: {len(outputs['outcome']):,} rows")


if __name__ == "__main__":
    main()
