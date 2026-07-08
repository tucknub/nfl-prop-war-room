from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import py_compile

import pandas as pd

from src.common import output_path, project_path


VISIBLE_PAGES = {
    "01_Signal_Command_Center.py",
    "02_By_Game_Matchup_Board.py",
    "03_Position_Signal_Boards.py",
    "04_Player_Signal_Drilldown.py",
    "05_Blocked_Review.py",
    "06_Research_Lab.py",
    "07_Admin_Readiness.py",
}

ARCHIVED_DEBUG_PAGES = {
    "00_Market_Hub.py",
    "01_Live_Readiness.py",
    "02_Receptions_Dashboard.py",
    "03_Line_Ladder.py",
    "04_Market_Edges.py",
    "05_Gate_Status.py",
    "06_Identity_Warnings.py",
    "07_Run_Reports.py",
    "08_Best_Overall_Board.py",
    "09_Receiving_Yards.py",
    "10_Rushing_Yards.py",
    "11_Carries.py",
    "12_Pass_Attempts.py",
    "13_Completions.py",
    "14_Current_Roster_Map.py",
    "15_Passing_Yards.py",
    "16_Current_Role_Map.py",
    "17_Current_Injury_Map.py",
    "18_Market_Odds_Map.py",
    "19_Edge_Preview_Board.py",
    "20_Edge_Dry_Run.py",
    "21_Live_Data_Intake.py",
    "22_Signal_Board_Foundation.py",
    "23_Slate_Signal_Board.py",
    "25_Receiving_Signal_Board.py",
    "26_Rushing_Signal_Board.py",
    "27_Passing_Signal_Board.py",
    "29_Signal_Score_Audit.py",
    "30_Historical_Signal_Backtest.py",
    "31_Signal_Weight_Tuning.py",
    "32_Champion_vs_Challenger.py",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def read_status_value(check_name: str, default: str = "UNKNOWN") -> str:
    path = output_path("run_reports/latest_receptions_pipeline_status.csv")
    if not path.exists():
        return default
    df = pd.read_csv(path, low_memory=False)
    if df.empty or not {"check_name", "value"}.issubset(df.columns):
        return default
    row = df[df["check_name"].astype(str).eq(check_name)]
    return default if row.empty else str(row["value"].iloc[0])


def add(rows: list[dict[str, str]], check_name: str, expected: object, actual: object, passed: bool, notes: str = "") -> None:
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


def compile_streamlit_files() -> tuple[bool, list[str]]:
    failures: list[str] = []
    candidates = [project_path("dashboard", "Home.py"), project_path("dashboard", "app.py")]
    candidates.extend(sorted(project_path("dashboard", "pages").glob("*.py")))
    for path in candidates:
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{path.name}: {exc.msg}")
    return not failures, failures


def validate_product_reset() -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, str]] = []
    pages_dir = project_path("dashboard", "pages")
    archive_dir = project_path("dashboard", "archived_pages")
    visible_files = {path.name for path in pages_dir.glob("*.py")}
    archived_files = {path.name for path in archive_dir.glob("*.py")} if archive_dir.exists() else set()

    add(checks, "visible_pages_exactly_simplified_set", sorted(VISIBLE_PAGES), sorted(visible_files), visible_files == VISIBLE_PAGES)
    add(checks, "archived_pages_folder_exists", True, archive_dir.exists(), archive_dir.exists())
    add(checks, "old_debug_pages_not_visible", [], sorted(visible_files & ARCHIVED_DEBUG_PAGES), not (visible_files & ARCHIVED_DEBUG_PAGES))
    add(checks, "old_debug_pages_archived", sorted(ARCHIVED_DEBUG_PAGES), sorted(ARCHIVED_DEBUG_PAGES - archived_files), ARCHIVED_DEBUG_PAGES.issubset(archived_files))

    required = {
        "home_page_exists": project_path("dashboard", "Home.py"),
        "signal_command_center_exists": pages_dir / "01_Signal_Command_Center.py",
        "position_signal_boards_exists": pages_dir / "03_Position_Signal_Boards.py",
        "research_lab_exists": pages_dir / "06_Research_Lab.py",
        "admin_readiness_exists": pages_dir / "07_Admin_Readiness.py",
    }
    for name, path in required.items():
        add(checks, name, True, path.exists(), path.exists())

    home = read_text(project_path("dashboard", "Home.py"))
    command = read_text(pages_dir / "01_Signal_Command_Center.py")
    combined = f"{home}\n{command}".lower()
    discouraged = ["market edges", "edge board", "clv build", "odds shopping", "best sportsbook"]
    hits = [phrase for phrase in discouraged if phrase in combined]
    add(checks, "home_command_center_not_odds_clv_centered", "no odds/CLV workflow promotion", hits, not hits)

    final = read_status_value("final_live_readiness", "NO-GO")
    live = read_status_value("live_betting_output_created", "False")
    leakage = read_status_value("leakage_status", "UNKNOWN")
    add(checks, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(checks, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(checks, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    compile_ok, compile_failures = compile_streamlit_files()
    add(checks, "visible_streamlit_pages_compile", True, compile_failures, compile_ok)

    result = pd.DataFrame(checks)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_dashboard_product_reset_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_dashboard_product_reset_validation.md").write_text(
        f"""# Dashboard Product Reset Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Visible sidebar pages: `{', '.join(sorted(visible_files))}`

Archived page count: `{len(archived_files)}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live betting output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_product_reset()
    print(f"Dashboard product reset validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
