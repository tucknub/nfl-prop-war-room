from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

import run_margin_research as core

SEASON = 2026
WEEKS = list(range(1, 7))
FORCED_WEEK1 = ['LAC', 'JAX', 'DET']


def team_rows(games: pd.DataFrame) -> pd.DataFrame:
    g = games[(games.season.eq(SEASON)) & games.game_type.eq('REG') & games.week.isin(WEEKS)].copy()
    for c in ['week','spread_line','total_line']:
        g[c] = pd.to_numeric(g[c], errors='coerce')
    g = g.dropna(subset=['spread_line']).copy()
    home = pd.DataFrame({
        'season': SEASON,
        'week': g.week.astype(int),
        'game_id': g.game_id.astype(str),
        'team': g.home_team.astype(str),
        'opponent': g.away_team.astype(str),
        'is_home': True,
        'market_expected_margin': g.spread_line.astype(float),
        'total_line': g.total_line.astype(float),
    })
    away = pd.DataFrame({
        'season': SEASON,
        'week': g.week.astype(int),
        'game_id': g.game_id.astype(str),
        'team': g.away_team.astype(str),
        'opponent': g.home_team.astype(str),
        'is_home': False,
        'market_expected_margin': -g.spread_line.astype(float),
        'total_line': g.total_line.astype(float),
    })
    return pd.concat([home, away], ignore_index=True)


def validate(sel: pd.DataFrame, weeks: list[int]) -> None:
    if sorted(sel.week.astype(int).tolist()) != weeks:
        raise AssertionError('Bad week coverage')
    if sel.team.duplicated().any():
        raise AssertionError('Team reuse')


def exact_assignment(rows: pd.DataFrame, weeks: list[int], excluded: set[str] | None = None) -> tuple[pd.DataFrame, float]:
    excluded = excluded or set()
    d = rows[rows.week.isin(weeks) & ~rows.team.isin(excluded)].copy()
    teams = sorted(set(d.team))
    wi = {w:i for i,w in enumerate(weeks)}
    ti = {t:j for j,t in enumerate(teams)}
    INF = 1e8
    cost = np.full((len(weeks), len(teams)), INF)
    lookup = {}
    for _, r in d.iterrows():
        w = int(r.week); t = str(r.team)
        if w not in wi:
            continue
        v = float(r.market_expected_margin)
        cost[wi[w],ti[t]] = -v + ti[t] * 1e-9
        lookup[(w,t)] = r
    rr, cc = linear_sum_assignment(cost)
    if len(rr) != len(weeks) or np.any(cost[rr,cc] >= INF/2):
        raise RuntimeError('No feasible assignment')
    picked = [lookup[(weeks[i], teams[j])] for i,j in sorted(zip(rr,cc))]
    s = pd.DataFrame(picked).reset_index(drop=True)
    validate(s, weeks)
    return s, float(s.market_expected_margin.sum())


def greedy(rows: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    used = set(); picks = []
    for week in WEEKS:
        c = rows[rows.week.eq(week) & ~rows.team.isin(used)].copy()
        c = c.sort_values(['market_expected_margin','total_line','team'], ascending=[False,False,True], kind='stable')
        r = c.iloc[0].copy()
        picks.append(r); used.add(str(r.team))
    s = pd.DataFrame(picks).reset_index(drop=True)
    validate(s, WEEKS)
    return s, float(s.market_expected_margin.sum())


def forced_week1_path(rows: pd.DataFrame, team: str) -> tuple[pd.DataFrame, float]:
    w1 = rows[(rows.week.eq(1)) & rows.team.eq(team)].copy()
    if w1.empty:
        raise RuntimeError(f'No Week-1 row for {team}')
    first = w1.iloc[0].copy()
    future, future_obj = exact_assignment(rows, list(range(2,7)), excluded={team})
    s = pd.concat([pd.DataFrame([first]), future], ignore_index=True)
    validate(s, WEEKS)
    return s, float(first.market_expected_margin + future_obj)


def route_text(s: pd.DataFrame) -> str:
    return ' | '.join(f'W{int(r.week)} {r.team} {float(r.market_expected_margin):+.1f} vs {r.opponent}' for _,r in s.iterrows())


def main() -> None:
    games = core.load_games()
    for c in ['season','week']:
        games[c] = pd.to_numeric(games[c], errors='coerce')
    rows = team_rows(games)
    counts = rows.groupby('week').game_id.nunique()
    if any(int(counts.get(w,0)) == 0 for w in WEEKS):
        raise AssertionError('Missing Week 1-6 market coverage')

    greedy_sel, greedy_obj = greedy(rows)
    opt_sel, opt_obj = exact_assignment(rows, WEEKS)

    print('=== 2026 SIX-WEEK LIVE MARKET ROADMAP ===')
    print('Uses only currently populated Week 1-6 market spreads. No Week 7-18 forecast is used.')
    print(f'GREEDY_OBJECTIVE={greedy_obj:.1f}')
    print(f'OPTIMAL_OBJECTIVE={opt_obj:.1f}')
    print(f'ALLOCATION_EDGE={opt_obj-greedy_obj:.1f}')
    print('GREEDY_ROUTE=' + route_text(greedy_sel))
    print('OPTIMAL_ROUTE=' + route_text(opt_sel))

    print('=== FORCED WEEK-1 PATHS ===')
    results = []
    for team in FORCED_WEEK1:
        s, obj = forced_week1_path(rows, team)
        results.append({
            'week1_team': team,
            'week1_spread': float(s.iloc[0].market_expected_margin),
            'six_week_objective': obj,
            'gap_to_unrestricted_optimal': obj - opt_obj,
            'gap_to_lac': np.nan,
            'route': route_text(s),
        })
    d = pd.DataFrame(results)
    lac_obj = float(d.loc[d.week1_team.eq('LAC'),'six_week_objective'].iloc[0])
    d['gap_to_lac'] = d.six_week_objective - lac_obj
    print(d.to_csv(index=False))

    print('=== WEEK-BY-WEEK TOP FIVE CURRENT MARKET FAVORITES ===')
    for week in WEEKS:
        c = rows[rows.week.eq(week)].sort_values(['market_expected_margin','team'], ascending=[False,True]).head(5)
        print(f'WEEK={week}')
        print(c[['team','opponent','market_expected_margin','total_line','game_id']].to_csv(index=False))


if __name__ == '__main__':
    main()
