from __future__ import annotations

import sys
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import load_production_data, load_situational_data, player_selector_rows, primary_rows  # noqa: E402
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
    default_home_week,
    game_href,
    player_href,
    report_period_notice,
    team_href,
)


REPLAY_WEEKS = [2, 5, 8, 11, 14, 17, 18]


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
        assert weak["production_rate"].le(WEEKLY_REPORT_CONFIG.maximum_role_specific_production_rate).all()
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
            if row["situation_type"] == "reciprocal_transfer":
                assert row["category"] == CATEGORY_GAINED
                assert CATEGORY_GAINED in technical["category"].tolist()
            else:
                expected = min(technical["category"], key=priority.get)
                assert row["category"] == expected
        member_ids = [
            player_id
            for values in cards["situation_member_ids"].str.split(" | ", regex=False)
            for player_id in values
        ]
        assert len(member_ids) == len(set(member_ids))


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
    for href, count in cards["team_href"].value_counts().items():
        assert html.count(escape(str(href))) == count
    for href, count in cards["game_href"].value_counts().items():
        assert html.count(escape(str(href))) == count


def test_home_copy_and_public_navigation_remain_within_scope() -> None:
    home = (ROOT / "dashboard" / "home_page.py").read_text(encoding="utf-8")
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    assert "This Week in NFL Roles" in home
    assert "Weekly Observable Changes" not in home
    assert "View all qualifying results" in home
    assert 'title="Research Admin"' not in app


def test_reciprocal_team_role_changes_are_consolidated_and_minnesota_week_eight_is_one_situation() -> None:
    cards, matches = build_weekly_role_report(2025, 8)
    min_card = cards[
        cards["team"].eq("MIN") & cards["role_family"].eq("rb_opportunity_share")
    ]
    assert len(min_card) == 1
    row = min_card.iloc[0]
    assert row["situation_type"] == "reciprocal_transfer"
    assert row["player_name"] == "Aaron Jones"
    assert set(row["situation_member_names"].split(" | ")) == {
        "Aaron Jones", "Jordan Mason", "Zavier Scott",
    }
    assert int(row["situation_member_count"]) == 3
    min_technical = matches[
        matches["team"].eq("MIN") & matches["role_family"].eq("rb_opportunity_share")
    ]
    assert {CATEGORY_GAINED, CATEGORY_LOST, CATEGORY_OVERSTATED}.issubset(set(min_technical["category"]))


def test_no_team_exceeds_two_default_situations_and_team_family_is_unique() -> None:
    for _, cards, _ in _reports():
        assert cards.groupby("team").size().le(WEEKLY_REPORT_CONFIG.maximum_cards_per_team).all()
        assert not cards.duplicated(["team", "role_family"]).any()


def test_role_group_allocation_reserves_target_capacity_when_both_groups_qualify() -> None:
    for _, cards, _ in _reports():
        qualified = cards.attrs["qualified_situation_counts"]
        for category in DISPLAY_CATEGORIES:
            qualified_groups = {
                group for group in ["backfield", "target"] if qualified.get((category, group), 0) > 0
            }
            displayed_groups = set(cards.loc[cards["category"].eq(category), "role_group"])
            if qualified_groups == {"backfield", "target"} and len(cards[cards["category"].eq(category)]) >= 2:
                assert displayed_groups == qualified_groups


def test_early_season_and_week_eighteen_notices_and_default_week() -> None:
    assert report_period_notice(2) == (
        "info", "Early-season sample: Week 2 comparisons use Week 1 only, so the baseline is one previous game."
    )
    assert "two prior games" in report_period_notice(3)[1]
    assert "rest decisions" in report_period_notice(18)[1]
    assert default_home_week(2025, range(1, 19)) == 17
    assert default_home_week(2025, range(1, 17)) == 16
    cards, _ = build_weekly_role_report(2025, 2)
    changed = cards[cards["category"].isin([CATEGORY_GAINED, CATEGORY_LOST])]
    assert changed["explanation"].str.contains("Week 2 share", regex=False).all()
    assert changed["explanation"].str.contains("Week 1", regex=False).all()


