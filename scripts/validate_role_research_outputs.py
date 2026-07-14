from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import canonical_quality_profile, load_opportunity_events, load_production_data, load_role_data, load_situational_data, primary_rows  # noqa: E402


PUBLIC_FILES = [
    ROOT / "dashboard" / "Home.py",
    ROOT / "dashboard" / "home_page.py",
    ROOT / "dashboard" / "app.py",
    ROOT / "dashboard" / "research_ui.py",
    *sorted((ROOT / "dashboard" / "pages").glob("0[1-5]_*.py")),
]
PROHIBITED = [
    r"\boverall_signal_score\b", r"\bmatchup_score\b", r"\brecommended_user_action\b",
    r"\bconfidence grade\b", r"\bsportsbook\b", r"\bbetting\b", r"\bodds\b",
    r"\bsustainable\b", r"\bpersistent\b", r"\bemerging\b", r"\bdeteriorating\b",
    r"\bsignal command center\b", r"\btop 5\b", r"\btop 25\b",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(name: str, passed: bool, observed: object, expected: object) -> dict[str, object]:
    return {"check": name, "passed": bool(passed), "observed": observed, "expected": expected}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "role_research")
    args = parser.parse_args()
    manifest_path = args.output_dir / "build_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit_2025 = json.loads((args.output_dir / "canonical_audit_2025.json").read_text(encoding="utf-8"))
    canonical = load_role_data()
    public = primary_rows()
    situational = load_situational_data()
    production = load_production_data()
    events = load_opportunity_events()
    profile = canonical_quality_profile(canonical)
    checks: list[dict[str, object]] = []
    checks += [
        check("canonical_seasons", profile["seasons"] == list(range(2018, 2026)), profile["seasons"], list(range(2018, 2026))),
        check("latest_completed_season", profile["latest_completed_season"] == 2025, profile["latest_completed_season"], 2025),
        check("canonical_duplicate_keys", profile["duplicate_keys"] == 0, profile["duplicate_keys"], 0),
        check("canonical_required_missing_cells", profile["required_missing_cells"] == 0, profile["required_missing_cells"], 0),
        check("canonical_identity_coverage", profile["identity_coverage"] == 1.0, profile["identity_coverage"], 1.0),
        check("confirmed_partial_excluded", not public["confirmed_partial_game"].any(), int(public["confirmed_partial_game"].sum()), 0),
        check("suspected_partial_visible", bool(public["suspected_partial_game"].any()), int(public["suspected_partial_game"].sum()), "> 0"),
        check("situational_seasons", sorted(situational["season"].unique().tolist()) == [2023, 2024, 2025], sorted(situational["season"].unique().tolist()), [2023, 2024, 2025]),
        check("production_seasons", sorted(production["season"].unique().tolist()) == [2023, 2024, 2025], sorted(production["season"].unique().tolist()), [2023, 2024, 2025]),
        check("event_seasons", sorted(events["season"].unique().tolist()) == [2023, 2024, 2025], sorted(events["season"].unique().tolist()), [2023, 2024, 2025]),
        check("situational_share_range", situational["share"].between(0, 1).all(), [float(situational["share"].min()), float(situational["share"].max())], "[0, 1]"),
        check("situational_numerator_le_denominator", situational["raw_opportunities"].le(situational["team_opportunities"]).all(), int((situational["raw_opportunities"] > situational["team_opportunities"]).sum()), 0),
    ]
    sit_key = ["season", "week", "game_id", "team", "player_id", "role_family", "context"]
    event_key = ["season", "week", "game_id", "play_id", "team", "player_id", "opportunity_type"]
    prod_key = ["season", "week", "game_id", "team", "player_id"]
    checks += [
        check("situational_unique_grain", not situational.duplicated(sit_key).any(), int(situational.duplicated(sit_key).sum()), 0),
        check("event_unique_grain", not events.duplicated(event_key).any(), int(events.duplicated(event_key).sum()), 0),
        check("production_unique_grain", not production.duplicated(prod_key).any(), int(production.duplicated(prod_key).sum()), 0),
    ]
    canonical_2025 = canonical[canonical["season"].eq(2025)]
    confirmed_2025 = canonical_2025[canonical_2025["confirmed_partial_game"]]
    checks += [
        check("canonical_2025_rows", len(canonical_2025) == audit_2025["canonical_rows"], len(canonical_2025), audit_2025["canonical_rows"]),
        check("canonical_2025_games", canonical_2025["game_id"].nunique() == 272, int(canonical_2025["game_id"].nunique()), 272),
        check("canonical_2025_weeks", sorted(canonical_2025["week"].astype(int).unique().tolist()) == list(range(1, 19)), sorted(canonical_2025["week"].astype(int).unique().tolist()), list(range(1, 19))),
        check("2025_opportunity_join_coverage", audit_2025["opportunity_to_identity_coverage"] == 1.0, audit_2025["opportunity_to_identity_coverage"], 1.0),
        check("2025_participation_join_coverage", audit_2025["participating_player_to_identity_coverage"] >= 0.999, audit_2025["participating_player_to_identity_coverage"], ">= 0.999"),
        check("2025_participation_play_coverage", audit_2025["participation_play_coverage"] == 1.0, audit_2025["participation_play_coverage"], 1.0),
        check("2025_confirmed_partial_evidence_policy", confirmed_2025["partial_game_reason"].eq("EXPLICIT_PBP_INJURY_NO_OFFENSIVE_RETURN_AND_ROLE_DROP").all(), sorted(confirmed_2025["partial_game_reason"].dropna().unique().tolist()), ["EXPLICIT_PBP_INJURY_NO_OFFENSIVE_RETURN_AND_ROLE_DROP"]),
        check("2025_suspected_partial_visible", int(public.loc[public["season"].eq(2025), "suspected_partial_game"].sum()) == audit_2025["suspected_partial_family_rows"], int(public.loc[public["season"].eq(2025), "suspected_partial_game"].sum()), audit_2025["suspected_partial_family_rows"]),
        check("2025_no_detector_or_betting_columns", not audit_2025["detector_or_betting_columns_present"], audit_2025["detector_or_betting_columns_present"], []),
        check("2025_temporal_and_season_boundary", audit_2025["temporal_and_season_boundary_checks_passed"], audit_2025["temporal_and_season_boundary_checks_passed"], True),
    ]
    canonical_2325 = public[public["season"].isin([2023, 2024, 2025])]
    reconciliation = []
    key = ["season", "week", "game_id", "team", "player_id", "role_family"]
    for context, suffix in [("all_play", "all"), ("normal_game", "normal")]:
        split = situational[situational["context"].eq(context)][key + ["raw_opportunities", "team_opportunities"]]
        joined = canonical_2325.merge(split, on=key, how="inner")
        raw_diff = (joined["raw_opportunities"] - joined[f"raw_opportunities_{suffix}"]).abs().sum()
        denom_diff = (joined["team_opportunities"] - joined[f"team_opportunities_{suffix}"]).abs().sum()
        reconciliation.append({"context": context, "matched_rows": int(len(joined)), "raw_absolute_difference": float(raw_diff), "denominator_absolute_difference": float(denom_diff)})
        checks.append(check(f"{context}_canonical_reconciliation", raw_diff == 0 and denom_diff == 0, reconciliation[-1], "zero absolute count difference"))
    output_hashes = {
        "situational_sha256": sha256(args.output_dir / "situational_player_week.csv.gz"),
        "production_sha256": sha256(args.output_dir / "game_player_usage.csv.gz"),
        "opportunity_events_sha256": sha256(args.output_dir / "opportunity_events.csv.gz"),
    }
    for key_name, observed in output_hashes.items():
        checks.append(check(f"manifest_{key_name}", observed == manifest[key_name], observed, manifest[key_name]))
    public_text = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_FILES).lower()
    language_failures = [pattern for pattern in PROHIBITED if re.search(pattern, public_text)]
    checks.append(check("public_language_guardrail", not language_failures, language_failures, []))

    report = {
        "status": "PASS" if all(item["passed"] for item in checks) else "FAIL",
        "canonical_profile": profile,
        "descriptive_2025_audit": audit_2025,
        "source_seasons_physically_opened_for_situational_build": manifest["source_seasons_physically_opened"],
        "seasons_admitted_to_situational_outputs": manifest["seasons_admitted"],
        "reconciliation": reconciliation,
        "output_hashes": output_hashes,
        "checks": checks,
    }
    json_path = args.output_dir / "validation_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = [
        "# PropWar Role Research Data Validation", "", f"Status: **{report['status']}**", "",
        f"- Canonical rows: {profile['rows']:,}",
        f"- Seasons: {profile['seasons']}",
        f"- Duplicate canonical keys: {profile['duplicate_keys']}",
        f"- Required missing cells: {profile['required_missing_cells']}",
        f"- Identity coverage: {profile['identity_coverage']:.1%}",
        f"- Confirmed partial rows in source: {profile['confirmed_partial_rows']:,}; excluded from public primary rows.",
        f"- Suspected partial rows in public primary data: {int(public['suspected_partial_game'].sum()):,}; included and visible.",
        f"- 2025 played games/weeks: {audit_2025['played_games']} games across Weeks 1–18.",
        f"- 2025 opportunity/participation identity coverage: {audit_2025['opportunity_to_identity_coverage']:.3%} / {audit_2025['participating_player_to_identity_coverage']:.3%}.",
        f"- 2025 injury PBP identity resolution: {audit_2025['injury_pbp_identity_resolution_rate']:.3%}; injury report timestamps available: {audit_2025['injury_report_timestamp_available']}.",
        f"- Situational source seasons physically opened: {manifest['source_seasons_physically_opened']}",
        f"- Seasons admitted to situational outputs: {manifest['seasons_admitted']}", "",
        "| Check | Passed | Observed | Expected |", "|---|---:|---|---|",
    ]
    for item in checks:
        md.append(f"| {item['check']} | {item['passed']} | `{item['observed']}` | `{item['expected']}` |")
    (args.output_dir / "DATA_VALIDATION.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
