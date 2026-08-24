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
import run_margin_field_simulation as field

SEASONS = list(range(2021, 2026))
SNAPSHOT_WEEKS = [10, 13, 16]
FIELD_SIZES = [10, 25, 50, 100]
GAPS_TO_LEADER = [-30, -15, 0, 15]
N_SIMS = 20_000
BANDWIDTH = 3.0
SEED = 20260823
CANDIDATE_K = 6
MIXED_PROFILE = {'bf': 0.35, 'anchor': 0.30, 'top2': 0.20, 'top3': 0.15}


def build_context(games: pd.DataFrame):
    tg = core.canonical_team_games(games)
    fg = dist.favorite_games(games)
    gpi = core.build_period_index(games)
    regular = games[games.game_type.eq('REG')].copy()
    max_week = regular.groupby('season').week.max().astype(int).to_dict()
    weekly, metric_cols = future.build_weekly_metrics()
    snapshots = future.build_origin_snapshots(weekly, metric_cols, max_week)
    ff, core_style, _ = future.build_future_frame(games, snapshots, metric_cols)
    return tg, fg, gpi, ff, core_style


def build_modern_past_library(tg, gpi, fg, ff, core_style):
    rows = []
    meta = []
    lookups = {}
    for season in SEASONS:
        lookup = strat.train_future_predictions(ff, season, core_style)
        lookups[season] = lookup
        paths: list[tuple[str, str, pd.DataFrame]] = [
            ('biggest_favorite', 'bf', core.greedy_biggest_favorite(tg, season).selections.copy()),
            ('cap2_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 2.0, lookup)),
            ('cap3_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 3.0, lookup)),
            ('cap4_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 4.0, lookup)),
            ('uncapped_anchor', 'anchor', safeguards.capped_anchored_policy(tg, gpi, fg, season, 999.0, lookup)),
        ]
        for j in range(5):
            paths.append((
                f'top2_r{j}', 'top2',
                field.stochastic_chalk_path(tg, season, top_k=2, temperature=1.0, seed=SEED + season * 100 + j),
            ))
            paths.append((
                f'top3_r{j}', 'top3',
                field.stochastic_chalk_path(tg, season, top_k=3, temperature=1.5, seed=SEED + season * 100 + 50 + j),
            ))
        for name, group, picks in paths:
            p = picks[['season','week','game_id','team','opponent','is_home','market_expected_margin','actual_margin']].copy()
            p['path_name'] = name
            p['path_group'] = group
            rows.append(p)
            meta.append({'season': season, 'path_name': name, 'path_group': group})
    return pd.concat(rows, ignore_index=True), pd.DataFrame(meta).drop_duplicates(), lookups


def greedy_snapshot_plan(rem: pd.DataFrame, remaining: list[int], used: set[str], *, top_k: int = 1, seed: int = 0) -> pd.DataFrame:
    used_now = set(used)
    rows = []
    rng = np.random.default_rng(seed)
    for week in remaining:
        c = rem[rem.week.eq(week) & ~rem.team.isin(used_now)].copy()
        c = c.sort_values(['forecast_spread','forecast_ev','team'], ascending=[False,False,True], kind='stable').head(top_k).reset_index(drop=True)
        if c.empty:
            raise RuntimeError(f'No snapshot-greedy option W{week}')
        if top_k == 1 or len(c) == 1:
            idx = 0
        else:
            vals = c.forecast_spread.to_numpy(float)
            z = vals - vals.max()
            p = np.exp(z)
            p /= p.sum()
            idx = int(rng.choice(np.arange(len(c)), p=p))
        r = c.iloc[idx].copy()
        rows.append(r)
        used_now.add(str(r.team))
    out = pd.DataFrame(rows).reset_index(drop=True)
    core.validate_selections(out, remaining)
    return out


def opponent_snapshot_plan(
    tg, gpi, fg, season: int, week: int, used: set[str], lookup, group: str, path_name: str
) -> pd.DataFrame:
    train_fav = fg[fg.season < season].copy()
    rem, remaining = anchor.build_remaining_values(tg, gpi, season, week, used, lookup, train_fav)
    if group == 'anchor':
        return core.optimize(rem, season, 'forecast_ev', weeks=remaining, eligible_teams=set(rem.team.unique())).selections
    if group == 'bf':
        return greedy_snapshot_plan(rem, remaining, used, top_k=1, seed=0)
    j = int(path_name.split('r')[-1]) if 'r' in path_name else 0
    if group == 'top2':
        return greedy_snapshot_plan(rem, remaining, used, top_k=2, seed=SEED + season * 1000 + week * 10 + j)
    return greedy_snapshot_plan(rem, remaining, used, top_k=3, seed=SEED + season * 1000 + week * 10 + 50 + j)


def hero_candidate_plans(tg, gpi, fg, season: int, week: int, used: set[str], lookup, baseline_team: str):
    train_fav = fg[fg.season < season].copy()
    rem, remaining = anchor.build_remaining_values(tg, gpi, season, week, used, lookup, train_fav)
    current = rem[rem.week.eq(week)].copy().sort_values(
        ['market_expected_margin','forecast_ev','team'], ascending=[False,False,True], kind='stable'
    )
    candidates = current.head(CANDIDATE_K).copy()
    if baseline_team not in set(candidates.team.astype(str)):
        candidates = pd.concat([candidates, current[current.team.astype(str).eq(baseline_team)].head(1)], ignore_index=True)
    candidates = candidates.drop_duplicates('team').reset_index(drop=True)

    plans = {}
    meta = []
    future_weeks = [w for w in remaining if w > week]
    for _, cand in candidates.iterrows():
        team = str(cand.team)
        if future_weeks:
            future_rows = rem[rem.week.isin(future_weeks) & ~rem.team.eq(team)].copy()
            assignment = core.optimize(
                future_rows, season, 'forecast_ev', weeks=future_weeks,
                eligible_teams=set(future_rows.team.unique())
            ).selections
            plan = pd.concat([pd.DataFrame([cand]), assignment], ignore_index=True)
        else:
            plan = pd.DataFrame([cand]).reset_index(drop=True)
        core.validate_selections(plan, remaining)
        plans[team] = plan
        meta.append({
            'team': team,
            'current_spread': float(cand.market_expected_margin),
            'plan_ev': float(plan.forecast_ev.sum()),
            'plan_forecast_sum': float(plan.forecast_spread.sum()),
            'is_cap3_current': team == baseline_team,
        })
    return plans, pd.DataFrame(meta), rem, remaining


def sample_snapshot_games(home_forecast: dict[str, float], game_ids: set[str], train_fav: pd.DataFrame, seed: int):
    ts = train_fav.favorite_spread.to_numpy(float)
    residual = train_fav.favorite_margin.to_numpy(float) - ts
    rng = np.random.default_rng(seed)
    out = {}
    for game_id in sorted(game_ids):
        hp = float(home_forecast[game_id])
        target = abs(hp)
        w = empirical.kernel_weights(ts, target, BANDWIDTH)
        sampled = rng.choice(residual, size=N_SIMS, replace=True, p=w)
        if hp > 0:
            hm = hp + sampled
        elif hp < 0:
            hm = hp - sampled
        else:
            hm = rng.choice(np.array([-1.0, 1.0]), size=N_SIMS) * sampled
        out[game_id] = np.rint(hm).astype(np.int16)
    return out


def score_plan(plan: pd.DataFrame, samples: dict[str, np.ndarray]) -> np.ndarray:
    out = np.zeros(N_SIMS, dtype=np.int32)
    for _, r in plan.iterrows():
        hm = samples[str(r.game_id)]
        out += hm if bool(r.is_home) else -hm
    return out


def expected_first_share(hero: np.ndarray, opponents: np.ndarray) -> float:
    mx = opponents.max(axis=0)
    top = hero >= mx
    ties = np.where(top, (opponents == hero[None, :]).sum(axis=0), 0)
    share = np.where(top, 1.0 / (ties + 1.0), 0.0)
    return float(share.mean())


def field_roster(meta: pd.DataFrame, season: int, field_size: int) -> list[tuple[str,str]]:
    m = meta[meta.season.eq(season)].sort_values('path_name').reset_index(drop=True)
    counts = m.groupby('path_group').size().to_dict()
    p = np.array([MIXED_PROFILE[str(g)] / counts[str(g)] for g in m.path_group], float)
    p /= p.sum()
    rng = np.random.default_rng(SEED + season * 100 + field_size)
    idx = rng.choice(np.arange(len(m)), size=field_size - 1, replace=True, p=p)
    return [(str(m.iloc[i].path_name), str(m.iloc[i].path_group)) for i in idx]


def run_snapshot(tg, gpi, fg, library, meta, lookup, season: int, week: int, field_size: int):
    hero_full = library[(library.season.eq(season)) & library.path_name.eq('cap3_anchor')].copy()
    used_hero = set(hero_full[hero_full.week < week].team.astype(str))
    baseline_team = str(hero_full[hero_full.week.eq(week)].iloc[0].team)
    hero_plans, hero_meta, _, remaining = hero_candidate_plans(tg, gpi, fg, season, week, used_hero, lookup, baseline_team)

    # A global no-used filter gives one leakage-safe forecast per team-game at this snapshot.
    train_fav = fg[fg.season < season].copy()
    all_rem, _ = anchor.build_remaining_values(tg, gpi, season, week, set(), lookup, train_fav)
    home_rows = all_rem[all_rem.is_home].copy()
    home_forecast = dict(zip(home_rows.game_id.astype(str), home_rows.forecast_spread.astype(float)))

    roster = field_roster(meta, season, field_size)
    opponent_plans = []
    opponent_starts = []
    cache = {}
    for path_name, group in roster:
        past = library[(library.season.eq(season)) & library.path_name.eq(path_name)].copy()
        used = set(past[past.week < week].team.astype(str))
        start = float(past[past.week < week].actual_margin.sum())
        key = (path_name, group, tuple(sorted(used)))
        if key not in cache:
            cache[key] = opponent_snapshot_plan(tg, gpi, fg, season, week, used, lookup, group, path_name)
        opponent_plans.append(cache[key])
        opponent_starts.append(start)

    game_ids = set()
    for p in hero_plans.values():
        game_ids.update(p.game_id.astype(str))
    for p in opponent_plans:
        game_ids.update(p.game_id.astype(str))
    samples = sample_snapshot_games(home_forecast, game_ids, train_fav, SEED + season * 10000 + week * 100 + field_size)

    opponent_future = np.vstack([score_plan(p, samples) for p in opponent_plans])
    opponent_start = np.asarray(opponent_starts, dtype=np.int32)[:, None]
    opponent_total_base = opponent_start + opponent_future
    current_leader = float(max(opponent_starts))

    hero_scores = {team: score_plan(plan, samples) for team, plan in hero_plans.items()}
    for i, r in hero_meta.iterrows():
        hero_meta.loc[i, 'future_sim_sd'] = float(hero_scores[str(r.team)].std(ddof=1))
        hero_meta.loc[i, 'future_sim_mean'] = float(hero_scores[str(r.team)].mean())

    base_row = hero_meta[hero_meta.is_cap3_current].iloc[0]
    results = []
    for gap in GAPS_TO_LEADER:
        start_score = current_leader + gap
        shares = {}
        for _, r in hero_meta.iterrows():
            team = str(r.team)
            hero_total = start_score + hero_scores[team]
            shares[team] = expected_first_share(hero_total, opponent_total_base)
        best_team = sorted(shares, key=lambda t: (-shares[t], -float(hero_meta.loc[hero_meta.team.eq(t),'plan_ev'].iloc[0]), t))[0]
        best = hero_meta[hero_meta.team.eq(best_team)].iloc[0]
        base_share = shares[baseline_team]
        results.append({
            'season': season,
            'week': week,
            'field_size': field_size,
            'gap_to_leader': gap,
            'cap3_team': baseline_team,
            'champ_team': best_team,
            'champ_differs': best_team != baseline_team,
            'cap3_first_share': base_share,
            'champ_first_share': shares[best_team],
            'first_share_lift': shares[best_team] - base_share,
            'current_spread_delta_champ_minus_cap3': float(best.current_spread - base_row.current_spread),
            'plan_ev_delta_champ_minus_cap3': float(best.plan_ev - base_row.plan_ev),
            'sim_sd_delta_champ_minus_cap3': float(best.future_sim_sd - base_row.future_sim_sd),
            'cap3_current_spread': float(base_row.current_spread),
            'champ_current_spread': float(best.current_spread),
            'cap3_plan_ev': float(base_row.plan_ev),
            'champ_plan_ev': float(best.plan_ev),
            'cap3_future_sd': float(base_row.future_sim_sd),
            'champ_future_sd': float(best.future_sim_sd),
            'candidate_count': len(hero_meta),
        })
    return pd.DataFrame(results), hero_meta.assign(season=season, week=week, field_size=field_size)


def main() -> None:
    games = core.load_games()
    for c in ['season','week','spread_line']:
        games[c] = pd.to_numeric(games[c], errors='coerce')
    tg, fg, gpi, ff, core_style = build_context(games)
    library, meta, lookups = build_modern_past_library(tg, gpi, fg, ff, core_style)

    rows = []
    candidate_rows = []
    for season in SEASONS:
        for week in SNAPSHOT_WEEKS:
            max_week = int(tg[tg.season.eq(season)].week.max())
            if week > max_week:
                continue
            for field_size in FIELD_SIZES:
                r, c = run_snapshot(tg, gpi, fg, library, meta, lookups[season], season, week, field_size)
                rows.append(r)
                candidate_rows.append(c)
    results = pd.concat(rows, ignore_index=True)
    candidates = pd.concat(candidate_rows, ignore_index=True)

    print('=== LEAKAGE-SAFE STANDINGS GAME THEORY: MODERN 2021-2025 ===')
    print(f'snapshot_weeks={SNAPSHOT_WEEKS} field_sizes={FIELD_SIZES} gaps={GAPS_TO_LEADER} sims={N_SIMS}')
    print('future game outcomes are centered on snapshot-available forecast spreads, not eventual future closing lines')
    print('field_profile=' + repr(MIXED_PROFILE))

    summary = (
        results.groupby(['field_size','gap_to_leader'], as_index=False)
        .agg(
            snapshots=('season','size'),
            cap3_first_share=('cap3_first_share','mean'),
            championship_first_share=('champ_first_share','mean'),
            mean_first_share_lift=('first_share_lift','mean'),
            median_first_share_lift=('first_share_lift','median'),
            switch_rate=('champ_differs','mean'),
            mean_current_spread_delta=('current_spread_delta_champ_minus_cap3','mean'),
            mean_plan_ev_delta=('plan_ev_delta_champ_minus_cap3','mean'),
            mean_sd_delta=('sim_sd_delta_champ_minus_cap3','mean'),
        )
        .sort_values(['field_size','gap_to_leader'])
    )
    print('=== SUMMARY BY FIELD SIZE AND STANDINGS GAP ===')
    print(summary.to_csv(index=False))

    gap_summary = (
        results.groupby('gap_to_leader', as_index=False)
        .agg(
            snapshots=('season','size'),
            cap3_first_share=('cap3_first_share','mean'),
            championship_first_share=('champ_first_share','mean'),
            mean_first_share_lift=('first_share_lift','mean'),
            switch_rate=('champ_differs','mean'),
            mean_current_spread_delta=('current_spread_delta_champ_minus_cap3','mean'),
            mean_plan_ev_delta=('plan_ev_delta_champ_minus_cap3','mean'),
            mean_sd_delta=('sim_sd_delta_champ_minus_cap3','mean'),
        )
        .sort_values('gap_to_leader')
    )
    print('=== AGGREGATE BY GAP ===')
    print(gap_summary.to_csv(index=False))

    print('=== CHAMPIONSHIP PICK TEAM FREQUENCY ===')
    print(
        results.groupby(['gap_to_leader','champ_team']).size().reset_index(name='count')
        .sort_values(['gap_to_leader','count','champ_team'], ascending=[True,False,True])
        .to_csv(index=False)
    )

    print('=== PER-SNAPSHOT RESULTS ===')
    print(results.sort_values(['season','week','field_size','gap_to_leader']).to_csv(index=False))
    print('=== CANDIDATE SETS ===')
    print(candidates.sort_values(['season','week','field_size','current_spread'], ascending=[True,True,True,False]).to_csv(index=False))


if __name__ == '__main__':
    main()
