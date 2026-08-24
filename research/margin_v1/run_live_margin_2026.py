from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_empirical_sampler as empirical
import run_margin_expected_allocation as evaudit
import run_2026_full_preseason_roadmap as preseason

DEFAULT_STATE = Path(__file__).with_name('live_state_2026.json')
BANDWIDTH = 3.0
EV_THRESHOLD = 0.5
DEFAULT_CAP = 3.0


def load_state(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def validate_state(state: dict) -> None:
    if int(state.get('season', 0)) != 2026:
        raise AssertionError('Live V1 runner is currently scoped to season 2026.')
    current = int(state['current_week'])
    if current < 1 or current > 18:
        raise AssertionError(f'Invalid current_week={current}')
    used = [str(x) for x in state.get('used_teams', [])]
    if len(used) != len(set(used)):
        raise AssertionError('used_teams contains duplicates')
    if len(used) != int(state.get('completed_week', 0)):
        raise AssertionError('used_teams count must equal completed_week')
    results = state.get('weekly_results', [])
    if len(results) != int(state.get('completed_week', 0)):
        raise AssertionError('weekly_results count must equal completed_week')
    calc_score = float(sum(float(x['actual_margin']) for x in results)) if results else 0.0
    if abs(calc_score - float(state.get('cumulative_score', 0.0))) > 1e-9:
        raise AssertionError('cumulative_score does not equal weekly_results sum')


def prepare_games(games: pd.DataFrame, season: int) -> pd.DataFrame:
    g = games[(pd.to_numeric(games.season, errors='coerce') == season) & games.game_type.eq('REG')].copy()
    for c in ['season','week','spread_line','total_line','home_score','away_score']:
        if c in g:
            g[c] = pd.to_numeric(g[c], errors='coerce')
    if g.empty:
        raise RuntimeError(f'No season={season} regular-season rows')
    return g


def build_available_market(g: pd.DataFrame, current_week: int, future_posted_mode: str) -> pd.DataFrame:
    d = g.copy()
    d['market_available'] = d.spread_line.notna()
    if future_posted_mode == 'current_week_only':
        d['market_available'] = d.market_available & d.week.le(current_week)
    elif future_posted_mode != 'live':
        raise ValueError(f'Unknown future_posted_mode={future_posted_mode}')
    return d


def fit_snapshot_ratings(g: pd.DataFrame):
    available = g[g.market_available].copy()
    if len(available) < 16:
        raise RuntimeError('Too few posted market games to build snapshot fallback ratings')
    temp = available.copy()
    temp['spread_line'] = np.where(temp.market_available, temp.spread_line, np.nan)
    return preseason.fit_market_ratings(temp)


def build_team_values(g: pd.DataFrame, current_week: int, future_posted_mode: str) -> tuple[pd.DataFrame, dict]:
    d = build_available_market(g, current_week, future_posted_mode)
    ratings, hfa = fit_snapshot_ratings(d)

    def home_inferred(r) -> float:
        adj = 0.0 if str(r.location).lower() != 'home' else hfa
        return float(ratings.get(str(r.home_team), 0.0) - ratings.get(str(r.away_team), 0.0) + adj)

    d['inferred_home_spread'] = d.apply(home_inferred, axis=1)
    d['snapshot_home_spread'] = np.where(d.market_available, d.spread_line, d.inferred_home_spread)
    d['home_value_source'] = np.where(
        d.week.eq(current_week) & d.market_available,
        'CURRENT_MARKET',
        np.where(d.market_available, 'POSTED_LOOKAHEAD', 'MARKET_RATING_INFERRED')
    )

    home = pd.DataFrame({
        'season': 2026,
        'week': d.week.astype(int),
        'game_id': d.game_id.astype(str),
        'team': d.home_team.astype(str),
        'opponent': d.away_team.astype(str),
        'is_home': True,
        'location': d.location,
        'raw_value_spread': d.snapshot_home_spread.astype(float),
        'value_source': d.home_value_source.astype(str),
        'posted_team_spread': np.where(d.market_available, d.spread_line, np.nan),
        'total_line': d.total_line,
    })
    away = pd.DataFrame({
        'season': 2026,
        'week': d.week.astype(int),
        'game_id': d.game_id.astype(str),
        'team': d.away_team.astype(str),
        'opponent': d.home_team.astype(str),
        'is_home': False,
        'location': d.location,
        'raw_value_spread': -d.snapshot_home_spread.astype(float),
        'value_source': d.home_value_source.astype(str),
        'posted_team_spread': np.where(d.market_available, -d.spread_line, np.nan),
        'total_line': d.total_line,
    })
    rows = pd.concat([home, away], ignore_index=True)
    return rows, {'ratings': ratings, 'hfa': hfa, 'posted_games_used_for_fallback': int(d.market_available.sum())}


def signed_distribution(train_fav: pd.DataFrame, spread: float, bandwidth: float = BANDWIDTH) -> dict[str, float]:
    s = float(spread)
    if abs(s) < 1e-12:
        # Use residuals near pick'em and symmetrize their sign so pick'em is not given an artificial side bias.
        ts = train_fav.favorite_spread.to_numpy(float)
        residual = train_fav.favorite_margin.to_numpy(float) - ts
        w = empirical.kernel_weights(ts, 0.0, bandwidth)
        margins = residual
        expected = 0.0
        p_loss = 0.5
        return {
            'calibrated_ev': expected,
            'p_loss': p_loss,
            'p_win10': float(np.sum(w * (margins >= 10))),
            'p_win20': float(np.sum(w * (margins >= 20))),
            'p_win30': float(np.sum(w * (margins >= 30))),
        }
    a = abs(s)
    ts = train_fav.favorite_spread.to_numpy(float)
    fm = train_fav.favorite_margin.to_numpy(float)
    residual = fm - ts
    w = empirical.kernel_weights(ts, a, bandwidth)
    favorite_margin = a + residual
    team_margin = favorite_margin if s > 0 else -favorite_margin
    return {
        'calibrated_ev': float(np.sum(w * team_margin)),
        'p_loss': float(np.sum(w * (team_margin < 0))),
        'p_win10': float(np.sum(w * (team_margin >= 10))),
        'p_win20': float(np.sum(w * (team_margin >= 20))),
        'p_win30': float(np.sum(w * (team_margin >= 30))),
    }


def add_calibration(rows: pd.DataFrame, train_fav: pd.DataFrame) -> pd.DataFrame:
    out = rows.copy()
    vals = [signed_distribution(train_fav, x) for x in out.raw_value_spread.to_numpy(float)]
    p = pd.DataFrame(vals, index=out.index)
    for c in p.columns:
        out[c] = p[c]
    return out


def exact_assignment(rows: pd.DataFrame, weeks: list[int], used: set[str]) -> tuple[pd.DataFrame, float]:
    d = rows[rows.week.isin(weeks) & ~rows.team.isin(used)].copy()
    teams = sorted(set(d.team.astype(str)))
    wi = {w:i for i,w in enumerate(weeks)}
    ti = {t:j for j,t in enumerate(teams)}
    INF = 1e8
    cost = np.full((len(weeks), len(teams)), INF)
    lookup = {}
    for _, r in d.iterrows():
        w = int(r.week); t = str(r.team)
        if w not in wi:
            continue
        v = float(r.calibrated_ev)
        cost[wi[w], ti[t]] = -v + ti[t] * 1e-9
        lookup[(w,t)] = r
    rr, cc = linear_sum_assignment(cost)
    if len(rr) != len(weeks) or np.any(cost[rr,cc] >= INF/2):
        raise RuntimeError('No feasible one-use assignment for remaining weeks')
    picked = [lookup[(weeks[i], teams[j])] for i,j in sorted(zip(rr,cc))]
    s = pd.DataFrame(picked).reset_index(drop=True)
    if sorted(s.week.astype(int).tolist()) != weeks:
        raise AssertionError('Assignment does not cover every remaining week')
    if s.team.duplicated().any():
        raise AssertionError('Assignment reused a team')
    return s, float(s.calibrated_ev.sum())


def candidate_plan(rows: pd.DataFrame, current_week: int, used: set[str], cand: pd.Series) -> tuple[pd.DataFrame, float]:
    remaining = sorted(int(x) for x in rows.week.unique() if int(x) >= current_week)
    future_weeks = [w for w in remaining if w > current_week]
    if future_weeks:
        future, obj = exact_assignment(rows, future_weeks, used | {str(cand.team)})
        route = pd.concat([pd.DataFrame([cand]), future], ignore_index=True)
        total = float(cand.calibrated_ev + obj)
    else:
        route = pd.DataFrame([cand]).reset_index(drop=True)
        total = float(cand.calibrated_ev)
    if route.team.duplicated().any():
        raise AssertionError('Candidate route reused a team')
    return route, total


def score_current_candidates(rows: pd.DataFrame, current_week: int, used: set[str]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    current = rows[rows.week.eq(current_week) & ~rows.team.isin(used)].copy()
    if current.empty:
        raise RuntimeError('No eligible current-week teams')
    if not current.value_source.eq('CURRENT_MARKET').all():
        raise RuntimeError('Current-week board requires posted current market for every team-game')

    current = current.sort_values(
        ['raw_value_spread','total_line','team'], ascending=[False,False,True], kind='stable'
    ).reset_index(drop=True)
    anchor = current.iloc[0]
    anchor_line = float(anchor.raw_value_spread)

    future_weeks = sorted(int(x) for x in rows.week.unique() if int(x) > current_week)
    if future_weeks:
        future_with_all, future_with_all_obj = exact_assignment(rows, future_weeks, used)
    else:
        future_with_all, future_with_all_obj = pd.DataFrame(), 0.0

    scored = []
    routes: dict[str, pd.DataFrame] = {}
    for _, cand in current.iterrows():
        team = str(cand.team)
        route, total = candidate_plan(rows, current_week, used, cand)
        routes[team] = route
        if future_weeks:
            _, future_without_obj = exact_assignment(rows, future_weeks, used | {team})
            future_cost = float(future_with_all_obj - future_without_obj)
        else:
            future_cost = 0.0
        scored.append({
            'team': team,
            'opponent': str(cand.opponent),
            'current_spread': float(cand.raw_value_spread),
            'calibrated_margin': float(cand.calibrated_ev),
            'p_loss': float(cand.p_loss),
            'p_win10': float(cand.p_win10),
            'p_win20': float(cand.p_win20),
            'p_win30': float(cand.p_win30),
            'future_cost': future_cost,
            'total_season_ev': total,
            'current_sacrifice_vs_anchor': float(anchor_line - float(cand.raw_value_spread)),
            'current_value_source': str(cand.value_source),
            'game_id': str(cand.game_id),
        })
    board = pd.DataFrame(scored)
    anchor_total = float(board.loc[board.team.eq(str(anchor.team)), 'total_season_ev'].iloc[0])
    board['total_season_ev_delta_vs_anchor'] = board.total_season_ev - anchor_total
    board['anchor_team'] = str(anchor.team)
    return board, routes


def choose_expected_points_pick(board: pd.DataFrame, current_week: int, cap: float, threshold: float) -> tuple[str, str]:
    anchor_team = str(board.anchor_team.iloc[0])
    if current_week <= 3:
        return anchor_team, 'WEEKS_1_TO_3_BIGGEST_FAVORITE_DEFAULT'

    eligible = board[board.current_sacrifice_vs_anchor <= cap + 1e-12].copy()
    eligible = eligible.sort_values(
        ['total_season_ev','current_spread','team'], ascending=[False,False,True], kind='stable'
    )
    best = eligible.iloc[0]
    if str(best.team) != anchor_team and float(best.total_season_ev_delta_vs_anchor) >= threshold - 1e-12:
        return str(best.team), 'CAP3_EV_DEVIATION'
    return anchor_team, 'ANCHOR_RETAINED'


def classify_board(board: pd.DataFrame, pick: str) -> pd.DataFrame:
    out = board.copy()
    anchor = str(out.anchor_team.iloc[0])
    out['status'] = 'WATCH'
    out.loc[out.team.eq(anchor), 'status'] = 'ANCHOR'
    out.loc[out.current_sacrifice_vs_anchor > DEFAULT_CAP + 1e-12, 'status'] = 'AVOID_CAP'
    out.loc[(out.total_season_ev_delta_vs_anchor > 0) & ~out.team.eq(pick), 'status'] = 'SAVE/PIVOT'
    out.loc[out.team.eq(pick), 'status'] = 'PICK'
    return out.sort_values(
        ['status','total_season_ev','current_spread','team'], ascending=[True,False,False,True], kind='stable'
    )


def run(state: dict, future_posted_mode: str = 'live') -> dict:
    validate_state(state)
    season = int(state['season'])
    current_week = int(state['current_week'])
    used = set(str(x) for x in state.get('used_teams', []))
    snapshot_utc = datetime.now(timezone.utc).isoformat()

    games = core.load_games()
    g = prepare_games(games, season)
    rows, fallback = build_team_values(g, current_week, future_posted_mode)

    historical_fav = dist.favorite_games(games)
    historical_fav = historical_fav[historical_fav.season < season].copy()
    rows = add_calibration(rows, historical_fav)
    rows = rows[rows.week.ge(current_week) & ~rows.team.isin(used)].copy()

    board, routes = score_current_candidates(rows, current_week, used)
    cap = float(state.get('model_policy', {}).get('default_current_spread_sacrifice_cap', DEFAULT_CAP))
    threshold = float(state.get('model_policy', {}).get('anchor_ev_threshold', EV_THRESHOLD))
    pick, pick_reason = choose_expected_points_pick(board, current_week, cap, threshold)
    board = classify_board(board, pick)

    anchor = str(board.anchor_team.iloc[0])
    pick_row = board[board.team.eq(pick)].iloc[0]
    anchor_row = board[board.team.eq(anchor)].iloc[0]
    selected_route = routes[pick]

    pool = state.get('pool', {})
    opponents = state.get('opponents', [])
    champ_ready = bool(pool.get('size')) and len(opponents) > 0
    championship_status = 'READY_FOR_SIMULATION' if champ_ready else 'UNAVAILABLE_POOL_STATE_MISSING'

    audit = {
        'schema_version': 'margin_live_decision_v1',
        'snapshot_utc': snapshot_utc,
        'season': season,
        'week': current_week,
        'used_teams': sorted(used),
        'cumulative_score': float(state.get('cumulative_score', 0.0)),
        'data_quality': {
            'season_games': int(len(g)),
            'current_week_games': int(g[g.week.eq(current_week)].game_id.nunique()),
            'current_week_posted_spreads': int(g[g.week.eq(current_week)].spread_line.notna().sum()),
            'snapshot_posted_market_games_used_for_fallback': fallback['posted_games_used_for_fallback'],
            'future_posted_mode': future_posted_mode,
            'remaining_value_source_counts': rows.value_source.value_counts().to_dict(),
            'fallback_hfa': fallback['hfa'],
        },
        'policy': {
            'expected_points_pick': pick,
            'pick_reason': pick_reason,
            'anchor': anchor,
            'anchor_ev_threshold': threshold,
            'current_spread_sacrifice_cap': cap,
            'championship_status': championship_status,
        },
        'pick': {
            'team': pick,
            'opponent': str(pick_row.opponent),
            'current_spread': float(pick_row.current_spread),
            'calibrated_margin': float(pick_row.calibrated_margin),
            'p_loss': float(pick_row.p_loss),
            'p_win20': float(pick_row.p_win20),
            'total_season_ev': float(pick_row.total_season_ev),
            'total_season_ev_delta_vs_anchor': float(pick_row.total_season_ev_delta_vs_anchor),
            'current_sacrifice_vs_anchor': float(pick_row.current_sacrifice_vs_anchor),
            'future_cost': float(pick_row.future_cost),
        },
        'anchor': {
            'team': anchor,
            'current_spread': float(anchor_row.current_spread),
            'calibrated_margin': float(anchor_row.calibrated_margin),
            'total_season_ev': float(anchor_row.total_season_ev),
        },
        'route': selected_route[[
            'week','team','opponent','raw_value_spread','calibrated_ev','value_source','game_id'
        ]].to_dict(orient='records'),
        'board': board.sort_values(['total_season_ev','current_spread'], ascending=[False,False]).to_dict(orient='records'),
    }
    return audit


def print_audit(audit: dict) -> None:
    print('=== LIVE MARGIN 2026 DECISION ===')
    print(f"snapshot_utc={audit['snapshot_utc']}")
    print(f"season={audit['season']} week={audit['week']} score={audit['cumulative_score']} used={audit['used_teams']}")
    print('data_quality=' + json.dumps(audit['data_quality'], sort_keys=True))
    print('policy=' + json.dumps(audit['policy'], sort_keys=True))
    print('pick=' + json.dumps(audit['pick'], sort_keys=True))
    print('anchor=' + json.dumps(audit['anchor'], sort_keys=True))

    board = pd.DataFrame(audit['board'])
    display_cols = [
        'team','opponent','current_spread','calibrated_margin','p_loss','p_win20',
        'future_cost','total_season_ev_delta_vs_anchor','current_sacrifice_vs_anchor','status','game_id'
    ]
    print('=== BOARD ===')
    print(board[display_cols].to_csv(index=False))

    route = pd.DataFrame(audit['route'])
    print('=== SELECTED PROVISIONAL REMAINING ROUTE ===')
    print(route.to_csv(index=False))

    print('=== AUDIT JSON ===')
    print(json.dumps(audit, sort_keys=True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', default=str(DEFAULT_STATE))
    ap.add_argument('--future-posted-mode', choices=['live','current_week_only'], default='live')
    args = ap.parse_args()
    state = load_state(Path(args.state))
    audit = run(state, future_posted_mode=args.future_posted_mode)
    print_audit(audit)


if __name__ == '__main__':
    main()
