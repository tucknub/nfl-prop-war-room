from __future__ import annotations

import copy

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_live_margin_2026 as live

REPLAY_SEASONS = list(range(2021, 2026))


def build_historical_team_values(games: pd.DataFrame, season: int, current_week: int) -> tuple[pd.DataFrame, dict]:
    """Recreate a live decision snapshot with eventual future-week lines hidden."""
    g = live.prepare_games(games, season)
    d = g.copy()
    d['market_available'] = d.spread_line.notna() & d.week.le(current_week)

    # A historical replay may use all lines through the current decision week, never later weeks.
    ratings, hfa = live.fit_snapshot_ratings(d)

    def home_inferred(r) -> float:
        adj = 0.0 if str(r.location).lower() != 'home' else hfa
        return float(ratings.get(str(r.home_team), 0.0) - ratings.get(str(r.away_team), 0.0) + adj)

    d['inferred_home_spread'] = d.apply(home_inferred, axis=1)
    d['snapshot_home_spread'] = np.where(d.market_available, d.spread_line, d.inferred_home_spread)
    d['home_value_source'] = np.where(
        d.week.eq(current_week) & d.market_available,
        'CURRENT_MARKET',
        np.where(d.market_available, 'PAST_MARKET', 'MARKET_RATING_INFERRED'),
    )

    home = pd.DataFrame({
        'season': season,
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
        'season': season,
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
    return rows, {
        'ratings': ratings,
        'hfa': hfa,
        'posted_games_available': int(d.market_available.sum()),
    }


def actual_margin(games: pd.DataFrame, season: int, game_id: str, team: str) -> float:
    g = games[(games.season == season) & games.game_type.eq('REG') & games.game_id.astype(str).eq(str(game_id))]
    if len(g) != 1:
        raise AssertionError(f'Expected one game row for {season=} {game_id=}, found {len(g)}')
    r = g.iloc[0]
    hs = float(r.home_score)
    aws = float(r.away_score)
    if team == str(r.home_team):
        return hs - aws
    if team == str(r.away_team):
        return aws - hs
    raise AssertionError(f'{team=} not in {game_id=}')


def replay_season(games: pd.DataFrame, favorite_history: pd.DataFrame, season: int) -> dict:
    reg = games[(games.season == season) & games.game_type.eq('REG')].copy()
    weeks = sorted(int(x) for x in reg.week.dropna().unique())
    expected_weeks = list(range(1, max(weeks) + 1))
    if weeks != expected_weeks:
        raise AssertionError(f'Non-contiguous weeks for {season}: {weeks}')

    used: set[str] = set()
    picks: list[dict] = []
    running_score = 0.0
    train_fav = favorite_history[favorite_history.season < season].copy()
    if train_fav.empty:
        raise AssertionError(f'No pre-{season} calibration history')

    for current_week in weeks:
        rows, snapshot = build_historical_team_values(games, season, current_week)
        rows = live.add_calibration(rows, train_fav)
        rows = rows[rows.week.ge(current_week) & ~rows.team.isin(used)].copy()

        # Leakage invariant: every future game must be inferred, never use its eventual historical spread.
        future = rows[rows.week.gt(current_week)]
        if not future.empty and not future.value_source.eq('MARKET_RATING_INFERRED').all():
            bad = future[~future.value_source.eq('MARKET_RATING_INFERRED')][['week','game_id','team','value_source']]
            raise AssertionError(f'Future-line leakage in {season} W{current_week}:\n{bad.head()}')

        current = rows[rows.week.eq(current_week)]
        if current.empty or not current.value_source.eq('CURRENT_MARKET').all():
            raise AssertionError(f'Current market incomplete/mislabeled in {season} W{current_week}')

        board, routes = live.score_current_candidates(rows, current_week, used)
        pick, reason = live.choose_expected_points_pick(board, current_week, live.DEFAULT_CAP, live.EV_THRESHOLD)
        anchor = str(board.anchor_team.iloc[0])
        pick_row = board[board.team.eq(pick)].iloc[0]
        route = routes[pick]

        # Core decision invariants.
        if pick in used:
            raise AssertionError(f'Reused team {pick} in {season} W{current_week}')
        if str(route.iloc[0].team) != pick or int(route.iloc[0].week) != current_week:
            raise AssertionError('Route does not begin with current pick')
        if route.team.duplicated().any():
            raise AssertionError(f'Route duplicates a team in {season} W{current_week}')
        if sorted(route.week.astype(int).tolist()) != list(range(current_week, max(weeks) + 1)):
            raise AssertionError(f'Route does not cover every remaining week in {season} W{current_week}')
        if current_week <= 3:
            if pick != anchor or reason != 'WEEKS_1_TO_3_BIGGEST_FAVORITE_DEFAULT':
                raise AssertionError(f'Weeks 1-3 anchor invariant failed in {season} W{current_week}')
        elif pick != anchor:
            if float(pick_row.current_sacrifice_vs_anchor) > live.DEFAULT_CAP + 1e-12:
                raise AssertionError(f'Cap violation in {season} W{current_week}')
            if float(pick_row.total_season_ev_delta_vs_anchor) < live.EV_THRESHOLD - 1e-12:
                raise AssertionError(f'EV threshold violation in {season} W{current_week}')
            if reason != 'CAP3_EV_DEVIATION':
                raise AssertionError(f'Unexpected deviation reason in {season} W{current_week}: {reason}')

        margin = actual_margin(games, season, str(pick_row.game_id), pick)
        running_score += margin
        picks.append({
            'week': current_week,
            'team': pick,
            'anchor': anchor,
            'reason': reason,
            'game_id': str(pick_row.game_id),
            'market_spread': float(pick_row.current_spread),
            'actual_margin': float(margin),
            'running_score': float(running_score),
            'current_sacrifice': float(pick_row.current_sacrifice_vs_anchor),
            'ev_delta_vs_anchor': float(pick_row.total_season_ev_delta_vs_anchor),
            'posted_games_available': int(snapshot['posted_games_available']),
        })
        used.add(pick)

        # State-advancement invariants after revealing exactly this week's result.
        if len(used) != current_week:
            raise AssertionError(f'Used-team count mismatch after {season} W{current_week}')
        if len({p['team'] for p in picks}) != len(picks):
            raise AssertionError(f'Duplicate historical pick after {season} W{current_week}')
        if abs(sum(float(p['actual_margin']) for p in picks) - running_score) > 1e-9:
            raise AssertionError(f'Running-score mismatch after {season} W{current_week}')

    if len(picks) != len(weeks) or len(used) != len(weeks):
        raise AssertionError(f'Full-season selection count mismatch for {season}')

    return {
        'season': season,
        'score': float(running_score),
        'selected_market_sum': float(sum(p['market_spread'] for p in picks)),
        'deviations': int(sum(p['team'] != p['anchor'] for p in picks)),
        'max_sacrifice': float(max(p['current_sacrifice'] for p in picks)),
        'teams': [p['team'] for p in picks],
        'picks': picks,
    }


def validate_live_state_contract() -> None:
    state = live.load_state(live.DEFAULT_STATE)
    live.validate_state(state)

    # Duplicate inventory must fail.
    bad = copy.deepcopy(state)
    bad['current_week'] = 3
    bad['completed_week'] = 2
    bad['used_teams'] = ['LAC', 'LAC']
    bad['weekly_results'] = [
        {'team': 'LAC', 'actual_margin': 1.0},
        {'team': 'LAC', 'actual_margin': 2.0},
    ]
    bad['cumulative_score'] = 3.0
    try:
        live.validate_state(bad)
        raise AssertionError('Duplicate used teams were not rejected')
    except AssertionError as exc:
        if 'duplicates' not in str(exc):
            raise

    # Score/history mismatch must fail.
    bad2 = copy.deepcopy(state)
    bad2['current_week'] = 2
    bad2['completed_week'] = 1
    bad2['used_teams'] = ['LAC']
    bad2['weekly_results'] = [{'team': 'LAC', 'actual_margin': 10.0}]
    bad2['cumulative_score'] = 9.0
    try:
        live.validate_state(bad2)
        raise AssertionError('Mismatched cumulative score was not rejected')
    except AssertionError as exc:
        if 'cumulative_score' not in str(exc):
            raise


def main() -> None:
    validate_live_state_contract()

    games = core.load_games()
    for c in ['season','week','spread_line','total_line','home_score','away_score']:
        if c in games.columns:
            games[c] = pd.to_numeric(games[c], errors='coerce')
    favorite_history = dist.favorite_games(games)

    results = []
    for season in REPLAY_SEASONS:
        result = replay_season(games, favorite_history, season)
        results.append(result)
        print(
            f"REPLAY {season}: score={result['score']:.1f} market={result['selected_market_sum']:.1f} "
            f"deviations={result['deviations']} max_sacrifice={result['max_sacrifice']:.1f} "
            f"teams={'/'.join(result['teams'])}"
        )

    # Determinism invariant: rerunning the exact same frozen historical season produces the same path.
    repeat = replay_season(games, favorite_history, 2025)
    first_2025 = next(x for x in results if x['season'] == 2025)
    if repeat['teams'] != first_2025['teams']:
        raise AssertionError('2025 replay path is not deterministic')
    if abs(repeat['score'] - first_2025['score']) > 1e-12:
        raise AssertionError('2025 replay score is not deterministic')

    summary = pd.DataFrame([
        {
            'season': r['season'],
            'score': r['score'],
            'selected_market_sum': r['selected_market_sum'],
            'deviations': r['deviations'],
            'max_sacrifice': r['max_sacrifice'],
        }
        for r in results
    ])
    print('=== REPLAY SUMMARY ===')
    print(summary.to_csv(index=False))
    print('=== INVARIANTS ===')
    print('live_state_validation=PASS')
    print('no_future_closing_line_leakage=PASS')
    print('one_pick_per_week=PASS')
    print('one_use_per_team=PASS')
    print('weeks_1_to_3_anchor=PASS')
    print('cap3_and_ev_threshold_on_deviations=PASS')
    print('state_advancement_and_score_reconciliation=PASS')
    print('deterministic_2025_replay=PASS')


if __name__ == '__main__':
    main()
