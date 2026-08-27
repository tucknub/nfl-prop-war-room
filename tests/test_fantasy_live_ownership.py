from __future__ import annotations

import pytest

from src.fantasy.live_ownership import (
    AVAILABLE,
    MINE,
    OTHER,
    STARTER,
    UnsafeLiveOwnership,
    lookup_live_sleeper_player,
    my_players_available_elsewhere,
)
from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    Manager,
    Roster,
)


def _league(
    league_id: str,
    name: str,
    *,
    my_players=(),
    other_players=(),
    ownership_ready=True,
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
            roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Me",
                team_name=f"{name} Mine",
            ),
            Manager(
                platform_user_id="opp",
                display_name="Opponent",
                team_name=f"{name} Opp",
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=tuple(my_players),
                starters=tuple(my_players[:1]),
                reserve=(),
                taxi=(),
            ),
            Roster(
                platform_roster_id="2",
                platform_user_id="opp",
                players=tuple(other_players),
                starters=(),
                reserve=(),
                taxi=(),
            ),
        ),
        rules_ready=True,
        draft_ready=False,
        ownership_ready=ownership_ready,
    )


def test_lookup_live_player_shows_mine_other_and_available():
    leagues = (
        _league("l1", "Papa John's", my_players=("p1",)),
        _league("l2", "Franchise", other_players=("p1",)),
        _league("l3", "Third League"),
    )

    result = lookup_live_sleeper_player(leagues, "p1")

    assert [row.status for row in result.statuses] == [MINE, OTHER, AVAILABLE]
    assert result.statuses[0].roster_slot == STARTER
    assert result.statuses[0].owner_name == "Papa John's Mine"
    assert result.statuses[1].owner_name == "Franchise Opp"
    assert result.mine_in == ("Papa John's",)
    assert result.available_in == ("Third League",)
    assert result.owned_elsewhere_in == ("Franchise",)
    assert result.actionable_elsewhere is True


def test_my_players_available_elsewhere_only_returns_actionable_players():
    leagues = (
        _league("l1", "Papa John's", my_players=("p1", "p2")),
        _league("l2", "Franchise", my_players=("p2",), other_players=("p1",)),
        _league("l3", "Third", other_players=("p2",)),
    )

    rows = my_players_available_elsewhere(leagues)

    assert [row.sleeper_player_id for row in rows] == ["p1"]
    assert rows[0].available_in == ("Third",)

    leagues = (
        _league("l1", "Papa John's", my_players=("p1", "p2")),
        _league("l2", "Franchise", other_players=("p2",)),
    )

    rows = my_players_available_elsewhere(leagues)

    assert [row.sleeper_player_id for row in rows] == ["p1"]
    assert rows[0].mine_in == ("Papa John's",)
    assert rows[0].available_in == ("Franchise",)


def test_lookup_preserves_unknown_when_provider_ownership_not_ready():
    leagues = (
        _league(
            "l1",
            "Pre-Draft",
            ownership_ready=False,
        ),
    )

    result = lookup_live_sleeper_player(leagues, "p1")

    assert result.statuses[0].status == "UNKNOWN"
    assert result.statuses[0].available is False


def test_duplicate_provider_ownership_fails_closed():
    league = _league("l1", "Broken", my_players=("p1",), other_players=("p1",))

    with pytest.raises(UnsafeLiveOwnership, match="multiple rosters"):
        lookup_live_sleeper_player((league,), "p1")


def test_blank_player_id_is_rejected():
    with pytest.raises(ValueError, match="required"):
        lookup_live_sleeper_player((), "")


def test_fantasy_hq_exposes_cross_league_ownership_ui():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert '"Cross-league"' in page
    assert "My players available in another league" in page
    assert "Look up any player" in page
    assert "lookup_live_sleeper_player" in page
    assert "my_players_available_elsewhere" in page
    assert "Sleeper leagues scanned" in page
