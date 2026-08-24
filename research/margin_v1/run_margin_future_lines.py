from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import nflreadpy as nfl

import run_margin_research as core
import run_margin_team_style as style

SEASONS = list(range(2006, 2026))
TEST_SEASONS = list(range(2011, 2026))
ROLLING_GAMES = 4
MIN_PRIOR_GAMES = 3
WINDOW_PERIODS = 32
HALF_LIFE = 8.0
RIDGE_POWER = 3.0
RIDGE_CORRECTION = 10.0


def build_weekly_metrics() -> tuple[pd.DataFrame, list[str]]:
    ts = style.to_pandas(nfl.load_team_stats(SEASONS, summary_level='week'))
    ts = ts[ts['season_type'].eq('REG')].copy()
    ts['season'] = pd.to_numeric(ts.season, errors='coerce').astype(int)
    ts['week'] = pd.to_numeric(ts.week, errors='coerce').astype(int)
    ts['team_canon'] = ts.team.astype(str).map(core.canon_team)
    ts['opponent_canon'] = ts.opponent_team.astype(str).map(core.canon_team)

    attempts = style.num(ts, 'attempts')
    carries = style.num(ts, 'carries')
    sacks = style.num(ts, 'sacks_suffered')
    plays = (attempts + carries + sacks).replace(0, np.nan)
    dropbacks = (attempts + sacks).replace(0, np.nan)
    ts['off_epa_pp'] = (style.num(ts, 'passing_epa') + style.num(ts, 'rushing_epa')) / plays
    ts['pass_epa_db'] = style.num(ts, 'passing_epa') / dropbacks
    ts['rush_epa_carry'] = style.num(ts, 'rushing_epa') / carries.replace(0, np.nan)
    ts['yards_pp'] = (style.num(ts, 'passing_yards') + style.num(ts, 'rushing_yards')) / plays

    explosive_cols = [c for c in ['passing_20', 'rushing_20'] if c in ts.columns]
    if explosive_cols:
        explosive = sum((style.num(ts, c) for c in explosive_cols), start=pd.Series(0.0, index=ts.index))
        ts['explosive_rate'] = explosive / plays
    else:
        ts['explosive_rate'] = np.nan

    fumble_lost_cols = [c for c in ['sack_fumbles_lost', 'rushing_fumbles_lost', 'receiving_fumbles_lost'] if c in ts.columns]
    lost = sum((style.num(ts, c) for c in fumble_lost_cols), start=pd.Series(0.0, index=ts.index))
    ts['turnovers_committed'] = style.num(ts, 'passing_interceptions') + lost

    opp_cols = ['game_id', 'team_canon', 'off_epa_pp', 'pass_epa_db', 'rush_epa_carry', 'yards_pp', 'explosive_rate', 'turnovers_committed']
    opp = ts[opp_cols].rename(columns={
        'team_canon': 'opp_team_canon',
        'off_epa_pp': 'def_epa_allowed_pp',
        'pass_epa_db': 'def_pass_epa_allowed_db',
        'rush_epa_carry': 'def_rush_epa_allowed_carry',
        'yards_pp': 'def_yards_pp_allowed',
        'explosive_rate': 'def_explosive_rate_allowed',
        'turnovers_committed': 'takeaways',
    })
    ts = ts.merge(
        opp,
        left_on=['game_id', 'opponent_canon'],
        right_on=['game_id', 'opp_team_canon'],
        how='left',
        validate='one_to_one',
    )
    ts['net_epa'] = ts.off_epa_pp - ts.def_epa_allowed_pp
    ts['net_pass_epa'] = ts.pass_epa_db - ts.def_pass_epa_allowed_db
    ts['net_rush_epa'] = ts.rush_epa_carry - ts.def_rush_epa_allowed_carry
    ts['net_ypp'] = ts.yards_pp - ts.def_yards_pp_allowed
    ts['net_explosive'] = ts.explosive_rate - ts.def_explosive_rate_allowed
    ts['turnover_margin'] = ts.takeaways - ts.turnovers_committed
    metrics = ['net_epa', 'net_pass_epa', 'net_rush_epa', 'net_ypp', 'net_explosive', 'turnover_margin']
    return ts[['season', 'week', 'game_id', 'team_canon'] + metrics].copy(), metrics


def build_origin_snapshots(metrics: pd.DataFrame, metric_cols: list[str], max_week_by_season: dict[int, int]) -> pd.DataFrame:
    rows = []
    metrics = metrics.sort_values(['season', 'team_canon', 'week', 'game_id']).copy()
    teams_by_season = metrics.groupby('season').team_canon.unique().to_dict()
    for season in SEASONS:
        d = metrics[metrics.season.eq(season)]
        for origin in range(1, int(max_week_by_season.get(season, 0))):
            prior = d[d.week < origin]
            for team in teams_by_season.get(season, []):
                hist = prior[prior.team_canon.eq(team)].tail(ROLLING_GAMES)
                if len(hist) < MIN_PRIOR_GAMES:
                    continue
                row = {'season': season, 'origin_week': origin, 'team_canon': team, 'prior_games': len(hist)}
                for c in metric_cols:
                    row[c] = float(hist[c].mean())
                rows.append(row)
    return pd.DataFrame(rows)


