from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path


REQUIRED_OUTPUTS = [
    "signal_boards/signal_score_audit_summary.csv",
    "signal_boards/signal_score_component_correlations.csv",
    "signal_boards/signal_score_tier_distribution.csv",
    "signal_boards/signal_score_driver_audit.csv",
    "signal_boards/signal_score_explainability.csv",
    "run_reports/latest_signal_score_audit_report.md",
]

FORBIDDEN = ["BET", "EDGE", "CLV", "ODDS"]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, str]], check_name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append(
        {
            "check_name": check_name,
            "expected": str(expected),
            "actual": str(actual),
            "status": "PASS" if passed else "FAIL",
            "severity": "INFO" if passed else "HIGH",
            "notes": notes,
        }
    )


def status_value(name: str, default: str = "UNKNOWN") -> str:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or not {"check_name", "value"}.issubset(status.columns):
        return default
    row = status[status["check_name"].astype(str).eq(name)]
    return default if row.empty else str(row["value"].iloc[0])


def forbidden_hits(*frames: pd.DataFrame) -> list[str]:
    text = ""
    for frame in frames:
        if not frame.empty:
            text += " " + " ".join(frame.fillna("").astype(str).agg(" ".join, axis=1).tolist())
    upper = text.upper()
    return [word for word in FORBIDDEN if word in upper]


def validate_signal_score_audit() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    for relative in REQUIRED_OUTPUTS:
        path = output_path(relative)
        add(rows, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())

    summary = read_csv("signal_boards/signal_score_audit_summary.csv")
    correlations = read_csv("signal_boards/signal_score_component_correlations.csv")
    drivers = read_csv("signal_boards/signal_score_driver_audit.csv")
    explain = read_csv("signal_boards/signal_score_explainability.csv")
    outcome = read_csv("signal_boards/signal_score_outcome_audit.csv")
    master = read_csv("signal_boards/player_week_signal_master.csv")

    add(rows, "summary_has_board_rows", ">=4", len(summary), len(summary) >= 4)
    add(rows, "explainability_output_exists_with_rows", ">0", len(explain), len(explain) > 0)
    add(rows, "driver_output_exists_with_rows", ">0", len(drivers), len(drivers) > 0)

    hits = forbidden_hits(drivers, explain)
    add(rows, "no_forbidden_action_language_in_audit_outputs", "no forbidden words", hits, not hits)

    if not correlations.empty and "double_count_risk" in correlations.columns:
        risky = correlations[correlations["double_count_risk"].astype(str).str.lower().eq("true")]
        risks_reported = risky.empty or risky["notes"].astype(str).str.len().gt(0).all()
        add(rows, "high_correlation_risks_reported_if_present", "risk rows have notes", len(risky), risks_reported)
    else:
        add(rows, "high_correlation_risks_reported_if_present", "correlation rows", len(correlations), False)

    outcome_text = outcome.apply(lambda row: " ".join(str(value) for value in row.tolist()), axis=1) if not outcome.empty else pd.Series(dtype=str)
    outcome_labeled = outcome_text.str.contains("NEEDS HISTORICAL SIGNAL BACKTEST DATA|PARTIAL_HISTORICAL_SIGNAL_BACKTEST", na=False, regex=True).any()
    add(rows, "outcome_audit_clearly_labeled", "NEEDS HISTORICAL SIGNAL BACKTEST DATA or PARTIAL_HISTORICAL_SIGNAL_BACKTEST", outcome_labeled, outcome_labeled)

    required_master_cols = ["signal_explanation", "recommended_user_action", "top_positive_driver_1", "top_negative_driver_1"]
    present = [col for col in required_master_cols if col in master.columns]
    add(rows, "master_contains_explanation_action_fields", required_master_cols, present, set(required_master_cols).issubset(master.columns))

    if "usage_status" in master.columns:
        usage_ok = master["usage_status"].astype(str).str.contains("HISTORICAL TEST ONLY|Research", case=False, regex=True, na=False).all()
        add(rows, "usage_remains_historical_or_research_only", "historical/research labels", sorted(master["usage_status"].astype(str).unique())[:10], usage_ok)
    else:
        add(rows, "usage_remains_historical_or_research_only", "usage_status column", "missing", False)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(rows, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(rows, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(rows, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    result = pd.DataFrame(rows)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_signal_score_audit_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_signal_score_audit_validation.md").write_text(
        f"""# Signal Score Audit Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Summary rows: `{len(summary)}`

Correlation rows: `{len(correlations)}`

Driver rows: `{len(drivers)}`

Explainability rows: `{len(explain)}`

Outcome audit labeled: `{outcome_labeled}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live betting output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_signal_score_audit()
    print(f"Signal score audit validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
