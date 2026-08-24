from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import run_margin_research as core
import run_margin_sensitivity as sens
import run_margin_future_lines as future

TEST_SEASONS = list(range(2011, 2026))
LONG_SLOW = dict(window_periods=32, half_life=8.0, ridge=3.0, include_current=True)


def train_future_predictions(frame: pd.DataFrame, season: int, cols: list[str]) -> dict[tuple[int, int, str], float]:
    train = frame[frame.season < season].copy()
    test = frame[frame.season.eq(season)].copy()
    if train.empty or test.empty:
        return {}
    model = make_pipeline(StandardScaler(), Ridge(alpha=future.RIDGE_CORRECTION))
    model.fit(future.correction_X(train, cols), train.forecast_error.to_numpy(float))
    pred = test.power_forecast.to_numpy(float) + model.predict(future.correction_X(test, cols))
    return {
        (int(r.origin_week), int(r.target_week), str(r.game_id)): float(pred_i)
        for pred_i, (_, r) in zip(pred, test.iterrows())
    }


def rolling_with_future_predictions(
    tg: pd.DataFrame,
    gpi: pd.DataFrame,
    season: int,
    home_spread_lookup: dict[tuple[int, int, str], float],
) -> tuple[float, float, pd.DataFrame]:
    d = tg[tg.season.eq(season)].copy()
    weeks = sorted(int(x) for x in d.week.unique())
    used: set[str] = set()
    picked = []
    for current in weeks:
        ratings, hfa = sens.fit_market_power_cfg(gpi, season, current, **LONG_SLOW)
        remaining = [w for w in weeks if w >= current]
        rem = d[d.week.isin(remaining) & ~d.team.isin(used)].copy()

        def raw_forecast(r):
            th = ratings.get(core.canon_team(r.team), 0.0)
            to = ratings.get(core.canon_team(r.opponent), 0.0)
            if str(r.location).lower() != 'home':
                adj = 0.0
            else:
                adj = hfa if bool(r.is_home) else -hfa
            return th - to + adj

        def forecast(r):
            if int(r.week) == current:
                return float(r.market_expected_margin)
            key = (current, int(r.week), str(r.game_id))
            home_pred = home_spread_lookup.get(key)
            if home_pred is None:
                return raw_forecast(r)
            return float(home_pred if bool(r.is_home) else -home_pred)

        rem['rolling_value'] = rem.apply(forecast, axis=1)
        assignment = core.optimize(
            rem,
            season,
            'rolling_value',
            weeks=remaining,
            eligible_teams=set(rem.team.unique()),
        )
        pick = assignment.selections[assignment.selections.week.eq(current)].iloc[0].copy()
        pick['decision_value'] = float(pick.rolling_value)
        picked.append(pick)
        used.add(str(pick.team))

    s = pd.DataFrame(picked).reset_index(drop=True)
    core.validate_selections(s, weeks)
    return float(s.actual_margin.sum()), float(s.market_expected_margin.sum()), s


