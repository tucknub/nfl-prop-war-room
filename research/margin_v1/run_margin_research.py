from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

DATA_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
SEASONS = list(range(2006, 2026))
ALIASES = {'SD':'LAC','STL':'LA','OAK':'LV'}


def canon_team(t: str) -> str:
    t = str(t)
    return ALIASES.get(t, t)


def load_games(source: str | None = None) -> pd.DataFrame:
    src = source or DATA_URL
    return pd.read_csv(src, low_memory=False)


def canonical_team_games(games: pd.DataFrame) -> pd.DataFrame:
    g = games[games['game_type'].eq('REG')].copy()
    g = g[g['season'].between(min(SEASONS), max(SEASONS))].copy()
    for c in ['season','week','home_score','away_score','spread_line','total_line']:
        g[c] = pd.to_numeric(g[c], errors='coerce')
    location = g['location'].fillna('Home') if 'location' in g else pd.Series('Home', index=g.index)
    home = pd.DataFrame({
        'season':g.season.astype(int), 'week':g.week.astype(int), 'game_id':g.game_id,
        'team':g.home_team, 'opponent':g.away_team, 'is_home':True, 'location':location,
        'points_for':g.home_score, 'points_against':g.away_score,
        'actual_margin':g.home_score-g.away_score,
        'market_expected_margin':g.spread_line, 'total_line':g.total_line,
    })
    away = pd.DataFrame({
        'season':g.season.astype(int), 'week':g.week.astype(int), 'game_id':g.game_id,
        'team':g.away_team, 'opponent':g.home_team, 'is_home':False, 'location':location,
        'points_for':g.away_score, 'points_against':g.home_score,
        'actual_margin':g.away_score-g.home_score,
        'market_expected_margin':-g.spread_line, 'total_line':g.total_line,
    })
    return pd.concat([home,away], ignore_index=True).sort_values(['season','week','game_id','team']).reset_index(drop=True)


def validate_season_data(tg: pd.DataFrame, season: int) -> dict:
    d = tg[tg.season.eq(season)]
    weeks = sorted(d.week.unique())
    expected_weeks = list(range(1, 19 if season >= 2021 else 18))
    missing_weeks = sorted(set(expected_weeks)-set(weeks))
    games_per_week = d.groupby('week').size()/2
    return {
        'season':season,'weeks':len(weeks),'expected_weeks':len(expected_weeks),
        'missing_weeks':','.join(map(str,missing_weeks)),
        'missing_market_team_rows':int(d.market_expected_margin.isna().sum()),
        'missing_score_team_rows':int(d.actual_margin.isna().sum()),
        'min_games_week':float(games_per_week.min()) if len(games_per_week) else np.nan,
        'max_games_week':float(games_per_week.max()) if len(games_per_week) else np.nan,
    }


@dataclass
class Result:
    selections: pd.DataFrame
    actual_score: float
    objective_value: float


def validate_selections(sel: pd.DataFrame, expected_weeks: list[int]):
    if sorted(sel.week.astype(int).tolist()) != expected_weeks:
        raise AssertionError(f'Bad week coverage: got {sel.week.tolist()} expected {expected_weeks}')
    if sel.team.duplicated().any():
        raise AssertionError(f'Team reused: {sel.loc[sel.team.duplicated(keep=False),"team"].tolist()}')


def greedy_biggest_favorite(tg: pd.DataFrame, season: int) -> Result:
    d=tg[tg.season.eq(season)].copy()
    weeks=sorted(int(x) for x in d.week.unique())
    used=set(); rows=[]
    for w in weeks:
        c=d[d.week.eq(w) & ~d.team.isin(used) & d.market_expected_margin.notna()].copy()
        if c.empty: raise RuntimeError(f'No eligible market row {season} W{w}')
        c=c.sort_values(['market_expected_margin','total_line','team'], ascending=[False,False,True], kind='stable')
        r=c.iloc[0]; rows.append(r); used.add(str(r.team))
    s=pd.DataFrame(rows).reset_index(drop=True); validate_selections(s,weeks)
    return Result(s,float(s.actual_margin.sum()),float(s.market_expected_margin.sum()))


