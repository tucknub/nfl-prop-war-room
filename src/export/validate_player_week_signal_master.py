from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path


REQUIRED_VIEWS = [
    "signal_boards/slate_signal_board.csv",
    "signal_boards/by_game_signal_board.csv",
    "signal_boards/receiving_signal_board.csv",
    "signal_boards/rushing_signal_board.csv",
    "signal_boards/passing_signal_board.csv",
    "signal_boards/blocked_review_board.csv",
]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, str]], check_name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append({"check_name": check_name, "expected": str(expected), "actual": str(actual), "status": "PASS" if passed else "FAIL", "severity": "INFO" if passed else "HIGH", "notes": notes})


def final_readiness() -> str:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or "check_name" not in status.columns:
        return "NO-GO"
    row = status[status["check_name"].astype(str).eq("final_live_readiness")]
    return "NO-GO" if row.empty else str(row["value"].iloc[0])


def live_output_created() -> bool:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or "check_name" not in status.columns:
        return False
    row = status[status["check_name"].astype(str).eq("live_betting_output_created")]
    return False if row.empty else str(row["value"].iloc[0]).lower() == "true"


def validate_player_week_signal_master() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    inventory_path = output_path("signal_boards/signal_data_inventory.csv")
    master_path = output_path("signal_boards/player_week_signal_master.csv")
    definitions_path = output_path("../SIGNAL_SCORE_DEFINITIONS.md")
    inventory = pd.read_csv(inventory_path, low_memory=False) if inventory_path.exists() else pd.DataFrame()
    master = pd.read_csv(master_path, low_memory=False) if master_path.exists() else pd.DataFrame()
    add(rows, "signal_data_inventory_exists", True, inventory_path.exists(), inventory_path.exists())
    add(rows, "score_definitions_doc_exists", True, definitions_path.exists(), definitions_path.exists())
    add(rows, "player_week_signal_master_exists", True, master_path.exists(), master_path.exists())
    add(rows, "player_week_signal_master_has_rows", ">0", len(master), len(master) > 0)
    for view in REQUIRED_VIEWS:
        path = output_path(view)
        add(rows, f"{view.replace('/', '_')}_exists", True, path.exists(), path.exists())
        frame = pd.read_csv(path, nrows=5, low_memory=False) if path.exists() else pd.DataFrame()
        independent_cols = {"score_formula", "weight_projection", "weight_weather", "independent_score_definition"}
        add(rows, f"{view.replace('/', '_')}_derived_from_master", "no independent score columns", sorted(independent_cols.intersection(frame.columns)), not independent_cols.intersection(frame.columns))
    if not inventory.empty:
        unavailable_real = inventory[inventory["implementation_status"].astype(str).isin(["NOT_AVAILABLE", "NEEDS SOURCE", "PLANNED_SOURCE"]) & inventory["available_now"].astype(str).eq("Yes")]
        add(rows, "unavailable_metrics_not_treated_as_real", 0, len(unavailable_real), unavailable_real.empty)
    if not master.empty:
        weather_available = master["weather_score"].notna().any() if "weather_score" in master.columns else False
        add(rows, "weather_not_green_without_source", False, weather_available, not weather_available)
        context_columns = ["opponent_fit_score", "game_script_score", "recent_form_score"]
        context_available = any(col in master.columns and master[col].notna().any() for col in context_columns)
        add(rows, "context_v1_scores_allowed_when_sourced", True, context_available, context_available)
        labels_ok = master["usage_status"].astype(str).isin(["HISTORICAL TEST ONLY", "Research Only", "Research Only - Historical Test Only - Not Betting Ready"]).all()
        add(rows, "usage_status_research_or_historical", "HISTORICAL TEST ONLY/research-only", sorted(master["usage_status"].astype(str).unique())[:10], labels_ok)
        no_bet_cols = not {"bet_recommendation", "wager", "stake", "clv"}.intersection(master.columns)
        add(rows, "support_markets_not_betting_recommendations", "no bet columns", sorted({"bet_recommendation", "wager", "stake", "clv"}.intersection(master.columns)), no_bet_cols)
        context_notes = master["review_reason"].astype(str).str.contains("Context V1", na=False).all()
        unavailable_notes = master["review_reason"].astype(str).str.contains("weather|route share|first-read|coverage", case=False, na=False).all()
        add(rows, "context_labeled_context_v1", "Context V1 review reason", context_notes, context_notes)
        add(rows, "unavailable_context_still_labeled", "weather/route/coverage unavailable", unavailable_notes, unavailable_notes)
    final = final_readiness()
    add(rows, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(rows, "no_live_betting_output_created", False, live_output_created(), not live_output_created())
    result = pd.DataFrame(rows)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_player_week_signal_master_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_player_week_signal_master_validation.md").write_text(
        f"""# Player Week Signal Master Validation

Run timestamp: `{datetime.now(timezone.utc).isoformat()}`

Overall status: `{overall}`

Master rows: `{len(master)}`

Inventory rows: `{len(inventory)}`

Final readiness: `{final}`

Live betting output created: `{live_output_created()}`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Next required action: Use the master table as the source of truth for future heatmap boards.
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_player_week_signal_master()
    print(f"Player week signal master validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
