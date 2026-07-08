from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import py_compile

import pandas as pd

from src.common import output_path, project_path


MAIN_WORKFLOW = [
    "dashboard/pages/23_Slate_Signal_Board.py",
    "dashboard/pages/24_By_Game_Matchup_Board.py",
    "dashboard/pages/25_Receiving_Signal_Board.py",
    "dashboard/pages/26_Rushing_Signal_Board.py",
    "dashboard/pages/27_Passing_Signal_Board.py",
    "dashboard/pages/28_Blocked_Review_Board.py",
    "dashboard/pages/33_Player_Signal_Drilldown.py",
]
RESEARCH = [
    "dashboard/pages/29_Signal_Score_Audit.py",
    "dashboard/pages/30_Historical_Signal_Backtest.py",
    "dashboard/pages/31_Signal_Weight_Tuning.py",
    "dashboard/pages/32_Champion_vs_Challenger.py",
]
ADMIN = [
    "dashboard/pages/01_Live_Readiness.py",
    "dashboard/pages/14_Current_Roster_Map.py",
    "dashboard/pages/16_Current_Role_Map.py",
    "dashboard/pages/17_Current_Injury_Map.py",
    "dashboard/pages/18_Market_Odds_Map.py",
    "dashboard/pages/20_Edge_Dry_Run.py",
    "dashboard/pages/21_Live_Data_Intake.py",
]
HOME = project_path("dashboard", "Home.py")
COMMAND_CENTER = project_path("dashboard", "pages", "02_Signal_Command_Center.py")
NAV_DOC = project_path("DASHBOARD_NAVIGATION.md")


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


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


def files_contain(files: list[str], label: str) -> tuple[bool, list[str]]:
    missing = []
    for relative in files:
        path = project_path(relative)
        if label not in text(path):
            missing.append(relative)
    return not missing, missing


def compile_pages() -> tuple[bool, list[str]]:
    failures = []
    for path in project_path("dashboard", "pages").glob("*.py"):
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{path.name}: {exc.msg}")
    for path in [project_path("dashboard", "Home.py"), project_path("dashboard", "app.py")]:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{path.name}: {exc.msg}")
    return not failures, failures


def validate_dashboard_navigation() -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, str]] = []
    add(checks, "dashboard_navigation_doc_exists", True, NAV_DOC.exists(), NAV_DOC.exists())
    add(checks, "signal_command_center_exists", True, COMMAND_CENTER.exists(), COMMAND_CENTER.exists())

    home_text = text(HOME)
    command_text = text(COMMAND_CENTER)
    add(checks, "home_mentions_signal_command_center", "Signal Command Center", "Signal Command Center" in home_text, "Signal Command Center" in home_text)
    add(checks, "home_mentions_main_product_signal_workflow", "main product is the signal board workflow", "main product is the signal board workflow" in home_text, "main product is the signal board workflow" in home_text)

    ok, missing = files_contain(MAIN_WORKFLOW, "Section: Main Signal Workflow")
    add(checks, "main_signal_pages_have_workflow_labels", "Section: Main Signal Workflow", missing, ok)
    ok, missing = files_contain(RESEARCH, "Section: Research / Audit Lab")
    add(checks, "research_pages_have_lab_labels", "Section: Research / Audit Lab", missing, ok)
    ok, missing = files_contain(ADMIN, "Section: Readiness / Data Admin")
    add(checks, "admin_pages_have_data_admin_labels", "Section: Readiness / Data Admin", missing, ok)

    combined_home = f"{home_text}\n{command_text}"
    discouraged = ["Edge Preview Board", "Odds shopping", "CLV build"]
    hits = [word for word in discouraged if word.lower() in combined_home.lower()]
    add(checks, "home_command_center_do_not_promote_edge_or_odds_workflow", "no edge/odds workflow promotion", hits, not hits)

    compile_ok, compile_failures = compile_pages()
    add(checks, "streamlit_page_files_compile", True, compile_failures, compile_ok)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(checks, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(checks, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(checks, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    result = pd.DataFrame(checks)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_dashboard_navigation_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_dashboard_navigation_validation.md").write_text(
        f"""# Dashboard Navigation Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Signal Command Center exists: `{COMMAND_CENTER.exists()}`

Navigation doc exists: `{NAV_DOC.exists()}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_dashboard_navigation()
    print(f"Dashboard navigation validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
