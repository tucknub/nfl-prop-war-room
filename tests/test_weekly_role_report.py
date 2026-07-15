from __future__ import annotations

import sys
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import primary_rows  # noqa: E402
from research_ui import resolve_query_choice, weekly_report_html  # noqa: E402
from weekly_report import (  # noqa: E402
    CATEGORY_GAINED,
    CATEGORY_LOST,
    CATEGORY_OVERSTATED,
    CATEGORY_PRIORITY,
    CATEGORY_WEAK_PRODUCTION,
    DISPLAY_CATEGORIES,
    WEEKLY_REPORT_CONFIG,
    build_weekly_role_report,
    game_href,
    player_href,
    team_href,
)


REPLAY_WEEKS = [2, 5, 8, 11, 14, 18]


def _reports() -> list[tuple[int, pd.DataFrame, pd.DataFrame]]:
    return [(week, *build_weekly_role_report(2025, week)) for week in REPLAY_WEEKS]


def test_every_default_card_belongs_to_selected_week_and_season() -> None:
    for week, cards, _ in _reports():
        assert not cards.empty
        assert cards["season"].eq(2025).all()
        assert cards["week"].eq(week).all()


def test_baselines_use_only_previous_same_season_qualifying_games() -> None:
    source = primary_rows()
    for week, cards, _ in _reports():
        for _, row in cards.iterrows():
            prior = source[
                source["season"].eq(2025)
                & source["week"].lt(week)
                & source["player_id"].astype(str).eq(str(row["player_id"]))
                & source["team"].eq(row["team"])
                & source["role_family"].eq(row["role_family"])
            ].sort_values("week").tail(WEEKLY_REPORT_CONFIG.baseline_games)
            assert len(prior) == row["baseline_games"]
            assert int(prior["week"].max()) < week
            assert prior["season"].eq(2025).all()


def test_baseline_share_is_summed_counts_not_weekly_percentage_average() -> None:
    source = primary_rows()
    _, cards, _ = _reports()[-1]
    for _, row in cards.iterrows():
        prior = source[
            source["season"].eq(2025)
            & source["week"].lt(18)
            & source["player_id"].astype(str).eq(str(row["player_id"]))
            & source["team"].eq(row["team"])
            & source["role_family"].eq(row["role_family"])
        ].sort_values("week").tail(4)
        expected = prior["raw_opportunities_normal"].sum() / prior["team_opportunities_normal"].sum()
        assert row["baseline_share"] == expected
        assert row["baseline_raw"] == prior["raw_opportunities_normal"].sum()
        assert row["baseline_denominator"] == prior["team_opportunities_normal"].sum()


def test_selected_week_numerator_denominator_reconcile() -> None:
    for _, cards, _ in _reports():
        assert (cards["current_denominator"] > 0).all()
        assert np.allclose(cards["current_share"], cards["current_raw"] / cards["current_denominator"])
        assert np.allclose(cards["all_play_share"], cards["all_play_raw"] / cards["all_play_denominator"])


def test_minimum_opportunity_and_category_rules_are_literal() -> None:
    for _, _, matches in _reports():
        mins = matches["role_family"].map(WEEKLY_REPORT_CONFIG.raw_minimums)
        gained = matches[matches["category"].eq(CATEGORY_GAINED)]
        assert gained["share_change"].ge(WEEKLY_REPORT_CONFIG.minimum_share_change).all()
        assert gained["current_raw"].ge(mins.loc[gained.index]).all()
        lost = matches[matches["category"].eq(CATEGORY_LOST)]
        assert lost["share_change"].le(-WEEKLY_REPORT_CONFIG.minimum_share_change).all()
        assert lost["baseline_share"].ge(WEEKLY_REPORT_CONFIG.minimum_baseline_share_for_loss).all()
        overstated = matches[matches["category"].eq(CATEGORY_OVERSTATED)]
        assert overstated["all_play_normal_gap"].ge(WEEKLY_REPORT_CONFIG.minimum_all_play_normal_gap).all()
        assert overstated["outside_normal_opportunities"].ge(WEEKLY_REPORT_CONFIG.minimum_outside_normal_opportunities).all()
        weak = matches[matches["category"].eq(CATEGORY_WEAK_PRODUCTION)]
        assert weak["current_share"].ge(WEEKLY_REPORT_CONFIG.minimum_strong_share).all()
        assert weak["yards_per_opportunity"].le(WEEKLY_REPORT_CONFIG.maximum_yards_per_opportunity).all()
        assert weak["useful_contexts"].ge(WEEKLY_REPORT_CONFIG.minimum_useful_contexts).all()


