from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_sensitivity as sens
import run_margin_future_lines as future
import run_margin_style_strategy as strat
import run_margin_expected_allocation as evaudit

SEASONS = list(range(2011, 2026))
DEV_SEASONS = list(range(2011, 2021))
LATER_SEASONS = list(range(2021, 2026))
THRESHOLDS = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 999.0]
POLICY_BW = 3.0
EVAL_BWS = [1.5, 3.0, 4.0]
MIN_STYLE_ORIGIN = 4
LONG_SLOW = dict(window_periods=32, half_life=8.0, ridge=3.0, include_current=True)


def team_value(train_fav: pd.DataFrame, spread: float, bw: float = POLICY_BW) -> float:
    return evaudit.expected_team_margin(train_fav, float(spread), bw)


def build_remaining_values(
    tg: pd.DataFrame,
    gpi: pd.DataFrame,
    season: int,
    current: int,
    used: set[str],
    home_spread_lookup: dict[tuple[int, int, str], float],
    train_fav: pd.DataFrame,
) -> tuple[pd.DataFrame, list[int]]:
    d = tg[tg.season.eq(season)].copy()
    weeks = sorted(int(x) for x in d.week.unique())
    remaining = [w for w in weeks if w >= current]
    rem = d[d.week.isin(remaining) & ~d.team.isin(used)].copy()
    ratings, hfa = sens.fit_market_power_cfg(gpi, season, current, **LONG_SLOW)

    def raw_future_spread(r) -> float:
        th = ratings.get(core.canon_team(r.team), 0.0)
        to = ratings.get(core.canon_team(r.opponent), 0.0)
        if str(r.location).lower() != 'home':
            adj = 0.0
        else:
            adj = hfa if bool(r.is_home) else -hfa
        return float(th - to + adj)

    def forecast_spread(r) -> float:
        if int(r.week) == current:
            return float(r.market_expected_margin)
        key = (current, int(r.week), str(r.game_id))
        home_pred = home_spread_lookup.get(key)
        if home_pred is None:
            return raw_future_spread(r)
        return float(home_pred if bool(r.is_home) else -home_pred)

    rem['forecast_spread'] = rem.apply(forecast_spread, axis=1)
    rem['forecast_ev'] = [team_value(train_fav, x) for x in rem.forecast_spread.to_numpy(float)]
    return rem, remaining


def candidate_total_ev(rem: pd.DataFrame, season: int, current: int, candidate: pd.Series, remaining: list[int]) -> float:
    current_value = float(candidate.forecast_ev)
    future_weeks = [w for w in remaining if w > current]
    if not future_weeks:
        return current_value
    future_rows = rem[rem.week.isin(future_weeks) & ~rem.team.eq(candidate.team)].copy()
    assignment = core.optimize(
        future_rows,
        season,
        'forecast_ev',
        weeks=future_weeks,
        eligible_teams=set(future_rows.team.unique()),
    )
    return current_value + float(assignment.objective_value)


