from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_empirical_sampler as empirical
import run_margin_future_lines as future
import run_margin_style_strategy as strat
import run_margin_anchor_safeguards as safeguards

SEASONS = list(range(2011, 2026))
RECENT_SEASONS = list(range(2021, 2026))
N_SIMS = 50_000
BANDWIDTH = 3.0
SEED = 20260823
FIELD_SIZES = [10, 25, 50, 100]
HEROES = ['biggest_favorite', 'cap3_anchor', 'uncapped_anchor']

# These are sensitivity scenarios, not claims about the user's actual pool.
FIELD_PROFILES = {
    'chalk_heavy': {'bf': 0.55, 'anchor': 0.20, 'top2': 0.15, 'top3': 0.10},
    'mixed': {'bf': 0.35, 'anchor': 0.30, 'top2': 0.20, 'top3': 0.15},
    'sharp_heavy': {'bf': 0.20, 'anchor': 0.50, 'top2': 0.15, 'top3': 0.15},
}


def stochastic_chalk_path(
    tg: pd.DataFrame,
    season: int,
    *,
    top_k: int,
    temperature: float,
    seed: int,
) -> pd.DataFrame:
    d = tg[tg.season.eq(season)].copy()
    weeks = sorted(int(x) for x in d.week.unique())
    used: set[str] = set()
    rows = []
    rng = np.random.default_rng(seed)
    for week in weeks:
        c = d[d.week.eq(week) & ~d.team.isin(used) & d.market_expected_margin.notna()].copy()
        if c.empty:
            raise RuntimeError(f'No eligible current-market team for {season} W{week}')
        c = c.sort_values(
            ['market_expected_margin', 'total_line', 'team'],
            ascending=[False, False, True],
            kind='stable',
        ).head(top_k).reset_index(drop=True)
        spreads = c.market_expected_margin.to_numpy(float)
        z = (spreads - spreads.max()) / max(float(temperature), 1e-6)
        p = np.exp(z)
        p = p / p.sum()
        idx = int(rng.choice(np.arange(len(c)), p=p))
        r = c.iloc[idx].copy()
        rows.append(r)
        used.add(str(r.team))
    out = pd.DataFrame(rows).reset_index(drop=True)
    core.validate_selections(out, weeks)
    return out


