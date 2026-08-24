from __future__ import annotations

import pandas as pd

import run_margin_research as core


def main() -> None:
    games = core.load_games()
    for c in ['season','week','spread_line','total_line','home_moneyline','away_moneyline']:
        if c in games.columns:
            games[c] = pd.to_numeric(games[c], errors='coerce')

    g = games[(games.season.eq(2026)) & games.game_type.eq('REG')].copy()
    if g.empty:
        raise RuntimeError('No 2026 regular-season schedule rows found.')

    weeks = sorted(int(x) for x in g.week.dropna().unique())
    print('=== 2026 DATA READINESS ===')
    print(f'games={len(g)} weeks={weeks} week_count={len(weeks)}')
    print(f'teams={len(set(g.home_team) | set(g.away_team))}')
    print(f'spread_games={int(g.spread_line.notna().sum())} total_games={int(g.total_line.notna().sum())}')
    if 'home_moneyline' in g:
        print(f'moneyline_games={int((g.home_moneyline.notna() & g.away_moneyline.notna()).sum())}')
    print(f'score_games={int((g.home_score.notna() & g.away_score.notna()).sum())}')

    coverage = g.groupby('week', as_index=False).agg(
        games=('game_id','count'),
        spreads=('spread_line', lambda x: int(x.notna().sum())),
        totals=('total_line', lambda x: int(x.notna().sum())),
        first_date=('gameday','min'),
        last_date=('gameday','max'),
    )
    print('=== COVERAGE BY WEEK ===')
    print(coverage.to_csv(index=False))

    w1 = g[g.week.eq(1)].copy()
    cols = [c for c in [
        'game_id','gameday','gametime','away_team','home_team','spread_line','total_line',
        'away_moneyline','home_moneyline','location','roof','surface'
    ] if c in w1.columns]
    print('=== WEEK 1 CURRENT FEED ===')
    print(w1[cols].sort_values(['gameday','gametime','game_id']).to_csv(index=False))

    missing = g[g.spread_line.isna()][['week','game_id','away_team','home_team','gameday']].copy()
    print('=== GAMES WITHOUT CURRENT SPREAD ===')
    print(missing.sort_values(['week','game_id']).to_csv(index=False))


if __name__ == '__main__':
    main()
