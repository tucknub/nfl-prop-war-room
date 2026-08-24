from __future__ import annotations

import hashlib
import math
from typing import Any

import numpy as np
import pandas as pd

from . import live_engine as base


MIN_CHAMPIONSHIP_WEEK = 10
DEFAULT_N_SIMS = 20_000
DEFAULT_SEED = 20260823
CANDIDATE_K = 6
PROFILE_NAMES = ("bf", "anchor", "top2", "top3")
MIXED_PROFILE = np.array([0.35, 0.30, 0.20, 0.15], dtype=float)
VALID_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LA", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}
ALIASES = {"SD": "LAC", "STL": "LA", "OAK": "LV"}
SUPPORTED_TIE_RULES = {"split", "shared"}


def canon_team(team: Any) -> str:
    value = str(team).strip().upper()
    return ALIASES.get(value, value)


def _stable_seed(value: str, base_seed: int = DEFAULT_SEED) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    offset = int.from_bytes(digest[:4], "big")
    return int((base_seed + offset) % (2**32 - 1))


def championship_readiness(state: dict) -> dict:
    """Return a strict, non-throwing readiness report for championship simulation.

    Production is deliberately fail-closed. A partial field never becomes ready.
    The simulator is only research-supported from Week 10 onward.
    """
    issues: list[str] = []
    invalid: list[str] = []
    missing: list[str] = []

    current_week = int(state.get("current_week", 0) or 0)
    completed_week = int(state.get("completed_week", 0) or 0)
    if current_week != completed_week + 1:
        invalid.append("current_week must equal completed_week + 1")

    hero_used = [canon_team(x) for x in state.get("used_teams", [])]
    if len(hero_used) != completed_week:
        invalid.append("hero used_teams count must equal completed_week")
    if len(hero_used) != len(set(hero_used)):
        invalid.append("hero used_teams contains duplicates")
    bad_hero = sorted(set(hero_used) - VALID_TEAMS)
    if bad_hero:
        invalid.append(f"hero used_teams contains invalid teams: {bad_hero}")

    pool = state.get("pool")
    if not isinstance(pool, dict):
        pool = {}
        missing.append("pool")

    raw_size = pool.get("size")
    if raw_size in (None, ""):
        missing.append("pool.size")
        pool_size = None
    else:
        try:
            pool_size = int(raw_size)
        except (TypeError, ValueError):
            pool_size = None
            invalid.append("pool.size must be an integer")
        if pool_size is not None and pool_size < 2:
            invalid.append("pool.size must be at least 2")

    tie_rule = pool.get("first_place_tie_rule")
    if tie_rule in (None, ""):
        missing.append("pool.first_place_tie_rule")
    elif str(tie_rule).strip().lower() not in SUPPORTED_TIE_RULES:
        invalid.append(
            "pool.first_place_tie_rule must be 'split' or 'shared' for V1 simulation"
        )

    opponents = state.get("opponents")
    if not isinstance(opponents, list):
        opponents = []
        missing.append("opponents")

    if pool_size is not None and len(opponents) != pool_size - 1:
        issues.append(
            f"opponent count {len(opponents)} does not match pool.size - 1 ({pool_size - 1})"
        )

    ids: list[str] = []
    for i, opponent in enumerate(opponents):
        prefix = f"opponents[{i}]"
        if not isinstance(opponent, dict):
            invalid.append(f"{prefix} must be an object")
            continue

        opponent_id = str(opponent.get("id", "")).strip()
        if not opponent_id:
            missing.append(f"{prefix}.id")
        else:
            ids.append(opponent_id)

        score = opponent.get("cumulative_score")
        if score in (None, ""):
            missing.append(f"{prefix}.cumulative_score")
        else:
            try:
                numeric_score = float(score)
                if not math.isfinite(numeric_score):
                    raise ValueError
            except (TypeError, ValueError):
                invalid.append(f"{prefix}.cumulative_score must be finite numeric")

        used = opponent.get("used_teams")
        if not isinstance(used, list):
            missing.append(f"{prefix}.used_teams")
            continue
        canon_used = [canon_team(x) for x in used]
        if len(canon_used) != completed_week:
            invalid.append(
                f"{prefix}.used_teams count must equal completed_week; missed-pick modeling is not supported"
            )
        if len(canon_used) != len(set(canon_used)):
            invalid.append(f"{prefix}.used_teams contains duplicates")
        bad = sorted(set(canon_used) - VALID_TEAMS)
        if bad:
            invalid.append(f"{prefix}.used_teams contains invalid teams: {bad}")

    if len(ids) != len(set(ids)):
        invalid.append("opponent ids must be unique")

    if invalid:
        status = "UNAVAILABLE_POOL_STATE_INVALID"
    elif missing:
        status = "UNAVAILABLE_POOL_STATE_MISSING"
    elif issues:
        status = "UNAVAILABLE_POOL_STATE_INCOMPLETE"
    elif current_week < MIN_CHAMPIONSHIP_WEEK:
        status = "UNAVAILABLE_EARLY_SEASON_RESEARCH_GATE"
    else:
        status = "READY_FOR_SIMULATION"

    return {
        "ready": status == "READY_FOR_SIMULATION",
        "status": status,
        "minimum_supported_week": MIN_CHAMPIONSHIP_WEEK,
        "pool_size": pool_size,
        "opponent_count": len(opponents),
        "missing": sorted(set(missing)),
        "invalid": sorted(set(invalid)),
        "issues": issues,
        "override_promoted": False,
    }


