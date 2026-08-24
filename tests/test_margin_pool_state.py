from __future__ import annotations

import pytest

from src.margin import pool_state


def base_state(*, current_week: int, completed_week: int) -> dict:
    used = ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL"][:completed_week]
    return {
        "season": 2026,
        "current_week": current_week,
        "completed_week": completed_week,
        "cumulative_score": 0.0,
        "used_teams": used,
        "weekly_results": [
            {"week": week, "team": team, "actual_margin": 0.0}
            for week, team in enumerate(used, start=1)
        ],
        "pool": {
            "name": None,
            "size": None,
            "pick_deadline": None,
            "picks_visible_before_deadline": None,
            "first_place_tie_rule": None,
            "payout_structure": "winner_take_all",
        },
        "opponents": [],
    }


def opponent_rows(completed_week: int) -> list[dict]:
    inv_a = ["DEN", "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LA"][:completed_week]
    inv_b = ["LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT"][:completed_week]
    return [
        {"id": "opp-a", "name": "Opponent A", "cumulative_score": 82, "used_teams": inv_a},
        {"id": "opp-b", "name": "Opponent B", "cumulative_score": 71, "used_teams": inv_b},
    ]


def test_parse_used_teams_accepts_delimiters_and_aliases() -> None:
    assert pool_state.parse_used_teams("SD|STL,OAK") == ["LAC", "LA", "LV"]


def test_snapshot_infers_pool_size_and_stays_fail_closed_without_tie_rule() -> None:
    state = base_state(current_week=10, completed_week=9)
    updated, readiness = pool_state.apply_pool_snapshot(state, opponent_rows(9))
    assert updated["pool"]["size"] == 3
    assert updated["pool"]["payout_structure"] == "winner_take_all"
    assert len(updated["opponents"]) == 2
    assert readiness["ready"] is False
    assert readiness["status"] == "UNAVAILABLE_POOL_STATE_MISSING"
    assert "pool.first_place_tie_rule" in readiness["missing"]


def test_complete_week10_snapshot_can_become_ready() -> None:
    state = base_state(current_week=10, completed_week=9)
    updated, readiness = pool_state.apply_pool_snapshot(
        state,
        opponent_rows(9),
        first_place_tie_rule="split",
        explicit_pool_size=3,
        picks_visible_before_deadline=False,
    )
    assert readiness["ready"] is True
    assert readiness["status"] == "READY_FOR_SIMULATION"
    assert updated["pool"]["picks_visible_before_deadline"] is False


def test_wrong_inventory_count_is_rejected() -> None:
    state = base_state(current_week=10, completed_week=9)
    rows = opponent_rows(9)
    rows[0]["used_teams"] = rows[0]["used_teams"][:-1]
    with pytest.raises(ValueError, match="used_teams count"):
        pool_state.apply_pool_snapshot(state, rows)


def test_duplicate_opponent_ids_are_rejected() -> None:
    state = base_state(current_week=10, completed_week=9)
    rows = opponent_rows(9)
    rows[1]["id"] = rows[0]["id"]
    with pytest.raises(ValueError, match="opponent ids must be unique"):
        pool_state.apply_pool_snapshot(state, rows)


def test_explicit_pool_size_mismatch_is_rejected() -> None:
    state = base_state(current_week=10, completed_week=9)
    with pytest.raises(ValueError, match="pool size mismatch"):
        pool_state.apply_pool_snapshot(state, opponent_rows(9), explicit_pool_size=4)
