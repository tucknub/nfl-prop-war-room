from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_future_lines as future
import run_margin_style_strategy as strat
import run_margin_anchor_policy as anchor
import run_margin_anchor_safeguards as safeguards

SEASONS = list(range(2011, 2026))
TEST_SEASONS = list(range(2016, 2026))
RECENT_SEASONS = list(range(2021, 2026))
CAPS = safeguards.CAPS
EVAL_BWS = [1.5, 3.0, 4.0]
PRIMARY_RULE = 'risk95_expanding'


def bootstrap_ci(values, n=100000, seed=20260823):
    a = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(n, len(a)), replace=True).mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def select_cap(prior: pd.DataFrame, rule: str) -> tuple[float, pd.DataFrame]:
    finite = prior[prior.cap.lt(999.0)].groupby('cap', as_index=False).agg(
        mean_ev=('ev_delta_3.0', 'mean'),
        mean_market=('market_delta_vs_bf', 'mean'),
        mean_actual=('actual_delta_vs_bf', 'mean'),
        seasons=('season', 'nunique'),
    )
    if finite.empty:
        raise ValueError('No finite caps available')

    best_ev = float(finite.mean_ev.max())
    if rule.startswith('maxev'):
        eligible = finite[np.isclose(finite.mean_ev, best_ev, atol=1e-12)].copy()
        chosen = float(eligible.cap.min())
        return chosen, finite

    if rule.startswith('risk95'):
        retain = 0.95
    elif rule.startswith('risk90'):
        retain = 0.90
    else:
        raise ValueError(f'Unknown rule: {rule}')

    # If prior evidence says no finite policy has positive mean EV, use the most
    # conservative tested cap rather than widening risk to chase a negative edge.
    if best_ev <= 0:
        return float(finite.cap.min()), finite

    floor = retain * best_ev
    eligible = finite[finite.mean_ev >= floor - 1e-12].copy()
    chosen = float(eligible.cap.min())
    return chosen, finite


def build_policy_grid() -> tuple[pd.DataFrame, pd.DataFrame]:
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
    for cap in CAPS:
        for season in SEASONS:
            picks = safeguards.capped_anchored_policy(
                tg, gpi, fg, season, cap, lookups[season]
            )
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

    return pd.DataFrame(rows), tg


def apply_walkforward_rule(d: pd.DataFrame, rule: str, rolling_years: int | None = None) -> pd.DataFrame:
    selected = []
    prev_cap = None
    switches = 0
    for season in TEST_SEASONS:
        prior = d[d.season < season].copy()
        if rolling_years is not None:
            prior = prior[prior.season >= season - rolling_years].copy()
        chosen_cap, cap_table = select_cap(prior, rule)
        row = d[(d.season.eq(season)) & (d.cap.eq(chosen_cap))].iloc[0].copy()
        row['selected_cap'] = chosen_cap
        row['selection_rule'] = rule
        row['prior_start'] = int(prior.season.min())
        row['prior_end'] = int(prior.season.max())
        row['prior_seasons'] = int(prior.season.nunique())
        row['prior_best_finite_ev'] = float(cap_table.mean_ev.max())
        chosen_prior = cap_table[cap_table.cap.eq(chosen_cap)].iloc[0]
        row['chosen_prior_mean_ev'] = float(chosen_prior.mean_ev)
        row['chosen_prior_retention'] = (
            float(chosen_prior.mean_ev / cap_table.mean_ev.max())
            if cap_table.mean_ev.max() > 0 else np.nan
        )
        if prev_cap is not None and chosen_cap != prev_cap:
            switches += 1
        row['cap_switches_so_far'] = switches
        prev_cap = chosen_cap
        selected.append(row)
    return pd.DataFrame(selected).reset_index(drop=True)


def summarize_selected(label: str, g: pd.DataFrame) -> dict:
    return {
        'strategy': label,
        'n_seasons': len(g),
        'mean_cap': float(g.selected_cap.mean()),
        'median_cap': float(g.selected_cap.median()),
        'cap_switches': int(g.cap_switches_so_far.max()) if len(g) else 0,
        'mean_market_delta': float(g.market_delta_vs_bf.mean()),
        'mean_ev_delta_bw1.5': float(g['ev_delta_1.5'].mean()),
        'mean_ev_delta_bw3': float(g['ev_delta_3.0'].mean()),
        'mean_ev_delta_bw4': float(g['ev_delta_4.0'].mean()),
        'mean_actual_delta': float(g.actual_delta_vs_bf.mean()),
        'ev_wins': int((g['ev_delta_3.0'] > 0).sum()),
        'ev_losses': int((g['ev_delta_3.0'] < 0).sum()),
        'avg_deviations': float(g.deviations.mean()),
        'avg_sacrifice': float(g.sacrifice_sum.mean()),
        'max_week_sacrifice': float(g.max_sacrifice.max()),
    }


