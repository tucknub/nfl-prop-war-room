from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import py_compile

import pandas as pd

from src.common import output_path, project_path


HELPERS = [
    "inject_signal_css",
    "render_section_pill",
    "render_status_banner",
    "render_kpi_card",
    "render_player_signal_card",
    "render_signal_badge",
    "render_action_badge",
    "render_reliability_badge",
    "render_metric_chip",
    "build_signal_heatmap",
    "safe_display_dataframe",
    "render_signal_legend",
]
SIGNAL_PAGES = [
    "dashboard/pages/01_Signal_Command_Center.py",
    "dashboard/pages/02_By_Game_Matchup_Board.py",
    "dashboard/pages/03_Position_Signal_Boards.py",
    "dashboard/pages/04_Player_Signal_Drilldown.py",
    "dashboard/pages/05_Blocked_Review.py",
]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def read_text(path: Path) -> str:
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


def compile_pages() -> tuple[bool, list[str]]:
    failures = []
    for relative in [*SIGNAL_PAGES, "dashboard/Home.py", "dashboard/app.py"]:
        path = project_path(relative)
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            failures.append(f"{relative}: {exc.msg}")
    return not failures, failures


def validate_signal_ux_polish() -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, str]] = []
    signal_ui = read_text(project_path("dashboard", "signal_ui.py"))
    missing_helpers = [name for name in HELPERS if f"def {name}" not in signal_ui]
    add(checks, "shared_signal_ui_helpers_exist", HELPERS, missing_helpers, not missing_helpers)

    command_center_path = project_path("dashboard", "pages", "01_Signal_Command_Center.py")
    command_center = read_text(command_center_path)
    add(checks, "command_center_exists", True, command_center_path.exists(), command_center_path.exists())
    wording_ok = "Color-coded player and matchup signals" in command_center and "No odds. No CLV. No betting output." in command_center
    add(checks, "command_center_signal_first_wording", True, wording_ok, wording_ok)

    page_texts = {relative: read_text(project_path(relative)) for relative in SIGNAL_PAGES}
    csv_missing = [relative for relative, text in page_texts.items() if "outputs/signal_boards/" not in text]
    add(checks, "signal_pages_read_signal_board_csvs", "outputs/signal_boards/", csv_missing, not csv_missing)

    centered_terms = []
    for relative, text in page_texts.items():
        lower = text.lower()
        if lower.count("clv") > 2 or lower.count("odds") > 4:
            centered_terms.append(relative)
    add(checks, "signal_pages_do_not_center_odds_clv_language", "low/no odds and CLV emphasis", centered_terms, not centered_terms)

    fake_hits = []
    for relative, text in page_texts.items():
        lower = text.lower()
        if "mock_" in lower or "fake_" in lower or "random." in lower:
            fake_hits.append(relative)
    add(checks, "no_fake_signal_data_columns_introduced", "no fake/mock/random signal data", fake_hits, not fake_hits)

    compile_ok, failures = compile_pages()
    add(checks, "streamlit_signal_pages_compile", True, failures, compile_ok)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(checks, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(checks, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(checks, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    result = pd.DataFrame(checks)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_signal_ux_polish_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_signal_ux_polish_validation.md").write_text(
        f"""# Signal UX Polish Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Signal pages checked: `{len(SIGNAL_PAGES)}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_signal_ux_polish()
    print(f"Signal UX polish validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
