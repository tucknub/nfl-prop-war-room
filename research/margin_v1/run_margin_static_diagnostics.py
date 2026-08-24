from __future__ import annotations

import numpy as np
import pandas as pd

from run_margin_research import (
    SEASONS,
    build_period_index,
    canonical_team_games,
    canon_team,
    fit_market_power,
    greedy_biggest_favorite,
    load_games,
    optimize,
    rolling_allocator,
    validate_selections,
    Result,
)


def forecast_from_snapshot(row: pd.Series, ratings: dict[str, float], hfa: float, snapshot_week: int) -> float:
    if int(row.week) == snapshot_week:
        return float(row.market_expected_margin)
    th = ratings.get(canon_team(row.team), 0.0)
    to = ratings.get(canon_team(row.opponent), 0.0)
    loc_home = bool(row.is_home) and str(row.location).lower() == 'home'
    loc_away = (not bool(row.is_home)) and str(row.location).lower() == 'home'
    adj = hfa if loc_home else (-hfa if loc_away else 0.0)
    return float(th - to + adj)


def static_week1_allocator(tg: pd.DataFrame, games_pi: pd.DataFrame, season: int) -> Result:
    d = tg[tg.season.eq(season)].copy()
    weeks = sorted(int(x) for x in d.week.unique())
    ratings, hfa = fit_market_power(games_pi, season, 1)
    d['static_value'] = d.apply(lambda r: forecast_from_snapshot(r, ratings, hfa, 1), axis=1)
    res = optimize(d, season, 'static_value', weeks=weeks, eligible_teams=set(d.team.unique()))
    s = res.selections.copy()
    s['decision_value'] = s['static_value'].astype(float)
    s['fitted_hfa'] = hfa
    validate_selections(s, weeks)
    return Result(s, float(s.actual_margin.sum()), float(s.static_value.sum()))


def selected_market_sum(res: Result) -> float:
    return float(pd.to_numeric(res.selections.market_expected_margin, errors='coerce').sum())


def bootstrap_ci(values: np.ndarray, seed: int = 20260823, n: int = 20000) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    values = np.asarray(values, dtype=float)
    means = np.empty(n)
    for i in range(n):
        means[i] = rng.choice(values, size=len(values), replace=True).mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def rolling_inventory_diagnostics(tg: pd.DataFrame, season: int, rolling: Result) -> pd.DataFrame:
    d = tg[tg.season.eq(season)].copy()
    used: set[str] = set()
    rows = []
    for _, pick in rolling.selections.sort_values('week').iterrows():
        w = int(pick.week)
        elig = d[d.week.eq(w) & ~d.team.isin(used) & d.market_expected_margin.notna()].copy()
        elig = elig.sort_values(['market_expected_margin', 'total_line', 'team'], ascending=[False, False, True], kind='stable')
        myopic = elig.iloc[0]
        rows.append({
            'week': w,
            'rolling_team': str(pick.team),
            'rolling_line': float(pick.market_expected_margin),
            'rolling_actual': float(pick.actual_margin),
            'myopic_team_for_same_inventory': str(myopic.team),
            'myopic_line_for_same_inventory': float(myopic.market_expected_margin),
            'current_market_sacrifice': float(myopic.market_expected_margin - pick.market_expected_margin),
            'rolling_residual': float(pick.actual_margin - pick.market_expected_margin),
        })
        used.add(str(pick.team))
    return pd.DataFrame(rows)