def test_card_labels_and_collapsed_all_plays_suppression() -> None:
    cards, _ = build_weekly_role_report(2025, 17)
    html = weekly_report_html(cards, DISPLAY_CATEGORIES)
    assert "Normal-game share" in html
    assert "Selected week</span>" not in html
    assert "All play</span>" not in html
    hidden = cards[~cards["show_all_play_prominently"]]
    assert not hidden.empty
    for _, row in hidden.iterrows():
        article = html.split(f'>{escape(str(row["player_name"]))} ', 1)[1].split("</article>", 1)[0]
        collapsed = article.split("<details>", 1)[0]
        assert "All-plays share" not in collapsed
        assert "All-plays share" in article


def test_context_facts_are_real_counts_limited_and_meet_documented_minimums() -> None:
    source = load_situational_data()
    for week, cards, _ in _reports():
        for _, row in cards.iterrows():
            facts = row["context_facts"]
            assert len(facts) <= WEEKLY_REPORT_CONFIG.maximum_context_facts
            for fact in facts:
                expected = source[
                    source["season"].eq(2025) & source["week"].eq(week)
                    & source["player_id"].astype(str).eq(str(row["player_id"]))
                    & source["team"].eq(row["team"])
                    & source["role_family"].eq(row["role_family"])
                    & source["context"].eq(fact["context"])
                ].iloc[0]
                assert int(fact["raw"]) == int(expected["raw_opportunities"])
                assert int(fact["denominator"]) == int(expected["team_opportunities"])
                minimum_raw, minimum_denominator = WEEKLY_REPORT_CONFIG.context_minimum_map[fact["context"]]
                assert int(fact["raw"]) >= minimum_raw
                assert int(fact["denominator"]) >= minimum_denominator


def test_role_specific_production_metrics_reconcile() -> None:
    production = load_production_data()
    all_matches = pd.concat([matches for _, _, matches in _reports()], ignore_index=True)
    weak = all_matches[all_matches["category"].eq(CATEGORY_WEAK_PRODUCTION)]
    assert set(weak["production_metric_label"]).issubset({
        "Yards per carry", "Yards per touch", "Receiving yards per target",
    })
    for _, row in weak.iterrows():
        game = production[
            production["player_id"].astype(str).eq(str(row["player_id"]))
            & production["game_id"].eq(row["game_id"])
        ].iloc[0]
        if row["role_family"] == "rb_carry_share":
            denominator = game["carries"]
            yards = game["rushing_yards"]
            label = "Yards per carry"
        elif row["role_family"] == "rb_opportunity_share":
            denominator = game["carries"] + game["receptions"]
            yards = game["rushing_yards"] + game["receiving_yards"]
            label = "Yards per touch"
        else:
            denominator = game["targets"]
            yards = game["receiving_yards"]
            label = "Receiving yards per target"
        assert row["production_metric_label"] == label
        assert np.isclose(row["production_rate"], yards / denominator)


def test_zavier_scott_week_eight_primary_technical_category_is_overstated() -> None:
    _, matches = build_weekly_role_report(2025, 8)
    zavier = matches[
        matches["player_name"].eq("Zavier Scott")
        & matches["role_family"].eq("rb_opportunity_share")
    ]
    assert set(zavier["category"]) == {CATEGORY_OVERSTATED, CATEGORY_LOST}
    row = zavier[zavier["category"].eq(CATEGORY_OVERSTATED)].iloc[0]
    assert (row["current_raw"], row["current_denominator"]) == (0, 14)
    assert (row["all_play_raw"], row["all_play_denominator"]) == (4, 18)
    assert np.isclose(row["all_play_normal_gap"], 4 / 18)
    assert row["individual_primary_category"] == CATEGORY_OVERSTATED


def test_multi_team_selector_labels_use_the_requested_time_boundary() -> None:
    season_data = primary_rows().loc[lambda frame: frame["season"].eq(2025)]
    latest = player_selector_rows(season_data, 18).set_index("player_id")
    expected = {
        "00-0030035": "PIT", "00-0031236": "BUF", "00-0032211": "LV",
        "00-0032394": "LA", "00-0034272": "PIT", "00-0038555": "PHI",
    }
    assert latest.loc[list(expected), "team"].to_dict() == expected
    week_one = player_selector_rows(season_data, 1).set_index("player_id")
    assert week_one.loc["00-0038555", "team"] == "JAX"
