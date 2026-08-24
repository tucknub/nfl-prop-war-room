from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import nflreadpy as nfl

import run_margin_research as core
import run_margin_distribution as dist

SEASONS=list(range(2006,2026))
TEST_SEASONS=list(range(2011,2026))
ROLLING_GAMES=4
MIN_PRIOR_GAMES=3


def to_pandas(frame):
    if isinstance(frame,pd.DataFrame): return frame.copy()
    if hasattr(frame,'to_dicts'): return pd.DataFrame(frame.to_dicts())
    if hasattr(frame,'to_pandas'): return frame.to_pandas()
    return pd.DataFrame(frame)


def num(df,col,default=0.0):
    if col not in df.columns: return pd.Series(default,index=df.index,dtype=float)
    return pd.to_numeric(df[col],errors='coerce').fillna(default).astype(float)


def build_team_form() -> tuple[pd.DataFrame,list[str]]:
    ts=to_pandas(nfl.load_team_stats(SEASONS,summary_level='week'))
    ts=ts[ts['season_type'].eq('REG')].copy()
    ts['season']=pd.to_numeric(ts.season,errors='coerce').astype(int)
    ts['week']=pd.to_numeric(ts.week,errors='coerce').astype(int)
    ts['team_canon']=ts.team.astype(str).map(core.canon_team)
    ts['opponent_canon']=ts.opponent_team.astype(str).map(core.canon_team)

    attempts=num(ts,'attempts'); carries=num(ts,'carries'); sacks=num(ts,'sacks_suffered')
    plays=(attempts+carries+sacks).replace(0,np.nan)
    dropbacks=(attempts+sacks).replace(0,np.nan)
    ts['off_epa_pp']=(num(ts,'passing_epa')+num(ts,'rushing_epa'))/plays
    ts['pass_epa_db']=num(ts,'passing_epa')/dropbacks
    ts['rush_epa_carry']=num(ts,'rushing_epa')/carries.replace(0,np.nan)
    ts['yards_pp']=(num(ts,'passing_yards')+num(ts,'rushing_yards'))/plays

    explosive_cols=[c for c in ['passing_20','rushing_20'] if c in ts.columns]
    if explosive_cols:
        explosive=sum((num(ts,c) for c in explosive_cols),start=pd.Series(0.0,index=ts.index))
        ts['explosive_rate']=explosive/plays
    else:
        ts['explosive_rate']=np.nan

    fumble_lost_cols=[c for c in ['sack_fumbles_lost','rushing_fumbles_lost','receiving_fumbles_lost'] if c in ts.columns]
    lost=sum((num(ts,c) for c in fumble_lost_cols),start=pd.Series(0.0,index=ts.index))
    ts['turnovers_committed']=num(ts,'passing_interceptions')+lost

    opp_cols=['game_id','team_canon','off_epa_pp','pass_epa_db','rush_epa_carry','yards_pp','explosive_rate','turnovers_committed']
    opp=ts[opp_cols].rename(columns={
        'team_canon':'opp_team_canon','off_epa_pp':'def_epa_allowed_pp','pass_epa_db':'def_pass_epa_allowed_db',
        'rush_epa_carry':'def_rush_epa_allowed_carry','yards_pp':'def_yards_pp_allowed',
        'explosive_rate':'def_explosive_rate_allowed','turnovers_committed':'takeaways',
    })
    ts=ts.merge(opp,left_on=['game_id','opponent_canon'],right_on=['game_id','opp_team_canon'],how='left',validate='one_to_one')
    ts['net_epa']=ts.off_epa_pp-ts.def_epa_allowed_pp
    ts['net_pass_epa']=ts.pass_epa_db-ts.def_pass_epa_allowed_db
    ts['net_rush_epa']=ts.rush_epa_carry-ts.def_rush_epa_allowed_carry
    ts['net_ypp']=ts.yards_pp-ts.def_yards_pp_allowed
    ts['net_explosive']=ts.explosive_rate-ts.def_explosive_rate_allowed
    ts['turnover_margin']=ts.takeaways-ts.turnovers_committed

    raw=['net_epa','net_pass_epa','net_rush_epa','net_ypp','net_explosive','turnover_margin']
    ts=ts.sort_values(['season','team_canon','week','game_id']).reset_index(drop=True)
    for c in raw:
        ts[f'{c}_form']=ts.groupby(['season','team_canon'],sort=False)[c].transform(
            lambda s:s.shift(1).rolling(ROLLING_GAMES,min_periods=MIN_PRIOR_GAMES).mean()
        )
    form_cols=[f'{c}_form' for c in raw if ts[f'{c}_form'].notna().any()]
    keep=['season','week','game_id','team_canon']+form_cols
    return ts[keep].copy(),form_cols