def _validate_route(route: pd.DataFrame, weeks: list[int]) -> None:
    if sorted(route.week.astype(int).tolist()) != weeks:
        raise AssertionError("championship route does not cover every remaining week")
    if route.team.astype(str).duplicated().any():
        raise AssertionError("championship route reused a team")


def _greedy_path(
    rows: pd.DataFrame,
    weeks: list[int],
    used: set[str],
    *,
    top_k: int,
    temperature: float,
    seed: int,
) -> pd.DataFrame:
    used_now = set(used)
    picks: list[pd.Series] = []
    rng = np.random.default_rng(seed)
    for week in weeks:
        current = rows[
            rows.week.eq(week) & ~rows.team.astype(str).isin(used_now)
        ].copy()
        current = current.sort_values(
            ["raw_value_spread", "calibrated_ev", "team"],
            ascending=[False, False, True],
            kind="stable",
        ).head(top_k).reset_index(drop=True)
        if current.empty:
            raise RuntimeError(f"No championship path option for Week {week}")
        if top_k == 1 or len(current) == 1:
            idx = 0
        else:
            values = current.raw_value_spread.to_numpy(float)
            z = (values - values.max()) / max(float(temperature), 1e-6)
            p = np.exp(z)
            p /= p.sum()
            idx = int(rng.choice(np.arange(len(current)), p=p))
        pick = current.iloc[idx].copy()
        picks.append(pick)
        used_now.add(str(pick.team))
    route = pd.DataFrame(picks).reset_index(drop=True)
    _validate_route(route, weeks)
    return route


def _profile_paths(
    rows: pd.DataFrame,
    current_week: int,
    used: set[str],
    opponent_id: str,
) -> dict[str, pd.DataFrame]:
    weeks = sorted(int(x) for x in rows.week.unique() if int(x) >= current_week)
    anchor_route, _ = base.exact_assignment(rows, weeks, used)
    _validate_route(anchor_route, weeks)
    seed = _stable_seed(opponent_id)
    return {
        "bf": _greedy_path(rows, weeks, used, top_k=1, temperature=1.0, seed=seed),
        "anchor": anchor_route,
        "top2": _greedy_path(rows, weeks, used, top_k=2, temperature=1.0, seed=seed + 1),
        "top3": _greedy_path(rows, weeks, used, top_k=3, temperature=1.5, seed=seed + 2),
    }


def _sample_home_margins(
    rows: pd.DataFrame,
    game_ids: set[str],
    train_fav: pd.DataFrame,
    n_sims: int,
    seed: int,
) -> dict[str, np.ndarray]:
    home = rows[rows.is_home].drop_duplicates("game_id").copy()
    home = home[home.game_id.astype(str).isin(game_ids)].copy()
    forecast = dict(
        zip(home.game_id.astype(str), home.raw_value_spread.astype(float))
    )
    missing_games = sorted(game_ids - set(forecast))
    if missing_games:
        raise RuntimeError(f"Missing home-side forecast rows for games: {missing_games[:5]}")

    ts = train_fav.favorite_spread.to_numpy(float)
    residual = train_fav.favorite_margin.to_numpy(float) - ts
    rng = np.random.default_rng(seed)
    samples: dict[str, np.ndarray] = {}
    for game_id in sorted(game_ids):
        home_spread = float(forecast[game_id])
        weights = base.kernel_weights(ts, abs(home_spread), base.BANDWIDTH)
        sampled = rng.choice(residual, size=n_sims, replace=True, p=weights)
        if home_spread > 0:
            home_margin = home_spread + sampled
        elif home_spread < 0:
            home_margin = home_spread - sampled
        else:
            home_margin = rng.choice(np.array([-1.0, 1.0]), size=n_sims) * sampled
        samples[game_id] = np.rint(home_margin).astype(np.int16)
    return samples


def _score_route(
    route: pd.DataFrame, samples: dict[str, np.ndarray], n_sims: int
) -> np.ndarray:
    score = np.zeros(n_sims, dtype=np.int32)
    for _, row in route.iterrows():
        margin = samples[str(row.game_id)]
        score += margin if bool(row.is_home) else -margin
    return score


def _first_place_metrics(hero: np.ndarray, opponents: np.ndarray) -> dict[str, float]:
    opponent_max = opponents.max(axis=0)
    tie_or_first = hero >= opponent_max
    outright = hero > opponent_max
    ties = np.where(
        tie_or_first,
        (opponents == hero[None, :]).sum(axis=0),
        0,
    )
    share = np.where(tie_or_first, 1.0 / (ties + 1.0), 0.0)
    return {
        "expected_first_share": float(share.mean()),
        "outright_first_probability": float(outright.mean()),
        "tie_or_first_probability": float(tie_or_first.mean()),
    }


