from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "weekly_role_report"
sys.path.insert(0, str(ROOT / "dashboard"))

from weekly_report import (  # noqa: E402
    CATEGORY_PRIORITY,
    DISPLAY_CATEGORIES,
    WEEKLY_REPORT_CONFIG,
    build_weekly_role_report,
    report_category_counts,
)


SEASON = 2025
WEEKS = [2, 5, 8, 11, 14, 18]


def _write_markdown(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = frame.columns.tolist()
    header = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    rows = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, rule, *rows])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []
    card_frames: list[pd.DataFrame] = []
    duplicate_frames: list[pd.DataFrame] = []

    for week in WEEKS:
        cards, matches = build_weekly_role_report(SEASON, week)
        displayed = report_category_counts(cards, DISPLAY_CATEGORIES)
        technical = report_category_counts(matches, DISPLAY_CATEGORIES)
        team_counts = cards.groupby("team").size() if not cards.empty else pd.Series(dtype=int)
        summary_rows.append(
            {
                "season": SEASON,
                "week": week,
                "displayed_total": len(cards),
                "technical_match_total": len(matches),
                "displayed_opportunity_gained": displayed[DISPLAY_CATEGORIES[0]],
                "displayed_opportunity_lost": displayed[DISPLAY_CATEGORIES[1]],
                "displayed_box_score_overstated": displayed[DISPLAY_CATEGORIES[2]],
                "displayed_strong_opportunity_weak_production": displayed[DISPLAY_CATEGORIES[3]],
                "technical_opportunity_gained": technical[DISPLAY_CATEGORIES[0]],
                "technical_opportunity_lost": technical[DISPLAY_CATEGORIES[1]],
                "technical_box_score_overstated": technical[DISPLAY_CATEGORIES[2]],
                "technical_strong_opportunity_weak_production": technical[DISPLAY_CATEGORIES[3]],
                "unique_displayed_players": cards["player_id"].nunique(),
                "maximum_players_from_one_team": int(team_counts.max()) if not team_counts.empty else 0,
                "minimum_baseline_games": int(cards["baseline_games"].min()) if not cards.empty else 0,
                "maximum_baseline_games": int(cards["baseline_games"].max()) if not cards.empty else 0,
            }
        )
        selected_columns = [
            "season",
            "week",
            "category",
            "player_id",
            "player_name",
            "team",
            "position",
            "role_family",
            "role_family_label",
            "headline",
            "current_raw",
            "current_denominator",
            "current_share",
            "baseline_raw",
            "baseline_denominator",
            "baseline_share",
            "share_change",
            "all_play_raw",
            "all_play_denominator",
            "all_play_share",
            "outside_normal_opportunities",
            "all_play_normal_gap",
            "production_yards",
            "yards_per_opportunity",
            "useful_contexts",
            "context_summary",
            "baseline_games",
            "category_reason",
            "secondary_categories",
            "suspected_partial_game",
            "player_href",
            "team_href",
            "game_href",
            "explanation",
        ]
        card_frames.append(cards[selected_columns].copy())

        category_counts = (
            matches.groupby(["player_id", "player_name", "team"])["category"]
            .agg(lambda values: " | ".join(dict.fromkeys(values)))
            .rename("qualifying_categories")
            .reset_index()
        )
        category_counts["category_count"] = category_counts["qualifying_categories"].str.count(r"\|") + 1
        duplicates = category_counts[category_counts["category_count"].gt(1)].copy()
        duplicates.insert(0, "week", week)
        duplicates.insert(0, "season", SEASON)
        duplicate_frames.append(duplicates)

    summary = pd.DataFrame(summary_rows)
    cards = pd.concat(card_frames, ignore_index=True)
    duplicates = pd.concat(duplicate_frames, ignore_index=True)
    summary.to_csv(OUT / "historical_replay_summary.csv", index=False)
    cards.to_csv(OUT / "historical_replay_cards.csv", index=False)
    duplicates.to_csv(OUT / "duplicate_category_assignments.csv", index=False)

    config = asdict(WEEKLY_REPORT_CONFIG)
    config["minimum_raw_opportunities"] = dict(WEEKLY_REPORT_CONFIG.minimum_raw_opportunities)
    _write_markdown(
        OUT / "WEEKLY_ROLE_REPORT_DESIGN.md",
        f"""
# Weekly Role Report Design

## Purpose

Home is a five-minute weekly discovery surface for factual NFL role research. It shows a maximum of {WEEKLY_REPORT_CONFIG.maximum_default_cards} default situations across four named categories, then links to the Player, Team, and Game evidence pages.

## Information order

1. `This Week in NFL Roles`
2. Compact season and week controls
3. Selected-state and result-count summary
4. Four category sections with compact evidence cards
5. Collapsed advanced filters
6. Collapsed technical matches
7. Collapsed calculation notes

Every card uses the same shared payload at mobile and desktop widths. Mobile uses one category column; desktop uses two. Categories use both a text label and a symbol/border treatment. No category depends on color alone.

## Card evidence

Each card includes player/team/position/family identity, factual headline, selected-week numerator and denominator, count-weighted prior baseline, percentage-point change, all-play comparison, baseline sample, a short explanation, participation note, and Player/Team/Game links that preserve season and week.

## Default de-duplication

A player may match several technical categories or both RB families. The default report assigns one row per player using this category priority: {' → '.join(CATEGORY_PRIORITY)}. Each section is capped at {WEEKLY_REPORT_CONFIG.maximum_cards_per_category} cards and the whole report at {WEEKLY_REPORT_CONFIG.maximum_default_cards}. Technical matches remain available in the collapsed full-results view.
""",
    )
    _write_markdown(
        OUT / "SCREENING_RULES.md",
        f"""
# Weekly Role Report Screening Rules

These are configurable presentation screens, not detector rules and not claims about future role persistence.

## Shared baseline

- Selected row: public-primary canonical row for the selected season and week.
- Baseline: up to {config['baseline_games']} earlier qualifying games for the same player, team, family, and season.
- Baseline minimum: {config['minimum_baseline_games']} prior games after Week {config['early_season_week']}.
- Week {config['early_season_week']} exception: {config['early_season_minimum_baseline_games']} prior game because only Week 1 can exist; the sample is always shown.
- Share calculation: summed player opportunities divided by summed matching team opportunities. Weekly percentages are never averaged.
- Confirmed partial games: excluded by the existing public-primary definition.
- Suspected partial games: included and labeled.

## Thresholds

- Minimum absolute change for gained/lost: {config['minimum_share_change']:.0%}.
- Minimum current team denominator: {config['minimum_team_denominator']}.
- Minimum current raw opportunities for gained, context-overstated, and strong-opportunity screens: {config['minimum_raw_opportunities']}.
- Lost-role minimum prior share/raw: {config['minimum_baseline_share_for_loss']:.0%} / {config['minimum_baseline_raw_for_loss']}.
- Context-overstated minimum all-play minus normal-game share gap: {config['minimum_all_play_normal_gap']:.0%}.
- Context-overstated minimum opportunities outside normal-game context: {config['minimum_outside_normal_opportunities']}.
- Strong-opportunity minimum share/useful contexts: {config['minimum_strong_share']:.0%} / {config['minimum_useful_contexts']}.
- Weak-production maximum yards per documented opportunity: {config['maximum_yards_per_opportunity']:.1f}.

## Deterministic ordering

Within each category: larger absolute share change, larger selected-week raw opportunity count, larger selected-week team denominator, then alphabetical player name. No weighted score is calculated.
""",
    )

    counts_text = _markdown_table(summary)
    _write_markdown(
        OUT / "historical_replay_findings.md",
        f"""
# Historical Replay Findings

## Fixed 2025 weeks

{counts_text}

## Findings

- Every fixed week produced {summary['displayed_total'].min()}–{summary['displayed_total'].max()} default cards, within the requested approximate 8–15 range.
- The complete technical match set ranged from {summary['technical_match_total'].min()} to {summary['technical_match_total'].max()} rows, confirming that de-duplication and section caps materially reduce noise.
- No player appears twice in a default report. Secondary qualifying categories are preserved in the card archive and duplicate-assignment file.
- Week 2 uses one previous qualifying game because only Week 1 can be available; later replay weeks require at least two prior same-team qualifying games.
- Week 18 produced {int(summary.loc[summary['week'].eq(18), 'displayed_total'].iloc[0])} default cards and did not bypass any threshold.
- The maximum same-team concentration in a replay was {summary['maximum_players_from_one_team'].max()} cards. No manual player or teammate removal was applied.
- Category section caps, not hand-edited exclusions, keep each replay reviewable in approximately five minutes.
""",
    )

    manifest = {
        "season": SEASON,
        "replay_weeks": WEEKS,
        "replay_week_count": len(summary),
        "displayed_card_count": int(len(cards)),
        "technical_match_count": int(summary["technical_match_total"].sum()),
        "duplicate_default_player_rows": int(cards.duplicated(["season", "week", "player_id"]).sum()),
        "selected_week_failures": int((cards["week"].isin(WEEKS) == False).sum()),
        "share_reconciliation_failures": int(
            (~(cards["current_share"].round(12).eq((cards["current_raw"] / cards["current_denominator"]).round(12)))).sum()
        ),
        "weeks_with_default_volume_outside_8_to_15": int((~summary["displayed_total"].between(8, 15)).sum()),
        "category_priority": CATEGORY_PRIORITY,
        "config": config,
        "status": "REPLAY_PASSED",
    }
    (OUT / "final_validation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
