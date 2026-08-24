from __future__ import annotations

import copy
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.margin import live_engine as live_engine_v1  # noqa: E402
from src.margin import live_engine_v2 as live_engine  # noqa: E402
from src.margin import state_store  # noqa: E402


def route_checksum(route: list[dict]) -> list[tuple]:
    return [
        (
            int(r["week"]),
            str(r["team"]),
            str(r["opponent"]),
            round(float(r["raw_value_spread"]), 10),
            str(r["value_source"]),
        )
        for r in route
    ]


def main() -> None:
    state = live_engine.base.load_state()
    audit = live_engine.run(state)
    v1_audit = live_engine_v1.run(state)

    pick = audit["pick"]
    policy = audit["policy"]
    route = audit["route"]
    board = audit["board"]

    assert audit["schema_version"] == "margin_live_decision_v2"
    assert pick["team"] == v1_audit["pick"]["team"]
    assert pick["opponent"] == v1_audit["pick"]["opponent"]
    assert abs(float(pick["current_spread"]) - float(v1_audit["pick"]["current_spread"])) < 1e-12
    assert route_checksum(route) == route_checksum(v1_audit["route"])
    assert pick["team"] == policy["expected_points_pick"]
    assert policy["anchor"] == pick["team"]
    assert audit["data_quality"]["current_week_games"] == audit["data_quality"]["current_week_posted_spreads"]
    assert len(route) == 18
    assert len({r["team"] for r in route}) == 18
    assert sorted(int(r["week"]) for r in route) == list(range(1, 19))
    assert len(board) == 32
    assert audit["data_quality"]["future_forecast_status"] == "EARLY_SEASON_FALLBACK_WEEKS_1_TO_3"
    assert audit["data_quality"]["future_forecast_model"] == "EARLY_SEASON_MARKET_RATING_FALLBACK"
    assert policy["style_numeric_override"] is False

    week4 = copy.deepcopy(state)
    week4["current_week"] = 4
    week4["completed_week"] = 3
    week4["used_teams"] = ["LAC", "SF", "DET"]
    week4["weekly_results"] = [
        {"week": 1, "team": "LAC", "actual_margin": 0.0},
        {"week": 2, "team": "SF", "actual_margin": 0.0},
        {"week": 3, "team": "DET", "actual_margin": 0.0},
    ]
    week4["cumulative_score"] = 0.0
    week4_audit = live_engine.run(week4)
    week4_route = week4_audit["route"]
    week4_board = week4_audit["board"]
    week4_sources = week4_audit["data_quality"]["remaining_value_source_counts"]

    assert week4_audit["data_quality"]["future_forecast_status"] == "RAW_LONG_SLOW_ACTIVE"
    assert week4_audit["data_quality"]["future_forecast_model"] == "RAW_LONG_SLOW_MARKET_POWER"
    assert int(week4_audit["data_quality"]["power_window_periods"]) == 32
    assert abs(float(week4_audit["data_quality"]["power_half_life"]) - 8.0) < 1e-12
    assert abs(float(week4_audit["data_quality"]["power_ridge"]) - 3.0) < 1e-12
    assert week4_sources.get("MARKET_POWER_FORECAST", 0) > 0
    assert "STYLE_FORECAST" not in week4_sources
    assert week4_audit["policy"]["style_numeric_override"] is False
    assert len(week4_route) == 15
    assert sorted(int(r["week"]) for r in week4_route) == list(range(4, 19))
    assert len({r["team"] for r in week4_route}) == 15
    assert not ({r["team"] for r in week4_route} & set(week4["used_teams"]))
    assert all(str(row["current_value_source"]) == "CURRENT_MARKET" for row in week4_board)

    week4_pick = week4_audit["pick"]
    assert float(week4_pick["current_sacrifice_vs_anchor"]) <= 3.0 + 1e-12
    if str(week4_pick["team"]) != str(week4_audit["anchor"]["team"]):
        assert float(week4_pick["total_season_ev_delta_vs_anchor"]) >= 0.5 - 1e-12

    page = REPO_ROOT / "dashboard" / "pages" / "07_Margin_War_Room.py"

    # The production page now requires private remote state. Patch only the
    # storage boundary in this test process so dashboard rendering can be
    # validated without putting a real PAT/private repository into Actions.
    private_config = {
        "token": "test-token",
        "repo": "tucknub/ci-private-margin-state",
        "branch": "main",
        "path": "margin/live_state_2026.json",
        "auth_mode": "OIDC_OWNER",
        "owner_email": "owner@example.com",
    }
    original_config_from_secrets = state_store.config_from_secrets
    original_owner_write_authorized = state_store.owner_write_authorized
    original_fetch_remote_state = state_store.fetch_remote_state
    try:
        state_store.config_from_secrets = lambda _secrets: dict(private_config)
        state_store.owner_write_authorized = lambda _config: True
        state_store.fetch_remote_state = lambda _config: (copy.deepcopy(state), "ci-state-sha")

        app = AppTest.from_file(str(page), default_timeout=45)
        app.run()
    finally:
        state_store.config_from_secrets = original_config_from_secrets
        state_store.owner_write_authorized = original_owner_write_authorized
        state_store.fetch_remote_state = original_fetch_remote_state

    if app.exception:
        raise AssertionError(f"Margin dashboard raised Streamlit exceptions: {[str(x.value) for x in app.exception]}")

    metrics = {str(m.label): str(m.value) for m in app.metric}
    assert metrics.get("RECOMMENDED") == str(pick["team"])
    assert metrics.get("Opponent") == str(pick["opponent"])
    assert metrics.get("Current spread") == f"{float(pick['current_spread']):+.1f}"

    body = "\n".join(str(x.value) for x in app.markdown)
    for required in [
        "Margin War Room",
        "Current recommendation",
        "Weekly board",
        "Provisional remaining route",
        "My pool state",
        "Pool field preview",
        "Data quality",
    ]:
        assert required in body, f"Missing dashboard section: {required}"

    text_inputs = {str(x.label): x for x in app.text_input}
    selectboxes = {str(x.label): x for x in app.selectbox}
    buttons = {str(x.label): x for x in app.button}
    assert "War Room admin key" not in text_inputs
    assert "Team to record" in selectboxes
    assert f"Commit {pick['team']} for Week 1" in buttons

    # Owner identity alone must not commit a pick; the explicit acknowledgement
    # remains required even when private storage is available.
    assert buttons[f"Commit {pick['team']} for Week 1"].disabled is True

    # Also prove that an unconfigured runtime does not fall back to the public
    # checked-in JSON. It must stop before rendering a recommendation.
    unconfigured = AppTest.from_file(str(page), default_timeout=45)
    unconfigured.run()
    unconfigured_errors = "\n".join(str(x.value) for x in unconfigured.error)
    unconfigured_metrics = {str(m.label): str(m.value) for m in unconfigured.metric}
    assert "Private Margin state is not configured" in unconfigured_errors
    assert "RECOMMENDED" not in unconfigured_metrics

    print("production_week1_v1_v2_parity=PASS")
    print("production_margin_route_invariants=PASS")
    print("production_week4_raw_long_slow=PASS")
    print("production_week4_cap3_threshold=PASS")
    print("production_no_style_numeric_override=PASS")
    print("production_margin_dashboard_private_state_render=PASS")
    print("production_margin_private_state_fail_closed=PASS")
    print("production_margin_dead_admin_key_removed=PASS")
    print("production_margin_pool_preview_render=PASS")
    print(f"current_pick={pick['team']} opponent={pick['opponent']} spread={pick['current_spread']:+.1f}")


if __name__ == "__main__":
    main()
