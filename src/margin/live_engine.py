from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


DATA_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
DEFAULT_STATE = Path(__file__).with_name("live_state_2026.json")
BANDWIDTH = 3.0
EV_THRESHOLD = 0.5
DEFAULT_CAP = 3.0
SEASON = 2026


def load_games(source: str | None = None) -> pd.DataFrame:
    return pd.read_csv(source or DATA_URL, low_memory=False)


def load_state(path: Path = DEFAULT_STATE) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_state(state: dict) -> None:
    if int(state.get("season", 0)) != SEASON:
        raise AssertionError("Margin V1 production engine is scoped to season 2026.")
    current = int(state["current_week"])
    if current < 1 or current > 18:
        raise AssertionError(f"Invalid current_week={current}")
    used = [str(x) for x in state.get("used_teams", [])]
    if len(used) != len(set(used)):
        raise AssertionError("used_teams contains duplicates")
    if len(used) != int(state.get("completed_week", 0)):
        raise AssertionError("used_teams count must equal completed_week")
    results = state.get("weekly_results", [])
    if len(results) != int(state.get("completed_week", 0)):
        raise AssertionError("weekly_results count must equal completed_week")
    calc_score = float(sum(float(x["actual_margin"]) for x in results)) if results else 0.0
    if abs(calc_score - float(state.get("cumulative_score", 0.0))) > 1e-9:
        raise AssertionError("cumulative_score does not equal weekly_results sum")


def prepare_games(games: pd.DataFrame, season: int) -> pd.DataFrame:
    g = games[(pd.to_numeric(games.season, errors="coerce") == season) & games.game_type.eq("REG")].copy()
    for c in ["season", "week", "spread_line", "total_line", "home_score", "away_score"]:
        if c in g:
            g[c] = pd.to_numeric(g[c], errors="coerce")
    if g.empty:
        raise RuntimeError(f"No season={season} regular-season rows")
    return g


def favorite_games(games: pd.DataFrame) -> pd.DataFrame:
    g = games[(games["game_type"].eq("REG")) & pd.to_numeric(games["season"], errors="coerce").between(2006, 2025)].copy()
    for c in ["season", "week", "home_score", "away_score", "spread_line", "total_line"]:
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g.dropna(subset=["home_score", "away_score", "spread_line", "total_line"]).copy()
    home_fav = g.spread_line >= 0
    g["favorite_spread"] = g.spread_line.abs().astype(float)
    g["favorite_margin"] = np.where(
        home_fav,
        g.home_score - g.away_score,
        g.away_score - g.home_score,
    ).astype(float)
    return g[["season", "week", "game_id", "favorite_spread", "favorite_margin"]].reset_index(drop=True)


def kernel_weights(train_spread: np.ndarray, target_spread: float, bandwidth: float) -> np.ndarray:
    w = np.exp(-0.5 * ((train_spread - target_spread) / bandwidth) ** 2)
    w = np.maximum(w, 1e-12)
    return w / w.sum()


def build_available_market(g: pd.DataFrame, current_week: int, future_posted_mode: str) -> pd.DataFrame:
    d = g.copy()
    d["market_available"] = d.spread_line.notna()
    if future_posted_mode == "current_week_only":
        d["market_available"] = d.market_available & d.week.le(current_week)
    elif future_posted_mode != "live":
        raise ValueError(f"Unknown future_posted_mode={future_posted_mode}")
    return d


def fit_market_ratings(g: pd.DataFrame, ridge: float = 3.0) -> tuple[dict[str, float], float]:
    d = g[g.spread_line.notna()].copy()
    teams = sorted(set(d.home_team.astype(str)) | set(d.away_team.astype(str)))
    idx = {t: i for i, t in enumerate(teams)}
    X = np.zeros((len(d), len(teams) + 1))
    y = d.spread_line.to_numpy(float)
    for i, (_, r) in enumerate(d.iterrows()):
        X[i, idx[str(r.home_team)]] = 1.0
        X[i, idx[str(r.away_team)]] = -1.0
        X[i, -1] = 0.0 if str(r.location).lower() != "home" else 1.0
    penalty = np.eye(X.shape[1]) * ridge
    penalty[-1, -1] = 0.05
    beta = np.linalg.solve(X.T @ X + penalty, X.T @ y)
    return {t: float(beta[idx[t]]) for t in teams}, float(beta[-1])


def fit_snapshot_ratings(g: pd.DataFrame) -> tuple[dict[str, float], float]:
    available = g[g.market_available].copy()
    if len(available) < 16:
        raise RuntimeError("Too few posted market games to build snapshot fallback ratings")
    temp = available.copy()
    temp["spread_line"] = np.where(temp.market_available, temp.spread_line, np.nan)
    return fit_market_ratings(temp)


