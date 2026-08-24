from __future__ import annotations

from typing import Any

import pandas as pd

from . import championship


PRIMARY_LIFT_THRESHOLD = 0.02
CONFIRMATION_SEED_OFFSETS = (1_000_003, 2_000_003, 3_000_003)


def _candidate_share(result: dict, team: str) -> float:
    simulation = result.get("simulation") or {}
    rows = simulation.get("candidate_results") or []
    for row in rows:
        if str(row.get("team")) == str(team):
            return float(row["expected_first_share"])
    raise RuntimeError(f"Championship confirmation missing candidate {team}")


def evaluate_override(
    state: dict,
    all_rows: pd.DataFrame,
    board: pd.DataFrame,
    routes: dict[str, pd.DataFrame],
    train_fav: pd.DataFrame,
    expected_points_pick: str,
    *,
    n_sims: int = championship.DEFAULT_N_SIMS,
    seed: int = championship.DEFAULT_SEED,
    primary_lift_threshold: float = PRIMARY_LIFT_THRESHOLD,
) -> dict[str, Any]:
    """Apply the independently validated Week-10+ championship promotion gate.

    Candidate selection occurs only on the primary seed. If that frozen candidate
    differs from the expected-points pick and clears the pre-registered 2-point
    first-share threshold, three independent seeds must each confirm positive lift.
    Any missing/incomplete state or failed confirmation retains expected points.
    """
    primary = championship.simulate_championship(
        state,
        all_rows,
        board,
        routes,
        train_fav,
        expected_points_pick,
        n_sims=n_sims,
        seed=seed,
    )
    readiness = dict(primary.get("readiness") or {})
    readiness["override_promoted"] = True

    base = {
        **primary,
        "readiness": readiness,
        "authoritative_pick": expected_points_pick,
        "override_applied": False,
        "promotion_policy": {
            "enabled": True,
            "minimum_week": championship.MIN_CHAMPIONSHIP_WEEK,
            "primary_lift_threshold": float(primary_lift_threshold),
            "confirmation_seeds": len(CONFIRMATION_SEED_OFFSETS),
            "confirmation_rule": "FROZEN_CANDIDATE_POSITIVE_ON_EVERY_INDEPENDENT_SEED",
        },
        "confirmation": None,
    }

    if primary.get("simulation") is None:
        base["override_status"] = "NOT_AVAILABLE"
        return base

    champ_pick = str(primary.get("championship_pick"))
    if champ_pick == str(expected_points_pick):
        base["override_status"] = "EXPECTED_POINTS_ALREADY_CHAMPIONSHIP_BEST"
        return base

    primary_lift = float(primary["simulation"]["first_share_lift"])
    if primary_lift < float(primary_lift_threshold):
        base["override_status"] = "PRIMARY_LIFT_BELOW_PROMOTION_THRESHOLD"
        return base

    confirmation_lifts: list[float] = []
    confirmation_rows: list[dict[str, float | int]] = []
    for offset in CONFIRMATION_SEED_OFFSETS:
        confirm_seed = int(seed + offset)
        confirmation = championship.simulate_championship(
            state,
            all_rows,
            board,
            routes,
            train_fav,
            expected_points_pick,
            n_sims=n_sims,
            seed=confirm_seed,
        )
        champ_share = _candidate_share(confirmation, champ_pick)
        expected_share = _candidate_share(confirmation, expected_points_pick)
        lift = float(champ_share - expected_share)
        confirmation_lifts.append(lift)
        confirmation_rows.append(
            {
                "seed": confirm_seed,
                "championship_first_share": champ_share,
                "expected_points_first_share": expected_share,
                "first_share_lift": lift,
            }
        )

    confirmation_mean = float(sum(confirmation_lifts) / len(confirmation_lifts))
    confirmation_min = float(min(confirmation_lifts))
    base["confirmation"] = {
        "frozen_championship_pick": champ_pick,
        "rows": confirmation_rows,
        "mean_first_share_lift": confirmation_mean,
        "minimum_first_share_lift": confirmation_min,
        "all_positive": all(x > 0.0 for x in confirmation_lifts),
    }

    if confirmation_min <= 0.0:
        base["override_status"] = "INDEPENDENT_CONFIRMATION_FAILED"
        return base

    base["authoritative_pick"] = champ_pick
    base["override_applied"] = True
    base["override_status"] = "CHAMPIONSHIP_OVERRIDE_PROMOTED_AND_CONFIRMED"
    return base