def test_tie_breaking_is_deterministic_within_each_category() -> None:
    for _, _, matches in _reports():
        for category in DISPLAY_CATEGORIES:
            rows = matches[matches["category"].eq(category)]
            expected = rows.sort_values(
                ["absolute_share_change", "current_raw", "current_denominator", "player_name"],
                ascending=[False, False, False, True],
                kind="stable",
            )["player_id"].tolist()
            assert rows["player_id"].tolist() == expected


def test_category_priority_and_default_deduplication_are_deterministic() -> None:
    priority = {category: index for index, category in enumerate(CATEGORY_PRIORITY)}
    for _, cards, matches in _reports():
        assert not cards["player_id"].duplicated().any()
        for _, row in cards.iterrows():
            technical = matches[matches["player_id"].eq(row["player_id"])]
            expected = min(technical["category"], key=priority.get)
            assert row["category"] == expected


def test_replay_volume_is_reviewable_and_sections_are_capped() -> None:
    for _, cards, _ in _reports():
        assert 8 <= len(cards) <= 15
        assert cards.groupby("category").size().le(WEEKLY_REPORT_CONFIG.maximum_cards_per_category).all()


def test_week_two_uses_one_prior_game_and_week_eighteen_replays() -> None:
    week_two, _ = build_weekly_role_report(2025, 2)
    week_eighteen, _ = build_weekly_role_report(2025, 18)
    assert week_two["baseline_games"].eq(1).all()
    assert not week_eighteen.empty
    assert week_eighteen["week"].eq(18).all()


def test_later_weeks_reject_one_game_baselines() -> None:
    for week in [5, 8, 11, 14, 18]:
        cards, matches = build_weekly_role_report(2025, week)
        assert cards["baseline_games"].ge(WEEKLY_REPORT_CONFIG.minimum_baseline_games).all()
        assert matches["baseline_games"].ge(WEEKLY_REPORT_CONFIG.minimum_baseline_games).all()


def test_all_play_and_normal_game_values_remain_distinct() -> None:
    _, matches = build_weekly_role_report(2025, 18)
    overstated = matches[matches["category"].eq(CATEGORY_OVERSTATED)]
    assert not overstated.empty
    assert overstated["all_play_share"].gt(overstated["current_share"]).all()
    assert overstated["all_play_raw"].gt(overstated["current_raw"]).all()


def test_confirmed_partial_games_never_create_cards_and_suspected_remain_visible() -> None:
    source = primary_rows()
    assert not source["confirmed_partial_game"].any()
    all_cards = pd.concat([matches for _, _, matches in _reports()], ignore_index=True)
    assert not all_cards["confirmed_partial_game"].any()
    assert all_cards["suspected_partial_game"].dtype == bool


def test_evidence_links_preserve_selected_state() -> None:
    cards, _ = build_weekly_role_report(2025, 18)
    for _, row in cards.iterrows():
        player = parse_qs(urlparse(row["player_href"]).query)
        team = parse_qs(urlparse(row["team_href"]).query)
        game = parse_qs(urlparse(row["game_href"]).query)
        assert player == {
            "player": [row["player_id"]], "season": ["2025"],
            "family": [row["role_family"]], "week": ["18"],
        }
        assert team == {
            "team": [row["team"]], "season": ["2025"],
            "family": [row["role_family"]], "week": ["18"],
        }
        assert game == {"season": ["2025"], "week": ["18"], "game": [row["game_id"]]}


def test_link_builders_encode_values_and_invalid_choices_fail_safely() -> None:
    assert "%20" in player_href("player id", 2025, "wr target", 18)
    assert "%20" in team_href("N Y", 2025, "wr target", 18)
    assert "%20" in game_href("game id", 2025, 18)
    assert resolve_query_choice([2024, 2025], 2026, 2025) == (None, True)
    assert resolve_query_choice(["A", "B"], "missing", "A") == (None, True)


def test_mobile_and_desktop_use_one_identical_card_payload() -> None:
    cards, _ = build_weekly_role_report(2025, 18)
    html = weekly_report_html(cards, DISPLAY_CATEGORIES)
    assert html.count('<article class="pw-report-card">') == len(cards)
    for _, row in cards.iterrows():
        assert html.count(escape(str(row["player_href"]))) == 1
        assert html.count(escape(str(row["team_href"]))) == 1
    for href, count in cards["game_href"].value_counts().items():
        assert html.count(escape(str(href))) == count


def test_home_copy_and_public_navigation_remain_within_scope() -> None:
    home = (ROOT / "dashboard" / "home_page.py").read_text(encoding="utf-8")
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    assert "This Week in NFL Roles" in home
    assert "Weekly Observable Changes" not in home
    assert "View all qualifying results" in home
    assert 'title="Research Admin"' not in app
