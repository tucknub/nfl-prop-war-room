from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_future_lines as future
import run_margin_style_strategy as strat
import run_margin_anchor_policy as anchor

SEASONS = list(range(2011, 2026))
DEV_SEASONS = list(range(2011, 2021))
LATER_SEASONS = list(range(2021, 2026))
FIXED_THRESHOLD = 0.5
CAPS = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 999.0]
EVAL_BWS = [1.5, 3.0, 4.0]


def capped_anchored_policy(
    tg: pd.DataFrame,
    gpi: pd.DataFrame,
    fg: pd.DataFrame,
    season: int,
    max_current_sacrifice: float,
    style_lookup: dict[tuple[int, int, str], float],
) -> pd.DataFrame:
    d = tg[tg.season.eq(season)].copy()
    weeks = sorted(int(x) for x in d.week.unique())
    train_fav = fg[fg.season < season].copy()
    used: set[str] = set()
    picks = []

    for current in weeks:
        if current < anchor.MIN_STYLE_ORIGIN:
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
            pick['current_sacrifice'] = 0.0
            pick['max_current_sacrifice'] = max_current_sacrifice
            picks.append(pick)
            used.add(str(pick.team))
            continue

        rem, remaining = anchor.build_remaining_values(
            tg, gpi, season, current, used, style_lookup, train_fav
        )
        current_rows = rem[rem.week.eq(current)].copy()
        current_rows = current_rows.sort_values(
            ['market_expected_margin', 'total_line', 'team'],
            ascending=[False, False, True],
            kind='stable',
        )
        anchor_pick = current_rows.iloc[0]
        anchor_total = anchor.candidate_total_ev(rem, season, current, anchor_pick, remaining)
        anchor_line = float(anchor_pick.market_expected_margin)

        eligible = current_rows[
            current_rows.market_expected_margin >= anchor_line - max_current_sacrifice - 1e-12
        ].copy()

        scored = []
        for _, cand in eligible.iterrows():
            total = anchor.candidate_total_ev(rem, season, current, cand, remaining)
            scored.append((total, float(cand.market_expected_margin), str(cand.team), cand))
        scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
        best_total, _, _, best = scored[0]
        advantage = float(best_total - anchor_total)

        if str(best.team) != str(anchor_pick.team) and advantage >= FIXED_THRESHOLD - 1e-12:
            pick = best.copy()
            deviated = True
        else:
            pick = anchor_pick.copy()
            deviated = False

        pick['anchor_team'] = str(anchor_pick.team)
        pick['best_total_team'] = str(best.team)
        pick['total_ev_advantage'] = advantage
        pick['deviated'] = deviated
        pick['current_sacrifice'] = float(anchor_line - float(pick.market_expected_margin))
        pick['max_current_sacrifice'] = max_current_sacrifice
        picks.append(pick)
        used.add(str(pick.team))

    s = pd.DataFrame(picks).reset_index(drop=True)
    core.validate_selections(s, weeks)
    return s


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
            'actual': float(base.actual_score),
            'market': float(base.selections.market_expected_margin.sum()),
            **{
                f'ev_{bw}': anchor.add_eval_ev(base.selections, train_fav, bw)
                for bw in EVAL_BWS
            },
        }
        lookups[season] = strat.train_future_predictions(ff, season, core_style)

    rows = []
    pick_rows = []
    for cap in CAPS:
        for season in SEASONS:
            picks = capped_anchored_policy(tg, gpi, fg, season, cap, lookups[season])
            train_fav = fg[fg.season < season].copy()
            row = {
                'cap': cap,
                'season': season,
                'actual_score': float(picks.actual_margin.sum()),
                'market_sum': float(picks.market_expected_margin.sum()),
                'actual_delta_vs_bf': float(picks.actual_margin.sum() - baselines[season]['actual']),
                'market_delta_vs_bf': float(picks.market_expected_margin.sum() - baselines[season]['market']),
                'deviations': int(picks.deviated.fillna(False).sum()),
                'sacrifice_sum': float(picks.current_sacrifice.fillna(0).sum()),
                'max_sacrifice': float(picks.current_sacrifice.fillna(0).max()),
            }
            for bw in EVAL_BWS:
                ev = anchor.add_eval_ev(picks, train_fav, bw)
                row[f'ev_{bw}'] = ev
                row[f'ev_delta_{bw}'] = ev - baselines[season][f'ev_{bw}']
            rows.append(row)

            tmp = picks[
                [
                    'season', 'week', 'team', 'opponent', 'market_expected_margin',
                    'actual_margin', 'anchor_team', 'best_total_team',
                    'total_ev_advantage', 'deviated', 'current_sacrifice'
                ]
            ].copy()
            tmp['cap'] = cap
            pick_rows.append(tmp)

    d = pd.DataFrame(rows)
    summary = []
    for cap, g in d.groupby('cap'):
        dev = g[g.season.isin(DEV_SEASONS)]
        later = g[g.season.isin(LATER_SEASONS)]
        summary.append({
            'cap': cap,
            'dev_market_delta': float(dev.market_delta_vs_bf.mean()),
            'dev_ev_delta_bw1.5': float(dev['ev_delta_1.5'].mean()),
            'dev_ev_delta_bw3': float(dev['ev_delta_3.0'].mean()),
            'dev_ev_delta_bw4': float(dev['ev_delta_4.0'].mean()),
            'dev_actual_delta': float(dev.actual_delta_vs_bf.mean()),
            'dev_avg_deviations': float(dev.deviations.mean()),
            'dev_avg_sacrifice': float(dev.sacrifice_sum.mean()),
            'dev_max_week_sacrifice': float(dev.max_sacrifice.max()),
            'later_market_delta': float(later.market_delta_vs_bf.mean()),
            'later_ev_delta_bw1.5': float(later['ev_delta_1.5'].mean()),
            'later_ev_delta_bw3': float(later['ev_delta_3.0'].mean()),
            'later_ev_delta_bw4': float(later['ev_delta_4.0'].mean()),
            'later_actual_delta': float(later.actual_delta_vs_bf.mean()),
            'later_avg_deviations': float(later.deviations.mean()),
            'later_avg_sacrifice': float(later.sacrifice_sum.mean()),
            'later_max_week_sacrifice': float(later.max_sacrifice.max()),
            'full_ev_delta_bw3': float(g['ev_delta_3.0'].mean()),
        })
    summary_df = pd.DataFrame(summary).sort_values('cap')

    print('=== FIXED +0.5 EV ANCHOR WITH CURRENT-SPREAD SACRIFICE CAPS ===')
    print(summary_df.to_csv(index=False))

    uncapped_dev_ev = float(summary_df.loc[summary_df.cap.eq(999.0), 'dev_ev_delta_bw3'].iloc[0])
    finite = summary_df[summary_df.cap.lt(999.0)].copy()
    finite['dev_ev_retention'] = finite.dev_ev_delta_bw3 / uncapped_dev_ev if uncapped_dev_ev != 0 else np.nan

    # Development-only choice: maximize mean BW=3 EV gain among finite safeguards.
    # Ties prefer the smaller cap. 2021-2025 is not used in this choice.
    chosen_row = finite.sort_values(['dev_ev_delta_bw3', 'cap'], ascending=[False, True]).iloc[0]
    chosen_cap = float(chosen_row.cap)
    print(f'UNCAPPED_DEV_EV_DELTA_BW3={uncapped_dev_ev}')
    print(f'DEV_SELECTED_FINITE_CAP={chosen_cap}')
    print(f'DEV_SELECTED_EV_RETENTION={float(chosen_row.dev_ev_retention)}')

    chosen = d[d.cap.eq(chosen_cap)].copy()
    print('=== CHOSEN FINITE-CAP UNCERTAINTY ===')
    for label, g in [
        ('dev_2011_2020', chosen[chosen.season.isin(DEV_SEASONS)]),
        ('later_2021_2025', chosen[chosen.season.isin(LATER_SEASONS)]),
        ('full_2011_2025', chosen),
    ]:
        print(label)
        for c in ['market_delta_vs_bf', 'ev_delta_1.5', 'ev_delta_3.0', 'ev_delta_4.0', 'actual_delta_vs_bf']:
            vals = g[c].to_numpy(float)
            print(
                f'  {c}: mean={vals.mean()} median={np.median(vals)} '
                f'ci={bootstrap_ci(vals)} wins={(vals>0).sum()} losses={(vals<0).sum()}'
            )
        print(
            f'  avg_deviations={g.deviations.mean()} '
            f'avg_sacrifice={g.sacrifice_sum.mean()} '
            f'max_week_sacrifice={g.max_sacrifice.max()}'
        )

    print('=== SANITY: CAP 999 SHOULD MATCH ORIGINAL FIXED +0.5 ANCHOR ===')
    max_market = 0.0
    max_ev = 0.0
    max_actual = 0.0
    for season in SEASONS:
        original = anchor.anchored_policy(tg, gpi, fg, season, FIXED_THRESHOLD, lookups[season])
        capped = capped_anchored_policy(tg, gpi, fg, season, 999.0, lookups[season])
        train_fav = fg[fg.season < season].copy()
        max_market = max(max_market, abs(float(original.market_expected_margin.sum() - capped.market_expected_margin.sum())))
        max_ev = max(max_ev, abs(anchor.add_eval_ev(original, train_fav, 3.0) - anchor.add_eval_ev(capped, train_fav, 3.0)))
        max_actual = max(max_actual, abs(float(original.actual_margin.sum() - capped.actual_margin.sum())))
    print(f'max_abs_market_delta={max_market} max_abs_ev_delta={max_ev} max_abs_actual_delta={max_actual}')

    print('=== PER-SEASON CHOSEN FINITE CAP ===')
    print(chosen.sort_values('season').to_csv(index=False))

    picks = pd.concat(pick_rows, ignore_index=True)
    chosen_picks = picks[picks.cap.eq(chosen_cap)].copy()
    print('=== CHOSEN FINITE-CAP DEVIATIONS ===')
    print(chosen_picks[chosen_picks.deviated.fillna(False)].to_csv(index=False))


if __name__ == '__main__':
    main()
