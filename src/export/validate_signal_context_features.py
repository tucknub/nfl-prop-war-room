from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import load_config, output_path, project_path, raw_path


CONTEXT_OUTPUTS = [
    "signal_boards/recent_form_features.csv",
    "signal_boards/game_environment_features.csv",
    "signal_boards/opponent_defense_fit_features.csv",
    "signal_boards/signal_context_features.csv",
]


def read_csv(relative: str, output: bool = True) -> pd.DataFrame:
    path = output_path(relative) if output else project_path(relative)
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


def validate_signal_context_features() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    cfg = load_config()["data"]
    target_season = int(cfg.get("target_season", cfg.get("projection_season", 2025)))
    target_week = int(cfg.get("target_week", cfg.get("projection_week", 1)))
    history_end = int(cfg.get("history_end_season", target_season - 1))

    for relative in CONTEXT_OUTPUTS:
        path = output_path(relative)
        add(rows, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())
        frame = pd.read_csv(path, nrows=5, low_memory=False) if path.exists() else pd.DataFrame()
        add(rows, f"{relative.replace('/', '_')}_has_rows", ">0", len(frame), len(frame) > 0)

    recent = read_csv("signal_boards/recent_form_features.csv")
    environment = read_csv("signal_boards/game_environment_features.csv")
    defense = read_csv("signal_boards/opponent_defense_fit_features.csv")
    context = read_csv("signal_boards/signal_context_features.csv")
    master = read_csv("signal_boards/player_week_signal_master.csv")
    inventory = read_csv("signal_boards/signal_data_inventory.csv")

    if not recent.empty and {"season", "week"}.issubset(recent.columns):
        no_target_actual = not ((pd.to_numeric(recent["season"], errors="coerce").eq(target_season)) & (pd.to_numeric(recent["week"], errors="coerce").eq(target_week)) & recent.get("recent_form_notes", "").astype(str).str.contains("target-week actual", case=False, na=False)).any()
        add(rows, "recent_form_no_target_week_actual_results", True, no_target_actual, no_target_actual)
    else:
        add(rows, "recent_form_no_target_week_actual_results", "recent rows", len(recent), False)

    env_sourced = not environment.empty and {"spread_line", "total_line", "game_environment_reliability"}.issubset(environment.columns)
    env_ok = env_sourced and environment["game_environment_reliability"].fillna("MISSING").astype(str).isin(["HIGH", "MEDIUM", "LOW", "MISSING"]).all()
    add(rows, "game_environment_sourced_or_unavailable", "spread/total fields or MISSING", env_ok, env_ok)

    defense_required = {"defense_fit_sample_games", "defense_fit_reliability", "defense_fit_notes"}
    defense_ok = not defense.empty and defense_required.issubset(defense.columns) and defense["defense_fit_notes"].astype(str).str.contains("shrinkage", case=False, na=False).any()
    add(rows, "defense_fit_uses_reliability_and_shrinkage", "sample/reliability/shrinkage", defense_required.intersection(defense.columns), defense_ok)

    if not inventory.empty and {"metric_name", "implementation_status"}.issubset(inventory.columns):
        weather = inventory[inventory["metric_name"].astype(str).str.lower().eq("weather")]
        weather_ok = not weather.empty and weather["implementation_status"].astype(str).isin(["NOT_AVAILABLE", "NEEDS SOURCE", "PLANNED_SOURCE"]).all()
        add(rows, "weather_remains_unavailable_unless_sourced", "NOT_AVAILABLE/NEEDS SOURCE", weather["implementation_status"].tolist() if not weather.empty else [], weather_ok)
        unavailable_terms = ["coverage_tendency", "shadow_cb_matchup", "route_share"]
        unavailable = inventory[inventory["metric_name"].astype(str).isin(unavailable_terms)]
        unavailable_ok = len(unavailable) == len(unavailable_terms) and unavailable["implementation_status"].astype(str).isin(["NOT_AVAILABLE", "NEEDS SOURCE", "PLANNED_SOURCE"]).all()
        add(rows, "coverage_shadow_route_remain_unavailable", "unavailable statuses", unavailable[["metric_name", "implementation_status"]].to_dict("records"), unavailable_ok)
    else:
        add(rows, "weather_remains_unavailable_unless_sourced", "inventory rows", len(inventory), False)
        add(rows, "coverage_shadow_route_remain_unavailable", "inventory rows", len(inventory), False)

    context_cols = ["recent_form_reliability", "game_environment_reliability", "defense_fit_reliability", "context_data_quality"]
    master_context_ok = not master.empty and all(col in master.columns for col in context_cols)
    add(rows, "player_week_signal_master_includes_sourced_context_columns", context_cols, [col for col in context_cols if col in master.columns], master_context_ok)

    boards_ok = True
    for board in ["slate_signal_board", "by_game_signal_board", "receiving_signal_board", "rushing_signal_board", "passing_signal_board", "blocked_review_board"]:
        frame = read_csv(f"signal_boards/{board}.csv")
        board_ok = frame.empty or "overall_signal_score" in frame.columns
        boards_ok = boards_ok and board_ok
        add(rows, f"{board}_derived_from_master_shape", "overall_signal_score column", "overall_signal_score" in frame.columns, board_ok)

    code_paths = [
        project_path("src/export/export_signal_context_features.py"),
        project_path("src/export/export_player_week_signal_master.py"),
        project_path("src/export/export_signal_board_views.py"),
    ]
    combined_code = "\n".join(path.read_text(encoding="utf-8", errors="replace").lower() for path in code_paths if path.exists())
    forbidden = [term for term in ["clv", "closing line value", "bet_recommendation", "stake_size", "wager"] if term in combined_code]
    add(rows, "no_odds_clv_or_betting_logic_added_to_context_code", "no forbidden betting terms", forbidden, not forbidden)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(rows, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(rows, "leakage_status_pass", "PASS", leakage, leakage == "PASS")
    add(rows, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")

    result = pd.DataFrame(rows)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_signal_context_features_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_signal_context_features_validation.md").write_text(
        f"""# Signal Context Features Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Target season/week: `{target_season} Week {target_week}`

History end season: `{history_end}`

Context rows: `{len(context)}`

Master rows: `{len(master)}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live betting output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Next required action: Keep context values as research signals until live data gates are verified.
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_signal_context_features()
    print(f"Signal context features validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
