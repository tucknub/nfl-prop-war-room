from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.common import load_config, output_path, raw_path
from src.export.export_google_sheet_receptions import export_google_sheet_receptions
from src.models.receptions_model import get_projection_target


GATE_DIR = "google_sheets"
RECEIVING_POSITIONS = {"WR", "RB", "TE", "FB"}


def updated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def gate_path(filename: str, config: dict[str, Any]) -> Path:
    return output_path(f"{GATE_DIR}/{filename}", config)


def american_odds_implied_probability(odds: float | int | None) -> float | None:
    if odds is None or pd.isna(odds) or odds == 0:
        return None
    odds = float(odds)
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def price_grade(edge_pct: float | None) -> str:
    if edge_pct is None or pd.isna(edge_pct):
        return ""
    if edge_pct >= 0.03:
        return "PASS"
    if edge_pct >= 0:
        return "REVIEW"
    return "BAD PRICE"


def _candidate_projection(config: dict[str, Any]) -> pd.DataFrame:
    _, _, week = get_projection_target(config)
    path = output_path(f"receptions_projection_week_{week:02d}_candidates.csv", config)
    if not path.exists():
        path = output_path(f"receptions_projection_week_{week:02d}.csv", config)
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    if "is_prop_candidate" in df.columns:
        df = df[df["is_prop_candidate"]].copy()
    return df.sort_values("projected_receptions_calibrated", ascending=False)


def _normalized_gate(config: dict[str, Any], gate: str, filename: str) -> tuple[pd.DataFrame | None, str | None]:
    status_path = output_path("gate_inputs_normalized/gate_input_status.csv", config)
    normalized_path = output_path(f"gate_inputs_normalized/{filename}", config)
    if not status_path.exists() or not normalized_path.exists():
        return None, None
    status_df = pd.read_csv(status_path, low_memory=False)
    row = status_df[status_df["gate"] == gate]
    if row.empty:
        return None, None
    is_real = bool(row["is_real_data"].iloc[0])
    status = str(row["status"].iloc[0])
    if not is_real or status not in {"READY", "REVIEW"}:
        return None, status
    data = pd.read_csv(normalized_path, low_memory=False)
    if data.empty:
        return None, status
    return data, status


