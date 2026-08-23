from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_sensitivity as sens

CAPS=[0.0,0.5,1.0,1.5,2.0,3.0,999.0]
CFG=dict(window_periods=32,half_life=8.0,ridge=3.0,include_current=True)


def build_forecast_table(tg,gpi,season,current,used):
    d=tg[tg.season.eq(season)].copy(); weeks=sorted(int(x) for x in d.week.unique())
    ratings,hfa=sens.fit_market_power_cfg(gpi,season,current,**CFG)
    remaining=[w for w in weeks if w>=current]
    rem=d[d.week.isin(remaining) & ~d.team.isin(used)].copy()
    def forecast(r):
        if int(r.week)==current:
            return float(r.market_expected_margin)
        th=ratings.get(core.canon_team(r.team),0.0); to=ratings.get(core.canon_team(r.opponent),0.0)
        if str(r.location).lower()!='home': adj=0.0
        else: adj=hfa if bool(r.is_home) else -hfa
        return float(th-to+adj)
    rem['rolling_value']=rem.apply(forecast,axis=1)
    return rem,remaining


def capped_rolling(tg,gpi,season,cap):
    d=tg[tg.season.eq(season)].copy(); weeks=sorted(int(x) for x in d.week.unique())
    used=set(); picks=[]
    for current in weeks:
        rem,remaining=build_forecast_table(tg,gpi,season,current,used)
        current_rows=rem[rem.week.eq(current)].copy()
        best_line=float(current_rows.market_expected_margin.max())
        candidates=current_rows[current_rows.market_expected_margin >= best_line-cap-1e-9].copy()
        scored=[]
        future_weeks=[w for w in remaining if w>current]
        for _,cand in candidates.iterrows():
            total_obj=float(cand.market_expected_margin)
            if future_weeks:
                future=rem[rem.week.isin(future_weeks) & ~rem.team.eq(cand.team)].copy()
                assn=core.optimize(future,season,'rolling_value',weeks=future_weeks,eligible_teams=set(future.team.unique()))
                total_obj += assn.objective_value
            scored.append((total_obj,float(cand.market_expected_margin),str(cand.team),cand))
        scored.sort(key=lambda x:(-x[0],-x[1],x[2]))
        _,line,_,pick=scored[0]
        pick=pick.copy(); pick['current_sacrifice']=best_line-line; pick['cap']=cap
        picks.append(pick); used.add(str(pick.team))
    s=pd.DataFrame(picks).reset_index(drop=True); core.validate_selections(s,weeks)
    return s


def summarize(vals):
    a=np.asarray(vals,float)
    return dict(mean=float(a.mean()),median=float(np.median(a)),wins=int((a>0).sum()),losses=int((a<0).sum()),ties=int((a==0).sum()),worst=float(a.min()),best=float(a.max()))


def main():
    games=core.load_games(); tg=core.canonical_team_games(games); gpi=core.build_period_index(games)
    baseline={s:core.greedy_biggest_favorite(tg,s).actual_score for s in core.SEASONS}
    rows=[]; season_rows=[]
    for cap in CAPS:
        diffs=[]; recent=[]; sacrifices=[]; selected_market=[]
        for season in core.SEASONS:
            picks=capped_rolling(tg,gpi,season,cap)
            score=float(picks.actual_margin.sum()); diff=score-baseline[season]
            season_rows.append({'cap':cap,'season':season,'score':score,'baseline':baseline[season],'improvement':diff,'market_sum':float(picks.market_expected_margin.sum()),'sacrifice_sum':float(picks.current_sacrifice.sum()),'max_week_sacrifice':float(picks.current_sacrifice.max())})
            diffs.append(diff); sacrifices.append(float(picks.current_sacrifice.sum())); selected_market.append(float(picks.market_expected_margin.sum()))
            if season>=2021: recent.append(diff)
        s=summarize(diffs); r=summarize(recent)
        rows.append({'cap':cap,**s,'avg_sacrifice':float(np.mean(sacrifices)),'avg_selected_market_sum':float(np.mean(selected_market)),'recent_mean':r['mean'],'recent_median':r['median'],'recent_wins':r['wins'],'recent_losses':r['losses'],'recent_worst':r['worst'],'recent_best':r['best']})
    print('=== CURRENT-MARKET SACRIFICE CAP: LONG/SLOW ROLLING ===')
    print(pd.DataFrame(rows).to_csv(index=False))
    season_df=pd.DataFrame(season_rows)
    print('=== PER-SEASON FOR CANDIDATE CAPS 0.5, 1.0, 1.5, 2.0, UNCONSTRAINED ===')
    print(season_df[season_df['cap'].isin([0.5,1.0,1.5,2.0,999.0])].to_csv(index=False))


if __name__=='__main__':
    main()
