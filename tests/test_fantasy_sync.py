from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from src.fantasy.identity import MATCHED, NEEDS_REVIEW, PRE_GSIS, TEAM_DEFENSE, UNRESOLVED
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.sync import (
    build_sleeper_identity_audit,
    build_sleeper_sync_result,
    collect_league_player_ids,
)


def _state(
    *,
    players=("1", "2", "3", "IND", "4"),
    starters=None,
    reserve=(),
    taxi=(),
    ownership_ready=True,
) -> FantasyLeagueState:
    player_tuple = tuple(players)
    starter_tuple = tuple(starters) if starters is not None else tuple(player_tuple[:2]) + ("0",)
    roster = Roster(
        platform_roster_id="1",
        platform_user_id="me",
        players=player_tuple,
        starters=starter_tuple,
        reserve=tuple(reserve),
        taxi=tuple(taxi),
        settings={},
    )
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="League One",
        season="2026",
        status="in_season",
        team_count=12,
        previous_platform_league_id="league-0",
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(roster_positions=("QB", "RB", "WR", "FLEX", "BN"), scoring_settings={"rec": 1}),
        draft=None,
        managers=(),
        rosters=(roster,),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def _ffverse() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"sleeper_id": "1", "gsis_id": "00-1", "yahoo_id": "101", "name": "One", "position": "RB", "team": "IND"},
            {"sleeper_id": "2", "gsis_id": None, "yahoo_id": "102", "name": "Two", "position": "WR", "team": "IND"},
            {"sleeper_id": "3", "gsis_id": "00-3", "yahoo_id": "103", "name": "Three", "position": "TE", "team": "IND"},
        ]
    )


def _propwar_crosswalk() -> pd.DataFrame:
    return pd.DataFrame({"player_id": ["00-1"], "player_name": ["One"]})


def _player_map():
    return {
        "1": {"full_name": "One", "position": "RB", "team": "IND", "yahoo_id": "101"},
        "2": {"full_name": "Two", "position": "WR", "team": "IND", "yahoo_id": "102"},
        "3": {"full_name": "Three", "position": "TE", "team": "IND", "yahoo_id": "103"},
        "4": {"full_name": "Four", "position": "WR", "team": "IND"},
        "IND": {"full_name": "Indianapolis Colts", "position": "DEF", "team": "IND", "fantasy_positions": ["DEF"]},
    }


def test_collect_league_player_ids_is_deterministic_and_ignores_sleeper_zero_placeholder():
    state = _state(
        players=("2", "1", "2", "IND"),
        starters=("1", "2", "0"),
        reserve=("2",),
        taxi=("4",),
    )

    assert collect_league_player_ids(state) == ("2", "1", "IND", "4")


def test_identity_audit_reports_each_nonmatching_class_without_overclaiming_readiness():
    audit = build_sleeper_identity_audit(
        _state(),
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar_crosswalk(),
        sleeper_player_map=_player_map(),
    )

    assert audit.player_ids == ("1", "2", "3", "IND", "4")
    assert audit.total_players == 5
    assert audit.counts == {
        MATCHED: 1,
        PRE_GSIS: 1,
        NEEDS_REVIEW: 1,
        UNRESOLVED: 1,
        TEAM_DEFENSE: 1,
    }
    assert audit.unlinked_player_ids == ("2", "3", "4")
    assert audit.status == "NEEDS_REVIEW"
    assert audit.role_join_ready is False


def test_ownership_ready_does_not_imply_identity_ready():
    result = build_sleeper_sync_result(
        _state(ownership_ready=True),
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar_crosswalk(),
        sleeper_player_map=_player_map(),
    )

    assert result.ownership_ready is True
    assert result.identity_status == "NEEDS_REVIEW"
    assert result.role_join_ready is False
    assert result.player_metadata_entries_used == 5


def test_pre_gsis_only_is_partial_not_failed_and_not_role_join_ready():
    state = _state(players=("1", "2"))
    result = build_sleeper_sync_result(
        state,
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar_crosswalk(),
        sleeper_player_map=_player_map(),
    )

    assert result.identity_audit.matched_players == 1
    assert result.identity_audit.pre_gsis_players == 1
    assert result.identity_status == "PARTIAL"
    assert result.role_join_ready is False


def test_exact_players_and_team_defense_produce_ready_identity_coverage():
    state = _state(players=("1", "IND"))
    result = build_sleeper_sync_result(
        state,
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar_crosswalk(),
        sleeper_player_map=_player_map(),
    )

    assert result.identity_audit.matched_players == 1
    assert result.identity_audit.team_defenses == 1
    assert result.identity_status == "READY"
    assert result.role_join_ready is True


def test_empty_pre_draft_rosters_report_no_players_instead_of_ready():
    roster = Roster(
        platform_roster_id="1",
        platform_user_id="me",
        players=(),
        starters=("0", "0"),
        reserve=(),
        taxi=(),
        settings={},
    )
    state = replace(_state(), rosters=(roster,), ownership_ready=False)

    audit = build_sleeper_identity_audit(
        state,
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar_crosswalk(),
        sleeper_player_map=_player_map(),
    )

    assert audit.total_players == 0
    assert audit.status == "NO_PLAYERS"
    assert audit.role_join_ready is False


def test_audit_rejects_non_sleeper_state():
    yahoo_state = replace(_state(), platform="YAHOO")

    with pytest.raises(ValueError, match="SLEEPER"):
        build_sleeper_identity_audit(
            yahoo_state,
            ffverse_player_ids=_ffverse(),
            propwar_identity_crosswalk=_propwar_crosswalk(),
            sleeper_player_map=_player_map(),
        )
