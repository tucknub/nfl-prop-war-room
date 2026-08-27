from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from src.fantasy.action_feed import (
    HEALTH,
    LINEUP,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    TRADE,
    WAIVER,
    WeeklyActionItem,
    build_weekly_action_feed,
    waiver_candidate_visible_in_feed,
)
from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    Manager,
    Roster,
)


def _league(league_id, name, *, status="in_season", ownership_ready=True):
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name=name,
        season="2026",
        status=status,
        team_count=10,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
            scoring_settings={"rec": 1.0},
            waiver_budget=100,
        ),
        draft=None,
        managers=(Manager("me", "Me", name),),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=("p1", "p2"),
                starters=("p1", "p2"),
                reserve=(),
                taxi=(),
                settings={},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def _action(
    league,
    *,
    priority,
    action_type,
    title,
    score,
    impact=None,
):
    return WeeklyActionItem(
        platform_league_id=league.platform_league_id,
        league_name=league.name,
        priority=priority,
        action_type=action_type,
        title=title,
        action=title,
        detail="detail",
        impact_points=impact,
        confidence="HIGH",
        score=score,
    )


def test_low_waiver_feed_requires_two_point_edge():
    assert waiver_candidate_visible_in_feed(
        SimpleNamespace(
            need="LOW",
            expected_lineup_improvement=1.99,
        )
    ) is False
    assert waiver_candidate_visible_in_feed(
        SimpleNamespace(
            need="LOW",
            expected_lineup_improvement=2.0,
        )
    ) is True
    assert waiver_candidate_visible_in_feed(
        SimpleNamespace(
            need="LOW",
            expected_lineup_improvement=None,
        )
    ) is False
    assert waiver_candidate_visible_in_feed(
        SimpleNamespace(
            need="HIGH",
            expected_lineup_improvement=0.0,
        )
    ) is True


def test_action_feed_globally_ranks_actions_across_leagues(monkeypatch):
    league_a = _league("a", "League A")
    league_b = _league("b", "League B")

    def fake_league_actions(league, *_args, **_kwargs):
        if league.platform_league_id == "a":
            return [
                _action(
                    league,
                    priority=PRIORITY_LOW,
                    action_type=WAIVER,
                    title="Small waiver upgrade",
                    score=135.0,
                    impact=1.2,
                )
            ]
        return [
            _action(
                league,
                priority=PRIORITY_HIGH,
                action_type=LINEUP,
                title="Fix starting lineup",
                score=350.0,
                impact=4.0,
            )
        ]

    monkeypatch.setattr(
        "src.fantasy.action_feed._league_actions",
        fake_league_actions,
    )

    result = build_weekly_action_feed(
        (league_a, league_b),
        {},
        (),
    )

    assert result.actions[0].league_name == "League B"
    assert result.actions[0].title == "Fix starting lineup"
    assert result.actions[1].league_name == "League A"
    assert result.high_count == 1
    assert result.actionable_league_count == 2


def test_action_feed_skips_pre_draft_and_unready_ownership(monkeypatch):
    drafted = _league("ready", "Ready")
    predraft = _league(
        "pre",
        "Pre",
        status="pre_draft",
        ownership_ready=False,
    )
    unsafe = _league("unsafe", "Unsafe", ownership_ready=False)
    seen = []

    def fake_league_actions(league, *_args, **_kwargs):
        seen.append(league.platform_league_id)
        return [
            _action(
                league,
                priority=PRIORITY_MEDIUM,
                action_type=HEALTH,
                title="Review",
                score=210.0,
            )
        ]

    monkeypatch.setattr(
        "src.fantasy.action_feed._league_actions",
        fake_league_actions,
    )

    result = build_weekly_action_feed(
        (drafted, predraft, unsafe),
        {},
        (),
    )

    assert seen == ["ready"]
    assert result.scanned_leagues == 3
    assert result.drafted_leagues == 1
    assert len(result.actions) == 1


def test_action_feed_forwards_matchups_transactions_and_all_leagues(monkeypatch):
    league = _league("a", "League A")
    matchup = object()
    transactions = (object(), object())
    captured = {}

    def fake_league_actions(
        current_league,
        _catalog,
        _props,
        *,
        current_week,
        trends,
        matchup,
        transactions,
        all_leagues,
    ):
        captured.update(
            {
                "current_week": current_week,
                "trends": trends,
                "matchup": matchup,
                "transactions": transactions,
                "all_leagues": all_leagues,
            }
        )
        return []

    monkeypatch.setattr(
        "src.fantasy.action_feed._league_actions",
        fake_league_actions,
    )

    build_weekly_action_feed(
        (league,),
        {},
        (),
        current_week=7,
        trends=("trend",),
        matchups_by_league={"a": matchup},
        transactions_by_league={"a": transactions},
    )

    assert captured["current_week"] == 7
    assert captured["trends"] == ("trend",)
    assert captured["matchup"] is matchup
    assert captured["transactions"] == transactions
    assert captured["all_leagues"] == (league,)


def test_action_feed_deduplicates_same_action_and_keeps_higher_score(monkeypatch):
    league = _league("a", "League A")
    low = _action(
        league,
        priority=PRIORITY_MEDIUM,
        action_type=WAIVER,
        title="Add Player X",
        score=220.0,
    )
    high = replace(
        low,
        priority=PRIORITY_HIGH,
        score=340.0,
    )

    monkeypatch.setattr(
        "src.fantasy.action_feed._league_actions",
        lambda *_args, **_kwargs: [low, high],
    )

    result = build_weekly_action_feed(
        (league,),
        {},
        (),
    )

    assert len(result.actions) == 1
    assert result.actions[0].priority == PRIORITY_HIGH
    assert result.actions[0].score == 340.0


def test_action_feed_respects_global_limit(monkeypatch):
    league = _league("a", "League A")

    monkeypatch.setattr(
        "src.fantasy.action_feed._league_actions",
        lambda *_args, **_kwargs: [
            _action(
                league,
                priority=PRIORITY_LOW,
                action_type=TRADE,
                title=f"Action {index}",
                score=100.0 + index,
            )
            for index in range(10)
        ],
    )

    result = build_weekly_action_feed(
        (league,),
        {},
        (),
        limit=3,
    )

    assert len(result.actions) == 3
    assert [row.title for row in result.actions] == [
        "Action 9",
        "Action 8",
        "Action 7",
    ]


def test_action_feed_isolates_one_league_failure(monkeypatch):
    good = _league("good", "Good")
    bad = _league("bad", "Bad")

    def fake_league_actions(league, *_args, **_kwargs):
        if league.platform_league_id == "bad":
            raise RuntimeError("market unavailable")
        return [
            _action(
                league,
                priority=PRIORITY_MEDIUM,
                action_type=LINEUP,
                title="Good action",
                score=245.0,
            )
        ]

    monkeypatch.setattr(
        "src.fantasy.action_feed._league_actions",
        fake_league_actions,
    )

    result = build_weekly_action_feed(
        (bad, good),
        {},
        (),
    )

    assert len(result.actions) == 1
    assert result.actions[0].league_name == "Good"
    assert len(result.errors) == 1
    assert "Bad" in result.errors[0]
    assert "market unavailable" in result.errors[0]


def test_fantasy_hq_exposes_what_should_i_do_feed():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "What Should I Do?" in page
    assert "build_weekly_action_feed" in page
    assert "Across all Sleeper leagues" in page
    assert "Recommended action" in page
    assert "Impact" in page
    assert "FAAB" in page
