from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "propwar_correctness_audit"
REQUIRED = {
    "TARGETED_CORRECTNESS_AUDIT.md",
    "calculation_discrepancies.csv",
    "cross_page_reconciliation.csv",
    "link_state_validation.csv",
    "explorer_validation.csv",
    "public_language_scan.csv",
    "final_validation.json",
    "COMMANDS_RUN.md",
}


def validate_descriptive(final: dict) -> list[str]:
    errors: list[str] = []
    checks = pd.read_csv(OUT / "calculation_discrepancies.csv")
    if final["sample_coverage"] != {
        "rb_players": 10, "wr_players": 10, "te_players": 10, "teams": 10,
        "games": 10, "home_rows": 25, "reports": 7, "explorer_cases": 18,
    }:
        errors.append("sample coverage differs from the frozen audit design")
    displayed = checks[checks["displayed_percentage"].notna() & checks["denominator"].gt(0)].copy()
    formula = displayed["numerator"] / displayed["denominator"]
    if (formula - displayed["expected_percentage"]).abs().max() > 1e-12:
        errors.append("an independent expected share is not numerator / denominator")
    if checks.loc[checks["audit_area"].eq("Player"), "status"].eq("FAIL").any():
        errors.append("player Season/Last 8/Last 4/Last 2 checks did not reconcile")
    if not checks.loc[checks["status"].eq("FAIL"), "sample_type"].eq("situational").all():
        errors.append("undocumented non-situational calculation failures exist")
    team_quality = final.get("team_quality_checks", {})
    for key in [
        "duplicate_player_team_week_family_keys", "shares_above_100_percent",
        "zero_or_negative_denominators", "inconsistent_team_game_family_denominators",
    ]:
        if team_quality.get(key) != 0:
            errors.append(f"team quality check failed: {key}")
    if not team_quality.get("numeric_sort_25_before_8_3") or not team_quality.get("null_sort_last"):
        errors.append("numeric or null percentage sorting failed")
    home = pd.read_csv(OUT / "home_validation.csv")
    if not home["no_future_leakage"].all() or not home["same_season"].all():
        errors.append("Home temporal or season-boundary check failed")
    if int(home["status"].eq("FAIL").sum()) != final["results"]["home_failures"]:
        errors.append("Home failure count does not match final manifest")
    games = pd.read_csv(OUT / "game_validation.csv")
    if not games["production_matches_source"].all():
        errors.append("game production values do not reconcile to weekly source")
    categories = set(";".join(games["categories"].dropna().astype(str).unique()).split(";"))
    for category in {"overtime", "blowout", "week_18", "traded_player", "confirmed_partial", "suspected_partial"}:
        if category not in categories:
            errors.append(f"missing required game category: {category}")
    for raw, denominator, share in [
        ("team_share_raw", "team_share_denominator", "team_share"),
        ("normal_raw", "normal_denominator", "normal_share"),
        ("prior_raw", "prior_denominator", "prior_share"),
    ]:
        eligible = games[games[denominator].gt(0)]
        if not eligible.empty and ((eligible[raw] / eligible[denominator]) - eligible[share]).abs().max() > 1e-12:
            errors.append(f"game ratio mismatch: {share}")
    players = pd.read_csv(OUT / "player_validation.csv")
    if not players["role_rank_matches"].all():
        errors.append("independent player team-role rank mismatch")
    return errors


def validate_cross_page(final: dict) -> list[str]:
    frame = pd.read_csv(OUT / "cross_page_reconciliation.csv")
    errors = []
    actual = int(frame["status"].eq("FAIL").sum())
    if actual != final["results"]["cross_page_failures"]:
        errors.append("cross-page failure count differs from final manifest")
    if actual:
        errors.append("identical-filter cross-page values disagree")
    return errors


def validate_link_state(final: dict) -> list[str]:
    frame = pd.read_csv(OUT / "link_state_validation.csv")
    required_checks = {
        "Home player links", "Home team links", "Team player links", "Game player links",
        "Report player links", "Explorer player links", "Direct player URL", "Invalid player value",
        "Direct team URL", "Invalid team value", "Research Admin navigation",
    }
    errors = []
    if not required_checks.issubset(set(frame["check"])):
        errors.append("link/state matrix is incomplete")
    if int(frame["status"].eq("FAIL").sum()) != final["results"]["link_state_failures"]:
        errors.append("link/state failure count differs from final manifest")
    if frame.loc[frame["check"].eq("Research Admin navigation"), "status"].iloc[0] != "PASS":
        errors.append("Research Admin is exposed")
    return errors


def validate_explorer(final: dict) -> list[str]:
    frame = pd.read_csv(OUT / "explorer_validation.csv")
    errors = []
    if frame["case_id"].nunique() != final["sample_coverage"]["explorer_cases"]:
        errors.append("Explorer matrix case count differs from manifest")
    if int(frame["status"].eq("FAIL").sum()) != final["results"]["explorer_failures"]:
        errors.append("Explorer failure count differs from final manifest")
    failures = frame[frame["status"].eq("FAIL")]
    if not failures.empty and not failures["likely_cause"].str.contains("zero-opportunity", na=False).all():
        errors.append("Explorer discrepancies are not transparently reason-coded")
    return errors


def validate_language(final: dict) -> list[str]:
    frame = pd.read_csv(OUT / "public_language_scan.csv")
    actual = int(frame["status"].eq("FAIL").sum())
    return [] if actual == final["results"]["language_failures"] == 0 else ["public-language guardrail failed"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--section", default="all",
        choices=["all", "descriptive", "cross-page", "link-state", "explorer", "language"],
    )
    args = parser.parse_args()
    missing = sorted(REQUIRED - {path.name for path in OUT.glob("*")})
    errors = [f"missing required artifact: {name}" for name in missing]
    if missing:
        print("\n".join(errors))
        return 1
    final = json.loads((OUT / "final_validation.json").read_text(encoding="utf-8"))
    validators = {
        "descriptive": validate_descriptive,
        "cross-page": validate_cross_page,
        "link-state": validate_link_state,
        "explorer": validate_explorer,
        "language": validate_language,
    }
    selected = validators if args.section == "all" else {args.section: validators[args.section]}
    for name, validator in selected.items():
        section_errors = validator(final)
        errors.extend(f"{name}: {error}" for error in section_errors)
    if errors:
        print("VALIDATION FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"VALIDATION PASSED: {args.section}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
