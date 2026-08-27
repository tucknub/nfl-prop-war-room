from __future__ import annotations

from src.fantasy.lineup_check import (
    NEEDS_ACTION,
    READY,
    WATCH,
    build_lineup_check,
)
from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    Manager,
    MatchupTeam,
    Roster,
)


CATALOG = {
    "qb1": {
        "full_name": "QB One",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "team": "IND",
        "status": "Active",
    },
    "qb2": {
        "full_name": "QB Two",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "team": "BUF",
        "status": "Active",
    },
    "rb1": {
        "full_name": "RB One",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "DET",
        "status": "Active",
    },
    "rb2": {
        "full_name": "RB Two",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "ATL",
        "status": "Active",
    },
    "wr1": {
        "full_name": "WR One",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "PHI",
        "status": "Active",
    },
    "wr2": {
        "full_name": "WR Two",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "CIN",
        "status": "Active",
    },
    "te1": {
        "full_name": "TE One",
        "position": "TE",
        "fantasy_positions": ["TE"],
        "team": "KC",
        "status": "Active",
    },
    "out_rb": {
        "full_name": "Out Running Back",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "MIA",
        "injury_status": "Out",
    },
    "q_wr": {
        "full_name": "Questionable Wideout",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "LAR",
        "injury_status": "Questionable",
    },
    "hunter": {
        "full_name": "Dual Eligible",
        "position": "WR",
        "fantasy_positions": ["WR", "DB"],
        "team": "JAX",
        "status": "Active",
    },
}


def _league(
    *,
    roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
    players=("qb1", "rb1", "wr1", "rb2", "wr2", "te1", "qb2"),
    starters=("qb1", "rb1", "wr1", "rb2"),
    reserve=(),
    taxi=(),
    status="in_season",
) -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="Test League",
        season="2026",
        status=status,
        team_count=12,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=tuple(roster_positions),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Me",
                team_name="My Team",
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
        ownership_ready=True,
    )


def test_open_flex_slot_keeps_slot_order_and_shows_eligible_options():
    league = _league(starters=("qb1", "rb1", "wr1", "0"))

    result = build_lineup_check(league, CATALOG)

    assert result is not None
    assert [row.slot for row in result.slots] == ["QB", "RB", "WR", "FLEX"]
    assert result.filled_starter_slots == 3
    assert result.open_starter_slots == 1

    flex = result.slots[3]
    assert flex.state == NEEDS_ACTION
    assert flex.starter is None
    assert [row.player_id for row in flex.eligible_alternatives] == [
        "rb2",
        "te1",
        "wr2",
    ]
    assert "qb2" not in {row.player_id for row in flex.eligible_alternatives}


def test_serious_direct_starter_surfaces_only_eligible_healthy_bench():
    league = _league(
        players=("qb1", "out_rb", "wr1", "rb2", "wr2", "te1", "qb2"),
        starters=("qb1", "out_rb", "wr1", "wr2"),
    )

    result = build_lineup_check(league, CATALOG)

    assert result is not None
    rb_slot = result.slots[1]
    assert rb_slot.state == NEEDS_ACTION
    assert rb_slot.starter is not None
    assert rb_slot.starter.player_id == "out_rb"
    assert [row.player_id for row in rb_slot.eligible_alternatives] == ["rb2"]
    assert result.needs_action_count == 1


def test_questionable_starter_is_watch_not_forced_change():
    league = _league(
        players=("qb1", "rb1", "q_wr", "rb2", "wr2", "te1"),
        starters=("qb1", "rb1", "q_wr", "rb2"),
    )

    result = build_lineup_check(league, CATALOG)

    assert result is not None
    wr_slot = result.slots[2]
    assert wr_slot.state == WATCH
    assert wr_slot.reason == "Current starter status: Questionable."
    assert [row.player_id for row in wr_slot.eligible_alternatives] == ["wr2"]
    assert result.watch_count == 1


