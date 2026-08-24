from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_empirical_sampler as empirical
import run_margin_future_lines as future
import run_margin_style_strategy as strat
import run_margin_anchor_policy as anchor
import run_margin_anchor_safeguards as safeguards

SEASONS = list(range(2011, 2026))
RECENT_SEASONS = list(range(2021, 2026))
N_SIMS = 100_000
BANDWIDTH = 3.0
SEED = 20260823
STRATEGIES = ['biggest_favorite', 'cap3_anchor', 'uncapped_anchor']


def build_paths(games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    tg = core.canonical_team_games(games)
    fg = dist.favorite_games(games)
    gpi = core.build_period_index(games)

    regular = games[games.game_type.eq('REG')].copy()
    max_week = regular.groupby('season').week.max().astype(int).to_dict()
    weekly, metric_cols = future.build_weekly_metrics()
    snapshots = future.build_origin_snapshots(weekly, metric_cols, max_week)
    ff, core_style, _ = future.build_future_frame(games, snapshots, metric_cols)

    rows = []
    for season in SEASONS:
        lookup = strat.train_future_predictions(ff, season, core_style)
        base = core.greedy_biggest_favorite(tg, season).selections.copy()
        cap3 = safeguards.capped_anchored_policy(tg, gpi, fg, season, 3.0, lookup)
        uncapped = safeguards.capped_anchored_policy(tg, gpi, fg, season, 999.0, lookup)
        for name, picks in [
            ('biggest_favorite', base),
            ('cap3_anchor', cap3),
            ('uncapped_anchor', uncapped),
        ]:
            p = picks[['season','week','game_id','team','opponent','is_home','market_expected_margin','actual_margin']].copy()
            p['strategy'] = name
            rows.append(p)
    return pd.concat(rows, ignore_index=True), fg


def sample_home_margins_for_games(
    season_games: pd.DataFrame,
    train_fav: pd.DataFrame,
    n_sims: int,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    ts = train_fav.favorite_spread.to_numpy(float)
    residual = (
        train_fav.favorite_margin.to_numpy(float)
        - train_fav.favorite_spread.to_numpy(float)
    )
    out: dict[str, np.ndarray] = {}
    for _, g in season_games.iterrows():
        game_id = str(g.game_id)
        home_market = float(g.spread_line)
        target = abs(home_market)
        w = empirical.kernel_weights(ts, target, BANDWIDTH)
        sampled_resid = rng.choice(residual, size=n_sims, replace=True, p=w)
        if home_market > 0:
            home_margin = home_market + sampled_resid
        elif home_market < 0:
            home_margin = home_market - sampled_resid
        else:
            # Pick'em games need no deterministic favorite orientation. Symmetrize
            # the favorite-side residual sample so home has no artificial bias.
            sign = rng.choice(np.array([-1.0, 1.0]), size=n_sims)
            home_margin = sign * sampled_resid
        # Contest margins are integer point differentials. The residual-centered
        # model can produce half-points when target/historical spreads have
        # different half-point parity, so round only at the simulated outcome layer.
        out[game_id] = np.rint(home_margin).astype(np.int16)
    return out


def score_strategy(
    picks: pd.DataFrame,
    home_margin_samples: dict[str, np.ndarray],
    n_sims: int,
) -> np.ndarray:
    total = np.zeros(n_sims, dtype=np.int32)
    for _, r in picks.iterrows():
        hm = home_margin_samples[str(r.game_id)]
        total += hm if bool(r.is_home) else -hm
    return total


def top_share(scores: dict[str, np.ndarray]) -> dict[str, float]:
    mat = np.vstack([scores[s] for s in STRATEGIES])
    mx = mat.max(axis=0)
    winners = mat == mx
    count = winners.sum(axis=0)
    return {
        s: float(np.mean(winners[i] / count))
        for i, s in enumerate(STRATEGIES)
    }


def pairwise(a: np.ndarray, b: np.ndarray) -> tuple[float,float,float]:
    return float(np.mean(a > b)), float(np.mean(a == b)), float(np.mean(a < b))


def simulate_season(
    games: pd.DataFrame,
    paths: pd.DataFrame,
    fg: pd.DataFrame,
    season: int,
) -> tuple[pd.DataFrame, dict]:
    train_fav = fg[fg.season < season].copy()
    season_games = games[(games.game_type.eq('REG')) & games.season.eq(season)].copy()
    season_games['spread_line'] = pd.to_numeric(season_games.spread_line, errors='coerce')
    season_games = season_games.dropna(subset=['spread_line']).copy()

    # Only simulate games selected by at least one compared strategy.
    used_game_ids = set(paths[paths.season.eq(season)].game_id.astype(str))
    selected_games = season_games[season_games.game_id.astype(str).isin(used_game_ids)].copy()
    rng = np.random.default_rng(SEED + season)
    home_samples = sample_home_margins_for_games(selected_games, train_fav, N_SIMS, rng)

    score = {}
    rows = []
    for strategy in STRATEGIES:
        picks = paths[(paths.season.eq(season)) & paths.strategy.eq(strategy)].copy()
        s = score_strategy(picks, home_samples, N_SIMS)
        score[strategy] = s
        rows.append({
            'season': season,
            'strategy': strategy,
            'sim_mean': float(s.mean()),
            'sim_sd': float(s.std(ddof=1)),
            'sim_p10': float(np.quantile(s, .10)),
            'sim_p25': float(np.quantile(s, .25)),
            'sim_median': float(np.median(s)),
            'sim_p75': float(np.quantile(s, .75)),
            'sim_p90': float(np.quantile(s, .90)),
            'observed_actual': float(picks.actual_margin.sum()),
            'selected_market_sum': float(picks.market_expected_margin.sum()),
        })

    shares = top_share(score)
    for row in rows:
        row['three_way_first_share'] = shares[row['strategy']]

    c3_bf = pairwise(score['cap3_anchor'], score['biggest_favorite'])
    uc_bf = pairwise(score['uncapped_anchor'], score['biggest_favorite'])
    c3_uc = pairwise(score['cap3_anchor'], score['uncapped_anchor'])
    pair = {
        'season': season,
        'cap3_gt_bf': c3_bf[0], 'cap3_eq_bf': c3_bf[1], 'cap3_lt_bf': c3_bf[2],
        'uncapped_gt_bf': uc_bf[0], 'uncapped_eq_bf': uc_bf[1], 'uncapped_lt_bf': uc_bf[2],
        'cap3_gt_uncapped': c3_uc[0], 'cap3_eq_uncapped': c3_uc[1], 'cap3_lt_uncapped': c3_uc[2],
    }
    return pd.DataFrame(rows), pair


def bootstrap_ci(values, n=100000, seed=SEED):
    a = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(n, len(a)), replace=True).mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def summarize(metrics: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    d = metrics[metrics.season.isin(seasons)].copy()
    rows = []
    for strategy, g in d.groupby('strategy'):
        rows.append({
            'strategy': strategy,
            'seasons': len(g),
            'mean_sim_score': float(g.sim_mean.mean()),
            'mean_sim_sd': float(g.sim_sd.mean()),
            'mean_selected_market_sum': float(g.selected_market_sum.mean()),
            'mean_observed_actual': float(g.observed_actual.mean()),
            'mean_three_way_first_share': float(g.three_way_first_share.mean()),
            'first_share_ci_low': bootstrap_ci(g.three_way_first_share.to_numpy(float))[0],
            'first_share_ci_high': bootstrap_ci(g.three_way_first_share.to_numpy(float))[1],
        })
    return pd.DataFrame(rows).sort_values('strategy')


def main() -> None:
    games = core.load_games()
    for c in ['season','week','spread_line']:
        games[c] = pd.to_numeric(games[c], errors='coerce')
    paths, fg = build_paths(games)

    metric_rows = []
    pair_rows = []
    for season in SEASONS:
        m, p = simulate_season(games, paths, fg, season)
        metric_rows.append(m)
        pair_rows.append(p)
    metrics = pd.concat(metric_rows, ignore_index=True)
    pairs = pd.DataFrame(pair_rows)

    print('=== JOINT MARGIN-POOL MONTE CARLO: 2011-2025 ===')
    print(f'n_sims_per_season={N_SIMS} bandwidth={BANDWIDTH} seed={SEED}')
    print(summarize(metrics, SEASONS).to_csv(index=False))

    print('=== MODERN 18-WEEK ERA: 2021-2025 ===')
    print(summarize(metrics, RECENT_SEASONS).to_csv(index=False))

    print('=== PAIRWISE CHAMPIONSHIP-STYLE COMPARISONS ===')
    for label, seasons in [('full_2011_2025', SEASONS), ('recent_2021_2025', RECENT_SEASONS)]:
        d = pairs[pairs.season.isin(seasons)]
        print(label)
        for stem in ['cap3_gt_bf','uncapped_gt_bf','cap3_gt_uncapped']:
            gt = d[stem]
            eq = d[stem.replace('_gt_','_eq_')]
            lt = d[stem.replace('_gt_','_lt_')]
            print(f'  {stem}: win={gt.mean()} tie={eq.mean()} loss={lt.mean()} win_ci={bootstrap_ci(gt.to_numpy(float))}')

    print('=== PER-SEASON STRATEGY DISTRIBUTIONS ===')
    print(metrics.sort_values(['season','strategy']).to_csv(index=False))
    print('=== PER-SEASON PAIRWISE ===')
    print(pairs.sort_values('season').to_csv(index=False))


if __name__ == '__main__':
    main()
