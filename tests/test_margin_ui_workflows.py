from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.margin import live_engine_v2 as margin_live  # noqa: E402
from src.margin import state_store  # noqa: E402


PAGE = ROOT / "dashboard" / "pages" / "07_Margin_War_Room.py"


def _base_state() -> dict[str, Any]:
    return {
        "season": 2026,
        "current_week": 1,
        "completed_week": 0,
        "cumulative_score": 0.0,
        "used_teams": [],
        "weekly_results": [],
        "pool": {
            "name": None,
            "size": None,
            "pick_deadline": None,
            "picks_visible_before_deadline": None,
            "first_place_tie_rule": None,
            "payout_structure": "winner_take_all",
        },
        "opponents": [],
        "current_decision": {
            "status": "PROVISIONAL",
            "provisional_pick": "LAC",
            "committed_pick": None,
        },
    }


def _audit_for(state: dict[str, Any]) -> dict[str, Any]:
    championship_ready = bool(state.get("opponents"))
    recommended = "JAX" if championship_ready else "LAC"
    board = [
        {
            "team": "LAC",
            "opponent": "ARI",
            "current_spread": 10.5,
            "calibrated_margin": 11.1,
            "p_loss": 0.18,
            "p_win20": 0.26,
            "status": "ANCHOR" if recommended == "JAX" else "PICK",
            "future_cost": 1.0,
            "total_season_ev": 20.0,
            "total_season_ev_delta_vs_anchor": 0.0,
            "current_sacrifice_vs_anchor": 0.0,
        },
        {
            "team": "JAX",
            "opponent": "CLE",
            "current_spread": 7.5,
            "calibrated_margin": 7.9,
            "p_loss": 0.26,
            "p_win20": 0.19,
            "status": "PICK" if recommended == "JAX" else "SAVE/PIVOT",
            "future_cost": 0.5,
            "total_season_ev": 19.5,
            "total_season_ev_delta_vs_anchor": 0.5 if recommended == "JAX" else -0.5,
            "current_sacrifice_vs_anchor": 3.0,
        },
    ]
    pick = next(row for row in board if row["team"] == recommended)
    anchor = board[0]
    return {
        "season": 2026,
        "week": int(state["current_week"]),
        "snapshot_utc": "2026-08-29T12:00:00+00:00",
        "pick": dict(pick),
        "anchor": dict(anchor),
        "policy": {
            "expected_points_pick": "LAC",
            "anchor": "LAC",
            "championship_status": "READY_FOR_SIMULATION" if championship_ready else "UNAVAILABLE_POOL_STATE_MISSING",
            "championship_override_promoted": True,
            "championship_override_applied": championship_ready,
            "championship_override_status": "APPLIED" if championship_ready else "NOT_READY",
        },
        "championship": {},
        "used_teams": list(state.get("used_teams", [])),
        "board": board,
        "route": [
            {
                "week": int(state["current_week"]),
                "team": recommended,
                "opponent": pick["opponent"],
                "raw_value_spread": pick["current_spread"],
                "calibrated_ev": pick["calibrated_margin"],
                "value_source": "CURRENT_MARKET",
            }
        ],
        "data_quality": {
            "current_week_games": 2,
            "current_week_posted_spreads": 2,
            "season_games": 272,
            "fallback_hfa": 1.5,
        },
    }


def _install_private_state(monkeypatch, initial_state: dict[str, Any]) -> dict[str, Any]:
    config = {
        "token": "test-token",
        "repo": "tucknub/ci-private-margin-state",
        "branch": "main",
        "path": "margin/live_state_2026.json",
        "auth_mode": "OIDC_OWNER",
        "owner_email": "owner@example.com",
    }
    box: dict[str, Any] = {
        "state": copy.deepcopy(initial_state),
        "writes": [],
        "calculation_states": [],
        "stale_on_transition": False,
        "stale_fetch_count": 0,
    }

    def fetch_remote_state(_config):
        if box["stale_on_transition"]:
            box["stale_fetch_count"] += 1
            if box["stale_fetch_count"] >= 2:
                stale = copy.deepcopy(box["state"])
                stale["cumulative_score"] = 99.0
                return stale, "stale-state-sha"
        return copy.deepcopy(box["state"]), "state-sha"

    def write_remote_state(_config, new_state, *, expected_sha, message):
        box["writes"].append(
            {
                "state": copy.deepcopy(new_state),
                "expected_sha": expected_sha,
                "message": message,
            }
        )
        box["state"] = copy.deepcopy(new_state)
        return "abcdef1234567890"

    monkeypatch.setattr(state_store, "config_from_secrets", lambda _secrets: dict(config))
    monkeypatch.setattr(state_store, "owner_write_authorized", lambda _config: True)
    monkeypatch.setattr(state_store, "fetch_remote_state", fetch_remote_state)
    monkeypatch.setattr(state_store, "write_remote_state", write_remote_state)
    def run_margin(state, future_posted_mode="live"):
        box["calculation_states"].append(copy.deepcopy(state))
        return _audit_for(state)

    monkeypatch.setattr(margin_live, "run", run_margin)
    return box


def _element_by_label(elements, label: str):
    return next(element for element in elements if str(element.label) == label)


