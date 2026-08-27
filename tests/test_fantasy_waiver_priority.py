from __future__ import annotations

from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.waiver_fit import RosterNeedWaiverBoard, WaiverNeedMatch
from src.fantasy.waiver_priority import (
    ACTION_FIT,
    MARKET_BACKED_ACTION,
    MARKET_BACKED_WATCH,
    WATCH_FIT,
    build_market_waiver_priority_board,
    priority_label,
)


CATALOG = {
    "rb_a": {
        "full_name": "Runner Alpha",
        "position": "RB",
        "team": "IND",
        "active": True,
    },
    "rb_b": {
        "full_name": "Runner Beta",
        "position": "RB",
        "team": "DET",
        "active": True,
    },
    "wr_a": {
        "full_name": "Wide Alpha",
        "position": "WR",
        "team": "PHI",
        "active": True,
    },
}


def _league() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league",
        name="League",
        season="2026",
        status="in_season",
        team_count=10,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
            scoring_settings={
                "rush_yd": 0.1,
                "rec_yd": 0.1,
                "rec": 1.0,
                "rush_td": 6.0,
                "rec_td": 6.0,
            },
        ),
        draft=None,
        managers=(Manager("me", "Me", "My Team"),),
        rosters=(Roster("1", "me", (), (), (), ()),),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _match(
    player_id: str,
    name: str,
    position: str,
    *,
    action_slots=(),
    watch_slots=(),
    trend_count=0,
    mine_elsewhere=(),
) -> WaiverNeedMatch:
    return WaiverNeedMatch(
        sleeper_player_id=player_id,
        player_name=name,
        position=position,
        nfl_team=str(CATALOG[player_id]["team"]),
        status="Active",
        action_slots=tuple(action_slots),
        watch_slots=tuple(watch_slots),
        mine_elsewhere=tuple(mine_elsewhere),
        trend_count=trend_count,
    )


def _prop(
    player,
    market,
    line,
    book,
    *,
    over_price=-110,
    under_price=-110,
):
    return {
        "event_id": "e1",
        "commence_time": "2026-09-13T17:00:00Z",
        "away_team": "IND",
        "home_team": "HOU",
        "book": book,
        "player": player,
        "market": market,
        "market_key": f"player_{market}",
        "line": line,
        "over_price": over_price,
        "under_price": under_price,
        "over_implied_prob": None,
        "under_implied_prob": None,
    }


def test_market_backed_action_candidates_rank_by_market_baseline():
    board = RosterNeedWaiverBoard(
        needs=(),
        matches=(
            _match("rb_a", "Runner Alpha", "RB", action_slots=("RB",)),
            _match("rb_b", "Runner Beta", "RB", action_slots=("RB",)),
        ),
    )
    props = [
        _prop("Runner Alpha", "rushing_yards", 79.5, "DK"),
        _prop("Runner Alpha", "rushing_yards", 80.5, "FD"),
        _prop("Runner Alpha", "receiving_yards", 24.5, "DK"),
        _prop("Runner Alpha", "receiving_yards", 25.5, "FD"),
        _prop("Runner Beta", "rushing_yards", 54.5, "DK"),
        _prop("Runner Beta", "rushing_yards", 55.5, "FD"),
        _prop("Runner Beta", "receiving_yards", 14.5, "DK"),
        _prop("Runner Beta", "receiving_yards", 15.5, "FD"),
    ]

    result = build_market_waiver_priority_board(
        _league(),
        board,
        CATALOG,
        props,
    )

    assert [row.sleeper_player_id for row in result.candidates] == [
        "rb_a",
        "rb_b",
    ]
    assert all(
        row.priority_tier == MARKET_BACKED_ACTION
        for row in result.candidates
    )
    assert result.candidates[0].market_fantasy_points > result.candidates[1].market_fantasy_points


def test_action_fit_outranks_market_backed_watch_fit():
    board = RosterNeedWaiverBoard(
        needs=(),
        matches=(
            _match("rb_a", "Runner Alpha", "RB", action_slots=("RB",)),
            _match("wr_a", "Wide Alpha", "WR", watch_slots=("WR",)),
        ),
    )
    props = [
        _prop("Wide Alpha", "receiving_yards", 99.5, "DK"),
        _prop("Wide Alpha", "receiving_yards", 100.5, "FD"),
        _prop("Wide Alpha", "receptions", 7.5, "DK"),
        _prop("Wide Alpha", "receptions", 7.5, "FD"),
    ]

    result = build_market_waiver_priority_board(
        _league(),
        board,
        CATALOG,
        props,
    )

    assert result.candidates[0].sleeper_player_id == "rb_a"
    assert result.candidates[0].priority_tier == ACTION_FIT
    assert result.candidates[1].priority_tier == MARKET_BACKED_WATCH


def test_thin_market_coverage_does_not_claim_market_backing():
    board = RosterNeedWaiverBoard(
        needs=(),
        matches=(
            _match("rb_a", "Runner Alpha", "RB", action_slots=("RB",)),
        ),
    )
    props = [
        _prop("Runner Alpha", "rushing_yards", 70.5, "DK"),
        _prop("Runner Alpha", "rushing_yards", 71.5, "FD"),
    ]

    result = build_market_waiver_priority_board(
        _league(),
        board,
        CATALOG,
        props,
    )

    row = result.candidates[0]
    assert row.priority_tier == ACTION_FIT
    assert row.market_fantasy_points is None
    assert row.market_coverage == "THIN"
    assert row.market_component_count == 1


def test_without_prop_markets_board_falls_back_to_structural_context():
    board = RosterNeedWaiverBoard(
        needs=(),
        matches=(
            _match(
                "rb_a",
                "Runner Alpha",
                "RB",
                action_slots=("RB",),
                trend_count=20,
            ),
            _match(
                "rb_b",
                "Runner Beta",
                "RB",
                action_slots=("RB",),
                trend_count=100,
                mine_elsewhere=("Other League",),
            ),
        ),
    )

    result = build_market_waiver_priority_board(
        _league(),
        board,
        CATALOG,
        (),
    )

    assert all(row.priority_tier == ACTION_FIT for row in result.candidates)
    assert result.candidates[0].sleeper_player_id == "rb_b"
    assert result.market_backed_count == 0


def test_watch_fit_labels_are_explicit():
    board = RosterNeedWaiverBoard(
        needs=(),
        matches=(
            _match("wr_a", "Wide Alpha", "WR", watch_slots=("WR",)),
        ),
    )

    result = build_market_waiver_priority_board(
        _league(),
        board,
        CATALOG,
        (),
    )

    assert result.candidates[0].priority_tier == WATCH_FIT
    assert priority_label(WATCH_FIT) == "Monitor · Watch fit"
    assert "Investigate first" in priority_label(MARKET_BACKED_ACTION)


def test_waiver_priority_limit_is_bounded():
    board = RosterNeedWaiverBoard(needs=(), matches=())

    try:
        build_market_waiver_priority_board(
            _league(),
            board,
            CATALOG,
            (),
            limit=0,
        )
    except ValueError as exc:
        assert "1 to 100" in str(exc)
    else:
        raise AssertionError("invalid waiver priority limit must fail")


def test_fantasy_hq_exposes_market_backed_waiver_priority():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Market-Backed Waiver Priority" in page
    assert "build_market_waiver_priority_board" in page
    assert "Investigate first" in page
    assert "Current-week market baseline" in page
