from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

import run_margin_research as core
import run_margin_distribution as dist

BANDWIDTHS = [1.0, 1.5, 2.0, 3.0, 4.0]
TEST_SEASONS = list(range(2011, 2026))


def weighted_probs(train: pd.DataFrame, test: pd.DataFrame, bandwidth: float):
    ts = train.favorite_spread.to_numpy(float)
    tm = train.favorite_margin.to_numpy(float)
    out=[]
    for _,r in test.iterrows():
        s=float(r.favorite_spread)
        w=np.exp(-0.5*((ts-s)/bandwidth)**2)
        # tiny floor prevents pathological zero-weight cases at extreme spreads
        w=np.maximum(w,1e-12); w=w/w.sum()
        out.append({
            'expected_margin':float(np.sum(w*tm)),
            'p_loss':float(np.sum(w*(tm<0))),
            'p_win10':float(np.sum(w*(tm>=10))),
            'p_win20':float(np.sum(w*(tm>=20))),
            'p_win30':float(np.sum(w*(tm>=30))),
        })
    return pd.DataFrame(out,index=test.index)


def main():
    fg=dist.favorite_games(core.load_games())
    rows=[]; season_rows=[]
    for bw in BANDWIDTHS:
        all_pred=[]
        for season in TEST_SEASONS:
            train=fg[fg.season<season].copy(); test=fg[fg.season.eq(season)].copy()
            p=weighted_probs(train,test,bw)
            d=test.join(p)
            d['bandwidth']=bw
            all_pred.append(d)
        pred=pd.concat(all_pred,ignore_index=True)
        targets={'loss':(pred.favorite_margin<0).astype(int),'win10':(pred.favorite_margin>=10).astype(int),'win20':(pred.favorite_margin>=20).astype(int),'win30':(pred.favorite_margin>=30).astype(int)}
        row={'bandwidth':bw,'n':len(pred),'mean_error':float((pred.expected_margin-pred.favorite_margin).mean()),'mae':float(np.abs(pred.expected_margin-pred.favorite_margin).mean()),'rmse':float(np.sqrt(np.mean((pred.expected_margin-pred.favorite_margin)**2)))}
        for name,y in targets.items(): row[f'brier_{name}']=float(brier_score_loss(y,pred[f'p_{name}']))
        recent=pred[pred.season>=2021]
        row['recent_mae']=float(np.abs(recent.expected_margin-recent.favorite_margin).mean())
        for name in targets:
            y=((recent.favorite_margin<0) if name=='loss' else (recent.favorite_margin>=int(name.replace('win','')))).astype(int)
            row[f'recent_brier_{name}']=float(brier_score_loss(y,recent[f'p_{name}']))
        rows.append(row)
        for season,d in pred.groupby('season'):
            season_rows.append({'bandwidth':bw,'season':int(season),'mae':float(np.abs(d.expected_margin-d.favorite_margin).mean()),'mean_error':float((d.expected_margin-d.favorite_margin).mean())})
    summary=pd.DataFrame(rows)
    print('=== EMPIRICAL KERNEL MARGIN SAMPLER: 2011-2025 ===')
    print(summary.to_csv(index=False))
    print('=== BEST BANDWIDTH BY METRIC ===')
    for c in ['mae','rmse','brier_loss','brier_win10','brier_win20','brier_win30','recent_mae','recent_brier_loss','recent_brier_win10','recent_brier_win20','recent_brier_win30']:
        r=summary.loc[summary[c].idxmin()]
        print(f'{c}: bandwidth={r.bandwidth} value={r[c]}')
    print('=== EXPECTED-MARGIN CHECK BY SPREAD BUCKET USING BW=2.0 ===')
    bw=2.0
    preds=[]
    for season in TEST_SEASONS:
        train=fg[fg.season<season]; test=fg[fg.season.eq(season)].copy(); p=weighted_probs(train,test,bw); preds.append(test.join(p))
    pred=pd.concat(preds,ignore_index=True)
    bins=[-0.001,2.99,4.49,6.49,7.49,9.49,11.49,13.49,99]
    labels=['0-2.5','3-4','4.5-6','6.5-7','7.5-9','9.5-11','11.5-13','13.5+']
    pred['bucket']=pd.cut(pred.favorite_spread,bins=bins,labels=labels,include_lowest=True)
    bucket=pred.groupby('bucket',observed=True).agg(games=('game_id','count'),avg_spread=('favorite_spread','mean'),pred_margin=('expected_margin','mean'),actual_margin=('favorite_margin','mean'),loss_rate=('favorite_margin',lambda s:(s<0).mean())).reset_index()
    print(bucket.to_csv(index=False))


if __name__=='__main__':
    main()