def optimize(tg: pd.DataFrame, season: int, value_col: str, *, weeks=None, eligible_teams=None) -> Result:
    d=tg[tg.season.eq(season)].copy()
    weeks=weeks or sorted(int(x) for x in d.week.unique())
    teams=sorted(eligible_teams or set(d.team.unique()))
    wi={w:i for i,w in enumerate(weeks)}; ti={t:j for j,t in enumerate(teams)}
    INF=1e8; cost=np.full((len(weeks),len(teams)),INF); rows={}
    for _,r in d.iterrows():
        w=int(r.week); t=str(r.team)
        if w not in wi or t not in ti: continue
        val=pd.to_numeric(r.get(value_col),errors='coerce')
        if pd.isna(val): continue
        cost[wi[w],ti[t]]=-float(val)+ti[t]*1e-9
        rows[(w,t)]=r
    rr,cc=linear_sum_assignment(cost)
    if len(rr)!=len(weeks) or np.any(cost[rr,cc] >= INF/2):
        raise RuntimeError(f'No feasible assignment {season} {value_col}')
    chosen=[rows[(weeks[i],teams[j])] for i,j in sorted(zip(rr,cc))]
    s=pd.DataFrame(chosen).reset_index(drop=True); validate_selections(s,weeks)
    return Result(s,float(s.actual_margin.sum()),float(pd.to_numeric(s[value_col], errors='coerce').sum()))


def build_period_index(games: pd.DataFrame) -> pd.DataFrame:
    g=games.copy()
    g['season']=pd.to_numeric(g.season,errors='coerce').astype('Int64')
    g['week']=pd.to_numeric(g.week,errors='coerce').astype('Int64')
    periods=g[['season','week']].dropna().drop_duplicates().sort_values(['season','week']).reset_index(drop=True)
    periods['period_index']=np.arange(len(periods))
    return g.merge(periods,on=['season','week'],how='left')


def fit_market_power(games_pi: pd.DataFrame, target_season: int, target_week: int, *, window_periods=20, half_life=6.0, ridge=3.0):
    cutoff = games_pi[(games_pi.season.eq(target_season)) & (games_pi.week.eq(target_week))].period_index.max()
    if pd.isna(cutoff): raise RuntimeError(f'No cutoff {target_season} W{target_week}')
    train=games_pi[(games_pi.period_index <= cutoff) & (games_pi.period_index >= cutoff-window_periods+1) & games_pi.spread_line.notna()].copy()
    train['home_canon']=train.home_team.map(canon_team); train['away_canon']=train.away_team.map(canon_team)
    teams=sorted(set(train.home_canon)|set(train.away_canon)); idx={t:i for i,t in enumerate(teams)}
    X=np.zeros((len(train),len(teams)+1)); y=pd.to_numeric(train.spread_line,errors='coerce').to_numpy(float)
    weights=[]
    for row_i,(_,r) in enumerate(train.iterrows()):
        X[row_i,idx[r.home_canon]]=1; X[row_i,idx[r.away_canon]]=-1
        neutral = str(r.get('location','Home')).lower() != 'home'
        X[row_i,-1]=0.0 if neutral else 1.0
        age=float(cutoff-r.period_index); weights.append(0.5**(age/half_life))
    w=np.asarray(weights); XtW=X.T*w
    penalty=np.eye(X.shape[1])*ridge; penalty[-1,-1]=0.05
    beta=np.linalg.solve(XtW@X+penalty, XtW@y)
    return {t:float(beta[i]) for t,i in idx.items()}, float(beta[-1])