def build_schedule_gate(config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    mode, season, week = get_projection_target(config)
    normalized, normalized_status = _normalized_gate(config, "schedule", "schedule_gate_normalized.csv")
    if normalized is not None:
        return normalized, normalized_status or "READY"
    path = raw_path("schedules.csv", config)
    columns = [
        "Season",
        "Week",
        "Game Date",
        "Away Team",
        "Home Team",
        "Neutral Site",
        "Venue",
        "Game ID",
        "Game Status",
        "Source",
        "Updated At",
        "Validation Status",
        "Notes",
    ]
    if not path.exists():
        row = {column: "" for column in columns}
        row.update(
            {
                "Season": season,
                "Week": week,
                "Source": str(path),
                "Updated At": updated_at(),
                "Validation Status": "NEEDS DATA",
                "Notes": "Target schedule file is missing. Do not fabricate future schedule data.",
            }
        )
        return pd.DataFrame([row], columns=columns), "NEEDS DATA"

    schedules = pd.read_csv(path, low_memory=False)
    target = schedules[(schedules["season"] == season) & (schedules["week"] == week)].copy()
    if target.empty:
        row = {column: "" for column in columns}
        row.update(
            {
                "Season": season,
                "Week": week,
                "Source": str(path),
                "Updated At": updated_at(),
                "Validation Status": "NEEDS DATA",
                "Notes": "Target schedule is missing from local schedule data. Do not fabricate schedule data.",
            }
        )
        return pd.DataFrame([row], columns=columns), "NEEDS DATA"

    out = pd.DataFrame(
        {
            "Season": target["season"],
            "Week": target["week"],
            "Game Date": target.get("gameday", ""),
            "Away Team": target.get("away_team", ""),
            "Home Team": target.get("home_team", ""),
            "Neutral Site": target.get("location", "").astype(str).str.upper().eq("NEUTRAL"),
            "Venue": target.get("stadium", ""),
            "Game ID": target.get("game_id", ""),
            "Game Status": target.get("game_type", ""),
            "Source": str(path),
            "Updated At": updated_at(),
            "Validation Status": "READY",
            "Notes": f"Schedule rows found for {mode} target.",
        }
    )
    return out[columns], "READY"


def _candidate_template_base(config: dict[str, Any]) -> pd.DataFrame:
    candidates = _candidate_projection(config)
    if candidates.empty:
        return pd.DataFrame(columns=["Player Name", "Player ID", "Team", "Position"])
    return pd.DataFrame(
        {
            "Player Name": candidates["player_name"],
            "Player ID": candidates["player_id"],
            "Team": candidates["team"],
            "Position": candidates["position"],
        }
    )


def build_roster_gate_template(config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    normalized, normalized_status = _normalized_gate(config, "roster", "roster_gate_normalized.csv")
    if normalized is not None:
        return normalized, normalized_status or "READY"
    map_status_path = output_path("roster/current_roster_map_status.csv", config)
    map_path = output_path("roster/current_roster_map.csv", config)
    if map_status_path.exists():
        map_status = pd.read_csv(map_status_path, low_memory=False)
        status = str(map_status["status"].iloc[0]) if not map_status.empty else "NEEDS DATA"
        real_rows = int(map_status["roster_rows_loaded"].iloc[0]) if not map_status.empty else 0
        if status == "READY" and real_rows > 0 and map_path.exists():
            mapped = pd.read_csv(map_path, low_memory=False)
            out = pd.DataFrame({
                "Player Name": mapped.get("player_name", ""),
                "Player ID": mapped.get("player_id", ""),
                "Position": mapped.get("position", ""),
                "Current Team": mapped.get("current_team", ""),
                "Roster Status": mapped.get("roster_status", ""),
                "Depth Chart Role": mapped.get("depth_chart_role", ""),
                "Source": mapped.get("source", ""),
                "Updated At": mapped.get("updated_at", ""),
                "Current Team Verified": True,
                "Team Verify Flag": "",
                "Validation Status": "READY",
                "Notes": mapped.get("notes", ""),
            })
            return out, "READY"
    base = _candidate_template_base(config)
    status = "NEEDS DATA"
    if map_status_path.exists():
        map_status = pd.read_csv(map_status_path, low_memory=False)
        if not map_status.empty:
            status = str(map_status["status"].iloc[0])
    out = pd.DataFrame(
        {
            "Player Name": base.get("Player Name", pd.Series(dtype="object")),
            "Player ID": base.get("Player ID", pd.Series(dtype="object")),
            "Position": base.get("Position", pd.Series(dtype="object")),
            "Current Team": base.get("Team", pd.Series(dtype="object")),
            "Roster Status": "",
            "Depth Chart Role": "",
            "Source": "manual/current roster required",
            "Updated At": updated_at(),
            "Current Team Verified": False,
            "Team Verify Flag": "TEAM_VERIFY",
            "Validation Status": status,
            "Notes": "Current roster source is not confirmed. See outputs/roster/current_roster_map_status.csv and current_roster_needs_review.csv.",
        }
    )
    return out, status


def build_role_gate_template(config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    normalized, normalized_status = _normalized_gate(config, "role", "role_gate_normalized.csv")
    if normalized is not None:
        return normalized, normalized_status or "READY"
    map_status_path = output_path("roles/current_role_map_status.csv", config)
    map_path = output_path("roles/current_role_map.csv", config)
    if map_status_path.exists():
        map_status = pd.read_csv(map_status_path, low_memory=False)
        status = str(map_status["status"].iloc[0]) if not map_status.empty else "NEEDS DATA"
        real_rows = int(map_status["role_rows_loaded"].iloc[0]) if not map_status.empty else 0
        if status == "READY" and real_rows > 0 and map_path.exists():
            mapped = pd.read_csv(map_path, low_memory=False)
            out = pd.DataFrame({"Player Name":mapped.get("player_name",""),"Player ID":mapped.get("player_id",""),"Team":mapped.get("current_team",""),"Position":mapped.get("position",""),"Expected Role":mapped.get("projected_role",""),"Starter Status":mapped.get("starter_status",""),"Projected Snap Share":mapped.get("projected_snap_share",""),"Projected Route Share":mapped.get("projected_route_share",""),"Target Share Override":mapped.get("projected_target_share",""),"Role Confidence":mapped.get("role_confidence",""),"Manual Override":mapped.get("manual_override",False),"Source":mapped.get("source",""),"Updated At":mapped.get("updated_at",""),"Validation Status":"READY","Notes":mapped.get("notes","")})
            return out,"READY"
    base = _candidate_template_base(config)
    status = "NEEDS DATA"
    if map_status_path.exists():
        map_status = pd.read_csv(map_status_path, low_memory=False)
        if not map_status.empty: status = str(map_status["status"].iloc[0])
    out = pd.DataFrame(
        {
            "Player Name": base.get("Player Name", pd.Series(dtype="object")),
            "Player ID": base.get("Player ID", pd.Series(dtype="object")),
            "Team": base.get("Team", pd.Series(dtype="object")),
            "Position": base.get("Position", pd.Series(dtype="object")),
            "Expected Role": "Unknown",
            "Starter Status": "Unknown",
            "Projected Snap Share": "",
            "Projected Route Share": "",
            "Target Share Override": "",
            "Role Confidence": 0,
            "Manual Override": "",
            "Source": "manual role gate required",
            "Updated At": updated_at(),
            "Validation Status": status,
            "Notes": "Unknown role prevents live use. See outputs/roles/current_role_map_status.csv and current_role_needs_review.csv.",
        }
    )
    return out, status


def build_injury_gate_template(config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    normalized, normalized_status = _normalized_gate(config, "injury", "injury_gate_normalized.csv")
    if normalized is not None:
        return normalized, normalized_status or "READY"
    map_status_path = output_path("injuries/current_injury_map_status.csv", config)
    map_path = output_path("injuries/current_injury_map.csv", config)
    if map_status_path.exists():
        map_status = pd.read_csv(map_status_path, low_memory=False);status = str(map_status["status"].iloc[0]) if not map_status.empty else "NEEDS DATA";real_rows = int(map_status["injury_rows_loaded"].iloc[0]) if not map_status.empty else 0
        if status == "READY" and real_rows > 0 and map_path.exists():
            mapped=pd.read_csv(map_path,low_memory=False);out=pd.DataFrame({"Player Name":mapped.get("player_name",""),"Player ID":mapped.get("player_id",""),"Team":mapped.get("current_team",""),"Position":mapped.get("position",""),"Injury Status":mapped.get("injury_status",""),"Practice Status":mapped.get("practice_status",""),"Game Status":mapped.get("game_status",""),"Availability Risk":mapped.get("availability_risk",""),"Confidence Penalty":0,"Projection Action":mapped.get("projection_action",""),"Manual Override":mapped.get("manual_override",False),"Source":mapped.get("source",""),"Updated At":mapped.get("updated_at",""),"Validation Status":"READY","Notes":mapped.get("notes","")});return out,"READY"
    base = _candidate_template_base(config)
    status = "NEEDS DATA"
    if map_status_path.exists():
        map_status=pd.read_csv(map_status_path,low_memory=False)
        if not map_status.empty:status=str(map_status["status"].iloc[0])
    out = pd.DataFrame(
        {
            "Player Name": base.get("Player Name", pd.Series(dtype="object")),
            "Player ID": base.get("Player ID", pd.Series(dtype="object")),
            "Team": base.get("Team", pd.Series(dtype="object")),
            "Position": base.get("Position", pd.Series(dtype="object")),
            "Injury Status": "Unknown",
            "Practice Status": "Unknown",
            "Game Status": "Unknown",
            "Availability Risk": "Unknown",
            "Confidence Penalty": 20,
            "Projection Action": "Monitor",
            "Manual Override": "",
            "Source": "manual injury gate required",
            "Updated At": updated_at(),
            "Validation Status": status,
            "Notes": "Unknown injury status blocks live use. See outputs/injuries/current_injury_map_status.csv and current_injury_needs_review.csv.",
        }
    )
    return out, status


def build_market_odds_gate_template(config: dict[str, Any]) -> tuple[pd.DataFrame, str]:
    normalized, normalized_status = _normalized_gate(config, "market_odds", "market_odds_gate_normalized.csv")
    if normalized is not None:
        return normalized, normalized_status or "READY"
    base = _candidate_template_base(config)
    status = "NEEDS DATA"
    out = pd.DataFrame(
        {
            "Player Name": base.get("Player Name", pd.Series(dtype="object")),
            "Player ID": base.get("Player ID", pd.Series(dtype="object")),
            "Team": base.get("Team", pd.Series(dtype="object")),
            "Opponent": "",
            "Position": base.get("Position", pd.Series(dtype="object")),
            "Market": "Receptions",
            "Sportsbook": "",
            "Line": "",
            "Over Odds": "",
            "Under Odds": "",
            "Implied Over Prob": "",
            "Model Over Prob": "",
            "Edge %": "",
            "Price Grade": "",
            "Updated At": updated_at(),
            "Validation Status": status,
            "Notes": "No odds source loaded. No betting edge is produced without market odds.",
        }
    )
    return out, status


def _history_status(config: dict[str, Any]) -> tuple[str, str]:
    path = output_path("history_window_audit.csv", config)
    if not path.exists():
        return "NEEDS DATA", "history_window_audit.csv missing"
    audit = pd.read_csv(path, low_memory=False)
    if audit.empty:
        return "NEEDS DATA", "history_window_audit.csv empty"
    return str(audit["leakage_status"].iloc[0]), f"leakage_exists={audit['leakage_exists'].iloc[0]}"


def build_live_readiness(
    config: dict[str, Any],
    gate_statuses: dict[str, str],
) -> tuple[pd.DataFrame, str]:
    mode, season, week = get_projection_target(config)
    history_status, history_note = _history_status(config)
    required_gate_statuses = {
        "History Audit": history_status,
        "Schedule Gate": gate_statuses["Schedule Gate"],
        "Roster Gate": gate_statuses["Roster Gate"],
        "Role Gate": gate_statuses["Role Gate"],
        "Injury Gate": gate_statuses["Injury Gate"],
    }
    final_ready = (
        mode == "forward_projection"
        and all(status in {"READY", "PASS"} for status in required_gate_statuses.values())
    )
    final_status = "GO" if final_ready else "NO-GO"
    rows = [
        {
            "Gate": "History Audit",
            "Requirement": "Feature data must come before target season/week.",
            "Status": history_status,
            "Current Value": history_note,
            "Action Needed": "" if history_status == "PASS" else "Rebuild leakage-safe feature table.",
            "Source": "outputs/history_window_audit.csv",
            "Notes": "",
        },
        {
            "Gate": "Schedule Gate",
            "Requirement": "Target schedule must exist.",
            "Status": gate_statuses["Schedule Gate"],
            "Current Value": f"{season} Week {week}",
            "Action Needed": "" if gate_statuses["Schedule Gate"] == "READY" else "Load target schedule data.",
            "Source": "outputs/google_sheets/schedule_gate_import.csv",
            "Notes": "Do not fabricate future schedule data.",
        },
        {
            "Gate": "Roster Gate",
            "Requirement": "Current team must be verified for every live player.",
            "Status": gate_statuses["Roster Gate"],
            "Current Value": "TEAM_VERIFY required until current roster import is confirmed.",
            "Action Needed": "Import and verify current roster/team data.",
            "Source": "outputs/roster/current_roster_map_status.csv | outputs/roster/current_roster_needs_review.csv",
            "Notes": "TEAM_VERIFY means DO NOT USE.",
        },
        {
            "Gate": "Role Gate",
            "Requirement": "Role must be known and confidence should be 60+.",
            "Status": gate_statuses["Role Gate"],
            "Current Value": "Unknown",
            "Action Needed": "Import expected roles, snap/route shares, and confidence.",
            "Source": "outputs/roles/current_role_map_status.csv | outputs/roles/current_role_needs_review.csv",
            "Notes": "Unknown role prevents high-confidence live use.",
        },
        {
            "Gate": "Injury Gate",
            "Requirement": "Availability must be known.",
            "Status": gate_statuses["Injury Gate"],
            "Current Value": "Unknown",
            "Action Needed": "Import injury and practice status.",
            "Source": "outputs/injuries/current_injury_map_status.csv | outputs/injuries/current_injury_needs_review.csv",
            "Notes": "Out, IR, Doubtful, Inactive, or Unknown blocks/downgrades live use.",
        },
        {
            "Gate": "Market Odds Gate",
            "Requirement": "Odds required for betting-edge mode.",
            "Status": gate_statuses["Market Odds Gate"],
            "Current Value": "No odds loaded",
            "Action Needed": "Import sportsbook lines and American odds for betting edge.",
            "Source": "outputs/google_sheets/market_odds_gate_import_template.csv",
            "Notes": "Optional for pure projection, required for betting edges.",
        },
        {
            "Gate": "Receptions Dashboard",
            "Requirement": "Dashboard import must be clearly labeled.",
            "Status": "HISTORICAL TEST ONLY" if mode == "historical_test" else "MODEL REVIEW",
            "Current Value": f"{mode} {season} Week {week}",
            "Action Needed": "Do not use for live betting until Final Betting Use is GO.",
            "Source": "outputs/google_sheets_receptions_historical_test.csv",
            "Notes": "Raw and calibrated projections remain visible.",
        },
        {
            "Gate": "Model Output Mode",
            "Requirement": "Historical test mode cannot be live betting ready.",
            "Status": "NOT READY" if mode == "historical_test" else "MODEL REVIEW",
            "Current Value": mode,
            "Action Needed": "Switch to forward_projection only after live gates are ready.",
            "Source": "config.yaml",
            "Notes": "Never silently fall back from forward_projection to historical_test.",
        },
        {
            "Gate": "Final Betting Use",
            "Requirement": "All required gates must be READY/PASS in forward_projection mode.",
            "Status": final_status,
            "Current Value": "READY" if final_ready else "NOT READY",
            "Action Needed": "" if final_ready else "Resolve blockers in forward_projection_blockers.csv.",
            "Source": "outputs/google_sheets/forward_projection_blockers.csv",
            "Notes": "Historical test mode always means NOT READY.",
        },
    ]
    return pd.DataFrame(rows), final_status


def build_forward_projection_blockers(
    config: dict[str, Any],
    gate_statuses: dict[str, str],
    final_status: str,
) -> pd.DataFrame:
    mode, _, _ = get_projection_target(config)
    blockers = []
    if mode == "historical_test":
        blockers.append(
            {
                "Blocker": "Historical test mode",
                "Severity": "HIGH",
                "Why It Matters": "Historical tests are for validation and must not be treated as live betting boards.",
                "Required Before Projection": "Switch config projection_mode to forward_projection after gates are ready.",
                "Required Before Betting": "Yes",
                "Next Action": "Keep usage_status as HISTORICAL TEST ONLY until forward gates pass.",
            }
        )
    for gate, status in gate_statuses.items():
        if status not in {"READY", "PASS"}:
            blockers.append(
                {
                    "Blocker": gate,
                    "Severity": "HIGH" if gate != "Market Odds Gate" else "MEDIUM",
                    "Why It Matters": f"{gate} status is {status}.",
                    "Required Before Projection": "Yes" if gate != "Market Odds Gate" else "No for pure projection",
                    "Required Before Betting": "Yes",
                    "Next Action": f"Complete {gate} import and validation.",
                }
            )
    if not blockers and final_status != "GO":
        blockers.append(
            {
                "Blocker": "Final readiness not GO",
                "Severity": "HIGH",
                "Why It Matters": "The system is not live-ready.",
                "Required Before Projection": "Review live_readiness_export.csv.",
                "Required Before Betting": "Yes",
                "Next Action": "Resolve readiness status.",
            }
        )
    return pd.DataFrame(blockers)


def assert_forward_projection_gates_ready(config: dict[str, Any]) -> None:
    mode, _, _ = get_projection_target(config)
    if mode != "forward_projection":
        return
    readiness_path = gate_path("live_readiness_export.csv", config)
    if not readiness_path.exists():
        raise RuntimeError("Cannot produce true forward projection: live readiness gates have not been exported.")
    readiness = pd.read_csv(readiness_path, low_memory=False)
    final = readiness[readiness["Gate"] == "Final Betting Use"]
    if final.empty or str(final["Status"].iloc[0]) != "GO":
        raise RuntimeError("Cannot produce true forward projection: required live readiness gates are not READY.")


def export_sheet_gates() -> dict[str, str]:
    config = load_config()
    schedule, schedule_status = build_schedule_gate(config)
    roster, roster_status = build_roster_gate_template(config)
    role, role_status = build_role_gate_template(config)
    injury, injury_status = build_injury_gate_template(config)
    odds, odds_status = build_market_odds_gate_template(config)
    gate_statuses = {
        "Schedule Gate": schedule_status,
        "Roster Gate": roster_status,
        "Role Gate": role_status,
        "Injury Gate": injury_status,
        "Market Odds Gate": odds_status,
    }
    readiness, final_status = build_live_readiness(config, gate_statuses)
    blockers = build_forward_projection_blockers(config, gate_statuses, final_status)
    dashboard = export_google_sheet_receptions()

    files = {
        "schedule_gate_import": gate_path("schedule_gate_import.csv", config),
        "roster_gate_import_template": gate_path("roster_gate_import_template.csv", config),
        "role_gate_import_template": gate_path("role_gate_import_template.csv", config),
        "injury_gate_import_template": gate_path("injury_gate_import_template.csv", config),
        "market_odds_gate_import_template": gate_path("market_odds_gate_import_template.csv", config),
        "live_readiness_export": gate_path("live_readiness_export.csv", config),
        "forward_projection_blockers": gate_path("forward_projection_blockers.csv", config),
        "receptions_dashboard": output_path("google_sheets_receptions_historical_test.csv", config),
    }
    schedule.to_csv(files["schedule_gate_import"], index=False)
    roster.to_csv(files["roster_gate_import_template"], index=False)
    role.to_csv(files["role_gate_import_template"], index=False)
    injury.to_csv(files["injury_gate_import_template"], index=False)
    odds.to_csv(files["market_odds_gate_import_template"], index=False)
    readiness.to_csv(files["live_readiness_export"], index=False)
    blockers.to_csv(files["forward_projection_blockers"], index=False)
    return {key: str(path) for key, path in files.items()}


def validation_summary() -> pd.DataFrame:
    config = load_config()
    files = export_sheet_gates()
    mode, season, week = get_projection_target(config)
    audit_path = output_path("history_window_audit.csv", config)
    readiness_path = gate_path("live_readiness_export.csv", config)
    audit = pd.read_csv(audit_path, low_memory=False) if audit_path.exists() else pd.DataFrame()
    readiness = pd.read_csv(readiness_path, low_memory=False)
    readiness_map = dict(zip(readiness["Gate"], readiness["Status"]))
    history_window = ""
    leakage_status = "NEEDS DATA"
    if not audit.empty:
        history_window = f"{audit['seasons_used_for_features'].iloc[0]}"
        leakage_status = str(audit["leakage_status"].iloc[0])
    rows = [
        ("projection_mode", mode),
        ("target_season", season),
        ("target_week", week),
        ("history window", history_window),
        ("leakage status", leakage_status),
        ("schedule gate status", readiness_map.get("Schedule Gate", "")),
        ("roster gate status", readiness_map.get("Roster Gate", "")),
        ("role gate status", readiness_map.get("Role Gate", "")),
        ("injury gate status", readiness_map.get("Injury Gate", "")),
        ("market odds gate status", readiness_map.get("Market Odds Gate", "")),
        ("final live readiness", readiness_map.get("Final Betting Use", "")),
    ]
    rows.extend((f"output file path: {key}", value) for key, value in files.items())
    return pd.DataFrame(rows, columns=["item", "value"])


def main() -> None:
    summary = validation_summary()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