def bootstrap_ci(values, n=100000, seed=42):
    a = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(n, len(a)), replace=True).mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def main() -> None:
    games = core.load_games()
    tg = core.canonical_team_games(games)
    gpi = core.build_period_index(games)

    regular = games[games.game_type.eq('REG')].copy()
    max_week = regular.groupby('season').week.max().astype(int).to_dict()
    weekly, metric_cols = future.build_weekly_metrics()
    snapshots = future.build_origin_snapshots(weekly, metric_cols, max_week)
    ff, core_style, plus_turn = future.build_future_frame(games, snapshots, metric_cols)

    rows = []
    pick_rows = []
    for season in TEST_SEASONS:
        baseline = core.greedy_biggest_favorite(tg, season)
        raw_score = sens.rolling_cfg(tg, gpi, season, LONG_SLOW)

        lookups = {
            'long_slow_recal': train_future_predictions(ff, season, []),
            'long_slow_style': train_future_predictions(ff, season, core_style),
            'long_slow_style_turnover': train_future_predictions(ff, season, plus_turn),
        }
        result = {
            'season': season,
            'biggest_favorite': baseline.actual_score,
            'long_slow_raw': raw_score,
        }
        for label, lookup in lookups.items():
            score, selected_market, picks = rolling_with_future_predictions(tg, gpi, season, lookup)
            result[label] = score
            result[f'{label}_selected_market'] = selected_market
            tmp = picks[['season', 'week', 'game_id', 'team', 'opponent', 'market_expected_margin', 'actual_margin', 'decision_value']].copy()
            tmp['strategy'] = label
            pick_rows.append(tmp)
        rows.append(result)

    out = pd.DataFrame(rows)
    print('=== END-TO-END STYLE-AWARE MARGIN STRATEGY: 2011-2025 ===')
    summary = []
    for model in ['long_slow_raw', 'long_slow_recal', 'long_slow_style', 'long_slow_style_turnover']:
        imp = out[model] - out.biggest_favorite
        vs_raw = out[model] - out.long_slow_raw
        recent = out[out.season >= 2021]
        recent_imp = recent[model] - recent.biggest_favorite
        recent_vs_raw = recent[model] - recent.long_slow_raw
        summary.append({
            'model': model,
            'mean_score': float(out[model].mean()),
            'mean_vs_biggest_favorite': float(imp.mean()),
            'median_vs_biggest_favorite': float(imp.median()),
            'wins_vs_biggest_favorite': int((imp > 0).sum()),
            'losses_vs_biggest_favorite': int((imp < 0).sum()),
            'worst_vs_biggest_favorite': float(imp.min()),
            'best_vs_biggest_favorite': float(imp.max()),
            'mean_vs_raw_long_slow': float(vs_raw.mean()),
            'wins_vs_raw_long_slow': int((vs_raw > 0).sum()),
            'losses_vs_raw_long_slow': int((vs_raw < 0).sum()),
            'recent_mean_vs_biggest_favorite': float(recent_imp.mean()),
            'recent_mean_vs_raw_long_slow': float(recent_vs_raw.mean()),
            'recent_wins_vs_raw': int((recent_vs_raw > 0).sum()),
            'recent_losses_vs_raw': int((recent_vs_raw < 0).sum()),
        })
    print(pd.DataFrame(summary).to_csv(index=False))

    print('=== PAIRED STYLE DELTA VS RAW LONG/SLOW ===')
    for model in ['long_slow_recal', 'long_slow_style', 'long_slow_style_turnover']:
        delta = (out[model] - out.long_slow_raw).to_numpy(float)
        ci = bootstrap_ci(delta)
        recent = out.season >= 2021
        print(f'{model}: mean={delta.mean()} median={np.median(delta)} ci=[{ci[0]},{ci[1]}] recent_mean={delta[recent].mean()}')

    print('=== PER-SEASON ===')
    display = out.copy()
    for model in ['long_slow_raw', 'long_slow_recal', 'long_slow_style', 'long_slow_style_turnover']:
        display[f'{model}_imp'] = display[model] - display.biggest_favorite
    print(display.to_csv(index=False))

    picks = pd.concat(pick_rows, ignore_index=True)
    # Inventory behavior diagnostics: how often style changed the selected team vs the recalibrated strategy.
    pivot = picks.pivot_table(index=['season', 'week'], columns='strategy', values='team', aggfunc='first').reset_index()
    if {'long_slow_recal', 'long_slow_style'}.issubset(pivot.columns):
        changed = pivot.long_slow_recal != pivot.long_slow_style
        print('=== PICK CHANGE RATE: STYLE VS RECAL ===')
        print(f'changed_weeks={int(changed.sum())} total_weeks={len(pivot)} rate={float(changed.mean())}')
        recent = pivot.season >= 2021
        print(f'recent_changed_weeks={int(changed[recent].sum())} recent_total_weeks={int(recent.sum())} recent_rate={float(changed[recent].mean())}')


if __name__ == '__main__':
    main()