def run() -> None:
    games = load_games()
    tg = canonical_team_games(games)
    gpi = build_period_index(games)

    season_rows = []
    results: dict[int, dict[str, Result]] = {}
    for season in SEASONS:
        base = greedy_biggest_favorite(tg, season)
        static = static_week1_allocator(tg, gpi, season)
        rolling = rolling_allocator(tg, gpi, season)
        results[season] = {'baseline': base, 'static': static, 'rolling': rolling}

        bm = selected_market_sum(base)
        sm = selected_market_sum(static)
        rm = selected_market_sum(rolling)
        br = base.actual_score - bm
        sr = static.actual_score - sm
        rr = rolling.actual_score - rm
        season_rows.append({
            'season': season,
            'weeks': len(base.selections),
            'baseline_actual': base.actual_score,
            'static_actual': static.actual_score,
            'rolling_actual': rolling.actual_score,
            'static_minus_baseline': static.actual_score - base.actual_score,
            'rolling_minus_static': rolling.actual_score - static.actual_score,
            'rolling_minus_baseline': rolling.actual_score - base.actual_score,
            'baseline_selected_market_sum': bm,
            'static_selected_market_sum': sm,
            'rolling_selected_market_sum': rm,
            'rolling_minus_baseline_market_sum': rm - bm,
            'baseline_residual': br,
            'static_residual': sr,
            'rolling_residual': rr,
            'rolling_minus_baseline_residual': rr - br,
        })

    summary = pd.DataFrame(season_rows)
    print('=== STATIC VS ROLLING: SEASON RESULTS ===')
    print(summary.to_csv(index=False))

    sb = summary.static_minus_baseline.to_numpy(float)
    rs = summary.rolling_minus_static.to_numpy(float)
    rb = summary.rolling_minus_baseline.to_numpy(float)
    sb_ci = bootstrap_ci(sb, seed=11)
    rs_ci = bootstrap_ci(rs, seed=12)
    rb_ci = bootstrap_ci(rb, seed=13)

    print('=== STATIC VS ROLLING: AGGREGATE ===')
    metrics = {
        'baseline_mean': summary.baseline_actual.mean(),
        'static_mean': summary.static_actual.mean(),
        'rolling_mean': summary.rolling_actual.mean(),
        'static_minus_baseline_mean': sb.mean(),
        'static_minus_baseline_median': np.median(sb),
        'static_beats_baseline_seasons': int((sb > 0).sum()),
        'static_minus_baseline_ci_low': sb_ci[0],
        'static_minus_baseline_ci_high': sb_ci[1],
        'rolling_minus_static_mean': rs.mean(),
        'rolling_minus_static_median': np.median(rs),
        'rolling_beats_static_seasons': int((rs > 0).sum()),
        'rolling_minus_static_ci_low': rs_ci[0],
        'rolling_minus_static_ci_high': rs_ci[1],
        'rolling_minus_baseline_mean': rb.mean(),
        'rolling_minus_baseline_ci_low': rb_ci[0],
        'rolling_minus_baseline_ci_high': rb_ci[1],
    }
    for k, v in metrics.items():
        print(f'{k}={v}')

    modern = summary[summary.season.ge(2021)]
    print('=== 2021-2025 EXACT 18-WEEK FORMAT ===')
    print(f"baseline_mean={modern.baseline_actual.mean()}")
    print(f"static_mean={modern.static_actual.mean()}")
    print(f"rolling_mean={modern.rolling_actual.mean()}")
    print(f"static_minus_baseline_mean={modern.static_minus_baseline.mean()}")
    print(f"rolling_minus_static_mean={modern.rolling_minus_static.mean()}")
    print(f"rolling_minus_baseline_mean={modern.rolling_minus_baseline.mean()}")

    for season in [2010, 2017]:
        base = results[season]['baseline']
        static = results[season]['static']
        rolling = results[season]['rolling']
        print(f'=== FAILURE AUTOPSY {season}: DECOMPOSITION ===')
        bm, sm, rm = map(selected_market_sum, [base, static, rolling])
        rows = [
            ('baseline', base.actual_score, bm, base.actual_score - bm),
            ('static', static.actual_score, sm, static.actual_score - sm),
            ('rolling', rolling.actual_score, rm, rolling.actual_score - rm),
        ]
        print(pd.DataFrame(rows, columns=['strategy','actual_score','selected_market_sum','outcome_residual']).to_csv(index=False))
        print(f"rolling_vs_baseline_actual_delta={rolling.actual_score-base.actual_score}")
        print(f"rolling_vs_baseline_market_delta={rm-bm}")
        print(f"rolling_vs_baseline_residual_delta={(rolling.actual_score-rm)-(base.actual_score-bm)}")

        inv = rolling_inventory_diagnostics(tg, season, rolling)
        print(f'=== FAILURE AUTOPSY {season}: ROLLING INVENTORY SACRIFICES ===')
        print(inv.to_csv(index=False))
        print(f"total_current_market_sacrifice={inv.current_market_sacrifice.sum()}")
        print(f"weeks_with_sacrifice_gt_0={(inv.current_market_sacrifice > 1e-9).sum()}")
        print(f"weeks_with_sacrifice_ge_2={(inv.current_market_sacrifice >= 2.0).sum()}")

        b = base.selections[['week','team','market_expected_margin','actual_margin']].copy()
        b.columns = ['week','baseline_team','baseline_line','baseline_actual']
        s = static.selections[['week','team','market_expected_margin','actual_margin']].copy()
        s.columns = ['week','static_team','static_line','static_actual']
        r = rolling.selections[['week','team','market_expected_margin','actual_margin']].copy()
        r.columns = ['week','rolling_team','rolling_line','rolling_actual']
        comp = b.merge(s, on='week').merge(r, on='week')
        comp['rolling_minus_baseline_week'] = comp.rolling_actual - comp.baseline_actual
        comp['rolling_minus_static_week'] = comp.rolling_actual - comp.static_actual
        comp['rolling_cum_vs_baseline'] = comp.rolling_minus_baseline_week.cumsum()
        comp['rolling_cum_vs_static'] = comp.rolling_minus_static_week.cumsum()
        print(f'=== FAILURE AUTOPSY {season}: WEEKLY PICKS ===')
        print(comp.to_csv(index=False))


if __name__ == '__main__':
    run()
