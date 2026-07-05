from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from src.common import load_config, output_path


BLOCKING_STATUSES = {"NEEDS DATA", "BLOCKED", "CHECK", "NOT READY"}
EXPECTED_GATE_FILES = [
    "google_sheets/schedule_gate_import.csv",
    "google_sheets/roster_gate_import_template.csv",
    "google_sheets/role_gate_import_template.csv",
    "google_sheets/injury_gate_import_template.csv",
    "google_sheets/market_odds_gate_import_template.csv",
    "google_sheets/live_readiness_export.csv",
    "google_sheets/forward_projection_blockers.csv",
]
EXPECTED_PACK_FILES = {
    "schedule_gate_import.csv",
    "roster_gate_import_template.csv",
    "role_gate_import_template.csv",
    "injury_gate_import_template.csv",
    "market_odds_gate_import_template.csv",
    "live_readiness_export.csv",
    "forward_projection_blockers.csv",
    "google_sheets_receptions_historical_test.csv",
    "import_manifest.csv",
    "IMPORT_INSTRUCTIONS.md",
}


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _gate_status(readiness: pd.DataFrame, gate: str) -> str:
    if readiness.empty:
        return "MISSING"
    rows = readiness[readiness["Gate"] == gate]
    return "MISSING" if rows.empty else str(rows["Status"].iloc[0])


def _add_check(
    rows: list[dict[str, str]],
    check_name: str,
    expected: str,
    actual: object,
    passed: bool,
    severity: str = "HIGH",
    notes: str = "",
) -> None:
    rows.append(
        {
            "check_name": check_name,
            "expected": expected,
            "actual": str(actual),
            "status": "PASS" if passed else "FAIL",
            "severity": "INFO" if passed else severity,
            "notes": notes,
        }
    )