def anchored_policy(
    tg: pd.DataFrame,
    gpi: pd.DataFrame,
    fg: pd.DataFrame,
    season: int,
    threshold: float,
    style_lookup: dict[tuple[int, int, str], float],
) -> pd.DataFrame:
    d = tg[tg.season.eq(season)].copy()
    weeks = sorted(int(x) for x in d.week.unique())
    train_fav = fg[fg.season < season].copy()
    used: set[str] = set()
    picks = []

    for current in weeks:
        # Before enough in-season team-style history exists, do not let the unvalidated
        # raw future model override the strongest current market favorite.
        if current < MIN_STYLE_ORIGIN:
            current_rows = d[d.week.eq(current) & ~d.team.isin(used)].copy()
            current_rows = current_rows.sort_values(
                ['market_expected_margin', 'total_line', 'team'],
                ascending=[False, False, True],
                kind='stable',
            )
            pick = current_rows.iloc[0].copy()
            pick['anchor_team'] = str(pick.team)
            pick['best_total_team'] = str(pick.team)
            pick['total_ev_advantage'] = 0.0
            pick['deviated'] = False
            picks.append(pick)
            used.add(str(pick.team))
            continue

        rem, remaining = build_remaining_values(tg, gpi, season, current, used, style_lookup, train_fav)
        current_rows = rem[rem.week.eq(current)].copy()
        current_rows = current_rows.sort_values(
            ['market_expected_margin', 'total_line', 'team'],
            ascending=[False, False, True],
            kind='stable',
        )
        anchor = current_rows.iloc[0]
        anchor_total = candidate_total_ev(rem, season, current, anchor, remaining)

        scored = []
        for _, cand in current_rows.iterrows():
            total = candidate_total_ev(rem, season, current, cand, remaining)
            scored.append((total, float(cand.market_expected_margin), str(cand.team), cand))
        scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
        best_total, _, _, best = scored[0]
        advantage = float(best_total - anchor_total)

        if str(best.team) != str(anchor.team) and advantage >= threshold - 1e-12:
            pick = best.copy()
            deviated = True
        else:
            pick = anchor.copy()
            deviated = False
        pick['anchor_team'] = str(anchor.team)
        pick['best_total_team'] = str(best.team)
        pick['total_ev_advantage'] = advantage
        pick['deviated'] = deviated
        pick['current_sacrifice'] = float(anchor.market_expected_margin - pick.market_expected_margin)
        picks.append(pick)
        used.add(str(pick.team))

    s = pd.DataFrame(picks).reset_index(drop=True)
    core.validate_selections(s, weeks)
    return s