def _metric_values(app: AppTest) -> dict[str, str]:
    return {str(metric.label): str(metric.value) for metric in app.metric}


def _preview_field(app: AppTest) -> None:
    _element_by_label(app.text_input, "Pool name").set_value("Official Margin Pool")
    _element_by_label(app.number_input, "Entrants (0 = infer from rows)").set_value(3)
    _element_by_label(app.selectbox, "First-place tie rule").set_value("split")
    _element_by_label(app.selectbox, "Picks before deadline").set_value("hidden")
    _element_by_label(app.text_input, "Pick deadline").set_value("Sunday 12:55 PM ET")
    _element_by_label(app.text_area, "Or paste the same CSV").set_value(
        "id,name,cumulative_score,used_teams\n"
        "opp-a,Opponent A,12,\n"
        "opp-b,Opponent B,-4,\n"
    )
    _element_by_label(app.button, "Validate & preview field").click()
    app.run()


def test_week_completion_requires_confirmation_and_accepts_confirmed_zero(monkeypatch) -> None:
    state = _base_state()
    committed = state_store.commit_pick_state(state, _audit_for(state), "LAC")
    box = _install_private_state(monkeypatch, committed)

    app = AppTest.from_file(str(PAGE), default_timeout=20).run()
    assert not app.exception

    _element_by_label(app.button, "Complete Week 1").click()
    app.run()
    assert box["writes"] == []
    assert any("Confirm the official final margin" in str(item.value) for item in app.warning)

    _element_by_label(
        app.checkbox,
        "I confirm this is the official final margin for LAC in Week 1.",
    ).set_value(True)
    _element_by_label(app.number_input, "Final point differential").set_value(0.0)
    _element_by_label(app.button, "Complete Week 1").click()
    app.run()

    assert not app.exception
    assert len(box["writes"]) == 1
    saved = box["state"]
    assert saved["completed_week"] == 1
    assert saved["current_week"] == 2
    assert saved["used_teams"] == ["LAC"]
    assert saved["cumulative_score"] == 0.0
    assert saved["weekly_results"][0]["actual_margin"] == 0.0
    assert saved["current_decision"]["status"] == "NEEDS_REFRESH"
    assert saved["current_decision"]["committed_pick"] is None


def test_validated_preview_is_non_mutating_until_confirmed_and_then_becomes_authoritative(monkeypatch) -> None:
    initial = _base_state()
    box = _install_private_state(monkeypatch, initial)
    app = AppTest.from_file(str(PAGE), default_timeout=20).run()
    assert _metric_values(app)["RECOMMENDED"] == "LAC"

    _preview_field(app)

    assert not app.exception
    assert box["writes"] == []
    assert box["state"] == initial
    preview_metrics = _metric_values(app)
    assert preview_metrics["RECOMMENDED"] == "LAC"
    assert preview_metrics["Preview PICK"] == "JAX"
    preview_calculations = sum(bool(item.get("opponents")) for item in box["calculation_states"])
    assert preview_calculations == 1

    _element_by_label(app.button, "Save validated field to Margin state").click()
    app.run()
    assert box["writes"] == []
    assert any("Confirm the validated field" in str(item.value) for item in app.warning)

    _element_by_label(
        app.checkbox,
        "I confirm the pool standings, scores, and burned-team inventories match the official Margin Pool.",
    ).set_value(True)
    _element_by_label(app.button, "Save validated field to Margin state").click()
    app.run()

    assert not app.exception
    assert len(box["writes"]) == 1
    saved = box["state"]
    assert saved["pool"] == {
        "name": "Official Margin Pool",
        "size": 3,
        "pick_deadline": "Sunday 12:55 PM ET",
        "picks_visible_before_deadline": False,
        "first_place_tie_rule": "split",
        "payout_structure": "winner_take_all",
    }
    assert saved["opponents"] == [
        {"id": "opp-a", "name": "Opponent A", "cumulative_score": 12.0, "used_teams": []},
        {"id": "opp-b", "name": "Opponent B", "cumulative_score": -4.0, "used_teams": []},
    ]
    authoritative_metrics = _metric_values(app)
    assert authoritative_metrics["RECOMMENDED"] == "JAX"
    assert "Preview PICK" not in authoritative_metrics
    authoritative_calculations = sum(bool(item.get("opponents")) for item in box["calculation_states"])
    assert authoritative_calculations == 2


def test_stale_authoritative_state_rejects_validated_preview_persistence(monkeypatch) -> None:
    box = _install_private_state(monkeypatch, _base_state())
    app = AppTest.from_file(str(PAGE), default_timeout=20).run()
    _preview_field(app)
    assert box["writes"] == []

    box["stale_on_transition"] = True
    box["stale_fetch_count"] = 0
    _element_by_label(
        app.checkbox,
        "I confirm the pool standings, scores, and burned-team inventories match the official Margin Pool.",
    ).set_value(True)
    _element_by_label(app.button, "Save validated field to Margin state").click()
    app.run()

    assert not app.exception
    assert box["writes"] == []
    errors = "\n".join(str(item.value) for item in app.error)
    assert "Authoritative private state changed" in errors
    assert _metric_values(app)["Preview PICK"] == "JAX"