def test_flex_family_eligibility_matches_sleeper_rules():
    base_players = (
        "qb1",
        "rb1",
        "wr1",
        "te1",
        "qb2",
        "rb2",
        "wr2",
    )

    superflex = _league(
        roster_positions=("QB", "SUPER_FLEX", "BN"),
        players=base_players,
        starters=("qb1", "0"),
    )
    result = build_lineup_check(superflex, CATALOG)
    assert result is not None
    assert {row.position for row in result.slots[1].eligible_alternatives} == {
        "QB",
        "RB",
        "WR",
        "TE",
    }

    rec_flex = _league(
        roster_positions=("QB", "REC_FLEX", "BN"),
        players=base_players,
        starters=("qb1", "0"),
    )
    result = build_lineup_check(rec_flex, CATALOG)
    assert result is not None
    assert {row.position for row in result.slots[1].eligible_alternatives} == {
        "WR",
        "TE",
    }

    wrrb_flex = _league(
        roster_positions=("QB", "WRRB_FLEX", "BN"),
        players=base_players,
        starters=("qb1", "0"),
    )
    result = build_lineup_check(wrrb_flex, CATALOG)
    assert result is not None
    assert {row.position for row in result.slots[1].eligible_alternatives} == {
        "RB",
        "WR",
    }


def test_reserve_and_taxi_players_are_not_presented_as_bench_alternatives():
    league = _league(
        starters=("qb1", "rb1", "wr1", "0"),
        reserve=("rb2",),
        taxi=("te1",),
    )

    result = build_lineup_check(league, CATALOG)

    assert result is not None
    flex_ids = {row.player_id for row in result.slots[3].eligible_alternatives}
    assert "rb2" not in flex_ids
    assert "te1" not in flex_ids
    assert "wr2" in flex_ids


def test_current_week_matchup_lineup_overrides_roster_starters():
    league = _league(
        players=("qb1", "rb1", "out_rb", "wr1", "wr2", "rb2"),
        starters=("qb1", "rb1", "wr1", "wr2"),
    )
    matchup = MatchupTeam(
        week=1,
        platform_roster_id="1",
        matchup_id="9",
        players=league.rosters[0].players,
        starters=("qb1", "out_rb", "wr1", "wr2"),
        points=0,
        custom_points=None,
        players_points={},
        starters_points=(),
    )

    result = build_lineup_check(
        league,
        CATALOG,
        matchup=matchup,
    )

    assert result is not None
    assert result.used_matchup_lineup is True
    assert result.slots[1].starter is not None
    assert result.slots[1].starter.player_id == "out_rb"
    assert result.slots[1].state == NEEDS_ACTION


def test_matchup_for_other_roster_does_not_override_my_lineup():
    league = _league()
    matchup = MatchupTeam(
        week=1,
        platform_roster_id="2",
        matchup_id="9",
        players=("out_rb",),
        starters=("out_rb",),
        points=0,
        custom_points=None,
        players_points={},
        starters_points=(),
    )

    result = build_lineup_check(league, CATALOG, matchup=matchup)

    assert result is not None
    assert result.used_matchup_lineup is False
    assert result.slots[1].starter is not None
    assert result.slots[1].starter.player_id == "rb1"


def test_multi_position_player_can_fill_direct_or_idp_flex_slot():
    direct = _league(
        roster_positions=("WR", "BN"),
        players=("hunter",),
        starters=("hunter",),
    )
    result = build_lineup_check(direct, CATALOG)
    assert result is not None
    assert result.slots[0].state == READY

    idp = _league(
        roster_positions=("IDP_FLEX", "BN"),
        players=("hunter",),
        starters=("0",),
    )
    result = build_lineup_check(idp, CATALOG)
    assert result is not None
    assert [row.player_id for row in result.slots[0].eligible_alternatives] == [
        "hunter"
    ]


def test_fantasy_hq_exposes_lineup_check():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert '"Lineup Check"' in page
    assert "build_lineup_check" in page
    assert "Eligible bench options" in page
    assert "eligibility/status only" in page


def test_predraft_empty_roster_is_not_a_nine_slot_lineup_emergency():
    league = _league(
        players=(),
        starters=(),
        status="pre_draft",
    )

    result = build_lineup_check(league, CATALOG)

    assert result is None


def test_fantasy_hq_predraft_mode_suppresses_live_tool_noise():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "pre_draft_mode" in page
    assert "Configured starter slots are not treated as lineup mistakes" in page
    assert "No ownership or availability warnings are shown before" in page
    assert "The NFL preseason week is not treated as your fantasy" in page
    assert "Opponent Scout will activate once Sleeper" in page
    assert "League settings are available now" in page