def validate_safety() -> tuple[pd.DataFrame, dict[str, object]]:
    cfg = load_config()
    data_cfg = cfg["data"]
    projection_mode = str(data_cfg.get("projection_mode", ""))
    target_season = int(data_cfg.get("target_season", data_cfg.get("projection_season", 0)))
    target_week = int(data_cfg.get("target_week", data_cfg.get("projection_week", 0)))
    history_start = int(data_cfg.get("history_start_season", 0))
    history_end = int(data_cfg.get("history_end_season", 0))

    audit = _read_csv(output_path("history_window_audit.csv", cfg))
    readiness = _read_csv(output_path("google_sheets/live_readiness_export.csv", cfg))
    blockers = _read_csv(output_path("google_sheets/forward_projection_blockers.csv", cfg))
    dashboard = _read_csv(output_path("google_sheets_receptions_historical_test.csv", cfg))
    manifest_path = output_path("google_sheets/import_manifest.csv", cfg)
    zip_path = output_path("google_sheets/latest_import_pack.zip", cfg)
    errors_path = output_path("run_reports/latest_receptions_pipeline_errors.csv", cfg)
    gate_input_status_path = output_path("gate_inputs_normalized/gate_input_status.csv", cfg)
    gate_input_status = _read_csv(gate_input_status_path)
    identity_report_path = output_path("identity/gate_identity_match_report.csv", cfg)
    identity_report = _read_csv(identity_report_path)
    unmatched_identity = _read_csv(output_path("identity/unmatched_gate_rows.csv", cfg))
    market_edges = _read_csv(output_path("market_edges/receptions_market_edges.csv", cfg))
    line_ladder_path = output_path("market_edges/receptions_line_ladder.csv", cfg)
    line_ladder = _read_csv(line_ladder_path)
    receiving_yards_board_path = output_path("google_sheets_receiving_yards_historical_test.csv", cfg)
    receiving_yards_board = _read_csv(receiving_yards_board_path)
    receiving_yards_ladder_path = output_path("market_edges/receiving_yards_line_ladder.csv", cfg)
    receiving_yards_ladder = _read_csv(receiving_yards_ladder_path)
    rushing_yards_board_path = output_path("google_sheets_rushing_yards_historical_test.csv", cfg)
    rushing_yards_board = _read_csv(rushing_yards_board_path)
    rushing_yards_ladder_path = output_path("market_edges/rushing_yards_line_ladder.csv", cfg)
    rushing_yards_ladder = _read_csv(rushing_yards_ladder_path)
    carries_board_path = output_path("google_sheets_carries_historical_test.csv", cfg)
    carries_board = _read_csv(carries_board_path)
    carries_ladder_path = output_path("market_edges/carries_line_ladder.csv", cfg)
    carries_ladder = _read_csv(carries_ladder_path)
    pass_attempts_board_path = output_path("google_sheets_pass_attempts_historical_test.csv", cfg)
    pass_attempts_board = _read_csv(pass_attempts_board_path)
    pass_attempts_ladder_path = output_path("market_edges/pass_attempts_line_ladder.csv", cfg)
    pass_attempts_ladder = _read_csv(pass_attempts_ladder_path)
    completions_board_path=output_path("google_sheets_completions_historical_test.csv",cfg);completions_board=_read_csv(completions_board_path)
    completions_ladder_path=output_path("market_edges/completions_line_ladder.csv",cfg);completions_ladder=_read_csv(completions_ladder_path)

    leakage_status = "MISSING" if audit.empty else str(audit["leakage_status"].iloc[0])
    leakage_exists = True if audit.empty else bool(audit["leakage_exists"].iloc[0])
    final_readiness = _gate_status(readiness, "Final Betting Use")
    blocked_gates = blockers["Blocker"].dropna().astype(str).tolist() if "Blocker" in blockers.columns else []
    usage_statuses = sorted(dashboard["usage_status"].dropna().astype(str).unique()) if "usage_status" in dashboard.columns else []
    live_betting_output_created = bool(any(status == "MODEL REVIEW" for status in usage_statuses) and final_readiness == "GO")

    rows: list[dict[str, str]] = []
    _add_check(rows, "projection_mode", "historical_test or forward_projection", projection_mode, projection_mode in {"historical_test", "forward_projection"})
    _add_check(rows, "target_season", "configured integer", target_season, target_season > 0)
    _add_check(rows, "target_week", "configured integer", target_week, target_week > 0)
    _add_check(rows, "history_start_season", "configured integer", history_start, history_start > 0)
    _add_check(rows, "history_end_season", ">= history_start_season", history_end, history_end >= history_start)
    _add_check(rows, "leakage_status", "PASS", leakage_status, leakage_status == "PASS", notes="Leakage audit must pass.")
    _add_check(rows, "leakage_exists", "False", leakage_exists, leakage_exists is False, notes="Future/target-week leakage must fail validation.")

    if projection_mode == "historical_test":
        _add_check(rows, "historical_test_final_readiness", "NO-GO", final_readiness, final_readiness == "NO-GO")
        all_historical = bool(usage_statuses) and set(usage_statuses) == {"HISTORICAL TEST ONLY"}
        _add_check(rows, "historical_test_usage_status", "all rows HISTORICAL TEST ONLY", usage_statuses, all_historical)

    gate_statuses = {
        "schedule_gate_status": _gate_status(readiness, "Schedule Gate"),
        "roster_gate_status": _gate_status(readiness, "Roster Gate"),
        "role_gate_status": _gate_status(readiness, "Role Gate"),
        "injury_gate_status": _gate_status(readiness, "Injury Gate"),
        "market_odds_gate_status": _gate_status(readiness, "Market Odds Gate"),
    }
    any_blocking_gate = any(status in BLOCKING_STATUSES for status in gate_statuses.values())
    _add_check(
        rows,
        "blocking_gates_do_not_go_live",
        "Final readiness not GO when a required gate blocks",
        f"final={final_readiness}; gates={gate_statuses}",
        (not any_blocking_gate) or final_readiness != "GO",
    )
    for name, status in gate_statuses.items():
        if name in {"roster_gate_status", "role_gate_status", "injury_gate_status", "market_odds_gate_status"}:
            _add_check(
                rows,
                f"{name}_not_silently_ready",
                "missing gate data is not READY",
                status,
                status != "READY",
                notes="Missing roster/role/injury/odds data must not be silently treated as ready.",
            )

    _add_check(
        rows,
        "no_live_betting_output_when_no_go",
        "False when final readiness is NO-GO",
        live_betting_output_created,
        final_readiness != "NO-GO" or live_betting_output_created is False,
    )
    _add_check(rows, "usage_status_column_exists", "usage_status present", "usage_status" in dashboard.columns, "usage_status" in dashboard.columns)
    if not market_edges.empty:
        edge_live_created = bool(market_edges["usage_status"].astype(str).eq("MODEL REVIEW").any() and final_readiness == "GO")
        historical_edges_labeled = (
            projection_mode != "historical_test"
            or market_edges["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        )
        pass_invalid_odds = market_edges[
            market_edges["price_grade"].astype(str).eq("PASS")
            & (
                market_edges["implied_over_probability"].isna()
                | market_edges["implied_under_probability"].isna()
            )
        ]
        probabilities_valid = (
            pd.to_numeric(market_edges["model_over_probability"], errors="coerce").between(0, 1).all()
            and pd.to_numeric(market_edges["model_under_probability"], errors="coerce").between(0, 1).all()
        )
        edge_without_implied = market_edges[
            (
                market_edges["over_edge"].notna()
                & market_edges["implied_over_probability"].isna()
            )
            | (
                market_edges["under_edge"].notna()
                & market_edges["implied_under_probability"].isna()
            )
        ]
        _add_check(
            rows,
            "no_live_market_edges_when_no_go",
            "False when final readiness is NO-GO",
            edge_live_created,
            final_readiness != "NO-GO" or edge_live_created is False,
        )
        _add_check(
            rows,
            "historical_market_edges_labeled",
            "all HISTORICAL TEST ONLY in historical_test",
            historical_edges_labeled,
            historical_edges_labeled,
        )
        _add_check(rows, "pass_price_requires_valid_odds", "no PASS with invalid odds", len(pass_invalid_odds), pass_invalid_odds.empty)
        _add_check(rows, "model_probabilities_between_zero_one", "all probabilities 0..1", probabilities_valid, probabilities_valid)
        _add_check(rows, "edge_requires_implied_probability", "no edge without implied probability", len(edge_without_implied), edge_without_implied.empty)
    else:
        _add_check(rows, "market_edges_empty_when_no_odds", "empty allowed with no odds", len(market_edges), True)
    _add_check(rows, "line_ladder_exists", "file exists", line_ladder_path.exists(), line_ladder_path.exists())
    if not line_ladder.empty:
        ladder_probabilities_valid = (
            pd.to_numeric(line_ladder["model_over_probability"], errors="coerce").between(0, 1).all()
            and pd.to_numeric(line_ladder["model_under_probability"], errors="coerce").between(0, 1).all()
        )
        ladder_historical_labeled = (
            projection_mode != "historical_test"
            or line_ladder["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        )
        forbidden_cols = {"edge", "best_edge", "price_grade", "bet_recommendation", "recommendation"}
        forbidden_present = sorted(forbidden_cols.intersection(set(line_ladder.columns)))
        _add_check(rows, "line_ladder_probabilities_between_zero_one", "all probabilities 0..1", ladder_probabilities_valid, ladder_probabilities_valid)
        _add_check(rows, "line_ladder_historical_rows_labeled", "all HISTORICAL TEST ONLY in historical_test", ladder_historical_labeled, ladder_historical_labeled)
        _add_check(rows, "line_ladder_has_no_edge_columns", "no edge/recommendation columns", forbidden_present, not forbidden_present)
        _add_check(
            rows,
            "line_ladder_not_live_betting_when_no_go",
            "no live betting output from ladder",
            final_readiness,
            final_readiness != "NO-GO" or line_ladder["usage_status"].astype(str).ne("MODEL REVIEW").all(),
        )
    _add_check(
        rows,
        "receiving_yards_board_exists",
        "file exists",
        receiving_yards_board_path.exists(),
        receiving_yards_board_path.exists(),
    )
    if not receiving_yards_board.empty:
        receiving_yards_historical = (
            projection_mode != "historical_test"
            or receiving_yards_board["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        )
        receiving_yards_live_created = bool(
            receiving_yards_board["usage_status"].astype(str).eq("MODEL REVIEW").any() and final_readiness == "GO"
        )
        _add_check(
            rows,
            "receiving_yards_historical_rows_labeled",
            "all HISTORICAL TEST ONLY in historical_test",
            receiving_yards_historical,
            receiving_yards_historical,
        )
        _add_check(
            rows,
            "receiving_yards_not_live_betting_when_no_go",
            "no live betting output from receiving yards",
            receiving_yards_live_created,
            final_readiness != "NO-GO" or receiving_yards_live_created is False,
        )
    _add_check(
        rows,
        "receiving_yards_ladder_exists",
        "file exists",
        receiving_yards_ladder_path.exists(),
        receiving_yards_ladder_path.exists(),
    )
    if not receiving_yards_ladder.empty:
        receiving_ladder_probs_valid = (
            pd.to_numeric(receiving_yards_ladder["model_over_probability"], errors="coerce").between(0, 1).all()
            and pd.to_numeric(receiving_yards_ladder["model_under_probability"], errors="coerce").between(0, 1).all()
        )
        receiving_ladder_historical = (
            projection_mode != "historical_test"
            or receiving_yards_ladder["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        )
        _add_check(
            rows,
            "receiving_yards_ladder_probabilities_between_zero_one",
            "all probabilities 0..1",
            receiving_ladder_probs_valid,
            receiving_ladder_probs_valid,
        )
        _add_check(
            rows,
            "receiving_yards_ladder_historical_rows_labeled",
            "all HISTORICAL TEST ONLY in historical_test",
            receiving_ladder_historical,
            receiving_ladder_historical,
        )
    _add_check(rows, "rushing_yards_board_exists", "file exists", rushing_yards_board_path.exists(), rushing_yards_board_path.exists())
    if not rushing_yards_board.empty:
        rushing_historical = projection_mode != "historical_test" or rushing_yards_board["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        rushing_live = bool(rushing_yards_board["usage_status"].astype(str).eq("MODEL REVIEW").any() and final_readiness == "GO")
        _add_check(rows, "rushing_yards_historical_rows_labeled", "all HISTORICAL TEST ONLY in historical_test", rushing_historical, rushing_historical)
        _add_check(rows, "rushing_yards_not_live_betting_when_no_go", "no live betting output from rushing yards", rushing_live,
                   final_readiness != "NO-GO" or rushing_live is False)
    _add_check(rows, "rushing_yards_ladder_exists", "file exists", rushing_yards_ladder_path.exists(), rushing_yards_ladder_path.exists())
    if not rushing_yards_ladder.empty:
        rushing_probs = (pd.to_numeric(rushing_yards_ladder["model_over_probability"], errors="coerce").between(0, 1).all()
                         and pd.to_numeric(rushing_yards_ladder["model_under_probability"], errors="coerce").between(0, 1).all())
        rushing_labeled = projection_mode != "historical_test" or rushing_yards_ladder["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        _add_check(rows, "rushing_yards_ladder_probabilities_between_zero_one", "all probabilities 0..1", rushing_probs, rushing_probs)
        _add_check(rows, "rushing_yards_ladder_historical_rows_labeled", "all HISTORICAL TEST ONLY in historical_test", rushing_labeled, rushing_labeled)
    _add_check(rows, "carries_board_exists", "file exists", carries_board_path.exists(), carries_board_path.exists())
    if not carries_board.empty:
        carries_historical = projection_mode != "historical_test" or carries_board["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        carries_live = bool(carries_board["usage_status"].astype(str).eq("MODEL REVIEW").any() and final_readiness == "GO")
        _add_check(rows, "carries_historical_rows_labeled", "all HISTORICAL TEST ONLY in historical_test", carries_historical, carries_historical)
        _add_check(rows, "carries_not_live_betting_when_no_go", "no live betting output from carries", carries_live,
                   final_readiness != "NO-GO" or carries_live is False)
    _add_check(rows, "carries_ladder_exists", "file exists", carries_ladder_path.exists(), carries_ladder_path.exists())
    if not carries_ladder.empty:
        carries_probs = (pd.to_numeric(carries_ladder["model_over_probability"], errors="coerce").between(0, 1).all()
                         and pd.to_numeric(carries_ladder["model_under_probability"], errors="coerce").between(0, 1).all())
        carries_labeled = projection_mode != "historical_test" or carries_ladder["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        _add_check(rows, "carries_ladder_probabilities_between_zero_one", "all probabilities 0..1", carries_probs, carries_probs)
        _add_check(rows, "carries_ladder_historical_rows_labeled", "all HISTORICAL TEST ONLY in historical_test", carries_labeled, carries_labeled)
    _add_check(rows, "pass_attempts_board_exists", "file exists", pass_attempts_board_path.exists(), pass_attempts_board_path.exists())
    if not pass_attempts_board.empty:
        pass_historical = projection_mode != "historical_test" or pass_attempts_board["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        pass_live = bool(pass_attempts_board["usage_status"].astype(str).eq("MODEL REVIEW").any() and final_readiness == "GO")
        _add_check(rows, "pass_attempts_historical_rows_labeled", "all HISTORICAL TEST ONLY in historical_test", pass_historical, pass_historical)
        _add_check(rows, "pass_attempts_not_live_betting_when_no_go", "no live betting output from pass attempts", pass_live, final_readiness != "NO-GO" or pass_live is False)
    _add_check(rows, "pass_attempts_ladder_exists", "file exists", pass_attempts_ladder_path.exists(), pass_attempts_ladder_path.exists())
    if not pass_attempts_ladder.empty:
        pass_probs = (pd.to_numeric(pass_attempts_ladder["model_over_probability"],errors="coerce").between(0,1).all() and pd.to_numeric(pass_attempts_ladder["model_under_probability"],errors="coerce").between(0,1).all())
        pass_labeled = projection_mode != "historical_test" or pass_attempts_ladder["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all()
        _add_check(rows, "pass_attempts_ladder_probabilities_between_zero_one", "all probabilities 0..1", pass_probs, pass_probs)
        _add_check(rows, "pass_attempts_ladder_historical_rows_labeled", "all HISTORICAL TEST ONLY in historical_test", pass_labeled, pass_labeled)
    _add_check(rows,"completions_board_exists","file exists",completions_board_path.exists(),completions_board_path.exists())
    if not completions_board.empty:
        labeled=projection_mode!="historical_test" or completions_board["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all();live=bool(completions_board["usage_status"].astype(str).eq("MODEL REVIEW").any() and final_readiness=="GO")
        _add_check(rows,"completions_historical_rows_labeled","all HISTORICAL TEST ONLY",labeled,labeled);_add_check(rows,"completions_not_live_betting_when_no_go","no live output",live,final_readiness!="NO-GO" or live is False)
    _add_check(rows,"completions_ladder_exists","file exists",completions_ladder_path.exists(),completions_ladder_path.exists())
    if not completions_ladder.empty:
        probs=pd.to_numeric(completions_ladder["model_over_probability"],errors="coerce").between(0,1).all() and pd.to_numeric(completions_ladder["model_under_probability"],errors="coerce").between(0,1).all();labeled=projection_mode!="historical_test" or completions_ladder["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").all();_add_check(rows,"completions_ladder_probabilities_between_zero_one","all probabilities 0..1",probs,probs);_add_check(rows,"completions_ladder_historical_rows_labeled","all HISTORICAL TEST ONLY",labeled,labeled)
    for file_name in EXPECTED_GATE_FILES:
        path = output_path(file_name, cfg)
        _add_check(rows, f"gate_file_exists:{file_name}", "file exists", path.exists(), path.exists())
    _add_check(rows, "gate_input_status_exists", "file exists", gate_input_status_path.exists(), gate_input_status_path.exists())
    if not gate_input_status.empty:
        templates_ignored = gate_input_status["is_real_data"].astype(str).str.upper().eq("FALSE").all()
        missing_not_ready = gate_input_status.loc[
            gate_input_status["is_real_data"].astype(str).str.upper().eq("FALSE"),
            "status",
        ].astype(str).ne("READY").all()
        _add_check(
            rows,
            "templates_do_not_count_as_real_data",
            "all template-only gates is_real_data=False",
            templates_ignored,
            templates_ignored,
        )
        _add_check(
            rows,
            "missing_real_gate_inputs_not_ready",
            "template-only gates are not READY",
            missing_not_ready,
            missing_not_ready,
            notes="Real gate inputs must pass validation before READY.",
        )
        for gate in ["roster", "role", "injury", "market_odds"]:
            gate_row = gate_input_status[gate_input_status["gate"] == gate]
            if not gate_row.empty and str(gate_row["is_real_data"].iloc[0]).upper() == "FALSE":
                _add_check(
                    rows,
                    f"{gate}_template_ignored_as_real_input",
                    "NEEDS DATA",
                    gate_row["status"].iloc[0],
                    str(gate_row["status"].iloc[0]) == "NEEDS DATA",
                )
    _add_check(rows, "identity_report_exists", "file exists", identity_report_path.exists(), identity_report_path.exists())
    if not identity_report.empty:
        identity_issues = (
            identity_report["unmatched_rows"].fillna(0).astype(int).sum()
            + identity_report["duplicate_name_rows"].fillna(0).astype(int).sum()
            + identity_report["team_verify_rows"].fillna(0).astype(int).sum()
        )
        ready_with_issues = (
            identity_report["status"].astype(str).eq("READY").any()
            and identity_issues > 0
        )
        team_verify_with_go = (
            identity_report["team_verify_rows"].fillna(0).astype(int).sum() > 0
            and final_readiness == "GO"
        )
        _add_check(
            rows,
            "identity_issues_prevent_ready",
            "no READY gate with unmatched/duplicate/team verify rows",
            ready_with_issues,
            ready_with_issues == False,
        )
        _add_check(
            rows,
            "team_verify_prevents_go",
            "Final readiness not GO with TEAM_VERIFY rows",
            team_verify_with_go,
            team_verify_with_go == False,
        )
    _add_check(
        rows,
        "unmatched_identity_rows_file_exists",
        "file exists",
        output_path("identity/unmatched_gate_rows.csv", cfg).exists(),
        output_path("identity/unmatched_gate_rows.csv", cfg).exists(),
    )
    _add_check(rows, "import_manifest_exists", "file exists", manifest_path.exists(), manifest_path.exists())
    _add_check(rows, "latest_import_pack_exists", "file exists", zip_path.exists(), zip_path.exists())
    if zip_path.exists():
        with ZipFile(zip_path) as archive:
            zip_names = set(archive.namelist())
        missing = sorted(EXPECTED_PACK_FILES.difference(zip_names))
        _add_check(rows, "import_pack_contents", "all expected CSVs and instructions", missing, not missing)
    else:
        _add_check(rows, "import_pack_contents", "all expected CSVs and instructions", "zip missing", False)

    errors = _read_csv(errors_path)
    errors_ok = errors_path.exists() and not errors.empty and {"error_type", "message"}.issubset(errors.columns)
    _add_check(rows, "pipeline_errors_csv_exists", "errors CSV exists with row", errors_path.exists(), errors_path.exists())
    _add_check(rows, "pipeline_errors_csv_has_content", "error_type/message row exists", errors_ok, errors_ok)

    validation = pd.DataFrame(rows)
    context = {
        "projection_mode": projection_mode,
        "target_season": target_season,
        "target_week": target_week,
        "history_start_season": history_start,
        "history_end_season": history_end,
        "leakage_status": leakage_status,
        "leakage_exists": leakage_exists,
        "final_readiness": final_readiness,
        "blocked_gates": blocked_gates,
        "live_betting_output_created": live_betting_output_created,
        "usage_statuses": usage_statuses,
    }
    return validation, context


def write_reports(validation: pd.DataFrame, context: dict[str, object]) -> None:
    cfg = load_config()
    report_dir = output_path("run_reports/.keep", cfg).parent
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = report_dir / "latest_receptions_safety_validation.csv"
    md_path = report_dir / "latest_receptions_safety_validation.md"
    validation.to_csv(csv_path, index=False)

    failed = validation[validation["status"] == "FAIL"]
    warnings = validation[(validation["status"] != "FAIL") & (validation["severity"].isin(["MEDIUM", "HIGH"]))]
    overall = "PASS" if failed.empty else "FAIL"
    failed_text = "None" if failed.empty else "\n".join(
        f"- {row.check_name}: expected {row.expected}, actual {row.actual}. {row.notes}"
        for row in failed.itertuples(index=False)
    )
    warnings_text = "None" if warnings.empty else "\n".join(
        f"- {row.check_name}: {row.status}. {row.notes}"
        for row in warnings.itertuples(index=False)
    )
    next_action = (
        "Resolve failed safety checks before importing or using outputs."
        if overall == "FAIL"
        else "Safe for historical-test review only; live use still requires gates to reach GO."
    )
    text = f"""# Receptions Safety Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall safety status: `{overall}`

Passed checks: `{len(validation) - len(failed)}`

Failed checks: `{len(failed)}`

Warnings: `{len(warnings)}`

Current projection mode: `{context['projection_mode']}`

Current live readiness: `{context['final_readiness']}`

Current blockers: `{', '.join(context['blocked_gates']) if context['blocked_gates'] else 'None'}`

Leakage status: `{context['leakage_status']}`

Leakage exists: `{context['leakage_exists']}`

Live betting output status: `{'CREATED' if context['live_betting_output_created'] else 'NOT CREATED'}`

Next required action: {next_action}

## Failed Checks

{failed_text}

## Warnings

{warnings_text}
"""
    md_path.write_text(text, encoding="utf-8")


def main() -> None:
    validation, context = validate_safety()
    write_reports(validation, context)
    failed = validation[validation["status"] == "FAIL"]
    overall = "PASS" if failed.empty else "FAIL"
    print(f"Overall safety status: {overall}")
    print(f"Final readiness: {context['final_readiness']}")
    print(f"Leakage status: {context['leakage_status']}")
    print(f"Live betting output created: {context['live_betting_output_created']}")
    print(f"Failed checks: {len(failed)}")
    if not failed.empty:
        print(failed[["check_name", "expected", "actual", "notes"]].to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
