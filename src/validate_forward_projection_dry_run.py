from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import ROOT, load_config, output_path
from src.export.export_receptions_market_edges import american_odds_implied_probability


FIXTURE_DIR = ROOT / "tests" / "fixtures"
SYNTHETIC_LABEL = "SYNTHETIC TEST ONLY"
BLOCKING_STATUSES = {"NEEDS DATA", "BLOCKED", "CHECK", "NOT READY", "NO-GO", "UNKNOWN", "MISSING"}
FIXTURES = {
    "schedule": "forward_ready_schedule.csv",
    "roster": "forward_ready_roster.csv",
    "role": "forward_ready_roles.csv",
    "injury": "forward_ready_injuries.csv",
    "market_odds": "forward_ready_odds.csv",
}


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _gate_status(readiness: pd.DataFrame, gate: str) -> str:
    if readiness.empty:
        return "MISSING"
    rows = readiness[readiness["Gate"] == gate]
    return "MISSING" if rows.empty else str(rows["Status"].iloc[0])


def _add(
    rows: list[dict[str, str]],
    scenario: str,
    check_name: str,
    expected: str,
    actual: object,
    passed: bool,
    severity: str = "HIGH",
    notes: str = "",
) -> None:
    rows.append(
        {
            "scenario": scenario,
            "check_name": check_name,
            "expected": expected,
            "actual": str(actual),
            "status": "PASS" if passed else "FAIL",
            "severity": "INFO" if passed else severity,
            "notes": notes,
        }
    )


def _fixture(path_name: str) -> pd.DataFrame:
    return _read_csv(FIXTURE_DIR / path_name)


def _all_synthetic(df: pd.DataFrame) -> bool:
    if df.empty or "Fixture Label" not in df.columns:
        return False
    labels_ok = df["Fixture Label"].fillna("").astype(str).eq(SYNTHETIC_LABEL).all()
    source_ok = True
    if "Source" in df.columns:
        source_ok = df["Source"].fillna("").astype(str).str.contains(SYNTHETIC_LABEL, regex=False).all()
    return bool(labels_ok and source_ok)


def _ready(df: pd.DataFrame) -> bool:
    return not df.empty and "Validation Status" in df.columns and df["Validation Status"].astype(str).eq("READY").all()


def _scenario_a(rows: list[dict[str, str]]) -> dict[str, object]:
    readiness = _read_csv(output_path("google_sheets/live_readiness_export.csv"))
    blockers = _read_csv(output_path("google_sheets/forward_projection_blockers.csv"))
    dashboard = _read_csv(output_path("google_sheets_receptions_historical_test.csv"))
    final = _gate_status(readiness, "Final Betting Use")
    gate_statuses = {
        "Roster Gate": _gate_status(readiness, "Roster Gate"),
        "Role Gate": _gate_status(readiness, "Role Gate"),
        "Injury Gate": _gate_status(readiness, "Injury Gate"),
        "Market Odds Gate": _gate_status(readiness, "Market Odds Gate"),
    }
    blocked = blockers["Blocker"].dropna().astype(str).tolist() if "Blocker" in blockers.columns else []
    live_output = False
    if "usage_status" in dashboard.columns:
        live_output = dashboard["usage_status"].astype(str).str.contains("MODEL REVIEW", regex=False).any() and final == "GO"

    scenario = "Scenario A - Missing real forward data"
    _add(rows, scenario, "real_forward_missing_data_no_go", "NO-GO", final, final == "NO-GO")
    for gate in ["Roster Gate", "Role Gate", "Injury Gate", "Market Odds Gate"]:
        _add(
            rows,
            scenario,
            f"{gate.lower().replace(' ', '_')}_remains_blocked",
            "blocking status",
            gate_statuses[gate],
            gate_statuses[gate] in BLOCKING_STATUSES,
        )
    _add(rows, scenario, "no_live_betting_output", "False", live_output, live_output == False)
    return {"result": "PASS" if all(row["status"] == "PASS" for row in rows if row["scenario"] == scenario) else "FAIL", "blocked": blocked, "live_output": live_output}


