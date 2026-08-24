from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.model_selection import KFold

import run_margin_research as core

SEASON = 2026
RIDGE = 3.0
SEED = 20260823


def fit_market_ratings(g: pd.DataFrame, ridge: float = RIDGE):
    d = g[g.spread_line.notna()].copy()
    teams = sorted(set(d.home_team.astype(str)) | set(d.away_team.astype(str)))
    idx = {t:i for i,t in enumerate(teams)}
    X = np.zeros((len(d), len(teams) + 1))
    y = d.spread_line.to_numpy(float)
    for i, (_, r) in enumerate(d.iterrows()):
        X[i, idx[str(r.home_team)]] = 1.0
        X[i, idx[str(r.away_team)]] = -1.0
        X[i, -1] = 0.0 if str(r.location).lower() != 'home' else 1.0
    penalty = np.eye(X.shape[1]) * ridge
    penalty[-1,-1] = 0.05
    beta = np.linalg.solve(X.T @ X + penalty, X.T @ y)
    ratings = {t: float(beta[idx[t]]) for t in teams}
    hfa = float(beta[-1])
    return ratings, hfa


def predict_home(r, ratings, hfa):
    adj = 0.0 if str(r.location).lower() != 'home' else hfa
    return float(ratings[str(r.home_team)] - ratings[str(r.away_team)] + adj)


def crossval_mae(g: pd.DataFrame) -> float:
    d = g[g.spread_line.notna()].copy().reset_index(drop=True)
    kf = KFold(n_splits=5, shuffle=True, random_state=SEED)
    errors = []
    for train_i, test_i in kf.split(d):
        train = d.iloc[train_i].copy(); test = d.iloc[test_i].copy()
        ratings, hfa = fit_market_ratings(train)
        for _, r in test.iterrows():
            # All teams have broad look-ahead coverage in this dataset; fall back to zero only defensively.
            pred = float(ratings.get(str(r.home_team), 0.0) - ratings.get(str(r.away_team), 0.0) + (0.0 if str(r.location).lower() != 'home' else hfa))
            errors.append(abs(pred - float(r.spread_line)))
    return float(np.mean(errors))


def team_rows(g: pd.DataFrame, ratings, hfa) -> pd.DataFrame:
    d = g.copy()
    d['pred_home_spread'] = d.apply(lambda r: predict_home(r, ratings, hfa), axis=1)
    d['roadmap_home_spread'] = np.where(d.spread_line.notna(), d.spread_line, d.pred_home_spread)
    d['value_source'] = np.where(d.spread_line.notna(), 'POSTED_MARKET', 'MARKET_RATING_INFERRED')
    home = pd.DataFrame({
        'season': SEASON, 'week': d.week.astype(int), 'game_id': d.game_id.astype(str),
        'team': d.home_team.astype(str), 'opponent': d.away_team.astype(str), 'is_home': True,
        'roadmap_spread': d.roadmap_home_spread.astype(float), 'value_source': d.value_source,
        'posted_spread': d.spread_line,
    })
    away = pd.DataFrame({
        'season': SEASON, 'week': d.week.astype(int), 'game_id': d.game_id.astype(str),
        'team': d.away_team.astype(str), 'opponent': d.home_team.astype(str), 'is_home': False,
        'roadmap_spread': -d.roadmap_home_spread.astype(float), 'value_source': d.value_source,
        'posted_spread': np.where(d.spread_line.notna(), -d.spread_line, np.nan),
    })
    return pd.concat([home, away], ignore_index=True)