def build_model_frame(games: pd.DataFrame,form: pd.DataFrame,form_cols:list[str]) -> tuple[pd.DataFrame,list[str],list[str]]:
    fg=dist.favorite_games(games).copy()
    fg['fav_canon']=fg.favorite.astype(str).map(core.canon_team)
    fg['dog_canon']=fg.underdog.astype(str).map(core.canon_team)
    fav=form.rename(columns={'team_canon':'fav_canon',**{c:f'fav_{c}' for c in form_cols}})
    dog=form.rename(columns={'team_canon':'dog_canon',**{c:f'dog_{c}' for c in form_cols}})
    d=fg.merge(fav,on=['season','week','game_id','fav_canon'],how='left',validate='one_to_one')
    d=d.merge(dog,on=['season','week','game_id','dog_canon'],how='left',validate='one_to_one')
    feature_map={
        'net_epa_form':'epa_strength_diff','net_pass_epa_form':'pass_strength_diff',
        'net_rush_epa_form':'rush_strength_diff','net_ypp_form':'ypp_strength_diff',
        'net_explosive_form':'explosive_strength_diff','turnover_margin_form':'turnover_strength_diff',
    }
    style=[]
    for base,out in feature_map.items():
        a=f'fav_{base}'; b=f'dog_{base}'
        if a in d.columns and b in d.columns:
            d[out]=d[a]-d[b]; style.append(out)
    core_style=[c for c in style if c!='turnover_strength_diff']
    plus_turn=style.copy()
    d['residual']=d.favorite_margin-d.favorite_spread
    required=['favorite_spread','favorite_margin','residual']+plus_turn
    d=d.dropna(subset=required).copy()
    return d,core_style,plus_turn


def X(df:pd.DataFrame,style_cols:list[str]):
    s=df.favorite_spread.to_numpy(float)
    pieces=[s,s**2]
    for c in style_cols: pieces.append(df[c].to_numpy(float))
    return np.column_stack(pieces)


def bootstrap_ci(values,n=50000,seed=42):
    a=np.asarray(values,float); rng=np.random.default_rng(seed)
    means=rng.choice(a,size=(n,len(a)),replace=True).mean(axis=1)
    return float(np.quantile(means,.025)),float(np.quantile(means,.975))


