from __future__ import annotations

import base64
import copy
import json

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


def owner_secrets() -> dict:
    return {
        "MARGIN_GITHUB_TOKEN": "token",
        "MARGIN_GITHUB_REPO": "tucknub/propwar-private-state",
        "PROPWAR_OWNER_EMAIL": "owner@example.com",
        "auth": {
            "redirect_uri": "https://propwar.streamlit.app/oauth2callback",
            "cookie_secret": "cookie-secret",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
        },
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


def test_zero_margin_is_preserved_as_a_valid_completed_week() -> None:
    committed = state_store.commit_pick_state(base_state(), audit(), "LAC")
    updated = state_store.complete_week_state(committed, 0)
    assert updated["completed_week"] == 1
    assert updated["current_week"] == 2
    assert updated["used_teams"] == ["LAC"]
    assert updated["cumulative_score"] == 0.0
    assert updated["weekly_results"][0]["actual_margin"] == 0.0
    assert updated["current_decision"]["status"] == "NEEDS_REFRESH"
    assert updated["current_decision"]["committed_pick"] is None


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


def test_write_config_requires_private_repo_secret_and_complete_owner_oidc() -> None:
    assert state_store.config_from_secrets({}) is None
    assert state_store.config_from_secrets({"MARGIN_GITHUB_TOKEN": "x"}) is None

    missing_repo = owner_secrets()
    missing_repo.pop("MARGIN_GITHUB_REPO")
    assert state_store.config_from_secrets(missing_repo) is None

    config = state_store.config_from_secrets(owner_secrets())
    assert config is not None
    assert config["repo"] == "tucknub/propwar-private-state"
    assert config["branch"] == "main"
    assert config["path"] == "margin/live_state_2026.json"
    assert config["auth_mode"] == "OIDC_OWNER"


def test_owner_write_authorization_uses_oidc_identity(monkeypatch) -> None:
    config = state_store.config_from_secrets(owner_secrets())
    assert config is not None

    monkeypatch.setattr(
        state_store,
        "_current_streamlit_user",
        lambda: {"is_logged_in": True, "email": "OWNER@example.com", "email_verified": True},
    )
    assert state_store.owner_write_authorized(config) is True

    monkeypatch.setattr(
        state_store,
        "_current_streamlit_user",
        lambda: {"is_logged_in": True, "email": "other@example.com", "email_verified": True},
    )
    assert state_store.owner_write_authorized(config) is False


def test_public_app_repo_is_rejected_before_network_access(monkeypatch) -> None:
    config = {
        "token": "token",
        "repo": "tucknub/nfl-prop-war-room",
        "branch": "streamlit-cloud-deploy",
        "path": "src/margin/live_state_2026.json",
    }
    monkeypatch.setattr(state_store, "_github_json", lambda *args, **kwargs: pytest.fail("network should not be called"))
    with pytest.raises(RuntimeError, match="separate private"):
        state_store.fetch_remote_state(config)


def test_private_remote_state_is_loaded_as_authority(monkeypatch) -> None:
    config = {
        "token": "token",
        "repo": "tucknub/propwar-private-state",
        "branch": "main",
        "path": "margin/live_state_2026.json",
    }
    state = base_state()
    encoded = base64.b64encode(json.dumps(state).encode("utf-8")).decode("ascii")

    def fake_github_json(_config, method, url, payload=None):
        assert method == "GET"
        if url.endswith("/repos/tucknub/propwar-private-state"):
            return {"private": True, "visibility": "private"}
        assert "margin/live_state_2026.json" in url
        return {"content": encoded, "sha": "state-sha"}

    monkeypatch.setattr(state_store, "_github_json", fake_github_json)
    loaded, sha = state_store.fetch_remote_state(config)
    assert loaded == state
    assert sha == "state-sha"


def test_non_private_remote_state_is_rejected(monkeypatch) -> None:
    config = {
        "token": "token",
        "repo": "tucknub/not-private",
        "branch": "main",
        "path": "margin/live_state_2026.json",
    }
    monkeypatch.setattr(
        state_store,
        "_github_json",
        lambda *_args, **_kwargs: {"private": False, "visibility": "public"},
    )
    with pytest.raises(RuntimeError, match="not private"):
        state_store.fetch_remote_state(config)
