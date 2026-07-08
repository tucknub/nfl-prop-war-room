from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path


REQUIRED = [
    "signal_boards/player_signal_profiles.csv",
    "signal_boards/player_signal_recent_history.csv",
    "signal_boards/player_signal_market_summary.csv",
    "signal_boards/player_signal_context_summary.csv",
    "run_reports/latest_player_signal_profiles_report.md",
]
EXPLANATION_COLUMNS = [
    "signal_explanation",
    "top_signal_reason",
    "review_reason",
    "blocked_reason",
    "top_positive_driver_1",
    "top_negative_driver_1",
]
FORBIDDEN = ["CLV", "ODDS", "BET"]


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


def text_from_frame(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    return " ".join(frame.fillna("").astype(str).apply(lambda row: " ".join(row.tolist()), axis=1).tolist())


def validate_player_signal_profiles() -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, str]] = []
    for relative in REQUIRED:
        path = output_path(relative)
        add(checks, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())

    profiles = read_csv("signal_boards/player_signal_profiles.csv")
    market = read_csv("signal_boards/player_signal_market_summary.csv")
    history = read_csv("signal_boards/player_signal_recent_history.csv")
    context = read_csv("signal_boards/player_signal_context_summary.csv")
    challenger = read_csv("signal_boards/signal_challenger_preview_rows.csv")

    drilldown_page = Path("dashboard/pages/04_Player_Signal_Drilldown.py")
    add(checks, "drilldown_dashboard_page_exists", True, drilldown_page.exists(), drilldown_page.exists())
    add(checks, "profiles_have_rows", ">0", len(profiles), len(profiles) > 0)
    add(checks, "market_summary_have_rows", ">0", len(market), len(market) > 0)
    add(checks, "context_summary_have_rows", ">0", len(context), len(context) > 0)
    history_available_or_marked = len(history) > 0 or "history_notes" in history.columns
    add(checks, "recent_history_exists_or_marked_unavailable", "rows or history_notes", len(history), history_available_or_marked)

    missing_explain = [col for col in EXPLANATION_COLUMNS if col not in profiles.columns]
    add(checks, "profiles_include_explanation_fields", EXPLANATION_COLUMNS, missing_explain, not missing_explain)

    if not challenger.empty and "preview_usage_status" in challenger.columns:
        research_only = challenger["preview_usage_status"].astype(str).eq("RESEARCH_ONLY").all()
    else:
        research_only = True
    add(checks, "challenger_data_labeled_research_only", True, research_only, research_only)

    no_future_flag = True
    if "history_notes" in history.columns and not history.empty:
        no_future_flag = history["history_notes"].astype(str).str.contains("target week and future rows excluded", case=False, na=False).all()
    add(checks, "recent_history_marks_target_future_exclusion", True, no_future_flag, no_future_flag)

    combined = (text_from_frame(profiles) + " " + text_from_frame(market) + " " + text_from_frame(context) + " " + text_from_frame(history)).upper()
    hits = [word for word in FORBIDDEN if word in combined]
    add(checks, "no_forbidden_language_in_drilldown_outputs", "no forbidden words", hits, not hits)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(checks, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(checks, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(checks, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    result = pd.DataFrame(checks)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_player_signal_profiles_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_player_signal_profiles_validation.md").write_text(
        f"""# Player Signal Profiles Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Profile rows: `{len(profiles)}`

Market summary rows: `{len(market)}`

Recent history rows: `{len(history)}`

Context summary rows: `{len(context)}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_player_signal_profiles()
    print(f"Player signal profiles validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
