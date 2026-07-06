from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path


COMMANDS = [
    "python -m src.run_prop_war_room_pipeline",
    "python -m src.validate_receptions_safety",
    "python -m src.validate_forward_projection_dry_run",
    "python -m src.load.validate_current_roster_map",
    "python -m src.load.validate_current_role_map",
    "python -m src.load.validate_current_injury_map",
    "python -m src.load.validate_market_odds_map",
    "python -m src.export.validate_edge_preview_board",
    "python -m src.validate_edge_dry_run",
]


CHECKLIST_ROWS = [
    {
        "gate": "Current Roster Map",
        "required_file_folder": "data/gates/rosters/",
        "template_file": "data/gates/rosters/current_roster_input_template.csv",
        "real_data_required": "Yes",
        "required_columns": "player_id, player_name, position, current_team, roster_status, depth_chart_role, source, source_url, updated_at, manual_override, notes",
        "validation_command": "python -m src.load.validate_current_roster_map",
        "ready_condition": "current_roster_map_status.csv status is READY and all real rows pass identity/team checks",
        "notes": "Template files do not count as real roster data.",
    },
    {
        "gate": "Role / Depth Chart Map",
        "required_file_folder": "data/gates/roles/",
        "template_file": "data/gates/roles/current_role_input_template.csv",
        "real_data_required": "Yes",
        "required_columns": "player_id, player_name, team, position, projected_role, starter_status, depth_chart_rank, projected_snap_share, projected_route_share, projected_carry_share, projected_target_share, role_confidence, source, source_url, updated_at, manual_override, notes",
        "validation_command": "python -m src.load.validate_current_role_map",
        "ready_condition": "current_role_map_status.csv status is READY and all roles are verified",
        "notes": "Unknown or low-confidence roles remain review blockers.",
    },
    {
        "gate": "Injury / Availability Map",
        "required_file_folder": "data/gates/injuries/",
        "template_file": "data/gates/injuries/current_injury_input_template.csv",
        "real_data_required": "Yes",
        "required_columns": "player_id, player_name, team, position, injury_status, injury_detail, practice_status, game_status, availability_risk, projection_action, source, source_url, updated_at, manual_override, notes",
        "validation_command": "python -m src.load.validate_current_injury_map",
        "ready_condition": "current_injury_map_status.csv status is READY and no availability blockers remain",
        "notes": "Out, IR, inactive, unknown, or unapproved rows block or require review.",
    },
    {
        "gate": "Market Odds Map",
        "required_file_folder": "data/gates/odds/",
        "template_file": "data/gates/odds/current_market_odds_input_template.csv",
        "real_data_required": "Yes",
        "required_columns": "player_id, player_name, team, opponent, market_key, market_display_name, sportsbook, line, over_odds, under_odds, odds_timestamp, source, source_url, manual_override, notes",
        "validation_command": "python -m src.load.validate_market_odds_map",
        "ready_condition": "current_market_odds_status.csv status is READY with valid lines, prices, identity, and gate context",
        "notes": "Odds are required before true edge can be calculated.",
    },
    {
        "gate": "Identity Validation",
        "required_file_folder": "outputs/identity/",
        "template_file": "N/A",
        "real_data_required": "Derived from loaded gate files",
        "required_columns": "gate, rows_checked, matched_rows, unmatched_rows, team_verify_rows, duplicate_name_rows, status, notes",
        "validation_command": "python -m src.load.validate_gate_identity_matches",
        "ready_condition": "No unmatched, duplicate-name, or TEAM_VERIFY rows for real gate data",
        "notes": "Player IDs are preferred over name-only matching.",
    },
    {
        "gate": "Edge Preview Board",
        "required_file_folder": "outputs/edge_preview/",
        "template_file": "N/A",
        "real_data_required": "Uses model ladders plus odds map",
        "required_columns": "decision_status, usage_status, blockers",
        "validation_command": "python -m src.export.validate_edge_preview_board",
        "ready_condition": "No Qualified Edge unless Final Readiness is GO",
        "notes": "Current board is research-only while gates need data.",
    },
    {
        "gate": "Safety Validator",
        "required_file_folder": "outputs/run_reports/",
        "template_file": "N/A",
        "real_data_required": "Derived report",
        "required_columns": "check_name, expected, actual, status, severity, notes",
        "validation_command": "python -m src.validate_receptions_safety",
        "ready_condition": "All checks PASS",
        "notes": "Safety validation protects against leakage, fake readiness, and live output while NO-GO.",
    },
    {
        "gate": "Forward Dry Run",
        "required_file_folder": "outputs/run_reports/",
        "template_file": "N/A",
        "real_data_required": "Synthetic fixture validation only",
        "required_columns": "scenario, check_name, expected, actual, status, severity, notes",
        "validation_command": "python -m src.validate_forward_projection_dry_run",
        "ready_condition": "Scenario A and Scenario B PASS",
        "notes": "Does not make production forward_projection live.",
    },
]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def scalar(relative: str, column: str = "status", default: str = "MISSING") -> str:
    frame = read_csv(relative)
    if frame.empty or column not in frame.columns:
        return default
    return str(frame[column].iloc[0])


