from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path, project_path
from src.load.build_current_roster_map import build_map_from_frames, discover_real_inputs


def _check(rows: list[dict[str, str]], name: str, expected: object, actual: object, passed: bool, notes: str = "") -> None:
    rows.append({"check_name": name, "expected": str(expected), "actual": str(actual), "status": "PASS" if passed else "FAIL", "severity": "INFO" if passed else "HIGH", "notes": notes})


def _fixture_identity() -> pd.DataFrame:
    values = [
        ("TEST-001", "Fixture Quarterback", "fixture quarterback", "IND", "QB"),
        ("TEST-002", "Fixture Receiver", "fixture receiver", "MIA", "WR"),
        ("TEST-003", "Fixture Runner", "fixture runner", "PHI", "RB"),
        ("TEST-004", "Fixture Tight End", "fixture tight end", "KC", "TE"),
    ]
    return pd.DataFrame(values, columns=["player_id", "player_name", "normalized_player_name", "team", "position"]).assign(season_max=2025)


def validate_current_roster_map() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    map_path = output_path("roster/current_roster_map.csv")
    status_path = output_path("roster/current_roster_map_status.csv")
    review_path = output_path("roster/current_roster_needs_review.csv")
    for name, path in [("current_roster_map_exists", map_path), ("current_roster_status_exists", status_path), ("current_roster_review_exists", review_path)]:
        _check(rows, name, True, path.exists(), path.exists())

    status = pd.read_csv(status_path, low_memory=False) if status_path.exists() else pd.DataFrame()
    production_status = "MISSING" if status.empty else str(status["status"].iloc[0])
    roster_files, override_files = discover_real_inputs(project_path("data", "gates", "rosters"))
    templates_ignored = (not roster_files and production_status == "NEEDS DATA") or bool(roster_files)
    _check(rows, "templates_do_not_count_as_real_data", "templates ignored", f"real_files={len(roster_files)}; status={production_status}", templates_ignored)
    _check(rows, "missing_roster_data_stays_needs_data", "NEEDS DATA when no real files", production_status, bool(roster_files) or production_status == "NEEDS DATA")

    fixtures = project_path("tests", "fixtures")
    roster = pd.read_csv(fixtures / "current_roster_sample.csv", low_memory=False)
    overrides = pd.read_csv(fixtures / "roster_team_overrides_sample.csv", low_memory=False)
    mapped = build_map_from_frames(roster, overrides, _fixture_identity())
    by_id = mapped.set_index("player_id", drop=False)
    _check(rows, "unchanged_team_maps_ready", "READY", by_id.loc["TEST-001", "team_mapping_status"], by_id.loc["TEST-001", "team_mapping_status"] == "READY")
    _check(rows, "unverified_team_change_detected", "NEEDS REVIEW", by_id.loc["TEST-002", "team_mapping_status"], by_id.loc["TEST-002", "team_mapping_status"] == "NEEDS REVIEW")
    approved = by_id.loc["TEST-003"]
    _check(rows, "approved_override_applied", "READY / DAL", f"{approved['team_mapping_status']} / {approved['projection_team']}", approved["team_mapping_status"] == "READY" and approved["projection_team"] == "DAL" and bool(approved["manual_override"]))
    missing_id = mapped[mapped["player_name"].eq("Fixture Tight End")].iloc[0]
    _check(rows, "missing_id_needs_review", "NEEDS REVIEW", missing_id["team_mapping_status"], missing_id["team_mapping_status"] == "NEEDS REVIEW")
    _check(rows, "unmatched_player_blocked", "BLOCKED", by_id.loc["TEST-999", "team_mapping_status"], by_id.loc["TEST-999", "team_mapping_status"] == "BLOCKED")
    changed_safe = mapped[mapped["notes"].str.contains("TEAM_CHANGE:", na=False)].apply(lambda r: r["team_mapping_status"] != "READY" or bool(r["manual_override"]) or "source-backed" in r["notes"], axis=1).all()
    _check(rows, "changed_teams_cannot_silently_pass", True, changed_safe, bool(changed_safe))

    readiness_path = output_path("google_sheets/live_readiness_export.csv")
    readiness = pd.read_csv(readiness_path, low_memory=False) if readiness_path.exists() else pd.DataFrame()
    final = readiness.loc[readiness.get("Gate", pd.Series(dtype=str)).eq("Final Betting Use"), "Status"] if not readiness.empty else pd.Series(dtype=str)
    final_status = str(final.iloc[0]) if not final.empty else "MISSING"
    _check(rows, "roster_validation_does_not_enable_live", "NO-GO", final_status, final_status == "NO-GO")

    report = pd.DataFrame(rows)
    overall = "PASS" if report["status"].eq("PASS").all() else "FAIL"
    report.to_csv(output_path("run_reports/latest_current_roster_map_validation.csv"), index=False)
    failed = report[report["status"].eq("FAIL")]["check_name"].tolist()
    markdown = f"""# Current Roster Map Validation

Run timestamp: `{datetime.now(timezone.utc).isoformat()}`

Overall status: `{overall}`

Production roster-map status: `{production_status}`

Real roster files: `{len(roster_files)}`

Override files: `{len(override_files)}`

Templates counted as data: `False`

Fixture validation: `SYNTHETIC TEST ONLY`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Final live readiness: `{final_status}`

Next required action: Load a source-backed, non-template current roster CSV and resolve every review/blocking row before forward use.
"""
    output_path("run_reports/latest_current_roster_map_validation.md").write_text(markdown, encoding="utf-8")
    return report, overall


def main() -> None:
    report, overall = validate_current_roster_map()
    print(f"Current roster map validation: {overall}")
    print(f"Failed checks: {int(report['status'].eq('FAIL').sum())}")


if __name__ == "__main__":
    main()
