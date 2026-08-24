from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
from run_margin_sensitivity import fit_market_power_cfg

DEFAULT_CFG = dict(window_periods=20, half_life=6.0, ridge=3.0, include_current=True)
LONG_SLOW_CFG = dict(window_periods=32, half_life=8.0, ridge=3.0, include_current=True)
WEIGHTS = [0.25, 0.50, 0.75]  # weight on responsive/default forecast; remainder on long/slow


def one_forecast(row, ratings, hfa):
    th = ratings.get(core.canon_team(row.team), 0.0)
    to = ratings.get(core.canon_team(row.opponent), 0.0)
    if str(row.location).lower() != 'home':
        adj = 0.0
    else:
        adj = hfa if bool(row.is_home) else -hfa
    return float(th - to + adj)


def ensemble_scores(tg: pd.DataFrame, gpi: pd.DataFrame, season: int) -> dict[float, float]:
    d = tg[tg.season.eq(season)].copy()
    weeks = sorted(int(x) for x in d.week.unique())
    state = {w: {'used': set(), 'picked': []} for w in WEIGHTS}

    for current in weeks:
        rd, hd = fit_market_power_cfg(gpi, season, current, **DEFAULT_CFG)
        rl, hl = fit_market_power_cfg(gpi, season, current, **LONG_SLOW_CFG)
        remaining_weeks = [x for x in weeks if x >= current]

        for weight in WEIGHTS:
            used = state[weight]['used']
            rem = d[d.week.isin(remaining_weeks) & ~d.team.isin(used)].copy()

            def forecast(row):
                if int(row.week) == current:
                    return float(row.market_expected_margin)
                vd = one_forecast(row, rd, hd)
                vl = one_forecast(row, rl, hl)
                return float(weight * vd + (1.0 - weight) * vl)

            rem['ensemble_value'] = rem.apply(forecast, axis=1)
            assignment = core.optimize(
                rem,
                season,
                'ensemble_value',
                weeks=remaining_weeks,
                eligible_teams=set(rem.team.unique()),
            )
            pick = assignment.selections[assignment.selections.week.eq(current)].iloc[0].copy()
            state[weight]['picked'].append(pick)
            used.add(str(pick.team))

    scores = {}
    for weight in WEIGHTS:
        s = pd.DataFrame(state[weight]['picked']).reset_index(drop=True)
        core.validate_selections(s, weeks)
        scores[weight] = float(s.actual_margin.sum())
    return scores


def summarize(values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    return dict(
        mean=float(values.mean()),
        median=float(np.median(values)),
        wins=int((values > 0).sum()),
        losses=int((values < 0).sum()),
        worst=float(values.min()),
        best=float(values.max()),
    )


def main():
    games = core.load_games()
    tg = core.canonical_team_games(games)
    gpi = core.build_period_index(games)
    baseline = {s: core.greedy_biggest_favorite(tg, s).actual_score for s in core.SEASONS}

    rows = []
    for season in core.SEASONS:
        scores = ensemble_scores(tg, gpi, season)
        for weight, score in scores.items():
            rows.append({
                'season': season,
                'default_weight': weight,
                'ensemble_score': score,
                'baseline_score': baseline[season],
                'improvement': score - baseline[season],
            })
    df = pd.DataFrame(rows)
    print('=== ENSEMBLE PER-SEASON ===')
    print(df.to_csv(index=False))

    periods = {
        'development_2006_2015': list(range(2006, 2016)),
        'validation_2016_2020': list(range(2016, 2021)),
        'recent_18_week_2021_2025': list(range(2021, 2026)),
        'full_2006_2025': list(range(2006, 2026)),
    }
    out = []
    for weight in WEIGHTS:
        wdf = df[df.default_weight.eq(weight)]
        for label, seasons in periods.items():
            vals = wdf[wdf.season.isin(seasons)].improvement.to_numpy(float)
            out.append({'default_weight': weight, 'period': label, **summarize(vals)})
    summary = pd.DataFrame(out)
    print('=== ENSEMBLE SUMMARY ===')
    print(summary.to_csv(index=False))


if __name__ == '__main__':
    main()