def build_team_values(g: pd.DataFrame, current_week: int, future_posted_mode: str) -> tuple[pd.DataFrame, dict]:
    d = build_available_market(g, current_week, future_posted_mode)
    ratings, hfa = fit_snapshot_ratings(d)

    def home_inferred(r: pd.Series) -> float:
        adj = 0.0 if str(r.location).lower() != "home" else hfa
        return float(ratings.get(str(r.home_team), 0.0) - ratings.get(str(r.away_team), 0.0) + adj)

    d["inferred_home_spread"] = d.apply(home_inferred, axis=1)
    d["snapshot_home_spread"] = np.where(d.market_available, d.spread_line, d.inferred_home_spread)
    d["home_value_source"] = np.where(
        d.week.eq(current_week) & d.market_available,
        "CURRENT_MARKET",
        np.where(d.market_available, "POSTED_LOOKAHEAD", "MARKET_RATING_INFERRED"),
    )

    common = {
        "season": SEASON,
        "week": d.week.astype(int),
        "game_id": d.game_id.astype(str),
        "location": d.location,
        "value_source": d.home_value_source.astype(str),
        "total_line": d.total_line,
    }
    home = pd.DataFrame({
        **common,
        "team": d.home_team.astype(str),
        "opponent": d.away_team.astype(str),
        "is_home": True,
        "raw_value_spread": d.snapshot_home_spread.astype(float),
        "posted_team_spread": np.where(d.market_available, d.spread_line, np.nan),
    })
    away = pd.DataFrame({
        **common,
        "team": d.away_team.astype(str),
        "opponent": d.home_team.astype(str),
        "is_home": False,
        "raw_value_spread": -d.snapshot_home_spread.astype(float),
        "posted_team_spread": np.where(d.market_available, -d.spread_line, np.nan),
    })
    return pd.concat([home, away], ignore_index=True), {
        "ratings": ratings,
        "hfa": hfa,
        "posted_games_used_for_fallback": int(d.market_available.sum()),
    }


def signed_distribution(train_fav: pd.DataFrame, spread: float, bandwidth: float = BANDWIDTH) -> dict[str, float]:
    s = float(spread)
    ts = train_fav.favorite_spread.to_numpy(float)
    fm = train_fav.favorite_margin.to_numpy(float)
    residual = fm - ts
    if abs(s) < 1e-12:
        w = kernel_weights(ts, 0.0, bandwidth)
        return {
            "calibrated_ev": 0.0,
            "p_loss": 0.5,
            "p_win10": float(np.sum(w * (residual >= 10))),
            "p_win20": float(np.sum(w * (residual >= 20))),
            "p_win30": float(np.sum(w * (residual >= 30))),
        }
    a = abs(s)
    w = kernel_weights(ts, a, bandwidth)
    favorite_margin = a + residual
    team_margin = favorite_margin if s > 0 else -favorite_margin
    return {
        "calibrated_ev": float(np.sum(w * team_margin)),
        "p_loss": float(np.sum(w * (team_margin < 0))),
        "p_win10": float(np.sum(w * (team_margin >= 10))),
        "p_win20": float(np.sum(w * (team_margin >= 20))),
        "p_win30": float(np.sum(w * (team_margin >= 30))),
    }


def add_calibration(rows: pd.DataFrame, train_fav: pd.DataFrame) -> pd.DataFrame:
    out = rows.copy()
    p = pd.DataFrame([signed_distribution(train_fav, x) for x in out.raw_value_spread.to_numpy(float)], index=out.index)
    for c in p.columns:
        out[c] = p[c]
    return out


def exact_assignment(rows: pd.DataFrame, weeks: list[int], used: set[str]) -> tuple[pd.DataFrame, float]:
    d = rows[rows.week.isin(weeks) & ~rows.team.isin(used)].copy()
    teams = sorted(set(d.team.astype(str)))
    wi = {w: i for i, w in enumerate(weeks)}
    ti = {t: j for j, t in enumerate(teams)}
    INF = 1e8
    cost = np.full((len(weeks), len(teams)), INF)
    lookup: dict[tuple[int, str], pd.Series] = {}
    for _, r in d.iterrows():
        w, t = int(r.week), str(r.team)
        if w not in wi:
            continue
        cost[wi[w], ti[t]] = -float(r.calibrated_ev) + ti[t] * 1e-9
        lookup[(w, t)] = r
    rr, cc = linear_sum_assignment(cost)
    if len(rr) != len(weeks) or np.any(cost[rr, cc] >= INF / 2):
        raise RuntimeError("No feasible one-use assignment for remaining weeks")
    s = pd.DataFrame([lookup[(weeks[i], teams[j])] for i, j in sorted(zip(rr, cc))]).reset_index(drop=True)
    if sorted(s.week.astype(int).tolist()) != weeks:
        raise AssertionError("Assignment does not cover every remaining week")
    if s.team.duplicated().any():
        raise AssertionError("Assignment reused a team")
    return s, float(s.calibrated_ev.sum())