def add_eval_ev(picks: pd.DataFrame, train_fav: pd.DataFrame, bw: float) -> float:
    return float(sum(team_value(train_fav, x, bw) for x in picks.market_expected_margin.to_numpy(float)))


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
    ff, core_style, _ = future.build_future_frame(games, snapshots, metric_cols)

    baselines = {}
    lookups = {}
    for season in SEASONS:
        base = core.greedy_biggest_favorite(tg, season)
        train_fav = fg[fg.season < season].copy()
        baselines[season] = {
            'actual': base.actual_score,
            'market': float(base.selections.market_expected_margin.sum()),
            **{f'ev_{bw}': add_eval_ev(base.selections, train_fav, bw) for bw in EVAL_BWS},
        }
        lookups[season] = strat.train_future_predictions(ff, season, core_style)

    rows = []
    pick_rows = []
    for threshold in THRESHOLDS:
        for season in SEASONS:
            picks = anchored_policy(tg, gpi, fg, season, threshold, lookups[season])
            train_fav = fg[fg.season < season].copy()
            row = {
                'threshold': threshold,
                'season': season,
                'actual_score': float(picks.actual_margin.sum()),
                'market_sum': float(picks.market_expected_margin.sum()),
                'actual_delta_vs_bf': float(picks.actual_margin.sum() - baselines[season]['actual']),
                'market_delta_vs_bf': float(picks.market_expected_margin.sum() - baselines[season]['market']),
                'deviations': int(picks.deviated.fillna(False).sum()),
                'sacrifice_sum': float(picks.get('current_sacrifice', pd.Series(0.0, index=picks.index)).fillna(0).sum()),
                'max_sacrifice': float(picks.get('current_sacrifice', pd.Series(0.0, index=picks.index)).fillna(0).max()),
            }
            for bw in EVAL_BWS:
                ev = add_eval_ev(picks, train_fav, bw)
                row[f'ev_{bw}'] = ev
                row[f'ev_delta_{bw}'] = ev - baselines[season][f'ev_{bw}']
            rows.append(row)
            tmp = picks[['season', 'week', 'team', 'opponent', 'market_expected_margin', 'actual_margin', 'anchor_team', 'best_total_team', 'total_ev_advantage', 'deviated']].copy()
            tmp['threshold'] = threshold
            pick_rows.append(tmp)

    d = pd.DataFrame(rows)
    print('=== BIGGEST-FAVORITE-ANCHORED CALIBRATED-EV POLICY ===')
    summary = []
    for threshold, g in d.groupby('threshold'):
        dev = g[g.season.isin(DEV_SEASONS)]
        later = g[g.season.isin(LATER_SEASONS)]
        summary.append({
            'threshold': threshold,
            'dev_market_delta': float(dev.market_delta_vs_bf.mean()),
            'dev_ev_delta_bw1.5': float(dev['ev_delta_1.5'].mean()),
            'dev_ev_delta_bw3': float(dev['ev_delta_3.0'].mean()),
            'dev_ev_delta_bw4': float(dev['ev_delta_4.0'].mean()),
            'dev_actual_delta': float(dev.actual_delta_vs_bf.mean()),
            'dev_avg_deviations': float(dev.deviations.mean()),
            'later_market_delta': float(later.market_delta_vs_bf.mean()),
            'later_ev_delta_bw1.5': float(later['ev_delta_1.5'].mean()),
            'later_ev_delta_bw3': float(later['ev_delta_3.0'].mean()),
            'later_ev_delta_bw4': float(later['ev_delta_4.0'].mean()),
            'later_actual_delta': float(later.actual_delta_vs_bf.mean()),
            'later_avg_deviations': float(later.deviations.mean()),
            'full_ev_delta_bw3': float(g['ev_delta_3.0'].mean()),
        })
    summary_df = pd.DataFrame(summary).sort_values('threshold')
    print(summary_df.to_csv(index=False))

    # Development selection criterion is fixed before looking at the later-period row below:
    # maximize mean BW=3 calibrated EV delta in 2011-2020; ties prefer the larger threshold.
    dev_rank = summary_df.sort_values(['dev_ev_delta_bw3', 'threshold'], ascending=[False, False])
    chosen = float(dev_rank.iloc[0].threshold)
    print(f'DEV_SELECTED_THRESHOLD={chosen}')

    chosen_rows = d[d.threshold.eq(chosen)].copy()
    dev = chosen_rows[chosen_rows.season.isin(DEV_SEASONS)]
    later = chosen_rows[chosen_rows.season.isin(LATER_SEASONS)]
    print('=== CHOSEN POLICY UNCERTAINTY ===')
    for label, g in [('dev_2011_2020', dev), ('later_2021_2025', later), ('full_2011_2025', chosen_rows)]:
        print(label)
        for c in ['market_delta_vs_bf', 'ev_delta_1.5', 'ev_delta_3.0', 'ev_delta_4.0', 'actual_delta_vs_bf']:
            vals = g[c].to_numpy(float)
            print(f'  {c}: mean={vals.mean()} median={np.median(vals)} ci={bootstrap_ci(vals)} wins={(vals>0).sum()} losses={(vals<0).sum()}')
        print(f'  avg_deviations={g.deviations.mean()} avg_sacrifice={g.sacrifice_sum.mean()} max_week_sacrifice={g.max_sacrifice.max()}')

    print('=== SANITY: THRESHOLD 999 SHOULD EQUAL BIGGEST FAVORITE ===')
    sanity = d[d.threshold.eq(999.0)]
    print(f'max_abs_market_delta={sanity.market_delta_vs_bf.abs().max()} max_abs_ev_delta={sanity["ev_delta_3.0"].abs().max()} max_abs_actual_delta={sanity.actual_delta_vs_bf.abs().max()}')

    print('=== PER-SEASON CHOSEN POLICY ===')
    print(chosen_rows.sort_values('season').to_csv(index=False))

    picks = pd.concat(pick_rows, ignore_index=True)
    chosen_picks = picks[picks.threshold.eq(chosen)].copy()
    print('=== CHOSEN POLICY DEVIATIONS ===')
    print(chosen_picks[chosen_picks.deviated.fillna(False)].to_csv(index=False))


if __name__ == '__main__':
    main()
