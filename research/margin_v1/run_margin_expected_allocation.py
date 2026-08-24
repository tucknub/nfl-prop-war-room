from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_empirical_sampler as emp
import run_margin_future_lines as future
import run_margin_style_strategy as strat

TEST_SEASONS = list(range(2011, 2026))
BANDWIDTHS = [1.5, 3.0, 4.0]


def expected_team_margin(train_favorites: pd.DataFrame, team_spread: float, bandwidth: float) -> float:
    s = float(team_spread)
    if abs(s) < 1e-12:
        return 0.0
    a = abs(s)
    ts = train_favorites.favorite_spread.to_numpy(float)
    residual = train_favorites.favorite_margin.to_numpy(float) - ts
    w = emp.kernel_weights(ts, a, bandwidth)
    expected_favorite = a + float(np.sum(w * residual))
    return expected_favorite if s > 0 else -expected_favorite


def add_expected_value(picks: pd.DataFrame, train_favorites: pd.DataFrame, bandwidth: float) -> pd.DataFrame:
    out = picks.copy()
    out['calibrated_expected_margin'] = [
        expected_team_margin(train_favorites, x, bandwidth)
        for x in out.market_expected_margin.to_numpy(float)
    ]
    return out


def bootstrap_ci(values, n=100000, seed=20260823):
    a = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(n, len(a)), replace=True).mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def main() -> None:
    games = core.load_games()
    tg = core.canonical_team_games(games)
    fg = dist.favorite_games(games)
    gpi = core.build_period_index(games)

    regular = games[games.game_type.eq('REG')].copy()
    max_week = regular.groupby('season').week.max().astype(int).to_dict()
    weekly, metric_cols = future.build_weekly_metrics()
    snapshots = future.build_origin_snapshots(weekly, metric_cols, max_week)
    ff, core_style, plus_turn = future.build_future_frame(games, snapshots, metric_cols)

    season_rows = []
    for season in TEST_SEASONS:
        train_fav = fg[fg.season < season].copy()
        base = core.greedy_biggest_favorite(tg, season)
        oracle = core.optimize(tg, season, 'market_expected_margin')
        raw_score, raw_market, raw_picks = strat.rolling_with_future_predictions(tg, gpi, season, {})
        style_lookup = strat.train_future_predictions(ff, season, core_style)
        turn_lookup = strat.train_future_predictions(ff, season, plus_turn)
        recal_lookup = strat.train_future_predictions(ff, season, [])
        style_score, style_market, style_picks = strat.rolling_with_future_predictions(tg, gpi, season, style_lookup)
        turn_score, turn_market, turn_picks = strat.rolling_with_future_predictions(tg, gpi, season, turn_lookup)
        recal_score, recal_market, recal_picks = strat.rolling_with_future_predictions(tg, gpi, season, recal_lookup)

        strategies = {
            'biggest_favorite': base.selections,
            'long_slow_raw': raw_picks,
            'long_slow_recal': recal_picks,
            'long_slow_style': style_picks,
            'long_slow_style_turnover': turn_picks,
            'closing_line_oracle': oracle.selections,
        }
        for label, picks in strategies.items():
            row = {
                'season': season,
                'strategy': label,
                'actual_score': float(picks.actual_margin.sum()),
                'selected_market_sum': float(picks.market_expected_margin.sum()),
                'realized_minus_market': float((picks.actual_margin - picks.market_expected_margin).sum()),
            }
            for bw in BANDWIDTHS:
                ev = add_expected_value(picks, train_fav, bw)
                row[f'calibrated_ev_bw{bw}'] = float(ev.calibrated_expected_margin.sum())
            season_rows.append(row)

    d = pd.DataFrame(season_rows)
    print('=== ALLOCATION QUALITY: 2011-2025 ===')
    rows = []
    for strategy, g in d.groupby('strategy'):
        recent = g[g.season >= 2021]
        row = {
            'strategy': strategy,
            'mean_actual_score': float(g.actual_score.mean()),
            'mean_selected_market_sum': float(g.selected_market_sum.mean()),
            'mean_realized_minus_market': float(g.realized_minus_market.mean()),
            'recent_market_sum': float(recent.selected_market_sum.mean()),
            'recent_realized_minus_market': float(recent.realized_minus_market.mean()),
        }
        for bw in BANDWIDTHS:
            c = f'calibrated_ev_bw{bw}'
            row[f'mean_ev_bw{bw}'] = float(g[c].mean())
            row[f'recent_ev_bw{bw}'] = float(recent[c].mean())
        rows.append(row)
    print(pd.DataFrame(rows).sort_values('strategy').to_csv(index=False))

    raw = d[d.strategy.eq('long_slow_raw')].sort_values('season').reset_index(drop=True)
    print('=== PAIRED DELTA VS RAW LONG/SLOW ===')
    for strategy in ['long_slow_recal', 'long_slow_style', 'long_slow_style_turnover']:
        alt = d[d.strategy.eq(strategy)].sort_values('season').reset_index(drop=True)
        assert (raw.season.to_numpy() == alt.season.to_numpy()).all()
        market_delta = alt.selected_market_sum.to_numpy(float) - raw.selected_market_sum.to_numpy(float)
        actual_delta = alt.actual_score.to_numpy(float) - raw.actual_score.to_numpy(float)
        print(f'{strategy}: market_delta_mean={market_delta.mean()} market_ci={bootstrap_ci(market_delta)} actual_delta_mean={actual_delta.mean()} actual_ci={bootstrap_ci(actual_delta)}')
        for bw in BANDWIDTHS:
            c = f'calibrated_ev_bw{bw}'
            ev_delta = alt[c].to_numpy(float) - raw[c].to_numpy(float)
            print(f'  bw={bw}: ev_delta_mean={ev_delta.mean()} ev_ci={bootstrap_ci(ev_delta)} recent_ev_delta={ev_delta[raw.season.to_numpy()>=2021].mean()}')

    print('=== STYLE VS BIGGEST FAVORITE EXPECTED ALLOCATION ===')
    base = d[d.strategy.eq('biggest_favorite')].sort_values('season').reset_index(drop=True)
    style_d = d[d.strategy.eq('long_slow_style')].sort_values('season').reset_index(drop=True)
    market_delta = style_d.selected_market_sum.to_numpy(float) - base.selected_market_sum.to_numpy(float)
    print(f'style_market_minus_biggest_mean={market_delta.mean()} ci={bootstrap_ci(market_delta)} recent={market_delta[base.season.to_numpy()>=2021].mean()}')
    for bw in BANDWIDTHS:
        c = f'calibrated_ev_bw{bw}'
        ev_delta = style_d[c].to_numpy(float) - base[c].to_numpy(float)
        print(f'bw={bw}: style_ev_minus_biggest_mean={ev_delta.mean()} ci={bootstrap_ci(ev_delta)} recent={ev_delta[base.season.to_numpy()>=2021].mean()}')

    print('=== ORACLE MARKET OPPORTUNITY ===')
    oracle = d[d.strategy.eq('closing_line_oracle')].sort_values('season').reset_index(drop=True)
    baseline_gap = oracle.selected_market_sum.to_numpy(float) - base.selected_market_sum.to_numpy(float)
    raw_gain = raw.selected_market_sum.to_numpy(float) - base.selected_market_sum.to_numpy(float)
    style_gain = style_d.selected_market_sum.to_numpy(float) - base.selected_market_sum.to_numpy(float)
    print(f'mean_oracle_market_gap={baseline_gap.mean()}')
    print(f'mean_raw_market_gain={raw_gain.mean()} fraction_of_oracle_gap={raw_gain.sum()/baseline_gap.sum()}')
    print(f'mean_style_market_gain={style_gain.mean()} fraction_of_oracle_gap={style_gain.sum()/baseline_gap.sum()}')

    print('=== PER-SEASON ===')
    print(d.sort_values(['season', 'strategy']).to_csv(index=False))


if __name__ == '__main__':
    main()