def simulate_championship(
    state: dict,
    all_rows: pd.DataFrame,
    board: pd.DataFrame,
    routes: dict[str, pd.DataFrame],
    train_fav: pd.DataFrame,
    expected_points_pick: str,
    *,
    n_sims: int = DEFAULT_N_SIMS,
    seed: int = DEFAULT_SEED,
) -> dict:
    readiness = championship_readiness(state)
    if not readiness["ready"]:
        return {
            "readiness": readiness,
            "simulation": None,
            "championship_pick": None,
            "authoritative_pick": expected_points_pick,
            "override_status": "NOT_AVAILABLE",
        }

    current_week = int(state["current_week"])
    hero_score = float(state.get("cumulative_score", 0.0))
    candidate_board = board.sort_values(
        ["current_spread", "total_season_ev", "team"],
        ascending=[False, False, True],
        kind="stable",
    ).head(CANDIDATE_K).copy()
    if expected_points_pick not in set(candidate_board.team.astype(str)):
        candidate_board = pd.concat(
            [
                candidate_board,
                board[board.team.astype(str).eq(expected_points_pick)].head(1),
            ],
            ignore_index=True,
        )
    candidate_board = candidate_board.drop_duplicates("team").reset_index(drop=True)

    opponent_paths: list[dict[str, pd.DataFrame]] = []
    opponent_starts: list[float] = []
    for opponent in state["opponents"]:
        opponent_id = str(opponent["id"])
        opponent_used = {canon_team(x) for x in opponent["used_teams"]}
        opponent_paths.append(
            _profile_paths(all_rows, current_week, opponent_used, opponent_id)
        )
        opponent_starts.append(float(opponent["cumulative_score"]))

    game_ids: set[str] = set()
    hero_routes: dict[str, pd.DataFrame] = {}
    for team in candidate_board.team.astype(str):
        route = routes[team].copy()
        hero_routes[team] = route
        game_ids.update(route.game_id.astype(str))
    for path_set in opponent_paths:
        for route in path_set.values():
            game_ids.update(route.game_id.astype(str))

    samples = _sample_home_margins(
        all_rows, game_ids, train_fav, n_sims, seed
    )

    # Each real opponent has known score/inventory but uncertain future behavior.
    # Draw one of the research-supported archetypes per simulation trial.
    behavior_rng = np.random.default_rng(seed + 1)
    opponent_totals = []
    for opponent, path_set, start in zip(
        state["opponents"], opponent_paths, opponent_starts
    ):
        profile_scores = np.vstack(
            [_score_route(path_set[name], samples, n_sims) for name in PROFILE_NAMES]
        )
        profile_idx = behavior_rng.choice(
            np.arange(len(PROFILE_NAMES)),
            size=n_sims,
            replace=True,
            p=MIXED_PROFILE,
        )
        selected = profile_scores[profile_idx, np.arange(n_sims)]
        opponent_totals.append(float(start) + selected)
    opponent_matrix = np.vstack(opponent_totals)

    result_rows = []
    for _, row in candidate_board.iterrows():
        team = str(row.team)
        future_score = _score_route(hero_routes[team], samples, n_sims)
        metrics = _first_place_metrics(hero_score + future_score, opponent_matrix)
        result_rows.append(
            {
                "team": team,
                "current_spread": float(row.current_spread),
                "total_season_ev": float(row.total_season_ev),
                "current_sacrifice_vs_anchor": float(
                    row.current_sacrifice_vs_anchor
                ),
                "sim_future_mean": float(future_score.mean()),
                "sim_future_sd": float(future_score.std(ddof=1)),
                **metrics,
            }
        )

    candidate_results = pd.DataFrame(result_rows).sort_values(
        ["expected_first_share", "total_season_ev", "current_spread", "team"],
        ascending=[False, False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    champ_pick = str(candidate_results.iloc[0].team)
    expected_share = float(
        candidate_results.loc[
            candidate_results.team.eq(expected_points_pick), "expected_first_share"
        ].iloc[0]
    )
    champ_share = float(candidate_results.iloc[0].expected_first_share)

    return {
        "readiness": readiness,
        "simulation": {
            "n_sims": int(n_sims),
            "seed": int(seed),
            "field_profile": dict(zip(PROFILE_NAMES, MIXED_PROFILE.tolist())),
            "candidate_count": int(len(candidate_results)),
            "candidate_results": candidate_results.to_dict(orient="records"),
            "expected_points_first_share": expected_share,
            "championship_first_share": champ_share,
            "first_share_lift": float(champ_share - expected_share),
            "would_switch": champ_pick != expected_points_pick,
        },
        "championship_pick": champ_pick,
        # Deliberately fail-safe: a separate promotion gate is required before
        # championship mode can become authoritative in the live app.
        "authoritative_pick": expected_points_pick,
        "override_status": "RANKING_ONLY_OVERRIDE_NOT_PROMOTED",
    }