def build_path_library(games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tg = core.canonical_team_games(games)
    fg = dist.favorite_games(games)
    gpi = core.build_period_index(games)

    regular = games[games.game_type.eq('REG')].copy()
    max_week = regular.groupby('season').week.max().astype(int).to_dict()
    weekly, metric_cols = future.build_weekly_metrics()
    snapshots = future.build_origin_snapshots(weekly, metric_cols, max_week)
    ff, core_style, _ = future.build_future_frame(games, snapshots, metric_cols)

    rows = []
    meta = []
    for season in SEASONS:
        lookup = strat.train_future_predictions(ff, season, core_style)
        paths: list[tuple[str, str, pd.DataFrame]] = [
            ('biggest_favorite', 'bf', core.greedy_biggest_favorite(tg, season).selections.copy()),
            ('cap2_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 2.0, lookup)),
            ('cap3_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 3.0, lookup)),
            ('cap4_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 4.0, lookup)),
            ('uncapped_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 999.0, lookup)),
        ]
        for j in range(6):
            paths.append((
                f'top2_r{j}', 'top2',
                stochastic_chalk_path(tg, season, top_k=2, temperature=1.0, seed=SEED + season * 100 + j),
            ))
            paths.append((
                f'top3_r{j}', 'top3',
                stochastic_chalk_path(tg, season, top_k=3, temperature=1.5, seed=SEED + season * 100 + 50 + j),
            ))

        for name, group, picks in paths:
            p = picks[[
                'season','week','game_id','team','opponent','is_home',
                'market_expected_margin','actual_margin'
            ]].copy()
            p['path_name'] = name
            p['path_group'] = group
            rows.append(p)
            meta.append({'season': season, 'path_name': name, 'path_group': group})

    return pd.concat(rows, ignore_index=True), pd.DataFrame(meta).drop_duplicates(), fg


def sample_home_margins_for_games(
    season_games: pd.DataFrame,
    train_fav: pd.DataFrame,
    n_sims: int,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    ts = train_fav.favorite_spread.to_numpy(float)
    residual = train_fav.favorite_margin.to_numpy(float) - ts
    out: dict[str, np.ndarray] = {}
    for _, g in season_games.iterrows():
        game_id = str(g.game_id)
        home_market = float(g.spread_line)
        target = abs(home_market)
        w = empirical.kernel_weights(ts, target, BANDWIDTH)
        sampled_resid = rng.choice(residual, size=n_sims, replace=True, p=w)
        if home_market > 0:
            hm = home_market + sampled_resid
        elif home_market < 0:
            hm = home_market - sampled_resid
        else:
            hm = rng.choice(np.array([-1.0, 1.0]), size=n_sims) * sampled_resid
        out[game_id] = np.rint(hm).astype(np.int16)
    return out


def score_path(picks: pd.DataFrame, samples: dict[str, np.ndarray]) -> np.ndarray:
    total = np.zeros(N_SIMS, dtype=np.int32)
    for _, r in picks.iterrows():
        hm = samples[str(r.game_id)]
        total += hm if bool(r.is_home) else -hm
    return total


def path_probabilities(meta: pd.DataFrame, profile: dict[str, float]) -> np.ndarray:
    group_counts = meta.groupby('path_group').size().to_dict()
    probs = np.array([
        profile[str(g)] / float(group_counts[str(g)])
        for g in meta.path_group
    ], dtype=float)
    probs /= probs.sum()
    return probs


def hero_field_result(
    hero_score: np.ndarray,
    path_scores: np.ndarray,
    probs: np.ndarray,
    field_size: int,
    rng: np.random.Generator,
) -> dict[str, float]:
    n_opp = field_size - 1
    # Each simulated pool entry independently draws an opponent path archetype.
    idx = rng.choice(np.arange(path_scores.shape[0]), size=(N_SIMS, n_opp), replace=True, p=probs)
    sim_col = np.arange(N_SIMS)[:, None]
    opp_scores = path_scores[idx, sim_col]
    opp_max = opp_scores.max(axis=1)
    hero_is_top = hero_score >= opp_max
    hero_out = hero_score > opp_max
    ties_at_top = np.where(hero_is_top, (opp_scores == hero_score[:, None]).sum(axis=1), 0)
    share = np.where(hero_is_top, 1.0 / (ties_at_top + 1.0), 0.0)
    return {
        'outright_first_prob': float(hero_out.mean()),
        'tie_or_first_prob': float(hero_is_top.mean()),
        'expected_first_share': float(share.mean()),
        'mean_winning_margin_when_outright': float((hero_score[hero_out] - opp_max[hero_out]).mean()) if hero_out.any() else np.nan,
        'mean_deficit_when_not_first': float((opp_max[~hero_is_top] - hero_score[~hero_is_top]).mean()) if (~hero_is_top).any() else np.nan,
    }


def simulate_season(
    games: pd.DataFrame,
    library: pd.DataFrame,
    meta: pd.DataFrame,
    fg: pd.DataFrame,
    season: int,
) -> pd.DataFrame:
    paths = library[library.season.eq(season)].copy()
    season_meta = meta[meta.season.eq(season)].sort_values('path_name').reset_index(drop=True)
    train_fav = fg[fg.season < season].copy()
    season_games = games[(games.game_type.eq('REG')) & games.season.eq(season)].copy()
    season_games['spread_line'] = pd.to_numeric(season_games.spread_line, errors='coerce')
    season_games = season_games.dropna(subset=['spread_line']).copy()

    used_ids = set(paths.game_id.astype(str))
    selected_games = season_games[season_games.game_id.astype(str).isin(used_ids)].copy()
    outcome_rng = np.random.default_rng(SEED + season)
    samples = sample_home_margins_for_games(selected_games, train_fav, N_SIMS, outcome_rng)

    score_map: dict[str, np.ndarray] = {}
    for name in season_meta.path_name:
        picks = paths[paths.path_name.eq(name)].copy()
        score_map[str(name)] = score_path(picks, samples)
    path_scores = np.vstack([score_map[str(n)] for n in season_meta.path_name])

    rows = []
    for profile_name, profile in FIELD_PROFILES.items():
        probs = path_probabilities(season_meta, profile)
        for field_size in FIELD_SIZES:
            # Reuse the same field draw across hero strategies to make comparisons paired.
            field_seed = SEED + season * 10000 + field_size * 10 + list(FIELD_PROFILES).index(profile_name)
            for hero in HEROES:
                rng = np.random.default_rng(field_seed)
                r = hero_field_result(score_map[hero], path_scores, probs, field_size, rng)
                rows.append({
                    'season': season,
                    'profile': profile_name,
                    'field_size': field_size,
                    'hero': hero,
                    'hero_sim_mean': float(score_map[hero].mean()),
                    **r,
                })
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    d = results[results.season.isin(seasons)].copy()
    return (
        d.groupby(['profile','field_size','hero'], as_index=False)
        .agg(
            seasons=('season','nunique'),
            mean_sim_score=('hero_sim_mean','mean'),
            outright_first_prob=('outright_first_prob','mean'),
            tie_or_first_prob=('tie_or_first_prob','mean'),
            expected_first_share=('expected_first_share','mean'),
            mean_win_margin=('mean_winning_margin_when_outright','mean'),
            mean_deficit_when_not_first=('mean_deficit_when_not_first','mean'),
        )
        .sort_values(['profile','field_size','hero'])
        .reset_index(drop=True)
    )


def main() -> None:
    games = core.load_games()
    for c in ['season','week','spread_line']:
        games[c] = pd.to_numeric(games[c], errors='coerce')
    library, meta, fg = build_path_library(games)

    print('=== FIELD MODEL ===')
    print(f'n_sims_per_season={N_SIMS} bandwidth={BANDWIDTH} seed={SEED}')
    print('field_profiles=' + repr(FIELD_PROFILES))
    print('path_counts=' + repr(meta.groupby('path_group').path_name.nunique().to_dict()))

    rows = []
    for season in SEASONS:
        rows.append(simulate_season(games, library, meta, fg, season))
    results = pd.concat(rows, ignore_index=True)

    print('=== HETEROGENEOUS FIELD: 2011-2025 ===')
    print(summarize(results, SEASONS).to_csv(index=False))
    print('=== HETEROGENEOUS FIELD: MODERN 2021-2025 ===')
    print(summarize(results, RECENT_SEASONS).to_csv(index=False))

    print('=== CAP3 MINUS BIGGEST FAVORITE FIRST-SHARE DELTA ===')
    wide = results.pivot_table(
        index=['season','profile','field_size'], columns='hero', values='expected_first_share'
    ).reset_index()
    wide['cap3_minus_bf'] = wide['cap3_anchor'] - wide['biggest_favorite']
    wide['cap3_minus_uncapped'] = wide['cap3_anchor'] - wide['uncapped_anchor']
    print(
        wide.groupby(['profile','field_size'], as_index=False)
        .agg(
            cap3_minus_bf=('cap3_minus_bf','mean'),
            cap3_minus_uncapped=('cap3_minus_uncapped','mean'),
            cap3_beats_bf_seasons=('cap3_minus_bf', lambda x: int((x > 0).sum())),
            cap3_beats_uncapped_seasons=('cap3_minus_uncapped', lambda x: int((x > 0).sum())),
        )
        .to_csv(index=False)
    )

    print('=== PER-SEASON FIELD RESULTS ===')
    print(results.sort_values(['season','profile','field_size','hero']).to_csv(index=False))


if __name__ == '__main__':
    main()