def exact_assignment(rows: pd.DataFrame, weeks: list[int], excluded: set[str] | None = None):
    excluded = excluded or set()
    d = rows[rows.week.isin(weeks) & ~rows.team.isin(excluded)].copy()
    teams = sorted(set(d.team))
    wi = {w:i for i,w in enumerate(weeks)}; ti = {t:j for j,t in enumerate(teams)}
    INF = 1e8
    cost = np.full((len(weeks), len(teams)), INF)
    lookup = {}
    for _, r in d.iterrows():
        w = int(r.week); t = str(r.team)
        if w not in wi: continue
        cost[wi[w], ti[t]] = -float(r.roadmap_spread) + ti[t] * 1e-9
        lookup[(w,t)] = r
    rr, cc = linear_sum_assignment(cost)
    if len(rr) != len(weeks) or np.any(cost[rr,cc] >= INF/2):
        raise RuntimeError('No feasible full-season assignment')
    picked = [lookup[(weeks[i], teams[j])] for i,j in sorted(zip(rr,cc))]
    s = pd.DataFrame(picked).reset_index(drop=True)
    if s.team.duplicated().any() or sorted(s.week.tolist()) != weeks:
        raise AssertionError('Invalid roadmap assignment')
    return s, float(s.roadmap_spread.sum())


def forced_week1(rows: pd.DataFrame, team: str):
    first = rows[(rows.week.eq(1)) & rows.team.eq(team)].iloc[0].copy()
    future, obj = exact_assignment(rows, list(range(2,19)), excluded={team})
    s = pd.concat([pd.DataFrame([first]), future], ignore_index=True)
    return s, float(first.roadmap_spread + obj)


def main() -> None:
    games = core.load_games()
    for c in ['season','week','spread_line']:
        games[c] = pd.to_numeric(games[c], errors='coerce')
    g = games[(games.season.eq(SEASON)) & games.game_type.eq('REG')].copy()
    if len(g) != 272:
        raise AssertionError(f'Expected 272 games, got {len(g)}')

    ratings, hfa = fit_market_ratings(g)
    cv = crossval_mae(g)
    rows = team_rows(g, ratings, hfa)
    route, objective = exact_assignment(rows, list(range(1,19)))

    print('=== 2026 FULL PRESEASON ROADMAP — PLANNING ONLY ===')
    print(f'posted_market_games={int(g.spread_line.notna().sum())} inferred_games={int(g.spread_line.isna().sum())}')
    print(f'implied_hfa={hfa:.3f} five_fold_current_line_reconstruction_mae={cv:.3f}')
    print(f'roadmap_objective_raw_spread_sum={objective:.2f}')
    print(f'route_posted_slots={int(route.value_source.eq("POSTED_MARKET").sum())} route_inferred_slots={int(route.value_source.eq("MARKET_RATING_INFERRED").sum())}')
    print('=== OPTIMAL PROVISIONAL ROUTE ===')
    print(route[['week','team','opponent','roadmap_spread','value_source','game_id']].to_csv(index=False))

    print('=== FORCED WEEK 1 FULL-ROADMAP COMPARISON ===')
    comp = []
    for team in ['LAC','JAX','DET','PHI']:
        s, obj = forced_week1(rows, team)
        comp.append({
            'week1_team': team,
            'week1_spread': float(s.iloc[0].roadmap_spread),
            'full_roadmap_objective': obj,
            'gap_to_unrestricted': obj - objective,
            'posted_slots': int(s.value_source.eq('POSTED_MARKET').sum()),
            'inferred_slots': int(s.value_source.eq('MARKET_RATING_INFERRED').sum()),
        })
    print(pd.DataFrame(comp).to_csv(index=False))

    print('=== MARKET-IMPLIED TEAM RATINGS ===')
    rating_df = pd.DataFrame([{'team':t,'rating':v} for t,v in ratings.items()]).sort_values(['rating','team'], ascending=[False,True])
    print(rating_df.to_csv(index=False))

    print('=== BEST ROADMAP SPOT BY TEAM ===')
    best = rows.sort_values(['team','roadmap_spread'], ascending=[True,False]).groupby('team', as_index=False).first()
    best = best.sort_values(['roadmap_spread','team'], ascending=[False,True])
    print(best[['team','week','opponent','roadmap_spread','value_source','game_id']].to_csv(index=False))


if __name__ == '__main__':
    main()
