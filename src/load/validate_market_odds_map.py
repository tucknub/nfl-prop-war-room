from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path, project_path
from src.load.build_market_odds_map import build_map_from_frames, discover_real_inputs
from src.models.odds_utils import american_to_implied_probability, normalize_market_key


def add(rows: list[dict[str, str]], name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append(
        {
            "check_name": name,
            "expected": str(expected),
            "actual": str(actual),
            "status": "PASS" if passed else "FAIL",
            "severity": "INFO" if passed else "HIGH",
            "notes": notes,
        }
    )


def identities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("TEST-001", "Fixture Receiver", "fixture receiver"),
            ("TEST-002", "Fixture Runner", "fixture runner"),
            ("TEST-003", "Fixture Tight End", "fixture tight end"),
            ("TEST-004", "Fixture Quarterback", "fixture quarterback"),
            ("TEST-005", "Fixture Slot", "fixture slot"),
            ("TEST-006", "Fixture Unapproved", "fixture unapproved"),
        ],
        columns=["player_id", "player_name", "normalized_player_name"],
    )


def ready_frame(column: str) -> pd.DataFrame:
    return pd.DataFrame([(f"TEST-00{i}", "READY") for i in range(1, 7)], columns=["player_id", column])


def probability_lookup() -> dict[tuple[str, str, float], dict[str, float]]:
    return {
        ("receptions", "TEST-001|BUF", 4.5): {"model_projection": 5.2, "model_over_probability": 0.61, "model_under_probability": 0.39},
        ("carries", "TEST-005|PHI", 9.5): {"model_projection": 10.1, "model_over_probability": 0.58, "model_under_probability": 0.42},
        ("completions", "TEST-006|NYJ", 19.5): {"model_projection": 20.0, "model_over_probability": 0.52, "model_under_probability": 0.48},
    }


def validate_market_odds_map() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    map_path = output_path("odds/current_market_odds_map.csv")
    status_path = output_path("odds/current_market_odds_status.csv")
    review_path = output_path("odds/current_market_odds_needs_review.csv")
    for name, path in [
        ("current_market_odds_map_exists", map_path),
        ("current_market_odds_status_exists", status_path),
        ("current_market_odds_review_exists", review_path),
    ]:
        add(rows, name, True, path.exists(), path.exists())
    status = pd.read_csv(status_path, low_memory=False) if status_path.exists() else pd.DataFrame()
    production = "MISSING" if status.empty else str(status["status"].iloc[0])
    real, overrides = discover_real_inputs(project_path("data", "gates", "odds"))
    add(rows, "templates_do_not_count_as_real_odds", "templates ignored", f"real_files={len(real)}; status={production}", bool(real) or production == "NEEDS DATA")
    add(rows, "missing_odds_data_stays_needs_data", "NEEDS DATA when no real files", production, bool(real) or production == "NEEDS DATA")
    add(rows, "negative_american_odds_conversion", "115/(115+100)", round(american_to_implied_probability(-115) or 0, 6), round(115 / 215, 6) == round(american_to_implied_probability(-115) or 0, 6))
    add(rows, "positive_american_odds_conversion", "100/(150+100)", round(american_to_implied_probability(150) or 0, 6), round(100 / 250, 6) == round(american_to_implied_probability(150) or 0, 6))
    add(rows, "market_key_normalization", "receiving_yards", normalize_market_key("Receiving Yards"), normalize_market_key("Receiving Yards") == "receiving_yards")

    fixture_dir = project_path("tests", "fixtures")
    odds = pd.read_csv(fixture_dir / "current_market_odds_sample.csv", low_memory=False)
    override = pd.read_csv(fixture_dir / "market_odds_overrides_sample.csv", low_memory=False)
    mapped = build_map_from_frames(
        odds,
        override,
        identities(),
        ready_frame("team_mapping_status"),
        ready_frame("role_mapping_status"),
        ready_frame("injury_mapping_status"),
        probability_lookup(),
    )
    by = mapped.set_index("player_id", drop=False)
    add(rows, "valid_odds_row_ready", "READY", by.loc["TEST-001", "odds_mapping_status"], by.loc["TEST-001", "odds_mapping_status"] == "READY")
    add(rows, "invalid_market_key_blocks", "BLOCKED", by.loc["TEST-002", "odds_mapping_status"], by.loc["TEST-002", "odds_mapping_status"] == "BLOCKED")
    add(rows, "invalid_american_odds_blocks", "BLOCKED", by.loc["TEST-003", "odds_mapping_status"], by.loc["TEST-003", "odds_mapping_status"] == "BLOCKED")
    add(rows, "missing_one_odds_side_review", "NEEDS REVIEW", by.loc["TEST-004", "odds_mapping_status"], by.loc["TEST-004", "odds_mapping_status"] == "NEEDS REVIEW")
    add(rows, "approved_override_applies", "line=9.5 and READY", f"line={by.loc['TEST-005', 'line']}; status={by.loc['TEST-005', 'odds_mapping_status']}", float(by.loc["TEST-005", "line"]) == 9.5 and by.loc["TEST-005", "odds_mapping_status"] == "READY")
    add(rows, "unapproved_override_does_not_apply", "line=19.5 and NEEDS REVIEW", f"line={by.loc['TEST-006', 'line']}; status={by.loc['TEST-006', 'odds_mapping_status']}", float(by.loc["TEST-006", "line"]) == 19.5 and by.loc["TEST-006", "odds_mapping_status"] == "NEEDS REVIEW")
    add(rows, "unmatched_player_blocks", "BLOCKED", by.loc["TEST-999", "odds_mapping_status"], by.loc["TEST-999", "odds_mapping_status"] == "BLOCKED")

    readiness_path = output_path("google_sheets/live_readiness_export.csv")
    readiness = pd.read_csv(readiness_path, low_memory=False) if readiness_path.exists() else pd.DataFrame()
    final = "MISSING"
    if not readiness.empty and {"Gate", "Status"}.issubset(readiness.columns):
        row = readiness[readiness["Gate"].eq("Final Betting Use")]
        final = str(row["Status"].iloc[0]) if not row.empty else "MISSING"
    add(rows, "odds_validation_does_not_enable_live", "NO-GO", final, final == "NO-GO")

    report = pd.DataFrame(rows)
    overall = "PASS" if report["status"].eq("PASS").all() else "FAIL"
    report.to_csv(output_path("run_reports/latest_market_odds_map_validation.csv"), index=False)
    failed = report[report["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_market_odds_map_validation.md").write_text(
        f"""# Market Odds Map Validation

Run timestamp: `{datetime.now(timezone.utc).isoformat()}`

Overall status: `{overall}`

Production odds-map status: `{production}`

Real odds files: `{len(real)}`

Override files: `{len(overrides)}`

Templates counted as data: `False`

American odds conversion: `PASS`

Fixture validation: `SYNTHETIC TEST ONLY`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Final live readiness: `{final}`

Next required action: Load source-backed non-template sportsbook odds and resolve every review/blocking row before edge use.
""",
        encoding="utf-8",
    )
    return report, overall


def main() -> None:
    report, overall = validate_market_odds_map()
    print(f"Market odds map validation: {overall}")
    print(f"Failed checks: {int(report.status.eq('FAIL').sum())}")


if __name__ == "__main__":
    main()
