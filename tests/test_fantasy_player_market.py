from __future__ import annotations

import pytest

from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.player_market import build_player_market_map
from src.fantasy.team_explorer import HIGH, LOW, MEDIUM


CATALOG = {
    "rb_target": {
        "full_name": "Target Runner",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "IND",
        "status": "Active",
        "active": True,
    },
    "qb1": {"full_name": "QB One", "position": "QB", "team": "BUF", "status": "Active", "active": True},
    "rb1": {"full_name": "RB One", "position": "RB", "team": "DET", "status": "Active", "active": True},
    "rb2": {"full_name": "RB Two", "position": "RB", "team": "ATL", "status": "Active", "active": True},
    "rb3": {"full_name": "RB Three", "position": "RB", "team": "GB", "status": "Active", "active": True},
    "wr1": {"full_name": "WR One", "position": "WR", "team": "PHI", "status": "Active", "active": True},
    "wr2": {"full_name": "WR Two", "position": "WR", "team": "CIN", "status": "Active", "active": True},
    "te1": {"full_name": "TE One", "position": "TE", "team": "KC", "status": "Active", "active": True},
}


def _league(*, target_owned_by: str | None = None, ownership_ready=True):
    a_players = ["qb1", "rb1", "wr1", "te1"]
    b_players = ["qb1", "rb1", "rb2", "wr1", "wr2", "te1"]
    c_players = ["qb1", "rb1", "rb2", "rb3", "wr1", "wr2", "te1"]
    if target_owned_by == "1":
        a_players.append("rb_target")
    elif target_owned_by == "2":
        b_players.append("rb_target")
    elif target_owned_by == "3":
        c_players.append("rb_target")

    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="League",
        season="2026",
        status="in_season",
        team_count=3,
        previous_platform_league_id=None,
        current_platform_user_id="u1",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(platform_user_id="u1", display_name="One", team_name="Team One"),
            Manager(platform_user_id="u2", display_name="Two", team_name="Team Two"),
            Manager(platform_user_id="u3", display_name="Three", team_name="Team Three"),
        ),
        rosters=(
            Roster("1", "u1", tuple(a_players), tuple(a_players[:4]), (), ()),
            Roster("2", "u2", tuple(b_players), tuple(b_players[:6]), (), ()),
            Roster("3", "u3", tuple(c_players), tuple(c_players[:7]), (), ()),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def test_player_market_map_identifies_available_player_and_team_fit_order():
    result = build_player_market_map(
        _league(),
        "rb_target",
        CATALOG,
    )

    assert result.available is True
    assert result.owner_team is None
    assert result.player_name == "Target Runner"
    assert result.positions == ("RB",)
    assert result.team_fits[0].team_name == "Team One"
    assert result.team_fits[0].fit_level == HIGH
    assert result.high_fit_count >= 1
    assert result.team_fits[-1].fit_level in {MEDIUM, LOW}


def test_player_market_map_identifies_current_owner_and_other_trade_fits():
    result = build_player_market_map(
        _league(target_owned_by="3"),
        "rb_target",
        CATALOG,
    )

    assert result.available is False
    assert result.owner_team == "Team Three"
    owner_rows = [row for row in result.team_fits if row.owns_player]
    assert len(owner_rows) == 1
    assert owner_rows[0].team_name == "Team Three"
    assert owner_rows[0].reason == "Current owner"
    assert result.team_fits[0].team_name != "Team Three"


def test_player_market_map_fails_closed_when_availability_is_unknown():
    with pytest.raises(ValueError, match="unsafe"):
        build_player_market_map(
            _league(ownership_ready=False),
            "rb_target",
            CATALOG,
        )


def test_player_market_map_rejects_missing_player():
    with pytest.raises(ValueError, match="not found"):
        build_player_market_map(
            _league(),
            "missing",
            CATALOG,
        )


def test_fantasy_hq_exposes_player_market_map():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Player Market Map" in page
    assert "build_player_market_map" in page
    assert "Roster-fit interest" in page
    assert "Current owner" in page
    assert "Likely interest" in page
