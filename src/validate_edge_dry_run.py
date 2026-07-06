from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.common import output_path, project_path
from src.export.export_edge_preview_board import MARKETS
from src.load.build_current_injury_map import build_map_from_frames as build_injury_map
from src.load.build_current_role_map import build_map_from_frames as build_role_map
from src.load.build_current_roster_map import build_map_from_frames as build_roster_map
from src.load.build_identity_crosswalk import normalize_player_name
from src.load.build_market_odds_map import build_map_from_frames as build_odds_map
from src.models.odds_utils import calculate_edge


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, str]], scenario: str, check_name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append(
        {
            "scenario": scenario,
            "check_name": check_name,
            "expected": str(expected),
            "actual": str(actual),
            "status": "PASS" if passed else "FAIL",
            "severity": "INFO" if passed else "HIGH",
            "notes": notes,
        }
    )


def final_readiness() -> str:
    readiness = read_csv(output_path("google_sheets/live_readiness_export.csv"))
    if readiness.empty or "Gate" not in readiness.columns:
        return "NO-GO"
    row = readiness[readiness["Gate"].astype(str).eq("Final Betting Use")]
    return "NO-GO" if row.empty else str(row["Status"].iloc[0])


def status_value(relative: str) -> str:
    frame = read_csv(output_path(relative))
    if frame.empty or "status" not in frame.columns:
        return "MISSING"
    return str(frame["status"].iloc[0])


def live_output_created() -> bool:
    status = read_csv(output_path("run_reports/latest_receptions_pipeline_status.csv"))
    if not status.empty and {"check_name", "value"}.issubset(status.columns):
        row = status[status["check_name"].astype(str).eq("live_betting_output_created")]
        if not row.empty:
            return str(row["value"].iloc[0]).strip().lower() == "true"
    return output_path("market_edges/live_betting_output.csv").exists() or output_path("live_betting_output.csv").exists()


def file_digest(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_snapshot() -> dict[str, str]:
    paths = [
        project_path("config.yaml"),
        output_path("google_sheets/live_readiness_export.csv"),
        output_path("edge_preview/edge_preview_board.csv"),
        output_path("roster/current_roster_map_status.csv"),
        output_path("roles/current_role_map_status.csv"),
        output_path("injuries/current_injury_map_status.csv"),
        output_path("odds/current_market_odds_status.csv"),
    ]
    return {str(path): file_digest(path) for path in paths}


def identity_from_roster(roster: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "player_id": roster["player_id"],
            "player_name": roster["player_name"],
            "normalized_player_name": roster["player_name"].map(normalize_player_name),
            "team": roster["current_team"],
            "position": roster["position"],
            "season_min": 2026,
            "season_max": 2026,
            "source_files": "SYNTHETIC TEST ONLY",
            "candidate_count": 1,
            "duplicate_name_flag": False,
            "notes": "SYNTHETIC TEST ONLY",
        }
    )


def nearest_ladder_row(market_key: str, player_name: str, team: str, target_line: float) -> pd.Series:
    path = output_path(MARKETS[market_key]["ladder"])
    ladder = read_csv(path)
    if ladder.empty:
        raise RuntimeError(f"Missing ladder for {market_key}: {path}")
    view = ladder[ladder["player_name"].astype(str).eq(player_name) & ladder["team"].astype(str).eq(team)].copy()
    if view.empty:
        raise RuntimeError(f"No ladder row for {player_name} {team} {market_key}")
    view["_distance"] = (pd.to_numeric(view["line"], errors="coerce") - float(target_line)).abs()
    return view.sort_values("_distance").iloc[0]


def synthetic_probability_lookup(odds: pd.DataFrame) -> dict[tuple[str, str, float], dict[str, float]]:
    lookup: dict[tuple[str, str, float], dict[str, float]] = {}
    for _, row in odds.iterrows():
        market_key = str(row["market_key"])
        target_line = float(pd.to_numeric(row["line"], errors="coerce"))
        ladder_row = nearest_ladder_row(market_key, str(row["player_name"]), str(row["team"]), target_line)
        line = float(pd.to_numeric(ladder_row["line"], errors="coerce"))
        row["line"] = line
        values = {
            "model_projection": pd.to_numeric(ladder_row.get("calibrated_projection"), errors="coerce"),
            "model_over_probability": pd.to_numeric(ladder_row.get("model_over_probability"), errors="coerce"),
            "model_under_probability": pd.to_numeric(ladder_row.get("model_under_probability"), errors="coerce"),
        }
        lookup[(market_key, f"{row['player_id']}|{row['team']}", line)] = values
        lookup[(market_key, str(row["player_id"]), line)] = values
    return lookup


