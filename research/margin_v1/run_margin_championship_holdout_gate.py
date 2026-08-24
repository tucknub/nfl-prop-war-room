from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_standings_game_theory as gt


EVAL_SEED_OFFSETS = [1_000_003, 2_000_003, 3_000_003]


def _disable_style_predictions(*_args, **_kwargs):
    return {}


def build_snapshot_components(tg, gpi, fg, library, meta, lookup, season: int, week: int, field_size: int):
    hero_full = library[(library.season.eq(season)) & library.path_name.eq('cap3_anchor')].copy()
    used_hero = set(hero_full[hero_full.week < week].team.astype(str))
    baseline_team = str(hero_full[hero_full.week.eq(week)].iloc[0].team)
    hero_plans, hero_meta, _, _ = gt.hero_candidate_plans(
        tg, gpi, fg, season, week, used_hero, lookup, baseline_team
    )

    train_fav = fg[fg.season < season].copy()
    all_rem, _ = gt.anchor.build_remaining_values(tg, gpi, season, week, set(), lookup, train_fav)
    home_rows = all_rem[all_rem.is_home].copy()
    home_forecast = dict(zip(home_rows.game_id.astype(str), home_rows.forecast_spread.astype(float)))

    roster = gt.field_roster(meta, season, field_size)
    opponent_plans = []
    opponent_starts = []
    cache = {}
    for path_name, group in roster:
        past = library[(library.season.eq(season)) & library.path_name.eq(path_name)].copy()
        used = set(past[past.week < week].team.astype(str))
        start = float(past[past.week < week].actual_margin.sum())
        key = (path_name, group, tuple(sorted(used)))
        if key not in cache:
            cache[key] = gt.opponent_snapshot_plan(
                tg, gpi, fg, season, week, used, lookup, group, path_name
            )
        opponent_plans.append(cache[key])
        opponent_starts.append(start)

    game_ids: set[str] = set()
    for plan in hero_plans.values():
        game_ids.update(plan.game_id.astype(str))
    for plan in opponent_plans:
        game_ids.update(plan.game_id.astype(str))

    return {
        'baseline_team': baseline_team,
        'hero_plans': hero_plans,
        'hero_meta': hero_meta,
        'train_fav': train_fav,
        'home_forecast': home_forecast,
        'opponent_plans': opponent_plans,
        'opponent_starts': np.asarray(opponent_starts, dtype=np.int32),
        'game_ids': game_ids,
    }


def shares_for_seed(parts: dict, seed: int) -> tuple[dict[int, dict[str, float]], dict[str, float]]:
    samples = gt.sample_snapshot_games(
        parts['home_forecast'], parts['game_ids'], parts['train_fav'], seed
    )
    opponent_future = np.vstack([
        gt.score_plan(plan, samples) for plan in parts['opponent_plans']
    ])
    opponent_total = parts['opponent_starts'][:, None] + opponent_future
    current_leader = float(parts['opponent_starts'].max())
    hero_scores = {
        team: gt.score_plan(plan, samples)
        for team, plan in parts['hero_plans'].items()
    }
    hero_means = {team: float(score.mean()) for team, score in hero_scores.items()}

    out: dict[int, dict[str, float]] = {}
    for gap in gt.GAPS_TO_LEADER:
        start_score = current_leader + gap
        out[gap] = {
            team: gt.expected_first_share(start_score + score, opponent_total)
            for team, score in hero_scores.items()
        }
    return out, hero_means


def choose_team(shares: dict[str, float], hero_meta: pd.DataFrame) -> str:
    plan_ev = dict(zip(hero_meta.team.astype(str), hero_meta.plan_ev.astype(float)))
    return sorted(shares, key=lambda t: (-shares[t], -plan_ev[t], t))[0]


def bootstrap_ci(values: np.ndarray, seed: int, n_boot: int = 50_000) -> tuple[float, float]:
    a = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(n_boot, len(a)), replace=True).mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return float(lo), float(hi)