def candidate_plan(rows: pd.DataFrame, current_week: int, used: set[str], cand: pd.Series) -> tuple[pd.DataFrame, float]:
    remaining = sorted(int(x) for x in rows.week.unique() if int(x) >= current_week)
    future_weeks = [w for w in remaining if w > current_week]
    if future_weeks:
        future, obj = exact_assignment(rows, future_weeks, used | {str(cand.team)})
        route = pd.concat([pd.DataFrame([cand]), future], ignore_index=True)
        total = float(cand.calibrated_ev + obj)
    else:
        route = pd.DataFrame([cand]).reset_index(drop=True)
        total = float(cand.calibrated_ev)
    if route.team.duplicated().any():
        raise AssertionError("Candidate route reused a team")
    return route, total


def score_current_candidates(rows: pd.DataFrame, current_week: int, used: set[str]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    current = rows[rows.week.eq(current_week) & ~rows.team.isin(used)].copy()
    if current.empty:
        raise RuntimeError("No eligible current-week teams")
    if not current.value_source.eq("CURRENT_MARKET").all():
        raise RuntimeError("Current-week board requires posted current market for every team-game")
    current = current.sort_values(["raw_value_spread", "total_line", "team"], ascending=[False, False, True], kind="stable").reset_index(drop=True)
    anchor = current.iloc[0]
    anchor_line = float(anchor.raw_value_spread)
    future_weeks = sorted(int(x) for x in rows.week.unique() if int(x) > current_week)
    if future_weeks:
        _, future_with_all_obj = exact_assignment(rows, future_weeks, used)
    else:
        future_with_all_obj = 0.0

    scored: list[dict] = []
    routes: dict[str, pd.DataFrame] = {}
    for _, cand in current.iterrows():
        team = str(cand.team)
        route, total = candidate_plan(rows, current_week, used, cand)
        routes[team] = route
        if future_weeks:
            _, future_without_obj = exact_assignment(rows, future_weeks, used | {team})
            future_cost = float(future_with_all_obj - future_without_obj)
        else:
            future_cost = 0.0
        scored.append({
            "team": team,
            "opponent": str(cand.opponent),
            "current_spread": float(cand.raw_value_spread),
            "calibrated_margin": float(cand.calibrated_ev),
            "p_loss": float(cand.p_loss),
            "p_win10": float(cand.p_win10),
            "p_win20": float(cand.p_win20),
            "p_win30": float(cand.p_win30),
            "future_cost": future_cost,
            "total_season_ev": total,
            "current_sacrifice_vs_anchor": float(anchor_line - float(cand.raw_value_spread)),
            "current_value_source": str(cand.value_source),
            "game_id": str(cand.game_id),
        })
    board = pd.DataFrame(scored)
    anchor_total = float(board.loc[board.team.eq(str(anchor.team)), "total_season_ev"].iloc[0])
    board["total_season_ev_delta_vs_anchor"] = board.total_season_ev - anchor_total
    board["anchor_team"] = str(anchor.team)
    return board, routes


def choose_expected_points_pick(board: pd.DataFrame, current_week: int, cap: float, threshold: float) -> tuple[str, str]:
    anchor_team = str(board.anchor_team.iloc[0])
    if current_week <= 3:
        return anchor_team, "WEEKS_1_TO_3_BIGGEST_FAVORITE_DEFAULT"
    eligible = board[board.current_sacrifice_vs_anchor <= cap + 1e-12].copy()
    eligible = eligible.sort_values(["total_season_ev", "current_spread", "team"], ascending=[False, False, True], kind="stable")
    best = eligible.iloc[0]
    if str(best.team) != anchor_team and float(best.total_season_ev_delta_vs_anchor) >= threshold - 1e-12:
        return str(best.team), "CAP3_EV_DEVIATION"
    return anchor_team, "ANCHOR_RETAINED"


def classify_board(board: pd.DataFrame, pick: str, cap: float) -> pd.DataFrame:
    out = board.copy()
    anchor = str(out.anchor_team.iloc[0])
    out["status"] = "WATCH"
    out.loc[out.team.eq(anchor), "status"] = "ANCHOR"
    out.loc[out.current_sacrifice_vs_anchor > cap + 1e-12, "status"] = "AVOID_CAP"
    out.loc[(out.total_season_ev_delta_vs_anchor > 0) & ~out.team.eq(pick), "status"] = "SAVE/PIVOT"
    out.loc[out.team.eq(pick), "status"] = "PICK"
    return out.sort_values(["status", "total_season_ev", "current_spread", "team"], ascending=[True, False, False, True], kind="stable")


def run(state: dict, future_posted_mode: str = "live", *, allow_pre_style_week4_plus: bool = False) -> dict:
    validate_state(state)
    season = int(state["season"])
    current_week = int(state["current_week"])
    if current_week >= 4 and not allow_pre_style_week4_plus:
        raise RuntimeError(
            "Margin V1 production safety gate: the validated in-season future-style correction must be wired in before Week 4."
        )
    used = set(str(x) for x in state.get("used_teams", []))
    snapshot_utc = datetime.now(timezone.utc).isoformat()

    games = load_games()
    g = prepare_games(games, season)
    current_games = g[g.week.eq(current_week)]
    if current_games.spread_line.isna().any():
        raise RuntimeError("Current-week board is blocked because one or more current spreads are missing.")

    rows, fallback = build_team_values(g, current_week, future_posted_mode)
    historical_fav = favorite_games(games)
    rows = add_calibration(rows, historical_fav)
    rows = rows[rows.week.ge(current_week) & ~rows.team.isin(used)].copy()

    board, routes = score_current_candidates(rows, current_week, used)
    cap = float(state.get("model_policy", {}).get("default_current_spread_sacrifice_cap", DEFAULT_CAP))
    threshold = float(state.get("model_policy", {}).get("anchor_ev_threshold", EV_THRESHOLD))
    pick, pick_reason = choose_expected_points_pick(board, current_week, cap, threshold)
    board = classify_board(board, pick, cap)

    anchor = str(board.anchor_team.iloc[0])
    pick_row = board[board.team.eq(pick)].iloc[0]
    anchor_row = board[board.team.eq(anchor)].iloc[0]
    selected_route = routes[pick]

    pool = state.get("pool", {})
    opponents = state.get("opponents", [])
    champ_ready = bool(pool.get("size")) and len(opponents) > 0
    championship_status = "READY_FOR_SIMULATION" if champ_ready else "UNAVAILABLE_POOL_STATE_MISSING"
    style_status = "INACTIVE_WEEKS_1_TO_3" if current_week <= 3 else "REQUIRED_ACTIVE"

    return {
        "schema_version": "margin_live_decision_v1",
        "snapshot_utc": snapshot_utc,
        "season": season,
        "week": current_week,
        "used_teams": sorted(used),
        "cumulative_score": float(state.get("cumulative_score", 0.0)),
        "data_quality": {
            "season_games": int(len(g)),
            "current_week_games": int(current_games.game_id.nunique()),
            "current_week_posted_spreads": int(current_games.spread_line.notna().sum()),
            "snapshot_posted_market_games_used_for_fallback": fallback["posted_games_used_for_fallback"],
            "future_posted_mode": future_posted_mode,
            "remaining_value_source_counts": rows.value_source.value_counts().to_dict(),
            "fallback_hfa": fallback["hfa"],
            "future_style_status": style_status,
        },
        "policy": {
            "expected_points_pick": pick,
            "pick_reason": pick_reason,
            "anchor": anchor,
            "anchor_ev_threshold": threshold,
            "current_spread_sacrifice_cap": cap,
            "championship_status": championship_status,
        },
        "pick": {
            "team": pick,
            "opponent": str(pick_row.opponent),
            "current_spread": float(pick_row.current_spread),
            "calibrated_margin": float(pick_row.calibrated_margin),
            "p_loss": float(pick_row.p_loss),
            "p_win20": float(pick_row.p_win20),
            "total_season_ev": float(pick_row.total_season_ev),
            "total_season_ev_delta_vs_anchor": float(pick_row.total_season_ev_delta_vs_anchor),
            "current_sacrifice_vs_anchor": float(pick_row.current_sacrifice_vs_anchor),
            "future_cost": float(pick_row.future_cost),
        },
        "anchor": {
            "team": anchor,
            "current_spread": float(anchor_row.current_spread),
            "calibrated_margin": float(anchor_row.calibrated_margin),
            "total_season_ev": float(anchor_row.total_season_ev),
        },
        "route": selected_route[["week", "team", "opponent", "raw_value_spread", "calibrated_ev", "value_source", "game_id"]].to_dict(orient="records"),
        "board": board.sort_values(["total_season_ev", "current_spread"], ascending=[False, False]).to_dict(orient="records"),
    }


def main() -> None:
    audit = run(load_state())
    print(json.dumps(audit, sort_keys=True))


if __name__ == "__main__":
    main()