def build_future_frame(games: pd.DataFrame, snapshots: pd.DataFrame, metric_cols: list[str]) -> tuple[pd.DataFrame, list[str], list[str]]:
    g = games[games.game_type.eq('REG')].copy()
    g = g[g.season.between(min(SEASONS), max(SEASONS))].copy()
    for c in ['season', 'week', 'spread_line']:
        g[c] = pd.to_numeric(g[c], errors='coerce')
    g = g.dropna(subset=['spread_line']).copy()
    g['season'] = g.season.astype(int)
    g['week'] = g.week.astype(int)
    g['home_canon'] = g.home_team.astype(str).map(core.canon_team)
    g['away_canon'] = g.away_team.astype(str).map(core.canon_team)
    gpi = core.build_period_index(games)

    snap_home = snapshots.rename(columns={'team_canon': 'home_canon', **{c: f'home_{c}' for c in metric_cols}})
    snap_away = snapshots.rename(columns={'team_canon': 'away_canon', **{c: f'away_{c}' for c in metric_cols}})

    rows = []
    for season in SEASONS:
        season_games = g[g.season.eq(season)]
        weeks = sorted(int(w) for w in season_games.week.unique())
        for origin in weeks[:-1]:
            ratings, hfa = core.fit_market_power(
                gpi,
                season,
                origin,
                window_periods=WINDOW_PERIODS,
                half_life=HALF_LIFE,
                ridge=RIDGE_POWER,
            )
            future = season_games[season_games.week > origin].copy()
            for _, r in future.iterrows():
                home = core.canon_team(r.home_canon)
                away = core.canon_team(r.away_canon)
                neutral = str(r.get('location', 'Home')).lower() != 'home'
                baseline = ratings.get(home, 0.0) - ratings.get(away, 0.0) + (0.0 if neutral else hfa)
                rows.append({
                    'season': season,
                    'origin_week': origin,
                    'target_week': int(r.week),
                    'horizon': int(r.week) - origin,
                    'game_id': r.game_id,
                    'home_canon': home,
                    'away_canon': away,
                    'target_spread': float(r.spread_line),
                    'power_forecast': float(baseline),
                    'fitted_hfa': float(hfa),
                })
    d = pd.DataFrame(rows)
    d = d.merge(snap_home, on=['season', 'origin_week', 'home_canon'], how='left', validate='many_to_one')
    d = d.merge(snap_away, on=['season', 'origin_week', 'away_canon'], how='left', validate='many_to_one')

    feature_map = {
        'net_epa': 'epa_strength_diff',
        'net_pass_epa': 'pass_strength_diff',
        'net_rush_epa': 'rush_strength_diff',
        'net_ypp': 'ypp_strength_diff',
        'net_explosive': 'explosive_strength_diff',
        'turnover_margin': 'turnover_strength_diff',
    }
    style_cols = []
    for base, out in feature_map.items():
        a = f'home_{base}'
        b = f'away_{base}'
        if a in d.columns and b in d.columns:
            d[out] = d[a] - d[b]
            style_cols.append(out)
    core_style = [c for c in style_cols if c != 'turnover_strength_diff']
    plus_turn = style_cols.copy()
    d['forecast_error'] = d.target_spread - d.power_forecast
    d = d.dropna(subset=['target_spread', 'power_forecast'] + plus_turn).copy()
    return d, core_style, plus_turn


def correction_X(df: pd.DataFrame, style_cols: list[str]) -> np.ndarray:
    p = df.power_forecast.to_numpy(float)
    h = df.horizon.to_numpy(float)
    pieces = [p, p ** 2, h, h ** 2]
    for c in style_cols:
        pieces.append(df[c].to_numpy(float))
    return np.column_stack(pieces)


def cluster_bootstrap_ci(frame: pd.DataFrame, delta_col: str, n: int = 20000, seed: int = 42) -> tuple[float, float]:
    clusters = frame.groupby(['season', 'game_id'], as_index=False)[delta_col].mean()[delta_col].to_numpy(float)
    rng = np.random.default_rng(seed)
    means = rng.choice(clusters, size=(n, len(clusters)), replace=True).mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def horizon_bucket(h: pd.Series) -> pd.Series:
    return pd.cut(h, bins=[0, 1, 2, 5, 9, 99], labels=['1', '2', '3-5', '6-9', '10+'])


