from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.common import load_config, output_path


PIPELINE_MODULES = [
    "src.markets.market_registry",
    "src.features.build_receptions_feature_table",
    "src.models.receptions_model",
    "src.backtest.backtest_receptions",
    "src.backtest.calibrate_receptions",
    "src.export.export_receptions_projection_csv",
    "src.features.build_receiving_yards_feature_table",
    "src.backtest.backtest_receiving_yards",
    "src.backtest.calibrate_receiving_yards",
    "src.models.receiving_yards_model",
    "src.export.export_receiving_yards_projection_csv",
    "src.export.export_google_sheet_receiving_yards",
    "src.export.export_receiving_yards_line_ladder",
    "src.features.build_rushing_yards_feature_table",
    "src.backtest.backtest_rushing_yards",
    "src.backtest.calibrate_rushing_yards",
    "src.models.rushing_yards_model",
    "src.export.export_rushing_yards_projection_csv",
    "src.export.export_google_sheet_rushing_yards",
    "src.export.export_rushing_yards_line_ladder",
    "src.features.build_carries_feature_table",
    "src.backtest.backtest_carries",
    "src.backtest.calibrate_carries",
    "src.models.carries_model",
    "src.export.export_carries_projection_csv",
    "src.export.export_google_sheet_carries",
    "src.export.export_carries_line_ladder",
    "src.features.build_pass_attempts_feature_table",
    "src.backtest.backtest_pass_attempts",
    "src.backtest.calibrate_pass_attempts",
    "src.models.pass_attempts_model",
    "src.export.export_pass_attempts_projection_csv",
    "src.export.export_google_sheet_pass_attempts",
    "src.export.export_pass_attempts_line_ladder",
    "src.features.build_completions_feature_table",
    "src.backtest.backtest_completions",
    "src.backtest.calibrate_completions",
    "src.models.completions_model",
    "src.export.export_completions_projection_csv",
    "src.export.export_google_sheet_completions",
    "src.export.export_completions_line_ladder",
    "src.features.build_passing_yards_feature_table",
    "src.backtest.backtest_passing_yards",
    "src.backtest.calibrate_passing_yards",
    "src.models.passing_yards_model",
    "src.export.export_passing_yards_projection_csv",
    "src.export.export_google_sheet_passing_yards",
    "src.export.export_passing_yards_line_ladder",
    "src.load.load_gate_inputs",
    "src.load.build_identity_crosswalk",
    "src.load.build_current_roster_map",
    "src.load.validate_current_roster_map",
    "src.load.build_current_role_map",
    "src.load.validate_current_role_map",
    "src.load.build_current_injury_map",
    "src.load.validate_current_injury_map",
    "src.load.build_market_odds_map",
    "src.load.validate_market_odds_map",
    "src.load.validate_gate_identity_matches",
    "src.export.export_sheet_gates",
    "src.models.receptions_probability",
    "src.export.export_receptions_market_edges",
    "src.export.export_receptions_line_ladder",
    "src.export.export_edge_preview_board",
    "src.export.validate_edge_preview_board",
    "src.export.export_live_data_intake_status",
    "src.export.validate_live_data_intake_status",
    "src.export.export_signal_data_inventory",
    "src.export.export_player_week_signal_master",
    "src.export.export_signal_board_views",
    "src.export.validate_player_week_signal_master",
    "src.export.build_google_sheets_import_pack",
]

REQUIRED_GATE_BLOCK_STATUSES = {"NEEDS DATA", "BLOCKED", "CHECK", "NOT READY"}


def run_module(module: str) -> tuple[bool, str, str, int]:
    command = [sys.executable, "-m", module]
    result = subprocess.run(command, capture_output=True, text=True)
    for _ in range(2):
        transient_write_error = "OSError: [Errno 22] Invalid argument" in result.stderr
        if result.returncode == 0 or not transient_write_error:
            break
        time.sleep(1)
        result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr, result.returncode


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _scalar(df: pd.DataFrame, column: str, default: Any = "") -> Any:
    if df.empty or column not in df.columns:
        return default
    return df[column].iloc[0]


