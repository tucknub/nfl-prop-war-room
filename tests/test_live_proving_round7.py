from __future__ import annotations

from dashboard import propwar_today_owner as today


def _margin_state(*, complete_field: bool) -> dict:
    pool = {
        "size": 100 if complete_field else None,
        "pick_deadline": "2026-09-13T12:55:00-04:00" if complete_field else None,
        "picks_visible_before_deadline": False if complete_field else None,
        "first_place_tie_rule": "split" if complete_field else None,
    }
    return {
        "season": 2026,
        "current_week": 1,
        "season_complete": False,
        "pool": pool,
        "opponents": [{"id": "opp-1"}] if complete_field else [],
        "current_decision": {
            "status": "PROVISIONAL",
            "committed_pick": None,
        },
    }


def _audit() -> dict:
    return {
        "snapshot_utc": "2026-08-28T19:00:00Z",
        "pick": {
            "team": "LAC",
            "opponent": "ARI",
            "current_spread": 10.5,
            "calibrated_margin": 11.12,
            "p_loss": 0.179,
            "p_win20": 0.264,
        },
    }


def test_margin_missing_field_inputs_are_explicit() -> None:
    state = _margin_state(complete_field=False)

    assert today._margin_missing_field_inputs(state) == (
        "pool size",
        "pick deadline",
        "pick visibility",
        "tie rule",
        "opponent field",
    )


def test_margin_complete_field_has_no_missing_inputs() -> None:
    assert today._margin_missing_field_inputs(
        _margin_state(complete_field=True)
    ) == ()


def test_today_margin_is_medium_until_pool_field_is_loaded(monkeypatch) -> None:
    monkeypatch.setattr(today, "_mapping", lambda value: {})
    monkeypatch.setattr(
        today.state_store,
        "config_from_secrets",
        lambda secrets: {"repo": "private"},
    )
    monkeypatch.setattr(
        today.state_store,
        "owner_write_authorized",
        lambda config: True,
    )
    monkeypatch.setattr(
        today,
        "_today_margin_state",
        lambda config: _margin_state(complete_field=False),
    )
    monkeypatch.setattr(
        today,
        "_today_margin_audit",
        lambda state_text: _audit(),
    )

    action = today._margin_action()

    assert action is not None
    assert action.priority == today.MEDIUM
    assert action.confidence == "PARTIAL FIELD"
    assert action.action == "PICK LAC"
    assert "Provisional pool context" in action.why
    assert "pool size" in action.why
    assert "opponent field" in action.why


def test_today_margin_can_be_high_when_field_inputs_are_complete(monkeypatch) -> None:
    monkeypatch.setattr(today, "_mapping", lambda value: {})
    monkeypatch.setattr(
        today.state_store,
        "config_from_secrets",
        lambda secrets: {"repo": "private"},
    )
    monkeypatch.setattr(
        today.state_store,
        "owner_write_authorized",
        lambda config: True,
    )
    monkeypatch.setattr(
        today,
        "_today_margin_state",
        lambda config: _margin_state(complete_field=True),
    )
    monkeypatch.setattr(
        today,
        "_today_margin_audit",
        lambda state_text: _audit(),
    )

    action = today._margin_action()

    assert action is not None
    assert action.priority == today.HIGH
    assert action.confidence == "FULL FIELD"
    assert "Provisional pool context" not in action.why
