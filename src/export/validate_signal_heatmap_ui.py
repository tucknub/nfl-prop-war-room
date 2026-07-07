from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path, project_path


PAGE_FILES = [
    "dashboard/signal_ui.py",
    "dashboard/pages/22_Signal_Board_Foundation.py",
    "dashboard/pages/23_Slate_Signal_Board.py",
    "dashboard/pages/24_By_Game_Matchup_Board.py",
    "dashboard/pages/25_Receiving_Signal_Board.py",
    "dashboard/pages/26_Rushing_Signal_Board.py",
    "dashboard/pages/27_Passing_Signal_Board.py",
    "dashboard/pages/28_Blocked_Review_Board.py",
]

SIGNAL_PATHS = [
    "outputs/signal_boards/player_week_signal_master.csv",
    "outputs/signal_boards/slate_signal_board.csv",
    "outputs/signal_boards/by_game_signal_board.csv",
    "outputs/signal_boards/receiving_signal_board.csv",
    "outputs/signal_boards/rushing_signal_board.csv",
    "outputs/signal_boards/passing_signal_board.csv",
    "outputs/signal_boards/blocked_review_board.csv",
    "outputs/signal_boards/signal_data_inventory.csv",
]

FORBIDDEN_CENTERED_TERMS = [
    "clv",
    "closing line value",
    "bet_recommendation",
    "stake_size",
    "wager",
]

UNSUPPORTED_FAKE_METRICS = [
    "coverage_grade",
    "defender_shadow",
    "wind_adjusted_projection",
    "weather_edge",
    "opponent_coverage_rating",
]


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


def final_readiness() -> str:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or "check_name" not in status.columns:
        return "NO-GO"
    row = status[status["check_name"].astype(str).eq("final_live_readiness")]
    return "NO-GO" if row.empty else str(row["value"].iloc[0])


def leakage_status() -> str:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or "check_name" not in status.columns:
        return "UNKNOWN"
    row = status[status["check_name"].astype(str).eq("leakage_status")]
    return "UNKNOWN" if row.empty else str(row["value"].iloc[0])


def live_output_created() -> bool:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or "check_name" not in status.columns:
        return False
    row = status[status["check_name"].astype(str).eq("live_betting_output_created")]
    return False if row.empty else str(row["value"].iloc[0]).lower() == "true"


def file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def validate_signal_heatmap_ui() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    for relative in PAGE_FILES:
        path = project_path(relative)
        add(rows, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())

    for relative in SIGNAL_PATHS:
        path = project_path(relative)
        add(rows, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())

    page_texts = {relative: file_text(project_path(relative)) for relative in PAGE_FILES}
    combined = "\n".join(page_texts.values()).lower()
    centered_hits = [term for term in FORBIDDEN_CENTERED_TERMS if term in combined]
    add(rows, "no_clv_or_betting_recommendation_language", "no centered betting terms", centered_hits, not centered_hits)

    fake_hits = [term for term in UNSUPPORTED_FAKE_METRICS if term in combined]
    add(rows, "no_unsupported_fake_metrics_introduced", "no fake metric names", fake_hits, not fake_hits)

    raw_model_paths = ["outputs/google_sheets_receptions_historical_test.csv", "outputs/market_edges/receptions_line_ladder.csv"]
    raw_refs = [path for path in raw_model_paths if path.lower() in combined]
    add(rows, "signal_pages_use_signal_board_outputs", "no direct model output paths", raw_refs, not raw_refs)

    required_board_refs = [
        "slate_signal_board.csv",
        "by_game_signal_board.csv",
        "receiving_signal_board.csv",
        "rushing_signal_board.csv",
        "passing_signal_board.csv",
        "blocked_review_board.csv",
    ]
    for board in required_board_refs:
        add(rows, f"page_references_{board}", board, board in combined, board in combined)

    final = final_readiness()
    leakage = leakage_status()
    live_output = live_output_created()
    add(rows, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(rows, "leakage_status_pass", "PASS", leakage, leakage == "PASS")
    add(rows, "no_live_betting_output_created", False, live_output, not live_output)

    result = pd.DataFrame(rows)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_signal_heatmap_ui_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_signal_heatmap_ui_validation.md").write_text(
        f"""# Signal Heatmap UI Validation

Run timestamp: `{datetime.now(timezone.utc).isoformat()}`

Overall status: `{overall}`

Dashboard helper: `dashboard/signal_ui.py`

Signal pages checked: `{len(PAGE_FILES) - 1}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live betting output created: `{live_output}`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Next required action: Keep these pages as signal research views until live gates are verified.
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_signal_heatmap_ui()
    print(f"Signal heatmap UI validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
