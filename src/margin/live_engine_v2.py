from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import live_engine as base


LONG_SLOW_WINDOW_PERIODS = 32
LONG_SLOW_HALF_LIFE = 8.0
LONG_SLOW_RIDGE = 3.0
ALIASES = {"SD": "LAC", "STL": "LA", "OAK": "LV"}


def canon_team(team: str) -> str:
    value = str(team)
    return ALIASES.get(value, value)


def build_period_index(games: pd.DataFrame) -> pd.DataFrame:
    g = games.copy()
    g["season"] = pd.to_numeric(g.season, errors="coerce").astype("Int64")
    g["week"] = pd.to_numeric(g.week, errors="coerce").astype("Int64")
    periods = (
        g[["season", "week"]]
        .dropna()
        .drop_duplicates()
        .sort_values(["season", "week"])
        .reset_index(drop=True)
    )
    periods["period_index"] = np.arange(len(periods))
    return g.merge(periods, on=["season", "week"], how="left")


def fit_long_slow_market_power(
    games: pd.DataFrame,
    target_season: int,
    target_week: int,
) -> tuple[dict[str, float], float, dict]:
    gpi = build_period_index(games)
    cutoff = gpi[
        gpi.season.eq(target_season) & gpi.week.eq(target_week)
    ].period_index.max()
    if pd.isna(cutoff):
        raise RuntimeError(f"No market-power cutoff for {target_season} Week {target_week}")

    upper = float(cutoff)
    train = gpi[
        (gpi.period_index <= upper)
        & (gpi.period_index >= upper - LONG_SLOW_WINDOW_PERIODS + 1)
        & gpi.spread_line.notna()
    ].copy()
    if train.empty:
        raise RuntimeError("No historical/current market rows available for long/slow power fit")

    train["home_canon"] = train.home_team.astype(str).map(canon_team)
    train["away_canon"] = train.away_team.astype(str).map(canon_team)
    teams = sorted(set(train.home_canon) | set(train.away_canon))
    idx = {team: i for i, team in enumerate(teams)}

    X = np.zeros((len(train), len(teams) + 1))
    y = pd.to_numeric(train.spread_line, errors="coerce").to_numpy(float)
    weights = []
    for row_i, (_, row) in enumerate(train.iterrows()):
        X[row_i, idx[row.home_canon]] = 1.0
        X[row_i, idx[row.away_canon]] = -1.0
        X[row_i, -1] = 0.0 if str(row.get("location", "Home")).lower() != "home" else 1.0
        age = float(upper - row.period_index)
        weights.append(0.5 ** (age / LONG_SLOW_HALF_LIFE))

    w = np.asarray(weights)
    xtw = X.T * w
    penalty = np.eye(X.shape[1]) * LONG_SLOW_RIDGE
    penalty[-1, -1] = 0.05
    beta = np.linalg.solve(xtw @ X + penalty, xtw @ y)
    ratings = {team: float(beta[i]) for team, i in idx.items()}
    hfa = float(beta[-1])
    return ratings, hfa, {
        "window_periods": LONG_SLOW_WINDOW_PERIODS,
        "half_life": LONG_SLOW_HALF_LIFE,
        "ridge": LONG_SLOW_RIDGE,
        "training_market_rows": int(len(train)),
        "training_period_min": int(train.period_index.min()),
        "training_period_max": int(train.period_index.max()),
    }


def build_team_values(
    all_games: pd.DataFrame,
    season_games: pd.DataFrame,
    current_week: int,
    future_posted_mode: str,
) -> tuple[pd.DataFrame, dict]:
    d = base.build_available_market(season_games, current_week, future_posted_mode)

    if current_week >= 4:
        ratings, hfa, model_meta = fit_long_slow_market_power(
            all_games, base.SEASON, current_week
        )
        inferred_source = "MARKET_POWER_FORECAST"
        forecast_model = "RAW_LONG_SLOW_MARKET_POWER"
    else:
        ratings, hfa = base.fit_snapshot_ratings(d)
        model_meta = {
            "window_periods": None,
            "half_life": None,
            "ridge": 3.0,
            "training_market_rows": int(d.market_available.sum()),
        }
        inferred_source = "MARKET_RATING_INFERRED"
        forecast_model = "EARLY_SEASON_MARKET_RATING_FALLBACK"

    def home_inferred(row: pd.Series) -> float:
        home = ratings.get(canon_team(row.home_team), 0.0)
        away = ratings.get(canon_team(row.away_team), 0.0)
        adj = 0.0 if str(row.location).lower() != "home" else hfa
        return float(home - away + adj)

    d["inferred_home_spread"] = d.apply(home_inferred, axis=1)
    d["snapshot_home_spread"] = np.where(
        d.market_available, d.spread_line, d.inferred_home_spread
    )
    d["home_value_source"] = np.where(
        d.week.eq(current_week) & d.market_available,
        "CURRENT_MARKET",
        np.where(d.market_available, "POSTED_LOOKAHEAD", inferred_source),
    )

    common = {
        "season": base.SEASON,
        "week": d.week.astype(int),
        "game_id": d.game_id.astype(str),
        "location": d.location,
        "value_source": d.home_value_source.astype(str),
        "total_line": d.total_line,
    }
    home = pd.DataFrame(
        {
            **common,
            "team": d.home_team.astype(str),
            "opponent": d.away_team.astype(str),
            "is_home": True,
            "raw_value_spread": d.snapshot_home_spread.astype(float),
            "posted_team_spread": np.where(d.market_available, d.spread_line, np.nan),
        }
    )
    away = pd.DataFrame(
        {
            **common,
            "team": d.away_team.astype(str),
            "opponent": d.home_team.astype(str),
            "is_home": False,
            "raw_value_spread": -d.snapshot_home_spread.astype(float),
            "posted_team_spread": np.where(d.market_available, -d.spread_line, np.nan),
        }
    )
    return pd.concat([home, away], ignore_index=True), {
        "ratings": ratings,
        "hfa": hfa,
        "posted_games_used_for_fallback": int(d.market_available.sum()),
        "forecast_model": forecast_model,
        **model_meta,
    }