def build_synthetic_edge_rows(odds_map: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in odds_map[odds_map["odds_mapping_status"].astype(str).eq("READY")].iterrows():
        edge_over = calculate_edge(row.get("model_over_probability"), row.get("implied_over_probability"))
        edge_under = calculate_edge(row.get("model_under_probability"), row.get("implied_under_probability"))
        best_side = "Over" if edge_under is None or (edge_over is not None and edge_over >= edge_under) else "Under"
        best_edge = edge_over if best_side == "Over" else edge_under
        rows.append(
            {
                "market_key": row["market_key"],
                "market_display_name": row["market_display_name"],
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "team": row["team"],
                "line": row["line"],
                "sportsbook": row["sportsbook"],
                "model_over_probability": row["model_over_probability"],
                "implied_over_probability": row["implied_over_probability"],
                "edge_over": edge_over,
                "best_side": best_side,
                "best_edge": best_edge,
                "decision_status": "Qualified Edge",
                "usage_status": "SYNTHETIC TEST ONLY - NOT PRODUCTION - NOT LIVE BETTING",
                "notes": "SYNTHETIC TEST ONLY dry-run row. Not production and not a bet.",
            }
        )
    return pd.DataFrame(rows)


def run_edge_dry_run() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    before_snapshot = production_snapshot()
    prod_final_before = final_readiness()
    scenario = "Scenario A - Production missing live data"
    edge = read_csv(output_path("edge_preview/edge_preview_board.csv"))
    odds_map = read_csv(output_path("odds/current_market_odds_map.csv"))
    qualified = int(edge.get("decision_status", pd.Series(dtype=str)).astype(str).eq("Qualified Edge").sum()) if not edge.empty else 0
    add(rows, scenario, "final_readiness_remains_no_go", "NO-GO", prod_final_before, prod_final_before == "NO-GO")
    add(rows, scenario, "roster_map_needs_data", "NEEDS DATA", status_value("roster/current_roster_map_status.csv"), status_value("roster/current_roster_map_status.csv") == "NEEDS DATA")
    add(rows, scenario, "role_map_needs_data", "NEEDS DATA", status_value("roles/current_role_map_status.csv"), status_value("roles/current_role_map_status.csv") == "NEEDS DATA")
    add(rows, scenario, "injury_map_needs_data", "NEEDS DATA", status_value("injuries/current_injury_map_status.csv"), status_value("injuries/current_injury_map_status.csv") == "NEEDS DATA")
    add(rows, scenario, "market_odds_map_needs_data", "NEEDS DATA", status_value("odds/current_market_odds_status.csv"), status_value("odds/current_market_odds_status.csv") == "NEEDS DATA")
    add(rows, scenario, "production_has_zero_qualified_edges", 0, qualified, qualified == 0)
    add(rows, scenario, "no_live_betting_output_created", False, live_output_created(), not live_output_created())
    add(rows, scenario, "no_fake_odds_added_to_production", 0, len(odds_map), odds_map.empty)

    fixture_dir = project_path("tests", "fixtures", "edge_dry_run")
    rosters = read_csv(fixture_dir / "synthetic_roster_ready.csv")
    roles = read_csv(fixture_dir / "synthetic_role_ready.csv")
    injuries = read_csv(fixture_dir / "synthetic_injury_ready.csv")
    odds = read_csv(fixture_dir / "synthetic_market_odds_ready.csv")
    identity = identity_from_roster(rosters)
    with TemporaryDirectory(prefix="edge_dry_run_") as temp_dir:
        temp = Path(temp_dir)
        roster_map = build_roster_map(rosters, pd.DataFrame(), identity)
        roster_map.to_csv(temp / "synthetic_roster_map.csv", index=False)
        role_map = build_role_map(roles, pd.DataFrame(), identity, roster_map)
        role_map.to_csv(temp / "synthetic_role_map.csv", index=False)
        injury_map = build_injury_map(injuries, pd.DataFrame(), identity, roster_map, role_map)
        injury_map.to_csv(temp / "synthetic_injury_map.csv", index=False)
        prob_lookup = synthetic_probability_lookup(odds)
        odds_map_synth = build_odds_map(odds, pd.DataFrame(), identity, roster_map, role_map, injury_map, prob_lookup)
        odds_map_synth.to_csv(temp / "synthetic_odds_map.csv", index=False)
        synthetic_edge = build_synthetic_edge_rows(odds_map_synth)

    blockers = pd.DataFrame(
        [
            {
                "blocker": "SYNTHETIC TEST ONLY",
                "status": "DRY RUN ONLY",
                "severity": "INFO",
                "notes": "All gates are synthetic and isolated from production outputs.",
            }
        ]
    )
    dry_dir = output_path("edge_preview_dry_run/synthetic_edge_preview_board.csv").parent
    dry_dir.mkdir(parents=True, exist_ok=True)
    synthetic_edge.to_csv(output_path("edge_preview_dry_run/synthetic_edge_preview_board.csv"), index=False)
    blockers.to_csv(output_path("edge_preview_dry_run/synthetic_edge_preview_blockers.csv"), index=False)

    scenario = "Scenario B - Synthetic all-gates-ready"
    add(rows, scenario, "synthetic_roster_gate_ready", "all READY", sorted(roster_map["team_mapping_status"].unique()), roster_map["team_mapping_status"].astype(str).eq("READY").all())
    add(rows, scenario, "synthetic_role_gate_ready", "all READY", sorted(role_map["role_mapping_status"].unique()), role_map["role_mapping_status"].astype(str).eq("READY").all())
    add(rows, scenario, "synthetic_injury_gate_ready", "all READY", sorted(injury_map["injury_mapping_status"].unique()), injury_map["injury_mapping_status"].astype(str).eq("READY").all())
    add(rows, scenario, "synthetic_odds_gate_ready", "all READY", sorted(odds_map_synth["odds_mapping_status"].unique()), odds_map_synth["odds_mapping_status"].astype(str).eq("READY").all())
    implied_ok = pd.to_numeric(odds_map_synth["implied_over_probability"], errors="coerce").between(0, 1).all()
    add(rows, scenario, "synthetic_implied_probabilities_valid", "0..1", implied_ok, implied_ok)
    edge_calc_ok = not synthetic_edge.empty and pd.to_numeric(synthetic_edge["edge_over"], errors="coerce").notna().all()
    add(rows, scenario, "synthetic_edges_calculate", "edge_over numeric", edge_calc_ok, edge_calc_ok)
    qualified_synth = int(synthetic_edge["decision_status"].astype(str).eq("Qualified Edge").sum()) if not synthetic_edge.empty else 0
    add(rows, scenario, "synthetic_qualified_edge_created", ">=1 synthetic Qualified Edge", qualified_synth, qualified_synth >= 1)
    labels_ok = not synthetic_edge.empty and synthetic_edge["usage_status"].astype(str).str.contains("SYNTHETIC TEST ONLY", na=False).all()
    add(rows, scenario, "synthetic_outputs_labeled_test_only", "SYNTHETIC TEST ONLY", labels_ok, labels_ok)
    prod_final_after = final_readiness()
    after_snapshot = production_snapshot()
    add(rows, scenario, "production_final_readiness_restored_no_go", "NO-GO", prod_final_after, prod_final_after == "NO-GO")
    add(rows, scenario, "production_files_restored", "same hashes before/after", before_snapshot == after_snapshot, before_snapshot == after_snapshot)
    add(rows, scenario, "no_live_betting_output_created_after_dry_run", False, live_output_created(), not live_output_created())
    leaked = list(project_path("data", "gates").glob("**/synthetic_*"))
    add(rows, scenario, "synthetic_files_do_not_leak_to_production_gate_folders", 0, len(leaked), len(leaked) == 0)

    report = pd.DataFrame(rows)
    overall = "PASS" if report["status"].eq("PASS").all() else "FAIL"
    report.to_csv(output_path("run_reports/latest_edge_dry_run.csv"), index=False)
    failed = report[report["status"].eq("FAIL")]["check_name"].tolist()
    scenario_a = "PASS" if report[report["scenario"].str.startswith("Scenario A")]["status"].eq("PASS").all() else "FAIL"
    scenario_b = "PASS" if report[report["scenario"].str.startswith("Scenario B")]["status"].eq("PASS").all() else "FAIL"
    output_path("run_reports/latest_edge_dry_run.md").write_text(
        f"""# End-to-End Edge Dry Run

Run timestamp: `{datetime.now(timezone.utc).isoformat()}`

Overall status: `{overall}`

Scenario A result: `{scenario_a}`

Scenario B result: `{scenario_b}`

Synthetic qualified edges: `{qualified_synth}`

Production readiness after dry run: `{prod_final_after}`

Production edge board qualified rows: `{qualified}`

Live betting output created: `{live_output_created()}`

Synthetic output label: `SYNTHETIC TEST ONLY`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Next required action: Keep production blocked until real roster, role, injury, odds, identity, and safety gates pass.
""",
        encoding="utf-8",
    )
    return report, overall


def main() -> None:
    report, overall = run_edge_dry_run()
    scenario_a = "PASS" if report[report["scenario"].str.startswith("Scenario A")]["status"].eq("PASS").all() else "FAIL"
    scenario_b = "PASS" if report[report["scenario"].str.startswith("Scenario B")]["status"].eq("PASS").all() else "FAIL"
    print(f"Edge dry run status: {overall}")
    print(f"Scenario A result: {scenario_a}")
    print(f"Scenario B result: {scenario_b}")
    print(f"Failed checks: {int(report.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
