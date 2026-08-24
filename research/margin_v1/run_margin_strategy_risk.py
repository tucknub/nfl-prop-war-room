from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_sacrifice_cap as capmod


def q(a, p):
    return float(np.quantile(np.asarray(a, dtype=float), p))


def bootstrap_ci(values, n=100000, seed=20260823):
    a=np.asarray(values,dtype=float)
    rng=np.random.default_rng(seed)
    means=rng.choice(a,size=(n,len(a)),replace=True).mean(axis=1)
    return float(np.quantile(means,.025)),float(np.quantile(means,.975))


def profile(name, scores, improvements, market_sums):
    s=np.asarray(scores,float); d=np.asarray(improvements,float); m=np.asarray(market_sums,float)
    return {
        'strategy':name,
        'mean_score':s.mean(),'median_score':np.median(s),'score_sd':s.std(ddof=1),
        'score_p10':q(s,.10),'score_p25':q(s,.25),'score_p75':q(s,.75),'score_p90':q(s,.90),
        'mean_improvement':d.mean(),'median_improvement':np.median(d),'improvement_sd':d.std(ddof=1),
        'imp_p10':q(d,.10),'imp_p25':q(d,.25),'imp_p75':q(d,.75),'imp_p90':q(d,.90),
        'seasons_below_baseline':int((d<0).sum()),'seasons_imp_le_minus20':int((d<=-20).sum()),
        'seasons_imp_ge20':int((d>=20).sum()),'seasons_imp_ge50':int((d>=50).sum()),
        'mean_selected_market_sum':m.mean(),
    }


def main():
    games=core.load_games(); tg=core.canonical_team_games(games); gpi=core.build_period_index(games)
    rows=[]
    for season in core.SEASONS:
        base=core.greedy_biggest_favorite(tg,season)
        c3=capmod.capped_rolling(tg,gpi,season,3.0)
        long=capmod.capped_rolling(tg,gpi,season,999.0)
        rows.append({
            'season':season,
            'baseline_score':base.actual_score,'baseline_market':base.objective_value,
            'cap3_score':float(c3.actual_margin.sum()),'cap3_market':float(c3.market_expected_margin.sum()),
            'long_score':float(long.actual_margin.sum()),'long_market':float(long.market_expected_margin.sum()),
        })
    d=pd.DataFrame(rows)
    d['cap3_imp']=d.cap3_score-d.baseline_score
    d['long_imp']=d.long_score-d.baseline_score
    d['cap3_minus_long']=d.cap3_score-d.long_score

    profiles=[]
    zero=np.zeros(len(d))
    profiles.append(profile('biggest_favorite',d.baseline_score,zero,d.baseline_market))
    profiles.append(profile('long_slow_unconstrained',d.long_score,d.long_imp,d.long_market))
    profiles.append(profile('long_slow_cap3',d.cap3_score,d.cap3_imp,d.cap3_market))
    print('=== REALIZED SEASON RISK PROFILE: 2006-2025 ===')
    print(pd.DataFrame(profiles).to_csv(index=False))

    print('=== PAIRED CAP3 VS UNCONSTRAINED LONG/SLOW ===')
    delta=d.cap3_minus_long.to_numpy(float); ci=bootstrap_ci(delta)
    print(f'mean_cap3_minus_long={delta.mean()}')
    print(f'median_cap3_minus_long={np.median(delta)}')
    print(f'cap3_beats_long={(delta>0).sum()}')
    print(f'cap3_ties_long={(delta==0).sum()}')
    print(f'cap3_loses_long={(delta<0).sum()}')
    print(f'cap3_minus_long_ci_low={ci[0]}')
    print(f'cap3_minus_long_ci_high={ci[1]}')
    print(f'worst_cap3_minus_long={delta.min()}')
    print(f'best_cap3_minus_long={delta.max()}')

    print('=== MODERN 18-WEEK ERA: 2021-2025 ===')
    recent=d[d.season>=2021].copy()
    for strategy,score_col,imp_col,market_col in [
        ('biggest_favorite','baseline_score',None,'baseline_market'),
        ('long_slow_unconstrained','long_score','long_imp','long_market'),
        ('long_slow_cap3','cap3_score','cap3_imp','cap3_market'),
    ]:
        imp=np.zeros(len(recent)) if imp_col is None else recent[imp_col].to_numpy(float)
        p=profile(strategy,recent[score_col],imp,recent[market_col])
        print(','.join([strategy,f"mean_score={p['mean_score']}",f"mean_imp={p['mean_improvement']}",f"score_sd={p['score_sd']}",f"imp_sd={p['improvement_sd']}",f"p10_imp={p['imp_p10']}",f"p90_imp={p['imp_p90']}"]))

    print('=== PER-SEASON ===')
    print(d.to_csv(index=False))


if __name__=='__main__':
    main()