def static_reference(d: pd.DataFrame, cap: float, seasons: list[int]) -> pd.DataFrame:
    g = d[(d.cap.eq(cap)) & (d.season.isin(seasons))].copy()
    g['selected_cap'] = cap
    g['selection_rule'] = f'static_cap_{cap}'
    g['cap_switches_so_far'] = 0
    return g


def main() -> None:
    d, _ = build_policy_grid()

    primary = apply_walkforward_rule(d, 'risk95_expanding')
    maxev = apply_walkforward_rule(d, 'maxev_expanding')
    risk90 = apply_walkforward_rule(d, 'risk90_expanding')
    risk95_roll5 = apply_walkforward_rule(d, 'risk95_rolling5', rolling_years=5)

    print('=== WALK-FORWARD CAP SELECTION: 2016-2025 ===')
    summaries = []
    for label, g in [
        ('risk95_expanding_PRIMARY', primary),
        ('maxev_expanding_reference', maxev),
        ('risk90_expanding_sensitivity', risk90),
        ('risk95_rolling5_sensitivity', risk95_roll5),
        ('static_cap3_reference', static_reference(d, 3.0, TEST_SEASONS)),
        ('static_cap4_reference', static_reference(d, 4.0, TEST_SEASONS)),
        ('uncapped_reference', static_reference(d, 999.0, TEST_SEASONS)),
    ]:
        summaries.append(summarize_selected(label, g))
    print(pd.DataFrame(summaries).to_csv(index=False))

    print('=== MODERN 18-WEEK ERA: 2021-2025 ===')
    recent_summaries = []
    for label, g in [
        ('risk95_expanding_PRIMARY', primary[primary.season.isin(RECENT_SEASONS)]),
        ('maxev_expanding_reference', maxev[maxev.season.isin(RECENT_SEASONS)]),
        ('risk90_expanding_sensitivity', risk90[risk90.season.isin(RECENT_SEASONS)]),
        ('risk95_rolling5_sensitivity', risk95_roll5[risk95_roll5.season.isin(RECENT_SEASONS)]),
        ('static_cap3_reference', static_reference(d, 3.0, RECENT_SEASONS)),
        ('static_cap4_reference', static_reference(d, 4.0, RECENT_SEASONS)),
        ('uncapped_reference', static_reference(d, 999.0, RECENT_SEASONS)),
    ]:
        recent_summaries.append(summarize_selected(label, g))
    print(pd.DataFrame(recent_summaries).to_csv(index=False))

    print('=== PRIMARY RULE UNCERTAINTY ===')
    for label, g in [
        ('2016_2025', primary),
        ('2021_2025', primary[primary.season.isin(RECENT_SEASONS)]),
    ]:
        vals = g['ev_delta_3.0'].to_numpy(float)
        print(
            f'{label}: mean={vals.mean()} median={np.median(vals)} ci={bootstrap_ci(vals)} '
            f'wins={(vals>0).sum()} losses={(vals<0).sum()} '
            f'max_sacrifice={g.max_sacrifice.max()}'
        )

    print('=== PRIMARY WALK-FORWARD CAP CHOICES ===')
    cols = [
        'season', 'selected_cap', 'prior_start', 'prior_end', 'prior_seasons',
        'prior_best_finite_ev', 'chosen_prior_mean_ev', 'chosen_prior_retention',
        'market_delta_vs_bf', 'ev_delta_3.0', 'actual_delta_vs_bf',
        'deviations', 'sacrifice_sum', 'max_sacrifice', 'cap_switches_so_far'
    ]
    print(primary[cols].to_csv(index=False))

    print('=== RULE CAP CHOICES BY SEASON ===')
    choices = pd.DataFrame({'season': TEST_SEASONS})
    choices['risk95_expanding'] = primary.selected_cap.to_numpy(float)
    choices['maxev_expanding'] = maxev.selected_cap.to_numpy(float)
    choices['risk90_expanding'] = risk90.selected_cap.to_numpy(float)
    choices['risk95_rolling5'] = risk95_roll5.selected_cap.to_numpy(float)
    print(choices.to_csv(index=False))


if __name__ == '__main__':
    main()
