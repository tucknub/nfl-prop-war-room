from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core


def fit_market_power_cfg(games_pi, target_season, target_week, *, window_periods, half_life, ridge, include_current):
    cutoff = games_pi[(games_pi.season.eq(target_season)) & (games_pi.week.eq(target_week))].period_index.max()
    upper = cutoff if include_current else cutoff - 1
    train = games_pi[(games_pi.period_index <= upper) & (games_pi.period_index >= upper-window_periods+1) & games_pi.spread_line.notna()].copy()
    train['home_canon'] = train.home_team.map(core.canon_team)
    train['away_canon'] = train.away_team.map(core.canon_team)
    teams = sorted(set(train.home_canon) | set(train.away_canon)); idx = {t:i for i,t in enumerate(teams)}
    X = np.zeros((len(train), len(teams)+1)); y = pd.to_numeric(train.spread_line, errors='coerce').to_numpy(float)
    weights = []
    for row_i, (_, r) in enumerate(train.iterrows()):
        X[row_i,idx[r.home_canon]] = 1; X[row_i,idx[r.away_canon]] = -1
        X[row_i,-1] = 0.0 if str(r.get('location','Home')).lower() != 'home' else 1.0
        age = float(upper-r.period_index); weights.append(0.5**(age/half_life))
    w = np.asarray(weights); XtW = X.T*w
    penalty = np.eye(X.shape[1])*ridge; penalty[-1,-1] = 0.05
    beta = np.linalg.solve(XtW@X+penalty, XtW@y)
    return {t:float(beta[i]) for t,i in idx.items()}, float(beta[-1])


def rolling_cfg(tg, gpi, season, cfg):
    d = tg[tg.season.eq(season)].copy(); weeks = sorted(int(x) for x in d.week.unique())
    used = set(); picked = []
    for current in weeks:
        ratings,hfa = fit_market_power_cfg(gpi, season, current, **cfg)
        remaining = [w for w in weeks if w >= current]
        rem = d[d.week.isin(remaining) & ~d.team.isin(used)].copy()
        def forecast(r):
            if int(r.week) == current:
                return r.market_expected_margin
            th = ratings.get(core.canon_team(r.team),0.0); to = ratings.get(core.canon_team(r.opponent),0.0)
            if str(r.location).lower() != 'home': adj = 0.0
            else: adj = hfa if bool(r.is_home) else -hfa
            return th-to+adj
        rem['rolling_value'] = rem.apply(forecast,axis=1)
        assignment = core.optimize(rem, season, 'rolling_value', weeks=remaining, eligible_teams=set(rem.team.unique()))
        pick = assignment.selections[assignment.selections.week.eq(current)].iloc[0].copy()
        picked.append(pick); used.add(str(pick.team))
    s = pd.DataFrame(picked).reset_index(drop=True); core.validate_selections(s,weeks)
    return float(s.actual_margin.sum())


def bootstrap_ci(values, n=100000, seed=42):
    values = np.asarray(values, dtype=float); rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n,len(values)), replace=True).mean(axis=1)
    return tuple(np.quantile(means,[0.025,0.975]))


def main():
    games = core.load_games(); tg = core.canonical_team_games(games); gpi = core.build_period_index(games)
    baseline = {s:core.greedy_biggest_favorite(tg,s).actual_score for s in core.SEASONS}
    configs = {
        'default': dict(window_periods=20,half_life=6.0,ridge=3.0,include_current=True),
        'strict_prior_only': dict(window_periods=20,half_life=6.0,ridge=3.0,include_current=False),
        'short_fast': dict(window_periods=12,half_life=4.0,ridge=3.0,include_current=True),
        'long_slow': dict(window_periods=32,half_life=8.0,ridge=3.0,include_current=True),
        'low_ridge': dict(window_periods=20,half_life=6.0,ridge=1.0,include_current=True),
        'high_ridge': dict(window_periods=20,half_life=6.0,ridge=6.0,include_current=True),
        'strict_short': dict(window_periods=12,half_life=4.0,ridge=3.0,include_current=False),
        'strict_long': dict(window_periods=32,half_life=8.0,ridge=3.0,include_current=False),
    }
    rows=[]
    for label,cfg in configs.items():
        scores={s:rolling_cfg(tg,gpi,s,cfg) for s in core.SEASONS}
        dif=np.array([scores[s]-baseline[s] for s in core.SEASONS],dtype=float)
        ci=bootstrap_ci(dif)
        no20=np.array([d for s,d in zip(core.SEASONS,dif) if s!=2020])
        rows.append(dict(config=label,mean=dif.mean(),median=np.median(dif),wins=int((dif>0).sum()),losses=int((dif<0).sum()),
                         worst=dif.min(),best=dif.max(),ci_low=ci[0],ci_high=ci[1],mean_ex_2020=no20.mean(),wins_ex_2020=int((no20>0).sum())))
    out=pd.DataFrame(rows).sort_values('config')
    print('=== SENSITIVITY ===')
    print(out.to_csv(index=False))

if __name__ == '__main__': main()
