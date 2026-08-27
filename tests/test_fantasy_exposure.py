from __future__ import annotations

from src.fantasy.exposure import build_my_player_exposure
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster


def _league(
    league_id: str,
    name: str,
    *,
    players=(),
    starters=(),
    reserve=(),
    taxi=(),
) -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name=name,
        season="2026",
        status="in_season",
        team_count=12,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "TE", "FLEX", "BN", "IR"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Me",
                team_name=f"{name} Team",
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=tuple(players),
                starters=tuple(starters),
                reserve=tuple(reserve),
                taxi=tuple(taxi),
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=bool(players),
    )


def test_player_exposure_aggregates_same_player_across_leagues():
    leagues = (
        _league(
            "papa",
            "Papa John's",
            players=("p1", "p2", "p3"),
            starters=("p1", "p2"),
            reserve=("p3",),
        ),
        _league(
            "franchise",
            "Franchise",
            players=("p1", "p4"),
            starters=("p4",),
        ),
        _league(
            "third",
            "Third",
            players=("p1", "p2", "p5"),
            starters=("p1",),
            taxi=("p2",),
        ),
    )

    index = build_my_player_exposure(leagues)

    assert index.distinct_player_count == 5
    assert index.multi_league_player_count == 2
    assert index.max_league_count == 3
    assert index.total_roster_slots == 8

    p1 = next(row for row in index.players if row.sleeper_player_id == "p1")
    assert p1.league_count == 3
    assert p1.starter_count == 2
    assert p1.bench_count == 1
    assert p1.reserve_count == 0
    assert p1.taxi_count == 0
    assert [row.league_name for row in p1.leagues] == [
        "Papa John's",
        "Franchise",
        "Third",
    ]


def test_player_exposure_preserves_ir_taxi_and_bench_slots():
    leagues = (
        _league(
            "one",
            "One",
            players=("bench", "ir", "taxi"),
            reserve=("ir",),
            taxi=("taxi",),
        ),
    )

    index = build_my_player_exposure(leagues)
    by_id = {row.sleeper_player_id: row for row in index.players}

    assert by_id["bench"].bench_count == 1
    assert by_id["ir"].reserve_count == 1
    assert by_id["taxi"].taxi_count == 1


def test_player_exposure_deduplicates_player_within_same_roster():
    league = _league(
        "one",
        "One",
        players=("p1",),
        starters=("p1",),
        reserve=("p1",),
    )

    index = build_my_player_exposure((league,))

    assert index.distinct_player_count == 1
    assert index.total_roster_slots == 1
    assert index.players[0].reserve_count == 1
    assert index.players[0].starter_count == 0


def test_player_exposure_empty_and_predraft_inputs_are_safe():
    index = build_my_player_exposure(
        (
            _league("one", "One"),
            _league("two", "Two"),
        )
    )

    assert index.players == ()
    assert index.distinct_player_count == 0
    assert index.multi_league_player_count == 0
    assert index.max_league_count == 0
    assert index.total_roster_slots == 0


def test_fantasy_hq_exposes_player_exposure():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "My Player Exposure" in page
    assert "build_my_player_exposure" in page
    assert "Multi-league players" in page
    assert "Only players owned in 2+ leagues" in page