def main() -> None:
    games = core.load_games()
    regular = games[games.game_type.eq('REG')].copy()
    max_week = regular.groupby('season').week.max().astype(int).to_dict()
    weekly, metric_cols = build_weekly_metrics()
    snapshots = build_origin_snapshots(weekly, metric_cols, max_week)
    d, core_style, plus_turn = build_future_frame(games, snapshots, metric_cols)

    print('=== FUTURE-LINE FORECAST DATA ===')
    print(f'rows={len(d)} seasons={d.season.min()}-{d.season.max()} origins={d.origin_week.min()}-{d.origin_week.max()}')
    print(f'window_periods={WINDOW_PERIODS} half_life={HALF_LIFE} ridge_power={RIDGE_POWER}')
    print(f'core_style={core_style}')
    print(f'plus_turnover={plus_turn}')

    pred_rows = []
    for season in TEST_SEASONS:
        train = d[d.season < season].copy()
        test = d[d.season.eq(season)].copy()
        if train.empty or test.empty:
            continue
        predictions = {'power_raw': test.power_forecast.to_numpy(float)}
        for name, cols in [
            ('power_recal', []),
            ('power_plus_style', core_style),
            ('power_plus_style_turnover', plus_turn),
        ]:
            model = make_pipeline(StandardScaler(), Ridge(alpha=RIDGE_CORRECTION))
            model.fit(correction_X(train, cols), train.forecast_error.to_numpy(float))
            predictions[name] = test.power_forecast.to_numpy(float) + model.predict(correction_X(test, cols))
        for name, pred in predictions.items():
            tmp = test[['season', 'origin_week', 'target_week', 'horizon', 'game_id', 'target_spread', 'power_forecast']].copy()
            tmp['model'] = name
            tmp['pred_spread'] = pred
            pred_rows.append(tmp)
    p = pd.concat(pred_rows, ignore_index=True)
    p['abs_error'] = (p.pred_spread - p.target_spread).abs()
    p['sq_error'] = (p.pred_spread - p.target_spread) ** 2
    p['error'] = p.pred_spread - p.target_spread
    p['horizon_bucket'] = horizon_bucket(p.horizon)

    print('=== WALK-FORWARD FUTURE CLOSING-LINE ERROR: 2011-2025 ===')
    rows = []
    for model, g in p.groupby('model'):
        recent = g[g.season >= 2021]
        rows.append({
            'model': model,
            'n': len(g),
            'mae': float(g.abs_error.mean()),
            'rmse': float(np.sqrt(g.sq_error.mean())),
            'bias': float(g.error.mean()),
            'recent_n': len(recent),
            'recent_mae': float(recent.abs_error.mean()),
            'recent_rmse': float(np.sqrt(recent.sq_error.mean())),
            'recent_bias': float(recent.error.mean()),
        })
    print(pd.DataFrame(rows).sort_values('mae').to_csv(index=False))

    print('=== ERROR BY FORECAST HORIZON ===')
    rows = []
    for (bucket, model), g in p.groupby(['horizon_bucket', 'model'], observed=True):
        recent = g[g.season >= 2021]
        rows.append({
            'horizon': str(bucket),
            'model': model,
            'n': len(g),
            'mae': float(g.abs_error.mean()),
            'rmse': float(np.sqrt(g.sq_error.mean())),
            'recent_n': len(recent),
            'recent_mae': float(recent.abs_error.mean()) if len(recent) else np.nan,
        })
    print(pd.DataFrame(rows).sort_values(['horizon', 'mae']).to_csv(index=False))

    print('=== PAIRED ABSOLUTE-ERROR DELTA VS RECALIBRATED POWER ===')
    base = p[p.model.eq('power_recal')][['season', 'origin_week', 'target_week', 'horizon', 'game_id', 'target_spread', 'abs_error']].rename(columns={'abs_error': 'base_abs'})
    for model in ['power_plus_style', 'power_plus_style_turnover']:
        alt = p[p.model.eq(model)][['season', 'origin_week', 'target_week', 'horizon', 'game_id', 'abs_error']].rename(columns={'abs_error': 'alt_abs'})
        m = base.merge(alt, on=['season', 'origin_week', 'target_week', 'horizon', 'game_id'], how='inner', validate='one_to_one')
        m['delta'] = m.alt_abs - m.base_abs
        ci = cluster_bootstrap_ci(m, 'delta')
        recent = m[m.season >= 2021]
        print(f'{model}: mean_delta={m.delta.mean()} ci=[{ci[0]},{ci[1]}] recent_delta={recent.delta.mean()}')
        for bucket, g in m.assign(horizon_bucket=horizon_bucket(m.horizon)).groupby('horizon_bucket', observed=True):
            bci = cluster_bootstrap_ci(g, 'delta', n=10000, seed=43)
            r = g[g.season >= 2021]
            print(f'  horizon={bucket}: n={len(g)} delta={g.delta.mean()} ci=[{bci[0]},{bci[1]}] recent_delta={r.delta.mean() if len(r) else np.nan}')


if __name__ == '__main__':
    main()