def _gate_status(readiness: pd.DataFrame, gate: str) -> str:
    if readiness.empty:
        return "UNKNOWN"
    rows = readiness[readiness["Gate"] == gate]
    if rows.empty:
        return "UNKNOWN"
    return str(rows["Status"].iloc[0])


def _collect_status(error_rows: list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    cfg = load_config()
    data_cfg = cfg["data"]
    audit = _read_csv(output_path("history_window_audit.csv", cfg))
    readiness = _read_csv(output_path("google_sheets/live_readiness_export.csv", cfg))
    blockers = _read_csv(output_path("google_sheets/forward_projection_blockers.csv", cfg))
    backtest = _read_csv(output_path("receptions_backtest_summary_candidates.csv", cfg))
    calibration = _read_csv(output_path("receptions_calibration_multipliers.csv", cfg))
    dashboard = _read_csv(output_path("google_sheets_receptions_historical_test.csv", cfg))

    projection_mode = str(data_cfg.get("projection_mode", ""))
    target_season = int(data_cfg.get("target_season", data_cfg.get("projection_season", 0)))
    target_week = int(data_cfg.get("target_week", data_cfg.get("projection_week", 0)))
    history_start = int(data_cfg.get("history_start_season", 0))
    history_end = int(data_cfg.get("history_end_season", 0))
    leakage_status = str(_scalar(audit, "leakage_status", "UNKNOWN"))
    leakage_exists = bool(_scalar(audit, "leakage_exists", True))
    final_readiness = _gate_status(readiness, "Final Betting Use")
    blocked_gates = blockers["Blocker"].dropna().astype(str).tolist() if "Blocker" in blockers.columns else []
    historical_test_rows = int(len(dashboard))
    import_pack_path = str(output_path("google_sheets/latest_import_pack.zip", cfg))

    live_betting_output_created = False
    if not dashboard.empty and "usage_status" in dashboard.columns:
        live_betting_output_created = bool(
            dashboard["usage_status"]
            .astype(str)
            .str.contains("MODEL REVIEW", regex=False)
            .any()
            and final_readiness == "GO"
        )

    statuses = {
        "projection_mode": projection_mode,
        "target_season": target_season,
        "target_week": target_week,
        "history_start_season": history_start,
        "history_end_season": history_end,
        "leakage_status": leakage_status,
        "leakage_exists": leakage_exists,
        "final_live_readiness": final_readiness,
        "blocked_gates": ", ".join(blocked_gates) if blocked_gates else "None",
        "live_betting_output_created": live_betting_output_created,
        "historical_test_rows": historical_test_rows,
        "schedule_gate_status": _gate_status(readiness, "Schedule Gate"),
        "roster_gate_status": _gate_status(readiness, "Roster Gate"),
        "role_gate_status": _gate_status(readiness, "Role Gate"),
        "injury_gate_status": _gate_status(readiness, "Injury Gate"),
        "market_odds_gate_status": _gate_status(readiness, "Market Odds Gate"),
        "import_pack_path": import_pack_path,
    }
    rows = []
    for name, value in statuses.items():
        status = "PASS"
        severity = "INFO"
        notes = ""
        if name == "projection_mode" and value == "historical_test":
            status = "HISTORICAL TEST ONLY"
            severity = "HIGH"
            notes = "Not live betting ready."
        elif name == "leakage_status" and value != "PASS":
            status = str(value)
            severity = "HIGH"
            notes = "Leakage audit must pass."
        elif name == "leakage_exists" and value:
            status = "FAIL"
            severity = "HIGH"
            notes = "Feature history contains target/future data."
        elif name.endswith("_gate_status") and str(value) in REQUIRED_GATE_BLOCK_STATUSES:
            status = str(value)
            severity = "HIGH"
            notes = "Required gate blocks live readiness."
        elif name == "final_live_readiness" and value != "GO":
            status = "NO-GO"
            severity = "HIGH"
            notes = "No live betting output should be used."
        elif name == "live_betting_output_created" and value:
            status = "CHECK"
            severity = "HIGH"
            notes = "Live betting output exists; verify readiness is GO."
        rows.append(
            {
                "check_name": name,
                "value": value,
                "status": status,
                "severity": severity,
                "notes": notes,
            }
        )
    context = {
        "audit": audit,
        "readiness": readiness,
        "blockers": blockers,
        "backtest": backtest,
        "calibration": calibration,
        "statuses": statuses,
        "errors": error_rows,
    }
    return pd.DataFrame(rows), context


def _write_errors(error_rows: list[dict[str, Any]], report_dir: Path) -> None:
    if not error_rows:
        error_rows = [{"error_type": "NONE", "message": "No errors"}]
    pd.DataFrame(error_rows).to_csv(report_dir / "latest_receptions_pipeline_errors.csv", index=False)


def _write_report(context: dict[str, Any], report_dir: Path) -> None:
    statuses = context["statuses"]
    backtest = context["backtest"]
    calibration = context["calibration"]
    blockers = context["blockers"]
    errors = context["errors"]
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    final = statuses["final_live_readiness"]
    live_status = "CREATED" if statuses["live_betting_output_created"] else "NOT CREATED"
    safety_label = "HISTORICAL TEST ONLY" if statuses["projection_mode"] == "historical_test" else statuses["projection_mode"]

    metric_text = "Backtest metrics unavailable."
    if not backtest.empty:
        b = backtest.iloc[0]
        metric_text = (
            f"Rows scored: {b.get('rows_scored')}; raw MAE/RMSE/bias: "
            f"{b.get('raw_mae'):.6f}/{b.get('raw_rmse'):.6f}/{b.get('raw_bias'):.6f}; "
            f"calibrated MAE/RMSE/bias: "
            f"{b.get('calibrated_mae'):.6f}/{b.get('calibrated_rmse'):.6f}/{b.get('calibrated_bias'):.6f}"
        )
    calibration_status = "available" if not calibration.empty else "missing"
    blocked = statuses["blocked_gates"]
    next_action = (
        "Resolve roster, role, injury, and odds gates; switch to forward_projection only after live gates are ready."
        if final != "GO"
        else "Import the pack and perform final human review before use."
    )
    gate_lines = [
        f"- Schedule Gate: {statuses['schedule_gate_status']}",
        f"- Roster Gate: {statuses['roster_gate_status']}",
        f"- Role Gate: {statuses['role_gate_status']}",
        f"- Injury Gate: {statuses['injury_gate_status']}",
        f"- Market Odds Gate: {statuses['market_odds_gate_status']}",
    ]
    error_text = "No errors" if not errors else "\n".join(f"- {row['error_type']}: {row['message']}" for row in errors)
    text = f"""# Receptions Pipeline Report

Run timestamp: `{timestamp}`

## Projection Mode

`{safety_label}`

## Target

Season/week: `{statuses['target_season']} Week {statuses['target_week']}`

History window: `{statuses['history_start_season']} to {statuses['history_end_season']}`

## Leakage Status

Leakage status: `{statuses['leakage_status']}`

Leakage exists: `{statuses['leakage_exists']}`

## Backtest Metrics

{metric_text}

## Calibration Status

Calibration status: `{calibration_status}`

## Gate Statuses

{chr(10).join(gate_lines)}

## Blocked Gates

`{blocked}`

## Import Pack

`{statuses['import_pack_path']}`

## Live Readiness Result

`{final}`

## Live Betting Output Status

`{live_status}`

## Next Required Action

{next_action}

## Errors

{error_text}
"""
    (report_dir / "latest_receptions_pipeline_report.md").write_text(text, encoding="utf-8")


def main() -> None:
    cfg = load_config()
    report_dir = output_path("run_reports/.keep", cfg).parent
    report_dir.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, Any]] = []

    for module in PIPELINE_MODULES:
        ok, stdout, stderr, code = run_module(module)
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        if not ok:
            errors.append(
                {
                    "error_type": "COMMAND_FAILED",
                    "message": f"python -m {module} failed with exit code {code}",
                    "module": module,
                    "stdout": stdout,
                    "stderr": stderr,
                }
            )
            break

    status_df, context = _collect_status(errors)
    status_df.to_csv(report_dir / "latest_receptions_pipeline_status.csv", index=False)
    _write_errors(errors, report_dir)
    _write_report(context, report_dir)

    final = context["statuses"]["final_live_readiness"]
    print(f"Pipeline complete. Final live readiness: {final}")
    print(f"Report: {report_dir / 'latest_receptions_pipeline_report.md'}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
