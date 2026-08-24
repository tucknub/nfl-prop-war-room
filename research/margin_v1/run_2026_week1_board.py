from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_empirical_sampler as empirical

SEASON = 2026
WEEK = 1
BANDWIDTH = 3.0


def current_favorite_rows(games: pd.DataFrame) -> pd.DataFrame:
    g = games[(games.season.eq(SEASON)) & games.game_type.eq('REG') & games.week.eq(WEEK)].copy()
    for c in ['spread_line','total_line','home_moneyline','away_moneyline']:
        if c in g:
            g[c] = pd.to_numeric(g[c], errors='coerce')
    g = g.dropna(subset=['spread_line']).copy()
    home_fav = g.spread_line >= 0
    out = pd.DataFrame({
        'game_id': g.game_id.astype(str),
        'gameday': g.gameday,
        'gametime': g.gametime,
        'favorite': np.where(home_fav, g.home_team, g.away_team),
        'underdog': np.where(home_fav, g.away_team, g.home_team),
        'favorite_spread': g.spread_line.abs().astype(float),
        'total_line': g.total_line,
        'favorite_moneyline': np.where(home_fav, g.home_moneyline, g.away_moneyline),
        'favorite_home': home_fav.astype(int),
        'location': g.location,
    })
    return out.reset_index(drop=True)


def main() -> None:
    games = core.load_games()
    for c in ['season','week']:
        games[c] = pd.to_numeric(games[c], errors='coerce')

    live = current_favorite_rows(games)
    if len(live) != 16:
        raise AssertionError(f'Expected 16 Week-1 priced games, got {len(live)}')

    historical = dist.favorite_games(games)
    historical = historical[historical.season <= 2025].copy()
    probs = empirical.weighted_probs(historical, live, BANDWIDTH, 'residual_centered')
    board = live.join(probs)
    board = board.sort_values(
        ['favorite_spread','expected_margin','favorite'], ascending=[False,False,True], kind='stable'
    ).reset_index(drop=True)
    board['rank'] = np.arange(1, len(board) + 1)
    board['status'] = np.where(board['rank'].eq(1), 'PICK/ANCHOR', np.where(board['rank'].le(3), 'PIVOT', 'WATCH'))

    # Week 1 V1 rule is market-first. No future-value penalty is applied here because
    # the validated in-season style layer does not yet exist for the 2026 season.
    board['future_cost_status'] = 'PRESEASON ROADMAP ONLY'

    print('=== 2026 WEEK 1 LIVE MARGIN BOARD ===')
    print(f'as_of_utc={datetime.now(timezone.utc).isoformat()} bandwidth={BANDWIDTH}')
    print('V1_WEEK1_RULE=Biggest current favorite is the default; future route is provisional.')
    cols = [
        'rank','favorite','underdog','favorite_spread','expected_margin','p_loss',
        'p_win10','p_win20','p_win30','favorite_moneyline','total_line','status',
        'gameday','gametime','game_id'
    ]
    print(board[cols].to_csv(index=False))

    top = board.iloc[0]
    second = board.iloc[1]
    third = board.iloc[2]
    print('=== TOP THREE ===')
    for label, r in [('PICK', top), ('PIVOT_1', second), ('PIVOT_2', third)]:
        print(
            f'{label}={r.favorite} vs {r.underdog} spread={r.favorite_spread:.1f} '
            f'calibrated_margin={r.expected_margin:.2f} p_loss={r.p_loss:.4f} '
            f'p20={r.p_win20:.4f} p30={r.p_win30:.4f}'
        )


if __name__ == '__main__':
    main()
