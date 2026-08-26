from __future__ import annotations

import pandas as pd
import pytest

from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.service import sync_sleeper_league, sync_sleeper_leagues


class FakeSleeperReader:
    def __init__(self, states):
        self.states = dict(states)
        self.calls = []

    def fetch_normalized_league(self, league_id, *, current_user_id=None):
        self.calls.append((league_id, current_user_id))
        return self.states[league_id]


def _state(league_id: str, players) -> FantasyLeagueState:
    roster = Roster(
        platform_roster_id="1",
        platform_user_id="me",
        players=tuple(players),
        starters=tuple(players),
        reserve=(),
        taxi=(),
        settings={},
    )
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name=f"League {league_id}",
        season="2026",
        status="in_season",
        team_count=12,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(roster_positions=("QB", "RB", "WR", "BN"), scoring_settings={"rec": 1}),
        draft=None,
        managers=(),
        rosters=(roster,),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _ffverse():
    return pd.DataFrame(
        [
            {"sleeper_id": "1", "gsis_id": "00-1", "yahoo_id": "101", "name": "One", "position": "RB", "team": "IND"},
            {"sleeper_id": "2", "gsis_id": None, "yahoo_id": "102", "name": "Two", "position": "WR", "team": "IND"},
        ]
    )


def _propwar():
    return pd.DataFrame({"player_id": ["00-1"], "player_name": ["One"]})


def _player_map():
    return {
        "1": {"full_name": "One", "position": "RB", "team": "IND", "yahoo_id": "101"},
        "2": {"full_name": "Two", "position": "WR", "team": "IND", "yahoo_id": "102"},
        "IND": {"full_name": "Indianapolis Colts", "position": "DEF", "team": "IND", "fantasy_positions": ["DEF"]},
    }


def test_single_league_service_fetches_then_applies_identity_audit():
    reader = FakeSleeperReader({"a": _state("a", ("1", "IND"))})

    result = sync_sleeper_league(
        reader,
        "a",
        current_user_id="me",
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar(),
        sleeper_player_map=_player_map(),
    )

    assert reader.calls == [("a", "me")]
    assert result.league_state.platform_league_id == "a"
    assert result.identity_status == "READY"
    assert result.role_join_ready is True


def test_multi_league_service_preserves_requested_order_and_builds_player_presence_index():
    reader = FakeSleeperReader(
        {
            "a": _state("a", ("1", "2")),
            "b": _state("b", ("1", "IND")),
        }
    )

    result = sync_sleeper_leagues(
        reader,
        ("b", "a"),
        current_user_id="me",
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar(),
        sleeper_player_map=_player_map(),
    )

    assert result.league_ids == ("b", "a")
    assert reader.calls == [("b", "me"), ("a", "me")]
    assert result.combined_player_ids == ("1", "IND", "2")
    assert result.player_leagues == {
        "1": ("b", "a"),
        "IND": ("b",),
        "2": ("a",),
    }
    assert result.role_join_ready_leagues == ("b",)
    assert result.leagues_needing_identity_attention == ("a",)
    assert result.all_role_join_ready is False


def test_shared_reference_frames_are_not_copied_or_mutated_by_service_contract():
    ffverse = _ffverse()
    propwar = _propwar()
    ffverse_before = ffverse.copy(deep=True)
    propwar_before = propwar.copy(deep=True)
    reader = FakeSleeperReader({"a": _state("a", ("1",)), "b": _state("b", ("1",))})

    result = sync_sleeper_leagues(
        reader,
        ("a", "b"),
        current_user_id="me",
        ffverse_player_ids=ffverse,
        propwar_identity_crosswalk=propwar,
        sleeper_player_map=_player_map(),
    )

    assert result.league_count == 2
    pd.testing.assert_frame_equal(ffverse, ffverse_before)
    pd.testing.assert_frame_equal(propwar, propwar_before)


def test_duplicate_league_ids_fail_before_any_provider_read():
    reader = FakeSleeperReader({"a": _state("a", ("1",))})

    with pytest.raises(ValueError, match="unique"):
        sync_sleeper_leagues(
            reader,
            ("a", "a"),
            current_user_id="me",
            ffverse_player_ids=_ffverse(),
            propwar_identity_crosswalk=_propwar(),
            sleeper_player_map=_player_map(),
        )

    assert reader.calls == []


def test_blank_or_empty_league_list_fails_closed():
    reader = FakeSleeperReader({})

    for league_ids in [(), ("",), (None,)]:
        with pytest.raises(ValueError, match="nonblank"):
            sync_sleeper_leagues(
                reader,
                league_ids,
                current_user_id="me",
                ffverse_player_ids=_ffverse(),
                propwar_identity_crosswalk=_propwar(),
                sleeper_player_map=_player_map(),
            )

    assert reader.calls == []


def test_all_ready_requires_every_league_to_be_role_join_ready():
    reader = FakeSleeperReader(
        {
            "a": _state("a", ("1", "IND")),
            "b": _state("b", ("1",)),
        }
    )

    result = sync_sleeper_leagues(
        reader,
        ("a", "b"),
        current_user_id="me",
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar(),
        sleeper_player_map=_player_map(),
    )

    assert result.role_join_ready_leagues == ("a", "b")
    assert result.leagues_needing_identity_attention == ()
    assert result.all_role_join_ready is True
