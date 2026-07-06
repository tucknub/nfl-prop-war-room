from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path


REQUIRED_COMMANDS = [
    "python -m src.run_prop_war_room_pipeline",
    "python -m src.validate_receptions_safety",
    "python -m src.validate_forward_projection_dry_run",
    "python -m src.load.validate_current_roster_map",
    "python -m src.load.validate_current_role_map",
    "python -m src.load.validate_current_injury_map",
    "python -m src.load.validate_market_odds_map",
    "python -m src.export.validate_edge_preview_board",
    "python -m src.validate_edge_dry_run",
]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, str]], check_name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append({"check_name": check_name, "expected": str(expected), "actual": str(actual), "status": "PASS" if passed else "FAIL", "severity": "INFO" if passed else "HIGH", "notes": notes})


def final_readiness() -> str:
    readiness = read_csv("google_sheets/live_readiness_export.csv")
    if readiness.empty or "Gate" not in readiness.columns:
        return "NO-GO"
    row = readiness[readiness["Gate"].astype(str).eq("Final Betting Use")]
    return "NO-GO" if row.empty else str(row["Status"].iloc[0])


def live_output_created() -> bool:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if not status.empty and {"check_name", "value"}.issubset(status.columns):
        row = status[status["check_name"].astype(str).eq("live_betting_output_created")]
        if not row.empty:
            return str(row["value"].iloc[0]).strip().lower() == "true"
    return False


def validate_live_data_intake_status() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    checklist_path = output_path("data_intake/live_data_intake_checklist.csv")
    status_path = output_path("data_intake/live_data_intake_status.csv")
    report_path = output_path("run_reports/latest_live_data_intake_report.md")
    guide_path = output_path("../LIVE_DATA_INTAKE.md")
    add(rows, "intake_checklist_exists", True, checklist_path.exists(), checklist_path.exists())
    add(rows, "intake_status_exists", True, status_path.exists(), status_path.exists())
    add(rows, "intake_report_exists", True, report_path.exists(), report_path.exists())
    add(rows, "intake_guide_exists", True, guide_path.exists(), guide_path.exists())
    checklist = pd.read_csv(checklist_path, low_memory=False) if checklist_path.exists() else pd.DataFrame()
    status = pd.read_csv(status_path, low_memory=False) if status_path.exists() else pd.DataFrame()
    for gate in ["Current Roster Map", "Role / Depth Chart Map", "Injury / Availability Map", "Market Odds Map"]:
        row = status[status["gate"].astype(str).eq(gate)] if not status.empty and "gate" in status.columns else pd.DataFrame()
        current = "MISSING" if row.empty else str(row["current_status"].iloc[0])
        add(rows, f"{gate.lower().replace(' / ', '_').replace(' ', '_')}_needs_data_reported", "NEEDS DATA", current, current == "NEEDS DATA")
    if not checklist.empty:
        template_ready = checklist[
            checklist["gate"].astype(str).isin(["Current Roster Map", "Role / Depth Chart Map", "Injury / Availability Map", "Market Odds Map"])
            & checklist["current_status"].astype(str).eq("READY")
        ]
        add(rows, "templates_do_not_make_gates_ready", 0, len(template_ready), template_ready.empty)
    final = final_readiness()
    add(rows, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(rows, "no_live_betting_output_exists", False, live_output_created(), not live_output_created())
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    for command in REQUIRED_COMMANDS:
        add(rows, f"report_includes_{command.replace(' ', '_').replace('-', '_')}", command, command in report_text, command in report_text)
    add(rows, "report_does_not_claim_go", "No GO claim", "Can forward projection be considered? `Yes`" in report_text, "Can forward projection be considered? `Yes`" not in report_text)
    result = pd.DataFrame(rows)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_live_data_intake_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_live_data_intake_validation.md").write_text(
        f"""# Live Data Intake Validation

Run timestamp: `{datetime.now(timezone.utc).isoformat()}`

Overall status: `{overall}`

Final readiness: `{final}`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Next required action: Fill real non-template gate files, rerun the intake export, and rerun all validators.
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_live_data_intake_status()
    print(f"Live data intake validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
