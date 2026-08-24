from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.margin import championship  # noqa: E402
from src.margin import championship_override  # noqa: E402
from src.margin import live_engine as base  # noqa: E402


HISTORICAL_USED = ["ARI", "ATL", "CAR", "CHI", "CIN", "DAL", "DET", "GB", "HOU"]


def complete_state() -> dict:
    return {
        "season": 2026,
        "current_week": 10,
        "completed_week": 9,
        "cumulative_score": 118.0,
        "used_teams": list(HISTORICAL_USED),
        "weekly_results": [
            {"week": w, "team": team, "actual_margin": 0.0}
            for w, team in enumerate(HISTORICAL_USED, start=1)
        ],
        "pool": {
            "name": "Synthetic validation pool",
            "size": 3,
            "pick_deadline": "synthetic",
            "picks_visible_before_deadline": False,
            "first_place_tie_rule": "split",
        },
        "opponents": [
            {
                "id": "opp-a",
                "name": "Opponent A",
                "cumulative_score": 126.0,
                "used_teams": list(HISTORICAL_USED),
            },
            {
                "id": "opp-b",
                "name": "Opponent B",
                "cumulative_score": 109.0,
                "used_teams": list(HISTORICAL_USED),
            },
        ],
    }


def team_rows() -> pd.DataFrame:
    rows = []

    def add_game(week: int, game_id: str, home: str, away: str, home_spread: float) -> None:
        source = "CURRENT_MARKET" if week == 10 else "MARKET_POWER_FORECAST"
        rows.append({
            "season": 2026,
            "week": week,
            "game_id": game_id,
            "team": home,
            "opponent": away,
            "is_home": True,
            "raw_value_spread": home_spread,
            "posted_team_spread": home_spread if week == 10 else np.nan,
            "value_source": source,
            "total_line": 45.0,
        })
        rows.append({
            "season": 2026,
            "week": week,
            "game_id": game_id,
            "team": away,
            "opponent": home,
            "is_home": False,
            "raw_value_spread": -home_spread,
            "posted_team_spread": -home_spread if week == 10 else np.nan,
            "value_source": source,
            "total_line": 45.0,
        })

    add_game(10, "w10-bal-cle", "BAL", "CLE", 7.0)
    add_game(10, "w10-buf-nyj", "BUF", "NYJ", 6.0)
    add_game(10, "w10-kc-lv", "KC", "LV", 5.0)
    add_game(10, "w10-sf-sea", "SF", "SEA", 4.0)
    add_game(11, "w11-bal-pit", "BAL", "PIT", 3.0)
    add_game(11, "w11-buf-mia", "BUF", "MIA", 2.0)
    add_game(11, "w11-kc-den", "KC", "DEN", 6.0)
    add_game(11, "w11-sf-la", "SF", "LA", 5.0)
    return pd.DataFrame(rows)


def training_favorites() -> pd.DataFrame:
    spreads = np.tile(np.arange(1.0, 11.0), 30)
    residual_pattern = np.array([-10, -6, -3, 0, 2, 4, 7, 10, 14, 18], dtype=float)
    residuals = np.resize(residual_pattern, spreads.shape)
    return pd.DataFrame({
        "favorite_spread": spreads,
        "favorite_margin": spreads + residuals,
    })


def assert_readiness_guards() -> None:
    default = base.load_state()
    r = championship.championship_readiness(default)
    assert r["ready"] is False
    assert r["status"] == "UNAVAILABLE_POOL_STATE_MISSING"

    state = complete_state()
    missing_tie = copy.deepcopy(state)
    missing_tie["pool"]["first_place_tie_rule"] = None
    r = championship.championship_readiness(missing_tie)
    assert r["status"] == "UNAVAILABLE_POOL_STATE_MISSING"

    mismatch = copy.deepcopy(state)
    mismatch["pool"]["size"] = 4
    r = championship.championship_readiness(mismatch)
    assert r["status"] == "UNAVAILABLE_POOL_STATE_INCOMPLETE"

    duplicate_id = copy.deepcopy(state)
    duplicate_id["opponents"][1]["id"] = "opp-a"
    r = championship.championship_readiness(duplicate_id)
    assert r["status"] == "UNAVAILABLE_POOL_STATE_INVALID"

    duplicate_team = copy.deepcopy(state)
    duplicate_team["opponents"][0]["used_teams"][1] = duplicate_team["opponents"][0]["used_teams"][0]
    r = championship.championship_readiness(duplicate_team)
    assert r["status"] == "UNAVAILABLE_POOL_STATE_INVALID"

    invalid_team = copy.deepcopy(state)
    invalid_team["opponents"][0]["used_teams"][0] = "XYZ"
    r = championship.championship_readiness(invalid_team)
    assert r["status"] == "UNAVAILABLE_POOL_STATE_INVALID"

    wrong_used_count = copy.deepcopy(state)
    wrong_used_count["opponents"][0]["used_teams"] = wrong_used_count["opponents"][0]["used_teams"][:-1]
    r = championship.championship_readiness(wrong_used_count)
    assert r["status"] == "UNAVAILABLE_POOL_STATE_INVALID"

    early = complete_state()
    early["current_week"] = 9
    early["completed_week"] = 8
    early["used_teams"] = early["used_teams"][:8]
    early["weekly_results"] = early["weekly_results"][:8]
    for opp in early["opponents"]:
        opp["used_teams"] = opp["used_teams"][:8]
    r = championship.championship_readiness(early)
    assert r["status"] == "UNAVAILABLE_EARLY_SEASON_RESEARCH_GATE"

    ready = championship.championship_readiness(state)
    assert ready["ready"] is True
    assert ready["status"] == "READY_FOR_SIMULATION"
    assert ready["override_promoted"] is False