def run(state: dict, future_posted_mode: str = "live") -> dict:
    base.validate_state(state)
    season = int(state["season"])
    current_week = int(state["current_week"])
    used = set(str(x) for x in state.get("used_teams", []))
    snapshot_utc = datetime.now(timezone.utc).isoformat()

    games = base.load_games()
    g = base.prepare_games(games, season)
    current_games = g[g.week.eq(current_week)]
    if current_games.spread_line.isna().any():
        raise RuntimeError(
            "Current-week board is blocked because one or more current spreads are missing."
        )

    rows, forecast = build_team_values(games, g, current_week, future_posted_mode)
    historical_fav = base.favorite_games(games)
    rows = base.add_calibration(rows, historical_fav)
    rows = rows[rows.week.ge(current_week) & ~rows.team.isin(used)].copy()

    board, routes = base.score_current_candidates(rows, current_week, used)
    cap = float(
        state.get("model_policy", {}).get(
            "default_current_spread_sacrifice_cap", base.DEFAULT_CAP
        )
    )
    threshold = float(
        state.get("model_policy", {}).get("anchor_ev_threshold", base.EV_THRESHOLD)
    )
    pick, pick_reason = base.choose_expected_points_pick(
        board, current_week, cap, threshold
    )
    board = base.classify_board(board, pick, cap)

    anchor = str(board.anchor_team.iloc[0])
    pick_row = board[board.team.eq(pick)].iloc[0]
    anchor_row = board[board.team.eq(anchor)].iloc[0]
    selected_route = routes[pick]

    pool = state.get("pool", {})
    opponents = state.get("opponents", [])
    champ_ready = bool(pool.get("size")) and len(opponents) > 0
    championship_status = (
        "READY_FOR_SIMULATION" if champ_ready else "UNAVAILABLE_POOL_STATE_MISSING"
    )
    forecast_status = (
        "RAW_LONG_SLOW_ACTIVE"
        if current_week >= 4
        else "EARLY_SEASON_FALLBACK_WEEKS_1_TO_3"
    )

    return {
        "schema_version": "margin_live_decision_v2",
        "snapshot_utc": snapshot_utc,
        "season": season,
        "week": current_week,
        "used_teams": sorted(used),
        "cumulative_score": float(state.get("cumulative_score", 0.0)),
        "data_quality": {
            "season_games": int(len(g)),
            "current_week_games": int(current_games.game_id.nunique()),
            "current_week_posted_spreads": int(
                current_games.spread_line.notna().sum()
            ),
            "snapshot_posted_market_games_used_for_fallback": forecast[
                "posted_games_used_for_fallback"
            ],
            "future_posted_mode": future_posted_mode,
            "remaining_value_source_counts": rows.value_source.value_counts().to_dict(),
            "fallback_hfa": forecast["hfa"],
            "future_forecast_status": forecast_status,
            "future_forecast_model": forecast["forecast_model"],
            "power_window_periods": forecast.get("window_periods"),
            "power_half_life": forecast.get("half_life"),
            "power_ridge": forecast.get("ridge"),
            "power_training_market_rows": forecast.get("training_market_rows"),
        },
        "policy": {
            "expected_points_pick": pick,
            "pick_reason": pick_reason,
            "anchor": anchor,
            "anchor_ev_threshold": threshold,
            "current_spread_sacrifice_cap": cap,
            "championship_status": championship_status,
            "future_forecast_model": forecast["forecast_model"],
            "style_numeric_override": False,
        },
        "pick": {
            "team": pick,
            "opponent": str(pick_row.opponent),
            "current_spread": float(pick_row.current_spread),
            "calibrated_margin": float(pick_row.calibrated_margin),
            "p_loss": float(pick_row.p_loss),
            "p_win20": float(pick_row.p_win20),
            "total_season_ev": float(pick_row.total_season_ev),
            "total_season_ev_delta_vs_anchor": float(
                pick_row.total_season_ev_delta_vs_anchor
            ),
            "current_sacrifice_vs_anchor": float(
                pick_row.current_sacrifice_vs_anchor
            ),
            "future_cost": float(pick_row.future_cost),
        },
        "anchor": {
            "team": anchor,
            "current_spread": float(anchor_row.current_spread),
            "calibrated_margin": float(anchor_row.calibrated_margin),
            "total_season_ev": float(anchor_row.total_season_ev),
        },
        "route": selected_route[
            [
                "week",
                "team",
                "opponent",
                "raw_value_spread",
                "calibrated_ev",
                "value_source",
                "game_id",
            ]
        ].to_dict(orient="records"),
        "board": board.sort_values(
            ["total_season_ev", "current_spread"], ascending=[False, False]
        ).to_dict(orient="records"),
    }


def main() -> None:
    import json

    print(json.dumps(run(base.load_state()), sort_keys=True))


if __name__ == "__main__":
    main()