def main():
    games=core.load_games(); form,available=build_team_form(); d,core_style,plus_turn=build_model_frame(games,form,available)
    print('=== TEAM STYLE DATA ===')
    print(f'rows={len(d)} seasons={d.season.min()}-{d.season.max()} rolling_games={ROLLING_GAMES} min_prior_games={MIN_PRIOR_GAMES}')
    print(f'available_form_columns={available}')
    print(f'core_style={core_style}')
    print(f'plus_turnover={plus_turn}')

    preds=[]
    for season in TEST_SEASONS:
        train=d[d.season<season].copy(); test=d[d.season.eq(season)].copy()
        if train.empty or test.empty: continue
        models={
            'market_raw':None,
            'market_recal':[],
            'market_plus_style':core_style,
            'market_plus_style_turnover':plus_turn,
        }
        margin_predictions={}
        margin_predictions['market_raw']=test.favorite_spread.to_numpy(float)
        for name,cols in models.items():
            if name=='market_raw': continue
            model=make_pipeline(StandardScaler(),Ridge(alpha=10.0))
            model.fit(X(train,cols),train.residual.to_numpy(float))
            margin_predictions[name]=test.favorite_spread.to_numpy(float)+model.predict(X(test,cols))
        for name,predmargin in margin_predictions.items():
            for i,(_,r) in enumerate(test.iterrows()):
                preds.append({'season':season,'game_id':r.game_id,'model':name,'actual_margin':float(r.favorite_margin),'spread':float(r.favorite_spread),'pred_margin':float(predmargin[i])})

    mp=pd.DataFrame(preds)
    print('=== WALK-FORWARD MARGIN ERROR: 2011-2025, IN-SEASON FORM AVAILABLE ===')
    rows=[]
    for model,g in mp.groupby('model'):
        err=g.pred_margin-g.actual_margin
        recent=g[g.season>=2021]; rerr=recent.pred_margin-recent.actual_margin
        rows.append({'model':model,'n':len(g),'mae':float(np.abs(err).mean()),'rmse':float(np.sqrt(np.mean(err**2))),'bias':float(err.mean()),
                     'recent_n':len(recent),'recent_mae':float(np.abs(rerr).mean()),'recent_rmse':float(np.sqrt(np.mean(rerr**2))),'recent_bias':float(rerr.mean())})
    print(pd.DataFrame(rows).sort_values('mae').to_csv(index=False))

    base=mp[mp.model.eq('market_recal')].sort_values(['season','game_id']).reset_index(drop=True)
    print('=== PAIRED ABSOLUTE-ERROR DELTA VS RECALIBRATED MARKET ===')
    for model in ['market_plus_style','market_plus_style_turnover']:
        alt=mp[mp.model.eq(model)].sort_values(['season','game_id']).reset_index(drop=True)
        assert (base[['season','game_id']].values==alt[['season','game_id']].values).all()
        delta=np.abs(alt.pred_margin-alt.actual_margin)-np.abs(base.pred_margin-base.actual_margin)
        ci=bootstrap_ci(delta.to_numpy())
        recent=base.season>=2021
        print(f'{model}: mean_delta={delta.mean()} ci=[{ci[0]},{ci[1]}] recent_delta={delta[recent].mean()}')

    # Tail-probability test: does style improve calibration/discrimination beyond spread alone?
    prob_rows=[]
    targets={'loss':lambda m:m<0,'win10':lambda m:m>=10,'win20':lambda m:m>=20,'win30':lambda m:m>=30}
    for season in TEST_SEASONS:
        train=d[d.season<season].copy(); test=d[d.season.eq(season)].copy()
        for target,fn in targets.items():
            ytr=fn(train.favorite_margin.to_numpy(float)).astype(int); yte=fn(test.favorite_margin.to_numpy(float)).astype(int)
            for name,cols in [('spread_only',[]),('spread_plus_style',core_style),('spread_plus_style_turnover',plus_turn)]:
                model=make_pipeline(StandardScaler(),LogisticRegression(C=1.0,max_iter=2000,solver='lbfgs'))
                model.fit(X(train,cols),ytr)
                p=model.predict_proba(X(test,cols))[:,1]
                for i,(_,r) in enumerate(test.iterrows()):
                    prob_rows.append({'season':season,'game_id':r.game_id,'target':target,'model':name,'y':int(yte[i]),'p':float(p[i])})
    pp=pd.DataFrame(prob_rows)
    print('=== WALK-FORWARD TAIL BRIER ===')
    rows=[]
    for (target,model),g in pp.groupby(['target','model']):
        recent=g[g.season>=2021]
        rows.append({'target':target,'model':model,'n':len(g),'brier':float(brier_score_loss(g.y,g.p)),'recent_brier':float(brier_score_loss(recent.y,recent.p))})
    print(pd.DataFrame(rows).sort_values(['target','brier']).to_csv(index=False))

    print('=== PAIRED BRIER DELTA VS SPREAD ONLY ===')
    for target in targets:
        b=pp[(pp.target.eq(target))&pp.model.eq('spread_only')].sort_values(['season','game_id']).reset_index(drop=True)
        for model in ['spread_plus_style','spread_plus_style_turnover']:
            a=pp[(pp.target.eq(target))&pp.model.eq(model)].sort_values(['season','game_id']).reset_index(drop=True)
            delta=(a.p-a.y)**2-(b.p-b.y)**2
            ci=bootstrap_ci(delta.to_numpy())
            recent=b.season>=2021
            print(f'{target},{model},mean_delta={delta.mean()},ci_low={ci[0]},ci_high={ci[1]},recent_delta={delta[recent].mean()}')


if __name__=='__main__':
    main()
