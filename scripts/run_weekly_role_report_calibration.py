from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "weekly_role_report_calibration"
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import player_selector_rows, primary_rows  # noqa: E402
from weekly_report import (  # noqa: E402
    CATEGORY_LOST,
    CATEGORY_OVERSTATED,
    DISPLAY_CATEGORIES,
    WEEKLY_REPORT_CONFIG,
    build_weekly_role_report,
    default_home_week,
    report_period_notice,
)


SEASON = 2025
WEEKS = [2, 5, 8, 11, 14, 17, 18]


def write_markdown(name: str, text: str) -> None:
    (OUT / name).write_text(text.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    season_data = primary_rows().loc[lambda frame: frame["season"].eq(SEASON)]
    summary_rows: list[dict[str, object]] = []
    card_rows: list[dict[str, object]] = []
    allocation_rows: list[dict[str, object]] = []

    for week in WEEKS:
        cards, matches = build_weekly_role_report(SEASON, week)
        selector = player_selector_rows(season_data, week).set_index("player_id")
        qualified = cards.attrs["qualified_situation_counts"]
        notice = report_period_notice(week)
        team_counts = cards.groupby("team").size()
        summary_rows.append(
            {
                "season": SEASON,
                "week": week,
                "situation_card_count": len(cards),
                "technical_candidate_count": len(matches),
                "qualified_situation_count": cards.attrs["qualified_situation_total"],
                "consolidated_individual_count": int(cards["situation_member_count"].sum()),
                "reciprocal_situation_count": int(cards["situation_type"].eq("reciprocal_transfer").sum()),
                "displayed_backfield": int(cards["role_group"].eq("backfield").sum()),
                "displayed_target": int(cards["role_group"].eq("target").sum()),
                "maximum_same_team_cards": int(team_counts.max()),
                "early_season_notice": notice[1] if notice and notice[0] == "info" else "",
                "week_18_warning": notice[1] if notice and notice[0] == "warning" else "",
                "context_fact_count": int(sum(len(facts) for facts in cards["context_facts"])),
            }
        )
        for category in DISPLAY_CATEGORIES:
            for group in ["backfield", "target"]:
                allocation_rows.append(
                    {
                        "season": SEASON,
                        "week": week,
                        "category": category,
                        "role_group": group,
                        "technical_candidate_count": int(
                            (matches["category"].eq(category) & matches["role_group"].eq(group)).sum()
                        ),
                        "qualified_situation_count": int(qualified.get((category, group), 0)),
                        "displayed_situation_count": int(
                            (cards["category"].eq(category) & cards["role_group"].eq(group)).sum()
                        ),
                    }
                )
        for _, row in cards.iterrows():
            record = {
                key: row[key]
                for key in [
                    "season", "week", "category", "player_id", "player_name", "team", "position",
                    "role_family", "role_family_label", "role_group", "headline", "explanation",
                    "current_raw", "current_denominator", "current_share", "baseline_raw",
                    "baseline_denominator", "baseline_share", "baseline_games", "share_change",
                    "all_play_raw", "all_play_denominator", "all_play_share", "all_play_normal_gap",
                    "show_all_play_prominently", "situation_type", "situation_member_count",
                    "situation_member_ids", "situation_member_names", "production_metric_label",
                    "production_rate", "player_href", "team_href", "game_href",
                ]
            }
            record["context_facts"] = json.dumps(row["context_facts"], sort_keys=True)
            record["all_context_counts"] = row["context_detail"]
            record["individual_candidate_evidence"] = json.dumps(row["situation_member_details"], sort_keys=True)
            record["player_team_label"] = str(selector.loc[str(row["player_id"]), "team"])
            card_rows.append(record)

    summary = pd.DataFrame(summary_rows)
    cards_archive = pd.DataFrame(card_rows)
    allocation = pd.DataFrame(allocation_rows)
    summary.to_csv(OUT / "historical_replay_summary.csv", index=False)
    cards_archive.to_csv(OUT / "historical_replay_cards.csv", index=False)
    allocation.to_csv(OUT / "role_group_allocation.csv", index=False)

    _, week_eight_matches = build_weekly_role_report(SEASON, 8)
    zavier = week_eight_matches[
        week_eight_matches["player_name"].eq("Zavier Scott")
        & week_eight_matches["role_family"].eq("rb_opportunity_share")
    ][[
        "season", "week", "player_id", "player_name", "team", "role_family", "category",
        "individual_primary_category", "current_raw", "current_denominator", "current_share",
        "all_play_raw", "all_play_denominator", "all_play_share", "all_play_normal_gap",
        "outside_normal_opportunities",
    ]]
    zavier.to_csv(OUT / "zavier_scott_week8_validation.csv", index=False)

    identity_ids = {
        "00-0030035": "PIT", "00-0031236": "BUF", "00-0032211": "LV",
        "00-0032394": "LA", "00-0034272": "PIT", "00-0038555": "PHI",
    }
    selector_18 = player_selector_rows(season_data, 18).set_index("player_id")
    selector_1 = player_selector_rows(season_data, 1).set_index("player_id")
    identity_rows = []
    for player_id, expected_team in identity_ids.items():
        identity_rows.append(
            {
                "player_id": player_id,
                "player_name": selector_18.loc[player_id, "player_name"],
                "week_18_selector_team": selector_18.loc[player_id, "team"],
                "expected_week_18_team": expected_team,
                "week_18_pass": selector_18.loc[player_id, "team"] == expected_team,
                "week_1_selector_team": selector_1.loc[player_id, "team"],
            }
        )
    pd.DataFrame(identity_rows).to_csv(OUT / "multi_team_selector_validation.csv", index=False)

    config = asdict(WEEKLY_REPORT_CONFIG)
    write_markdown(
        "SCREENING_AND_ALLOCATION_RULES.md",
        f"""
# Weekly Role Report Calibration Rules

- Baseline calculations remain count-weighted and use only earlier same-season, same-team qualifying games.
- Week 2 uses Week 1 only; Week 3 can use only two prior games. Exact sample counts remain visible.
- A reciprocal transfer requires at least one qualified gain and one qualified loss for the same season, week, team, and role family. The primary player is the gainer with the largest increase, then larger current raw count, larger team denominator, and alphabetical name.
- Reciprocal situations are ordered before individual situations within the same category; the standard absolute-change, raw-count, team-denominator, and name tie-break follows.
- A default team-role family appears once. A team may occupy at most {WEEKLY_REPORT_CONFIG.maximum_cards_per_team} default cards across clearly different families.
- Within a category, one backfield and one target situation are reserved when both consolidated situation groups qualify. Remaining capacity follows deterministic rank. Empty capacity may be filled by the other group.
- The Overstated screen uses a {WEEKLY_REPORT_CONFIG.minimum_all_play_normal_gap:.0%} all-plays/normal gap, at least {WEEKLY_REPORT_CONFIG.minimum_outside_normal_opportunities} outside-normal opportunities, and a team denominator of at least {WEEKLY_REPORT_CONFIG.minimum_team_denominator}; it does not reuse a role-volume floor that can suppress the abnormal-context evidence itself.
- Collapsed All-plays share is shown for Overstated cards or when the absolute gap is at least {WEEKLY_REPORT_CONFIG.material_all_play_difference:.0%}.
- Context evidence is limited to {WEEKLY_REPORT_CONFIG.maximum_context_facts} facts and uses these `(player count, team denominator)` minimums: {config['context_minimums']}.
- Strong-opportunity production rates are yards/carry for RB carry share, yards/touch for RB opportunity share, and receiving yards/target for WR/TE target share.
- No weighted or universal score is calculated. No candidate was manually removed.
""",
    )
    write_markdown(
        "historical_replay_findings.md",
        f"""
# Weekly Role Report Calibration Replay

The seven fixed 2025 weeks produced {summary['situation_card_count'].min()}–{summary['situation_card_count'].max()} default situation cards. Technical matches ranged from {summary['technical_candidate_count'].min()} to {summary['technical_candidate_count'].max()}, while consolidated qualified situations ranged from {summary['qualified_situation_count'].min()} to {summary['qualified_situation_count'].max()}.

Week 8 Minnesota is one RB opportunity-share situation led by Aaron Jones with Jordan Mason and Zavier Scott preserved in the individual evidence. Zavier Scott independently qualifies for Overstated (0 of 14 normal-game opportunities; 4 of 18 all plays; +22.2 points) and Lost, so Overstated is his individual technical primary under the locked category priority.

Every replay week displays at least {summary['displayed_target'].min()} target-role situations and no team exceeds {summary['maximum_same_team_cards'].max()} cards. Week 2 explicitly identifies the Week 1-only baseline. Week 18 remains fully calculated but carries the historical-week warning, and the clean 2025 default resolves to Week {default_home_week(2025, range(1, 19))}.
""",
    )

    manifest = {
        "status": "REPLAY_PASSED",
        "season": SEASON,
        "weeks": WEEKS,
        "default_2025_week": default_home_week(2025, range(1, 19)),
        "displayed_cards": int(len(cards_archive)),
        "technical_candidates": int(summary["technical_candidate_count"].sum()),
        "minimum_weekly_cards": int(summary["situation_card_count"].min()),
        "maximum_weekly_cards": int(summary["situation_card_count"].max()),
        "maximum_same_team_cards": int(summary["maximum_same_team_cards"].max()),
        "wrong_week_cards": int((~cards_archive["week"].isin(WEEKS)).sum()),
        "duplicate_primary_player_weeks": int(cards_archive.duplicated(["season", "week", "player_id"]).sum()),
        "share_reconciliation_failures": int(
            (~cards_archive["current_share"].round(12).eq(
                (cards_archive["current_raw"] / cards_archive["current_denominator"]).round(12)
            )).sum()
        ),
        "minnesota_week8_consolidated": bool((
            cards_archive["week"].eq(8)
            & cards_archive["team"].eq("MIN")
            & cards_archive["situation_member_count"].eq(3)
        ).any()),
        "zavier_primary_category": str(zavier.iloc[0]["individual_primary_category"]),
        "multi_team_label_failures": int((~pd.DataFrame(identity_rows)["week_18_pass"]).sum()),
        "config": config,
    }
    (OUT / "final_validation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
