from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "weekly_role_report_calibration"
sys.path.insert(0, str(ROOT / "dashboard"))

from weekly_report import (  # noqa: E402
    CATEGORY_OVERSTATED,
    DISPLAY_CATEGORIES,
    WEEKLY_REPORT_CONFIG,
    build_weekly_role_report,
    default_home_week,
)


WEEKS = [2, 5, 8, 11, 14, 17, 18]
REQUIRED = [
    "SCREENING_AND_ALLOCATION_RULES.md",
    "historical_replay_summary.csv",
    "historical_replay_cards.csv",
    "role_group_allocation.csv",
    "historical_replay_findings.md",
    "zavier_scott_week8_validation.csv",
    "multi_team_selector_validation.csv",
    "final_validation.json",
    "mobile_qa.md",
    "desktop_qa.md",
    "protected_scope_validation.json",
    "COMMANDS_RUN.md",
]
REQUIRED_SCREENSHOTS = [
    "mobile_home_week17.png",
    "mobile_home_week17_expanded.png",
    "mobile_home_week8_minnesota.png",
    "mobile_home_week2_notice.png",
    "mobile_home_week18_warning.png",
    "desktop_home_week17.png",
    "desktop_home_week8_minnesota.png",
]


def main() -> int:
    failures: list[str] = []
    failures.extend(f"missing artifact: {name}" for name in REQUIRED if not (OUT / name).exists())
    failures.extend(
        f"missing screenshot: {name}"
        for name in REQUIRED_SCREENSHOTS
        if not (OUT / "screenshots" / name).exists()
    )
    if failures:
        print("\n".join(failures))
        return 1
    summary = pd.read_csv(OUT / "historical_replay_summary.csv")
    archive = pd.read_csv(OUT / "historical_replay_cards.csv", dtype={"player_id": str})
    allocation = pd.read_csv(OUT / "role_group_allocation.csv")
    if summary["week"].tolist() != WEEKS:
        failures.append("replay weeks differ from the frozen calibration set")
    if not summary["situation_card_count"].between(8, 15).all():
        failures.append("weekly situation volume is outside 8–15")
    if summary["maximum_same_team_cards"].gt(WEEKLY_REPORT_CONFIG.maximum_cards_per_team).any():
        failures.append("same-team cap exceeded")
    if archive.duplicated(["season", "week", "player_id"]).any():
        failures.append("duplicate primary player-week card")
    if not np.allclose(archive["current_share"], archive["current_raw"] / archive["current_denominator"]):
        failures.append("normal-game share reconciliation failed")
    if default_home_week(2025, range(1, 19)) != 17:
        failures.append("2025 default does not resolve to Week 17")

    regenerated = []
    for week in WEEKS:
        cards, _ = build_weekly_role_report(2025, week)
        regenerated.append(cards)
        if not cards["week"].eq(week).all():
            failures.append(f"Week {week}: wrong-week card")
        if cards.groupby("team").size().gt(WEEKLY_REPORT_CONFIG.maximum_cards_per_team).any():
            failures.append(f"Week {week}: same-team cap")
        if cards.duplicated(["team", "role_family"]).any():
            failures.append(f"Week {week}: duplicate team-role situation")
        qualified = cards.attrs["qualified_situation_counts"]
        for category in DISPLAY_CATEGORIES:
            qualified_groups = {
                group for group in ["backfield", "target"] if qualified.get((category, group), 0) > 0
            }
            displayed_groups = set(cards.loc[cards["category"].eq(category), "role_group"])
            if qualified_groups == {"backfield", "target"} and len(displayed_groups) < 2:
                failures.append(f"Week {week}: {category} role-group reservation")

    regenerated = pd.concat(regenerated, ignore_index=True)
    archive_keys = set(archive[["season", "week", "player_id", "category", "role_family"]].astype(str).itertuples(index=False, name=None))
    regenerated_keys = set(regenerated[["season", "week", "player_id", "category", "role_family"]].astype(str).itertuples(index=False, name=None))
    if archive_keys != regenerated_keys:
        failures.append("archive differs from regenerated cards")

    minnesota = archive[
        archive["week"].eq(8) & archive["team"].eq("MIN")
        & archive["role_family"].eq("rb_opportunity_share")
    ]
    if len(minnesota) != 1 or int(minnesota.iloc[0]["situation_member_count"]) != 3:
        failures.append("Minnesota Week 8 is not one three-player situation")
    zavier = pd.read_csv(OUT / "zavier_scott_week8_validation.csv")
    if set(zavier["category"]) != {CATEGORY_OVERSTATED, "Opportunity Lost"}:
        failures.append("Zavier Scott technical categories are not reconciled")
    if not zavier["individual_primary_category"].eq(CATEGORY_OVERSTATED).all():
        failures.append("Zavier Scott primary technical category is not Overstated")
    identities = pd.read_csv(OUT / "multi_team_selector_validation.csv")
    if not identities["week_18_pass"].all():
        failures.append("multi-team selector labels failed")

    for (week, category), rows in allocation.groupby(["week", "category"]):
        qualified_groups = set(rows.loc[rows["qualified_situation_count"].gt(0), "role_group"])
        displayed_groups = set(rows.loc[rows["displayed_situation_count"].gt(0), "role_group"])
        if qualified_groups == {"backfield", "target"} and displayed_groups != qualified_groups:
            failures.append(f"Week {week}: allocation archive lacks both groups for {category}")

    manifest_path = OUT / "final_validation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["independent_validation"] = {
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "regenerated_cards": int(len(regenerated)),
        "archive_cards": int(len(archive)),
    }
    manifest["status"] = "PASS" if not failures else "FAIL"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if failures:
        print("CALIBRATION VALIDATION FAILED")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print(f"CALIBRATION VALIDATION PASSED: {len(regenerated)} cards across {len(WEEKS)} weeks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