def run_state(tg, gpi, fg, library, meta, lookup, season: int, week: int, field_size: int) -> list[dict]:
    parts = build_snapshot_components(tg, gpi, fg, library, meta, lookup, season, week, field_size)
    baseline = parts['baseline_team']
    hero_meta = parts['hero_meta']
    base_row = hero_meta[hero_meta.team.astype(str).eq(baseline)].iloc[0]
    base_seed = gt.SEED + season * 10000 + week * 100 + field_size

    selection_shares, _ = shares_for_seed(parts, base_seed)
    eval_share_sets = [
        shares_for_seed(parts, base_seed + offset)[0]
        for offset in EVAL_SEED_OFFSETS
    ]

    rows = []
    for gap in gt.GAPS_TO_LEADER:
        chosen = choose_team(selection_shares[gap], hero_meta)
        chosen_row = hero_meta[hero_meta.team.astype(str).eq(chosen)].iloc[0]
        selection_lift = selection_shares[gap][chosen] - selection_shares[gap][baseline]
        eval_lifts = [s[gap][chosen] - s[gap][baseline] for s in eval_share_sets]
        eval_chosen = [s[gap][chosen] for s in eval_share_sets]
        eval_base = [s[gap][baseline] for s in eval_share_sets]
        rows.append({
            'season': season,
            'week': week,
            'field_size': field_size,
            'gap_to_leader': gap,
            'cap3_team': baseline,
            'selected_champ_team': chosen,
            'switched': chosen != baseline,
            'selection_first_share_lift': float(selection_lift),
            'holdout_first_share_lift': float(np.mean(eval_lifts)),
            'holdout_first_share_lift_min_seed': float(np.min(eval_lifts)),
            'holdout_first_share_lift_max_seed': float(np.max(eval_lifts)),
            'holdout_cap3_first_share': float(np.mean(eval_base)),
            'holdout_champ_first_share': float(np.mean(eval_chosen)),
            'current_spread_delta': float(chosen_row.current_spread - base_row.current_spread),
            'plan_ev_delta': float(chosen_row.plan_ev - base_row.plan_ev),
        })
    return rows


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for gap, g in results.groupby('gap_to_leader', sort=True):
        switched = g[g.switched].copy()
        lo, hi = bootstrap_ci(g.holdout_first_share_lift.to_numpy(float), gt.SEED + int(gap) + 100)
        rows.append({
            'gap_to_leader': int(gap),
            'states': len(g),
            'switch_rate': float(g.switched.mean()),
            'selection_mean_lift': float(g.selection_first_share_lift.mean()),
            'holdout_mean_lift': float(g.holdout_first_share_lift.mean()),
            'holdout_median_lift': float(g.holdout_first_share_lift.median()),
            'holdout_ci_low': lo,
            'holdout_ci_high': hi,
            'switched_states': len(switched),
            'switched_positive_rate': float((switched.holdout_first_share_lift > 0).mean()) if len(switched) else np.nan,
            'switched_mean_lift': float(switched.holdout_first_share_lift.mean()) if len(switched) else 0.0,
            'mean_current_spread_delta': float(g.current_spread_delta.mean()),
            'mean_plan_ev_delta': float(g.plan_ev_delta.mean()),
        })
    return pd.DataFrame(rows)


def threshold_table(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for threshold in [0.0, 0.005, 0.01, 0.02, 0.03, 0.05]:
        for gap, g in results.groupby('gap_to_leader', sort=True):
            use = g.selection_first_share_lift > threshold
            realized = np.where(use, g.holdout_first_share_lift, 0.0)
            rows.append({
                'selection_lift_threshold': threshold,
                'gap_to_leader': int(gap),
                'override_rate': float(use.mean()),
                'holdout_mean_lift_after_threshold': float(realized.mean()),
                'override_positive_rate': float((g.loc[use, 'holdout_first_share_lift'] > 0).mean()) if use.any() else np.nan,
                'mean_current_spread_delta_when_override': float(g.loc[use, 'current_spread_delta'].mean()) if use.any() else 0.0,
                'mean_plan_ev_delta_when_override': float(g.loc[use, 'plan_ev_delta'].mean()) if use.any() else 0.0,
            })
    return pd.DataFrame(rows)


def main() -> None:
    gt.strat.train_future_predictions = _disable_style_predictions
    games = gt.core.load_games()
    for c in ['season', 'week', 'spread_line']:
        games[c] = pd.to_numeric(games[c], errors='coerce')
    tg, fg, gpi, ff, core_style = gt.build_context(games)
    library, meta, lookups = gt.build_modern_past_library(tg, gpi, fg, ff, core_style)

    rows = []
    for season in gt.SEASONS:
        for week in gt.SNAPSHOT_WEEKS:
            if week > int(tg[tg.season.eq(season)].week.max()):
                continue
            for field_size in gt.FIELD_SIZES:
                rows.extend(run_state(tg, gpi, fg, library, meta, lookups[season], season, week, field_size))
    results = pd.DataFrame(rows)

    print('=== INDEPENDENT-SEED CHAMPIONSHIP HOLDOUT GATE ===')
    print('future_model=raw_long_slow_market_power style_lookup=forced_empty')
    print(f'selection_sims={gt.N_SIMS} independent_eval_seeds={len(EVAL_SEED_OFFSETS)} x {gt.N_SIMS}')
    print('candidate chosen only on selection seed; all reported holdout lift uses independent outcome draws')
    print('=== HOLDOUT SUMMARY BY GAP ===')
    print(summarize(results).to_csv(index=False))
    print('=== FIXED SELECTION-LIFT THRESHOLD SENSITIVITY ===')
    print(threshold_table(results).to_csv(index=False))
    print('=== PER-STATE HOLDOUT RESULTS ===')
    print(results.sort_values(['gap_to_leader', 'season', 'week', 'field_size']).to_csv(index=False))


if __name__ == '__main__':
    main()
