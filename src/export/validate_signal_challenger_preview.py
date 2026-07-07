from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path


REQUIRED = [
    "signal_boards/signal_challenger_preview_rows.csv",
    "signal_boards/signal_challenger_preview_summary.csv",
    "signal_boards/signal_challenger_top_movers.csv",
    "signal_boards/signal_challenger_tier_changes.csv",
    "signal_boards/signal_challenger_family_comparison.csv",
    "signal_boards/challenger_slate_signal_board.csv",
    "signal_boards/challenger_receiving_signal_board.csv",
    "signal_boards/challenger_rushing_signal_board.csv",
    "signal_boards/challenger_passing_signal_board.csv",
    "run_reports/latest_signal_challenger_preview_report.md",
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


def validate_signal_challenger_preview() -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, str]] = []
    for relative in REQUIRED:
        path = output_path(relative)
        add(checks, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())

    preview = read_csv("signal_boards/signal_challenger_preview_rows.csv")
    family = read_csv("signal_boards/signal_challenger_family_comparison.csv")
    movers = read_csv("signal_boards/signal_challenger_top_movers.csv")
    master = read_csv("signal_boards/player_week_signal_master.csv")

    add(checks, "preview_rows_have_rows", ">0", len(preview), len(preview) > 0)
    add(checks, "family_comparison_have_rows", ">0", len(family), len(family) > 0)
    add(checks, "top_movers_have_rows", ">0", len(movers), len(movers) > 0)
    page_path = Path("dashboard/pages/32_Champion_vs_Challenger.py")
    add(checks, "streamlit_preview_page_exists", True, page_path.exists(), page_path.exists())

    required_preview_cols = {
        "preview_usage_status",
        "production_champion_profile",
        "challenger_profile_name",
        "current_overall_signal_score",
        "challenger_overall_signal_score",
        "signal_score_delta",
        "tier_change",
        "action_change",
    }
    add(checks, "preview_required_columns", required_preview_cols, set(preview.columns), required_preview_cols.issubset(preview.columns))
    research_only = not preview.empty and preview.get("preview_usage_status", pd.Series(dtype=str)).astype(str).eq("RESEARCH_ONLY").all()
    add(checks, "preview_rows_labeled_research_only", True, research_only, research_only)
    champion_status = not preview.empty and preview.get("production_champion_profile", pd.Series(dtype=str)).astype(str).eq("current_v1").all()
    add(checks, "production_champion_remains_current_v1", "current_v1", champion_status, champion_status)

    forbidden_master_cols = {"challenger_profile_name", "challenger_overall_signal_score", "signal_score_delta", "preview_usage_status"}
    master_clean = forbidden_master_cols.isdisjoint(set(master.columns))
    add(checks, "challenger_not_applied_to_production_master", "no challenger preview columns", sorted(forbidden_master_cols.intersection(master.columns)), master_clean)

    promoted = not family.empty and family.get("preview_recommendation", pd.Series(dtype=str)).astype(str).eq("CONSIDER_PROMOTION_LATER").any()
    promotion_applied = not preview.empty and preview.get("production_promotion_applied", pd.Series(dtype=str)).astype(str).str.lower().eq("true").any() if "production_promotion_applied" in preview.columns else False
    add(checks, "no_challenger_profile_auto_promoted", False, promotion_applied, not promotion_applied, f"promotion candidate present: {promoted}")

    combined = (text_from_frame(preview) + " " + text_from_frame(family) + " " + text_from_frame(movers)).upper()
    hits = [word for word in FORBIDDEN if word in combined]
    add(checks, "no_forbidden_language_in_preview_outputs", "no forbidden words", hits, not hits)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(checks, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(checks, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(checks, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    result = pd.DataFrame(checks)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_signal_challenger_preview_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_signal_challenger_preview_validation.md").write_text(
        f"""# Champion vs Challenger Signal Preview Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Preview rows: `{len(preview)}`

Family rows: `{len(family)}`

Top movers rows: `{len(movers)}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_signal_challenger_preview()
    print(f"Signal challenger preview validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