def _scenario_b(rows: list[dict[str, str]]) -> dict[str, object]:
    scenario = "Scenario B - Synthetic fixture pass"
    schedule = _fixture(FIXTURES["schedule"])
    roster = _fixture(FIXTURES["roster"])
    role = _fixture(FIXTURES["role"])
    injury = _fixture(FIXTURES["injury"])
    odds = _fixture(FIXTURES["market_odds"])
    fixture_frames = {
        "schedule": schedule,
        "roster": roster,
        "role": role,
        "injury": injury,
        "market_odds": odds,
    }
    for name, df in fixture_frames.items():
        _add(rows, scenario, f"{name}_fixture_exists", "non-empty fixture", len(df), not df.empty)
        _add(rows, scenario, f"{name}_synthetic_label", SYNTHETIC_LABEL, _all_synthetic(df), _all_synthetic(df))
        _add(rows, scenario, f"{name}_gate_ready", "READY", "READY" if _ready(df) else "NOT READY", _ready(df))

    no_team_verify = not roster.get("Team Verify Flag", pd.Series(dtype=str)).fillna("").astype(str).str.contains("TEAM_VERIFY", regex=False).any()
    no_unknown_role = not role.get("Expected Role", pd.Series(dtype=str)).fillna("").astype(str).eq("Unknown").any()
    role_confidence_ok = pd.to_numeric(role.get("Role Confidence", pd.Series(dtype=float)), errors="coerce").fillna(0).ge(60).all()
    no_injury_uncertainty = not injury.get("Injury Status", pd.Series(dtype=str)).fillna("").astype(str).isin(["Unknown", "Out", "IR", "Doubtful"]).any()
    injury_action_ok = not injury.get("Projection Action", pd.Series(dtype=str)).fillna("").astype(str).eq("DO NOT USE").any()
    odds_matched = not odds.empty and odds.get("Market", pd.Series(dtype=str)).astype(str).eq("Receptions").all()
    odds_ready = _ready(odds) and odds_matched and odds.get("Line", pd.Series(dtype=float)).notna().all()
    implied = american_odds_implied_probability(odds["Over Odds"].iloc[0]) if not odds.empty else None
    model_prob = pd.to_numeric(odds["Model Over Prob"].iloc[0], errors="coerce") if not odds.empty else pd.NA
    synthetic_edge = None if implied is None or pd.isna(model_prob) else float(model_prob) - implied
    all_ready = all(_ready(df) for df in fixture_frames.values())
    forward_go = all(
        [
            all_ready,
            no_team_verify,
            no_unknown_role,
            role_confidence_ok,
            no_injury_uncertainty,
            injury_action_ok,
            odds_ready,
        ]
    )

    _add(rows, scenario, "no_team_verify_rows", "True", no_team_verify, no_team_verify)
    _add(rows, scenario, "no_unknown_role_blockers", "True", no_unknown_role, no_unknown_role)
    _add(rows, scenario, "role_confidence_60_plus", "True", role_confidence_ok, role_confidence_ok)
    _add(rows, scenario, "no_injury_uncertainty_blockers", "True", no_injury_uncertainty, no_injury_uncertainty)
    _add(rows, scenario, "injury_projection_action_safe", "True", injury_action_ok, injury_action_ok)
    _add(rows, scenario, "odds_matched", "True", odds_matched, odds_matched)
    _add(rows, scenario, "synthetic_implied_probability_calculated", "not blank", implied, implied is not None)
    _add(rows, scenario, "synthetic_edge_calculated", "not blank", synthetic_edge, synthetic_edge is not None)
    _add(
        rows,
        scenario,
        "forward_readiness_logic_can_go",
        "GO only when all fixture gates are READY and no blockers exist",
        "GO" if forward_go else "NO-GO",
        forward_go,
        notes="Dry-run logic only. No production live output is created.",
    )
    _add(
        rows,
        scenario,
        "synthetic_not_production_output",
        "fixtures remain under tests/fixtures only",
        str(FIXTURE_DIR),
        str(FIXTURE_DIR).endswith("tests\\fixtures") or str(FIXTURE_DIR).endswith("tests/fixtures"),
    )
    return {"result": "PASS" if forward_go else "FAIL", "gate_results": {name: "READY" if _ready(df) else "NOT READY" for name, df in fixture_frames.items()}}