def rolling_allocator(tg: pd.DataFrame, games_pi: pd.DataFrame, season: int) -> Result:
    d=tg[tg.season.eq(season)].copy(); weeks=sorted(int(x) for x in d.week.unique())
    used=set(); picked=[]; total_obj=0.0
    for current in weeks:
        ratings,hfa=fit_market_power(games_pi,season,current)
        remaining_weeks=[w for w in weeks if w>=current]
        rem=d[d.week.isin(remaining_weeks) & ~d.team.isin(used)].copy()
        def forecast(r):
            if int(r.week)==current:
                return r.market_expected_margin
            th=ratings.get(canon_team(r.team),0.0); to=ratings.get(canon_team(r.opponent),0.0)
            loc_home = bool(r.is_home) and str(r.location).lower()=='home'
            loc_away = (not bool(r.is_home)) and str(r.location).lower()=='home'
            adj = hfa if loc_home else (-hfa if loc_away else 0.0)
            return th-to+adj
        rem['rolling_value']=rem.apply(forecast,axis=1)
        assignment=optimize(rem,season,'rolling_value',weeks=remaining_weeks,eligible_teams=set(rem.team.unique()))
        pick=assignment.selections[assignment.selections.week.eq(current)].iloc[0].copy()
        pick['decision_value']=float(pick['rolling_value']); pick['fitted_hfa']=hfa
        picked.append(pick); used.add(str(pick.team)); total_obj += float(pick['decision_value'])
    s=pd.DataFrame(picked).reset_index(drop=True); validate_selections(s,weeks)
    return Result(s,float(s.actual_margin.sum()),total_obj)


def run(games: pd.DataFrame):
    tg=canonical_team_games(games); gpi=build_period_index(games)
    quality=pd.DataFrame([validate_season_data(tg,s) for s in SEASONS])
    print('=== DATA QUALITY ==='); print(quality.to_csv(index=False))
    bad=quality[(quality.expected_weeks!=quality.weeks)|(quality.missing_market_team_rows>0)|(quality.missing_score_team_rows>0)]
    if not bad.empty: print('WARNING: data-quality exceptions exist.', file=sys.stderr)
    rows=[]; all_picks=[]
    for season in SEASONS:
        base=greedy_biggest_favorite(tg,season)
        close=optimize(tg,season,'market_expected_margin')
        actual=optimize(tg,season,'actual_margin')
        rolling=rolling_allocator(tg,gpi,season)
        rows.append({'season':season,'weeks':len(base.selections),'biggest_favorite':base.actual_score,
            'rolling_allocator':rolling.actual_score,'rolling_minus_baseline':rolling.actual_score-base.actual_score,
            'closing_line_oracle':close.actual_score,'actual_margin_oracle':actual.actual_score,
            'baseline_market_objective':base.objective_value,'closing_oracle_market_objective':close.objective_value})
        for name,res in [('baseline',base),('rolling',rolling),('closing_oracle',close),('actual_oracle',actual)]:
            tmp=res.selections.copy(); tmp['strategy']=name; all_picks.append(tmp)
    summary=pd.DataFrame(rows)
    print('=== SEASON RESULTS ==='); print(summary.to_csv(index=False))
    dif=summary.rolling_minus_baseline
    print('=== AGGREGATE ===')
    agg={'seasons':len(summary),'baseline_mean':summary.biggest_favorite.mean(),'rolling_mean':summary.rolling_allocator.mean(),
        'mean_improvement':dif.mean(),'median_improvement':dif.median(),'rolling_wins':int((dif>0).sum()),
        'ties':int((dif==0).sum()),'rolling_losses':int((dif<0).sum()),'worst_improvement':dif.min(),
        'best_improvement':dif.max(),'closing_oracle_mean':summary.closing_line_oracle.mean(),'actual_oracle_mean':summary.actual_margin_oracle.mean()}
    for k,v in agg.items(): print(f'{k}={v}')
    print(f"CHECKSUM_2006_BASELINE={summary[summary.season.eq(2006)].iloc[0].biggest_favorite}")
    picks=pd.concat(all_picks,ignore_index=True)
    print('=== 2006 PICKS ===')
    cols=['strategy','week','team','opponent','market_expected_margin','actual_margin']
    extra=['decision_value','fitted_hfa']
    print(picks[picks.season.eq(2006)][cols+[c for c in extra if c in picks.columns]].to_csv(index=False))


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source', default=None); args=ap.parse_args(); run(load_games(args.source))

if __name__=='__main__': main()