def assert_tie_splitting() -> None:
    hero = np.array([10, 10, 11, 9], dtype=int)
    opponents = np.array([
        [10, 8, 11, 10],
        [7, 10, 9, 8],
    ], dtype=int)
    metrics = championship._first_place_metrics(hero, opponents)
    assert abs(metrics["expected_first_share"] - 0.375) < 1e-12
    assert abs(metrics["outright_first_probability"] - 0.0) < 1e-12
    assert abs(metrics["tie_or_first_probability"] - 0.75) < 1e-12


def assert_deterministic_simulation() -> None:
    state = complete_state()
    train_fav = training_favorites()
    rows = base.add_calibration(team_rows(), train_fav)
    used = set(state["used_teams"])
    hero_rows = rows[~rows.team.isin(used)].copy()
    board, routes = base.score_current_candidates(hero_rows, 10, used)
    expected_pick, _ = base.choose_expected_points_pick(board, 10, 3.0, 0.5)

    first = championship.simulate_championship(
        state, rows, board, routes, train_fav, expected_pick,
        n_sims=3000, seed=20260823,
    )
    second = championship.simulate_championship(
        state, rows, board, routes, train_fav, expected_pick,
        n_sims=3000, seed=20260823,
    )

    assert first == second, "fixed-seed championship simulation must be deterministic"
    assert first["readiness"]["ready"] is True
    assert first["simulation"]["candidate_count"] >= 1
    assert first["championship_pick"] is not None
    assert first["authoritative_pick"] == expected_pick
    assert first["override_status"] == "RANKING_ONLY_OVERRIDE_NOT_PROMOTED"
    assert 0.0 <= first["simulation"]["expected_points_first_share"] <= 1.0
    assert 0.0 <= first["simulation"]["championship_first_share"] <= 1.0
    assert first["simulation"]["championship_first_share"] + 1e-12 >= first["simulation"]["expected_points_first_share"]


def _fake_result(seed: int, *, primary_lift: float = 0.03, fail_seed: int | None = None) -> dict:
    expected_share = 0.30
    if seed == championship.DEFAULT_SEED:
        lift = primary_lift
    elif fail_seed is not None and seed == fail_seed:
        lift = -0.005
    else:
        lift = 0.025
    champ_share = expected_share + lift
    return {
        "readiness": {"ready": True, "status": "READY_FOR_SIMULATION", "override_promoted": False},
        "simulation": {
            "first_share_lift": lift,
            "candidate_results": [
                {"team": "BAL", "expected_first_share": expected_share},
                {"team": "BUF", "expected_first_share": champ_share},
            ],
        },
        "championship_pick": "BUF",
        "authoritative_pick": "BAL",
        "override_status": "RANKING_ONLY_OVERRIDE_NOT_PROMOTED",
    }


def assert_override_promotion_policy() -> None:
    original = championship.simulate_championship
    dummy = pd.DataFrame()
    try:
        championship.simulate_championship = lambda *args, **kwargs: _fake_result(
            int(kwargs["seed"]), primary_lift=0.019
        )
        below = championship_override.evaluate_override(
            complete_state(), dummy, dummy, {}, dummy, "BAL"
        )
        assert below["authoritative_pick"] == "BAL"
        assert below["override_applied"] is False
        assert below["override_status"] == "PRIMARY_LIFT_BELOW_PROMOTION_THRESHOLD"

        fail_seed = championship.DEFAULT_SEED + championship_override.CONFIRMATION_SEED_OFFSETS[1]
        championship.simulate_championship = lambda *args, **kwargs: _fake_result(
            int(kwargs["seed"]), primary_lift=0.03, fail_seed=fail_seed
        )
        failed = championship_override.evaluate_override(
            complete_state(), dummy, dummy, {}, dummy, "BAL"
        )
        assert failed["authoritative_pick"] == "BAL"
        assert failed["override_applied"] is False
        assert failed["override_status"] == "INDEPENDENT_CONFIRMATION_FAILED"
        assert failed["confirmation"]["all_positive"] is False

        championship.simulate_championship = lambda *args, **kwargs: _fake_result(
            int(kwargs["seed"]), primary_lift=0.03
        )
        passed = championship_override.evaluate_override(
            complete_state(), dummy, dummy, {}, dummy, "BAL"
        )
        assert passed["authoritative_pick"] == "BUF"
        assert passed["override_applied"] is True
        assert passed["override_status"] == "CHAMPIONSHIP_OVERRIDE_PROMOTED_AND_CONFIRMED"
        assert passed["confirmation"]["all_positive"] is True
        assert len(passed["confirmation"]["rows"]) == 3
        assert passed["readiness"]["override_promoted"] is True
    finally:
        championship.simulate_championship = original


def main() -> None:
    assert_readiness_guards()
    assert_tie_splitting()
    assert_deterministic_simulation()
    assert_override_promotion_policy()
    print("championship_readiness_fail_closed=PASS")
    print("championship_complete_field_required=PASS")
    print("championship_week10_research_gate=PASS")
    print("championship_tie_split=PASS")
    print("championship_fixed_seed_determinism=PASS")
    print("championship_base_simulator_ranking_only=PASS")
    print("championship_primary_2pp_threshold=PASS")
    print("championship_independent_confirmation_fail_closed=PASS")
    print("championship_confirmed_override_promotion=PASS")


if __name__ == "__main__":
    main()