def validate_forward_projection_dry_run() -> tuple[pd.DataFrame, dict[str, object]]:
    config_before = (ROOT / "config.yaml").read_text(encoding="utf-8")
    import_pack_path = output_path("google_sheets/latest_import_pack.zip")
    import_pack_mtime_before = import_pack_path.stat().st_mtime if import_pack_path.exists() else None
    rows: list[dict[str, str]] = []
    warnings: list[str] = []
    try:
        scenario_a = _scenario_a(rows)
        scenario_b = _scenario_b(rows)
    finally:
        config_after = (ROOT / "config.yaml").read_text(encoding="utf-8")
    import_pack_mtime_after = import_pack_path.stat().st_mtime if import_pack_path.exists() else None
    config_restored = config_before == config_after
    import_pack_unchanged = import_pack_mtime_before == import_pack_mtime_after
    _add(rows, "Dry-run safety", "config_restored", "True", config_restored, config_restored)
    _add(rows, "Dry-run safety", "import_pack_not_overwritten", "True", import_pack_unchanged, import_pack_unchanged)
    _add(rows, "Dry-run safety", "synthetic_report_label", SYNTHETIC_LABEL, SYNTHETIC_LABEL, True, notes="All fixture rows must remain synthetic/test-only.")
    validation = pd.DataFrame(rows)
    context = {
        "scenario_a": scenario_a,
        "scenario_b": scenario_b,
        "config_restored": config_restored,
        "import_pack_unchanged": import_pack_unchanged,
        "warnings": warnings,
        "live_betting_output_created": scenario_a["live_output"],
    }
    return validation, context


def write_reports(validation: pd.DataFrame, context: dict[str, object]) -> None:
    report_dir = output_path("run_reports/.keep").parent
    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = report_dir / "latest_forward_projection_dry_run.csv"
    md_path = report_dir / "latest_forward_projection_dry_run.md"
    validation.to_csv(csv_path, index=False)
    failed = validation[validation["status"] == "FAIL"]
    warnings = context.get("warnings", [])
    overall = "PASS" if failed.empty else "FAIL"
    failed_text = "None" if failed.empty else "\n".join(
        f"- {row.scenario} / {row.check_name}: expected {row.expected}, actual {row.actual}. {row.notes}"
        for row in failed.itertuples(index=False)
    )
    text = f"""# Forward Projection Dry Run

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Scenario A result: `{context['scenario_a']['result']}`

Scenario B result: `{context['scenario_b']['result']}`

Forward readiness logic result: `{overall}`

Blocked gates in real mode: `{', '.join(context['scenario_a']['blocked']) if context['scenario_a']['blocked'] else 'None'}`

Synthetic fixture gate results: `{context['scenario_b']['gate_results']}`

Whether live betting output was created: `{context['live_betting_output_created']}`

Warnings: `{', '.join(warnings) if warnings else 'None'}`

Synthetic label: `{SYNTHETIC_LABEL}`

Config restored: `{context['config_restored']}`

Import pack unchanged: `{context['import_pack_unchanged']}`

Next required action: Real 2026 schedule, roster, role, injury, and odds data are still required before live use. This dry-run is not a betting run.

## Failed Checks

{failed_text}
"""
    md_path.write_text(text, encoding="utf-8")


def main() -> None:
    validation, context = validate_forward_projection_dry_run()
    write_reports(validation, context)
    failed = validation[validation["status"] == "FAIL"]
    overall = "PASS" if failed.empty else "FAIL"
    print(f"Forward projection dry-run status: {overall}")
    print(f"Scenario A result: {context['scenario_a']['result']}")
    print(f"Scenario B result: {context['scenario_b']['result']}")
    print(f"Config restored: {context['config_restored']}")
    print(f"Live betting output created: {context['live_betting_output_created']}")
    print(f"Warnings: {', '.join(context['warnings']) if context['warnings'] else 'None'}")
    if not failed.empty:
        print(failed[["scenario", "check_name", "expected", "actual", "notes"]].to_string(index=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
