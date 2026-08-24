from __future__ import annotations

import copy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.margin import live_engine


def main() -> None:
    state = live_engine.load_state()
    audit = live_engine.run(state)

    pick = audit["pick"]
    policy = audit["policy"]
    route = audit["route"]
    board = audit["board"]

    assert pick["team"] == policy["expected_points_pick"]
    assert policy["anchor"] == pick["team"], "Weeks 1-3 production policy must retain the current biggest-favorite anchor."
    assert audit["data_quality"]["current_week_games"] == audit["data_quality"]["current_week_posted_spreads"]
    assert len(route) == 18
    assert len({r["team"] for r in route}) == 18
    assert sorted(int(r["week"]) for r in route) == list(range(1, 19))
    assert len(board) == 32
    assert audit["data_quality"]["future_style_status"] == "INACTIVE_WEEKS_1_TO_3"

    # Safety invariant: this package must refuse Week 4+ until the validated style layer is promoted.
    blocked = copy.deepcopy(state)
    blocked["current_week"] = 4
    blocked["completed_week"] = 3
    blocked["used_teams"] = ["LAC", "SEA", "SF"]
    blocked["weekly_results"] = [
        {"week": 1, "team": "LAC", "actual_margin": 0.0},
        {"week": 2, "team": "SEA", "actual_margin": 0.0},
        {"week": 3, "team": "SF", "actual_margin": 0.0},
    ]
    blocked["cumulative_score"] = 0.0
    try:
        live_engine.run(blocked)
        raise AssertionError("Week-4 future-style safety gate did not fire")
    except RuntimeError as exc:
        if "future-style correction" not in str(exc):
            raise

    repo_root = Path(__file__).resolve().parents[1]
    page = repo_root / "dashboard" / "pages" / "07_Margin_War_Room.py"
    app = AppTest.from_file(str(page), default_timeout=45)
    app.run()
    if app.exception:
        raise AssertionError(f"Margin dashboard raised Streamlit exceptions: {[str(x.value) for x in app.exception]}")

    metrics = {str(m.label): str(m.value) for m in app.metric}
    assert metrics.get("PICK") == str(pick["team"])
    assert metrics.get("Opponent") == str(pick["opponent"])
    assert metrics.get("Current spread") == f"{float(pick['current_spread']):+.1f}"

    body = "\n".join(str(x.value) for x in app.markdown)
    for required in ["Margin War Room", "Weekly board", "Provisional remaining route", "My pool state", "Data quality"]:
        assert required in body, f"Missing dashboard section: {required}"

    print("production_margin_engine=PASS")
    print("production_margin_route_invariants=PASS")
    print("production_week4_style_safety_gate=PASS")
    print("production_margin_dashboard_render=PASS")
    print(f"current_pick={pick['team']} opponent={pick['opponent']} spread={pick['current_spread']:+.1f}")


if __name__ == "__main__":
    main()
