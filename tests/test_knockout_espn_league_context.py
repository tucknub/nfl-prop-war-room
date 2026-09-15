from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.fantasy.espn import _library_player_row
from src.knockout import engine
from src.knockout.espn_sync import apply_espn_snapshot


def _state() -> dict:
    return {
        "schema_version": "knockout_live_state_v1",
        "season": 2026,
        "status": "ACTIVE",
        "current_week": 2,
        "faab_remaining": 1000,
        "roster": _roster("Mine"),
        "weekly_results": [],
        "eliminations": [],
        "released_rosters": [],
        "faab_transactions": [],
        "league": {
            "name": "Elwood TKO",
            "teams": 18,
            "scoring": "FULL_PPR",
            "roster_size": 14,
            "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DST": 1},
            "faab_start": 1000,
            "faab_type": "CONTINUOUS",
            "trades_allowed": False,
            "elimination_rule": "LOWEST_WEEKLY_SCORE",
            "elimination_weeks": "1-17",
            "eliminated_roster_to_waivers": True,
            "espn_league_id": "60191612",
            "espn_team_id": 7,
        },
        "espn_connection": {
            "provider": "ESPN",
            "mode": "PRIVATE_COOKIE_READ_ONLY",
            "league_id": "60191612",
            "league_name": "Elwood TKO",
            "team_id": 7,
            "team_name": "Ricky's Rowdy Team",
            "credential_envelope": "encrypted-token",
        },
    }


def _roster(prefix: str) -> list[dict[str, str]]:
    positions = ["QB", "RB", "RB", "RB", "RB", "RB", "RB", "WR", "WR", "WR", "WR", "TE", "K", "DST"]
    teams = ["DAL", "LAC", "DEN", "WSH", "ARI", "KC", "SF", "PHI", "CIN", "CLE", "NYJ", "NYG", "BAL", "NYJ"]
    return [
        {"player": f"{prefix} {index}", "position": position, "nfl_team": team}
        for index, (position, team) in enumerate(zip(positions, teams), 1)
    ]


def _snapshot() -> dict:
    return {
        "provider": "ESPN",
        "league_id": "60191612",
        "league_name": "Elwood TKO",
        "season": 2026,
        "team_count": 18,
        "team_id": 7,
        "team_name": "Ricky's Rowdy Team",
        "current_week": 2,
        "faab_remaining": 1000,
        "current_score": None,
        "roster": _roster("Mine"),
    }


def test_library_player_row_normalizes_espn_player() -> None:
    player = SimpleNamespace(
        name="Saquon Barkley",
        position="RB",
        proTeam="PHI",
        playerId=3929630,
        injuryStatus="ACTIVE",
        percent_owned=99.9,
        projected_points=18.4,
    )
    assert _library_player_row(player) == {
        "player": "Saquon Barkley",
        "position": "RB",
        "nfl_team": "PHI",
        "espn_player_id": "3929630",
        "injury_status": "ACTIVE",
        "percent_owned": 99.9,
        "projected_points": 18.4,
    }


def test_snapshot_reconciles_elimination_release_and_waiver_pool() -> None:
    state = _state()
    snapshot = _snapshot()
    snapshot["available_players"] = [
        {"player": "Saquon Barkley", "position": "RB", "nfl_team": "PHI", "percent_owned": 99.9},
        {"player": "Drake London", "position": "WR", "nfl_team": "ATL", "percent_owned": 99.0},
    ]
    snapshot["league_week_scores"] = [
        {"week": 1, "team_id": 7, "team": "Ricky's Rowdy Team", "score": 121.5},
        {"week": 1, "team_id": 3, "team": "Natasha's Team", "score": 62.0},
    ]
    snapshot["detected_elimination"] = {
        "week": 1,
        "team_id": 3,
        "team": "Natasha's Team",
        "score": 62.0,
        "user_score": 121.5,
        "user_eliminated": False,
        "players": _roster("Released"),
    }

    updated = apply_espn_snapshot(state, snapshot)
    assert updated["eliminations"] == [{"week": 1, "team": "Natasha's Team"}]
    assert updated["weekly_results"] == [{"week": 1, "user_score": 121.5, "user_eliminated": False}]
    assert len(updated["released_rosters"]) == 1
    assert len(updated["released_rosters"][0]["players"]) == 14
    assert engine.active_team_count(updated) == 17
    assert [row["player"] for row in updated["espn_connection"]["available_players"]] == ["Saquon Barkley", "Drake London"]

    resynced = apply_espn_snapshot(updated, snapshot)
    assert len(resynced["eliminations"]) == 1
    assert len(resynced["weekly_results"]) == 1
    assert len(resynced["released_rosters"]) == 1


def test_conflicting_detected_elimination_never_overwrites_ledger() -> None:
    state = _state()
    state["eliminations"] = [{"week": 1, "team": "Stored Team"}]
    snapshot = _snapshot()
    snapshot["detected_elimination"] = {
        "week": 1,
        "team_id": 3,
        "team": "Different Team",
        "score": 50.0,
        "user_score": 100.0,
        "user_eliminated": False,
        "players": [],
    }
    with pytest.raises(ValueError, match="different Week 1 elimination"):
        apply_espn_snapshot(state, snapshot)


def test_failed_league_context_keeps_last_good_pool() -> None:
    state = _state()
    state["espn_connection"]["available_players"] = [
        {"player": "Existing Player", "position": "RB", "nfl_team": "TB"}
    ]
    snapshot = _snapshot()
    snapshot["league_context_error"] = "temporary read failure"
    updated = apply_espn_snapshot(state, snapshot)
    assert updated["espn_connection"]["available_players"][0]["player"] == "Existing Player"
    assert updated["espn_connection"]["league_context_error"] == "temporary read failure"
