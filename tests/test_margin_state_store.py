from __future__ import annotations

import copy

import pytest

from src.margin import state_store


def base_state() -> dict:
    return {
        "season": 2026,
        "current_week": 1,
        "completed_week": 0,
        "cumulative_score": 0.0,
        "used_teams": [],
        "weekly_results": [],
        "pool": {},
        "opponents": [],
        "current_decision": {
            "status": "PROVISIONAL",
            "provisional_pick": "LAC",
            "committed_pick": None,
        },
    }


def audit() -> dict:
    return {
        "season": 2026,
        "week": 1,
        "snapshot_utc": "2026-08-24T12:00:00+00:00",
        "pick": {"team": "LAC"},
        "anchor": {"team": "LAC"},
        "policy": {
            "expected_points_pick": "LAC",
            "anchor": "LAC",
            "championship_override_applied": False,
        },
        "board": [
            {
                "team": "LAC",
                "opponent": "ARI",
                "current_spread": 10.5,
                "calibrated_margin": 11.12,
                "p_loss": 0.179,
                "p_win20": 0.264,
            },
            {
                "team": "JAX",
                "opponent": "CLE",
                "current_spread": 7.5,
                "calibrated_margin": 7.92,
                "p_loss": 0.258,
                "p_win20": 0.188,
            },
        ],
    }


def test_commit_pick_records_selected_team_without_burning_it() -> None:
    state = base_state()
    updated = state_store.commit_pick_state(
        state,
        audit(),
        "JAX",
        now_iso="2026-08-24T12:01:00+00:00",
    )
    assert state["current_decision"]["committed_pick"] is None
    assert updated["current_decision"]["status"] == "COMMITTED"
    assert updated["current_decision"]["committed_pick"] == "JAX"
    assert updated["current_decision"]["current_spread"] == 7.5
    assert updated["current_decision"]["expected_points_pick"] == "LAC"
    assert updated["used_teams"] == []
    assert updated["completed_week"] == 0


def test_commit_pick_can_be_replaced_before_completion() -> None:
    first = state_store.commit_pick_state(base_state(), audit(), "LAC")
    second = state_store.commit_pick_state(first, audit(), "JAX")
    assert second["current_decision"]["committed_pick"] == "JAX"
    assert second["used_teams"] == []


def test_complete_week_burns_team_updates_score_and_advances() -> None:
    committed = state_store.commit_pick_state(base_state(), audit(), "LAC")
    updated = state_store.complete_week_state(
        committed,
        14,
        now_iso="2026-09-13T20:00:00+00:00",
    )
    assert updated["completed_week"] == 1
    assert updated["current_week"] == 2
    assert updated["used_teams"] == ["LAC"]
    assert updated["cumulative_score"] == 14.0
    assert updated["weekly_results"] == [
        {
            "week": 1,
            "team": "LAC",
            "actual_margin": 14.0,
            "completed_at_utc": "2026-09-13T20:00:00+00:00",
        }
    ]
    assert updated["current_decision"]["status"] == "NEEDS_REFRESH"
    assert updated["current_decision"]["committed_pick"] is None


def test_negative_margin_is_preserved() -> None:
    committed = state_store.commit_pick_state(base_state(), audit(), "JAX")
    updated = state_store.complete_week_state(committed, -6)
    assert updated["cumulative_score"] == -6.0
    assert updated["weekly_results"][0]["actual_margin"] == -6.0


def test_completion_requires_committed_pick() -> None:
    with pytest.raises(ValueError, match="must be committed"):
        state_store.complete_week_state(base_state(), 7)


def test_used_team_cannot_be_committed() -> None:
    state = base_state()
    state["current_week"] = 2
    state["completed_week"] = 1
    state["used_teams"] = ["LAC"]
    state["weekly_results"] = [{"week": 1, "team": "LAC", "actual_margin": 3.0}]
    state["cumulative_score"] = 3.0
    week2_audit = copy.deepcopy(audit())
    week2_audit["week"] = 2
    with pytest.raises(ValueError, match="already used"):
        state_store.commit_pick_state(state, week2_audit, "LAC")


def test_admin_config_requires_token_and_key() -> None:
    assert state_store.config_from_secrets({}) is None
    assert state_store.config_from_secrets({"MARGIN_GITHUB_TOKEN": "x"}) is None
    config = state_store.config_from_secrets({
        "MARGIN_GITHUB_TOKEN": "token",
        "MARGIN_ADMIN_KEY": "secret",
    })
    assert config is not None
    assert config["repo"] == "tucknub/nfl-prop-war-room"
    assert config["branch"] == "streamlit-cloud-deploy"
    assert state_store.admin_key_valid(config, "secret") is True
    assert state_store.admin_key_valid(config, "wrong") is False
