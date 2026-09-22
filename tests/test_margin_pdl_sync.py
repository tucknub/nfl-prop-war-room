from __future__ import annotations

import copy

import pytest

from src.margin import pdl_sync


def stored_state() -> dict:
    return {
        "schema_version": "margin_live_state_v1",
        "season": 2026,
        "current_week": 1,
        "completed_week": 0,
        "cumulative_score": 0.0,
        "used_teams": [],
        "weekly_results": [],
        "pool": {
            "first_place_tie_rule": "split",
            "pick_deadline": "Sunday 12:55 PM ET",
            "picks_visible_before_deadline": False,
            "payout_structure": "winner_take_all",
        },
        "opponents": [],
        "current_decision": {"status": "NEEDS_REFRESH", "committed_pick": None},
        "model_policy": {"anchor_ev_threshold": 0.5},
    }


def entry(name: str, w1: str = "Jaguars", w2: str = "Buccaneers") -> dict:
    return {
        "name": name,
        "status": "ACTIVE",
        "weeks": [
            {"week": 1, "team": w1, "margin": 24, "status": "FINAL"},
            {"week": 2, "team": w2, "margin": -4, "status": "FINAL"},
        ],
    }


def payload(active_count: int = 3) -> dict:
    entrants = [entry("Ricky T.")]
    entrants.extend(entry(f"Opponent {i}", "Jaguars", "49ers") for i in range(1, active_count))
    entrants.append({"name": "Removed", "status": "REMOVED", "weeks": []})
    return {
        "schema_version": "pdl_season_v2",
        "league": {
            "name": "Point Differential League",
            "season": 2026,
            "current_week": 2,
            "completed_week": 2,
            "updated": "2026-09-21",
        },
        "teams": {
            "Jaguars": "jax",
            "Buccaneers": "tb",
            "49ers": "sf",
            "Rams": "lar",
            "Commanders": "wsh",
        },
        "entrants": entrants,
        "data_fingerprint_sha256": "fixture-fingerprint",
    }


def test_ricky_history_becomes_authoritative_margin_state() -> None:
    state = pdl_sync.reconcile_state(stored_state(), payload())
    assert state["current_week"] == 3
    assert state["completed_week"] == 2
    assert state["cumulative_score"] == 20.0
    assert state["used_teams"] == ["JAX", "TB"]
    assert "SF" not in state["used_teams"]
    assert state["weekly_results"] == [
        {"week": 1, "team": "JAX", "actual_margin": 24.0},
        {"week": 2, "team": "TB", "actual_margin": -4.0},
    ]


def test_full_active_field_is_loaded_without_removed_entrant() -> None:
    state = pdl_sync.reconcile_state(stored_state(), payload(active_count=42))
    assert state["pool"]["size"] == 42
    assert len(state["opponents"]) == 41
    assert state["pool"]["first_place_tie_rule"] == "split"
    assert all(row["name"] != "Removed" for row in state["opponents"])


def test_missing_final_week_is_rejected() -> None:
    data = payload()
    data["entrants"][1]["weeks"] = data["entrants"][1]["weeks"][:1]
    with pytest.raises(ValueError, match="finalized weeks"):
        pdl_sync.reconcile_state(stored_state(), data)


def test_reused_team_is_rejected() -> None:
    data = payload()
    data["entrants"][1]["weeks"][1]["team"] = "Jaguars"
    with pytest.raises(ValueError, match="reused team JAX"):
        pdl_sync.reconcile_state(stored_state(), data)


def test_private_current_week_commit_is_preserved_until_pdl_logs_pick() -> None:
    stored = stored_state()
    stored["current_week"] = 3
    stored["completed_week"] = 2
    stored["used_teams"] = ["JAX", "TB"]
    stored["weekly_results"] = [
        {"week": 1, "team": "JAX", "actual_margin": 24.0},
        {"week": 2, "team": "TB", "actual_margin": -4.0},
    ]
    stored["cumulative_score"] = 20.0
    stored["current_decision"] = {"status": "COMMITTED", "committed_pick": "KC"}
    state = pdl_sync.reconcile_state(stored, payload())
    assert state["current_decision"]["committed_pick"] == "KC"


def test_pdl_pending_pick_overrides_private_commit() -> None:
    stored = stored_state()
    stored["current_week"] = 3
    stored["current_decision"] = {"status": "COMMITTED", "committed_pick": "KC"}
    data = payload()
    data["entrants"][0]["weeks"].append(
        {"week": 3, "team": "49ers", "margin": None, "status": "PENDING"}
    )
    state = pdl_sync.reconcile_state(stored, data)
    assert state["current_decision"]["committed_pick"] == "SF"
    assert state["current_decision"]["reason"].startswith("Synced from")


def test_espn_team_aliases_map_to_propwar_canonical_codes() -> None:
    data = payload(active_count=2)
    data["entrants"][0]["weeks"] = [
        {"week": 1, "team": "Rams", "margin": 7, "status": "FINAL"},
        {"week": 2, "team": "Commanders", "margin": 3, "status": "FINAL"},
    ]
    data["entrants"][1]["weeks"] = [
        {"week": 1, "team": "Jaguars", "margin": 1, "status": "FINAL"},
        {"week": 2, "team": "49ers", "margin": 2, "status": "FINAL"},
    ]
    state = pdl_sync.reconcile_state(stored_state(), data)
    assert state["used_teams"] == ["LA", "WAS"]