def final_readiness() -> str:
    readiness = read_csv("google_sheets/live_readiness_export.csv")
    if readiness.empty or "Gate" not in readiness.columns:
        return "NO-GO"
    row = readiness[readiness["Gate"].astype(str).eq("Final Betting Use")]
    return "NO-GO" if row.empty else str(row["Status"].iloc[0])


def build_checklist() -> pd.DataFrame:
    status_lookup = {
        "Current Roster Map": scalar("roster/current_roster_map_status.csv"),
        "Role / Depth Chart Map": scalar("roles/current_role_map_status.csv"),
        "Injury / Availability Map": scalar("injuries/current_injury_map_status.csv"),
        "Market Odds Map": scalar("odds/current_market_odds_status.csv"),
        "Identity Validation": _identity_status(),
        "Edge Preview Board": _edge_preview_status(),
        "Safety Validator": _validation_status("run_reports/latest_receptions_safety_validation.csv"),
        "Forward Dry Run": _validation_status("run_reports/latest_forward_projection_dry_run.csv"),
    }
    rows = []
    for row in CHECKLIST_ROWS:
        item = row.copy()
        item["current_status"] = status_lookup.get(item["gate"], "MISSING")
        rows.append(item)
    return pd.DataFrame(rows)


def _validation_status(relative: str) -> str:
    frame = read_csv(relative)
    if frame.empty or "status" not in frame.columns:
        return "MISSING"
    return "FAIL" if frame["status"].astype(str).eq("FAIL").any() else "PASS"


def _identity_status() -> str:
    frame = read_csv("identity/gate_identity_match_report.csv")
    if frame.empty:
        return "NEEDS DATA"
    statuses = set(frame.get("status", pd.Series(dtype=str)).dropna().astype(str))
    if "BLOCKED" in statuses or "FAIL" in statuses:
        return "BLOCKED"
    if "NEEDS DATA" in statuses:
        return "NEEDS DATA"
    return "PASS"


def _edge_preview_status() -> str:
    blockers = read_csv("edge_preview/edge_preview_blockers.csv")
    if blockers.empty:
        return "MISSING"
    return "BLOCKED" if len(blockers) else "PASS"


def build_status(checklist: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in checklist.iterrows():
        status = str(row["current_status"])
        rows.append(
            {
                "gate": row["gate"],
                "current_status": status,
                "needs_real_data": "Yes" if status in {"NEEDS DATA", "NEEDS REVIEW", "BLOCKED", "MISSING"} and row["real_data_required"] == "Yes" else "No",
                "required_file_folder": row["required_file_folder"],
                "template_file": row["template_file"],
                "validation_command": row["validation_command"],
                "ready_condition": row["ready_condition"],
                "notes": row["notes"],
            }
        )
    return pd.DataFrame(rows)


def write_report(status: pd.DataFrame, checklist: pd.DataFrame) -> None:
    final = final_readiness()
    blockers = status[status["current_status"].astype(str).isin({"NEEDS DATA", "NEEDS REVIEW", "BLOCKED", "MISSING", "FAIL"})]
    files_needed = checklist[checklist["current_status"].astype(str).isin({"NEEDS DATA", "NEEDS REVIEW", "BLOCKED", "MISSING"})]
    can_forward = final == "GO" and blockers.empty
    text = f"""# Live Data Intake Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Can forward projection be considered? `{'Yes' if can_forward else 'No'}`

Can true betting edge be considered? `{'Yes' if can_forward and scalar('odds/current_market_odds_status.csv') == 'READY' else 'No'}`

Final readiness: `{final}`

Why not? `{'; '.join(blockers['gate'].astype(str) + ': ' + blockers['current_status'].astype(str)) if not blockers.empty else 'All intake gates are clear.'}`

Files needing real data:
{chr(10).join('- `' + row.required_file_folder + '` using `' + row.template_file + '`' for _, row in files_needed.iterrows() if row.template_file != 'N/A') or '- None'}

Validation commands to run next:
```powershell
{chr(10).join(COMMANDS)}
```

Templates do not count as real data. Synthetic dry-run fixtures do not count as production data.
"""
    output_path("run_reports/latest_live_data_intake_report.md").write_text(text, encoding="utf-8")


def export_live_data_intake_status() -> tuple[pd.DataFrame, pd.DataFrame]:
    checklist = build_checklist()
    status = build_status(checklist)
    checklist.to_csv(output_path("data_intake/live_data_intake_checklist.csv"), index=False)
    status.to_csv(output_path("data_intake/live_data_intake_status.csv"), index=False)
    write_report(status, checklist)
    return checklist, status


def main() -> None:
    checklist, status = export_live_data_intake_status()
    print(f"live_data_intake_checklist: {len(checklist):,} rows")
    print(f"live_data_intake_status: {len(status):,} rows")
    print(f"final_readiness: {final_readiness()}")


if __name__ == "__main__":
    main()
