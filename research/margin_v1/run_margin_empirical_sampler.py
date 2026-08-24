from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

import run_margin_research as core
import run_margin_distribution as dist

BANDWIDTHS = [1.0, 1.5, 2.0, 3.0, 4.0]
TEST_SEASONS = list(range(2011, 2026))


def kernel_weights(train_spread: np.ndarray, target_spread: float, bandwidth: float) -> np.ndarray:
    w=np.exp(-0.5*((train_spread-target_spread)/bandwidth)**2)
    w=np.maximum(w,1e-12)
    return w/w.sum()


def weighted_probs(train: pd.DataFrame, test: pd.DataFrame, bandwidth: float, mode: str):
    ts=train.favorite_spread.to_numpy(float)
    tm=train.favorite_margin.to_numpy(float)
    residual=tm-ts
    out=[]
    for _,r in test.iterrows():
        s=float(r.favorite_spread)
        w=kernel_weights(ts,s,bandwidth)
        simulated=tm if mode=='raw_margin' else s+residual
        out.append({
            'expected_margin':float(np.sum(w*simulated)),
            'p_loss':float(np.sum(w*(simulated<0))),
            'p_win10':float(np.sum(w*(simulated>=10))),
            'p_win20':float(np.sum(w*(simulated>=20))),
            'p_win30':float(np.sum(w*(simulated>=30))),
        })
    return pd.DataFrame(out,index=test.index)


def evaluate(fg: pd.DataFrame, mode: str):
    rows=[]
    cache={}
    for bw in BANDWIDTHS:
        all_pred=[]
        for season in TEST_SEASONS:
            train=fg[fg.season<season].copy(); test=fg[fg.season.eq(season)].copy()
            p=weighted_probs(train,test,bw,mode)
            d=test.join(p); d['bandwidth']=bw; all_pred.append(d)
        pred=pd.concat(all_pred,ignore_index=True); cache[bw]=pred
        targets={'loss':(pred.favorite_margin<0).astype(int),'win10':(pred.favorite_margin>=10).astype(int),'win20':(pred.favorite_margin>=20).astype(int),'win30':(pred.favorite_margin>=30).astype(int)}
        row={'mode':mode,'bandwidth':bw,'n':len(pred),'mean_error':float((pred.expected_margin-pred.favorite_margin).mean()),'mae':float(np.abs(pred.expected_margin-pred.favorite_margin).mean()),'rmse':float(np.sqrt(np.mean((pred.expected_margin-pred.favorite_margin)**2)))}
        for name,y in targets.items(): row[f'brier_{name}']=float(brier_score_loss(y,pred[f'p_{name}']))
        recent=pred[pred.season>=2021]
        row['recent_mae']=float(np.abs(recent.expected_margin-recent.favorite_margin).mean())
        for name in targets:
            y=((recent.favorite_margin<0) if name=='loss' else (recent.favorite_margin>=int(name.replace('win','')))).astype(int)
            row[f'recent_brier_{name}']=float(brier_score_loss(y,recent[f'p_{name}']))
        rows.append(row)
    return pd.DataFrame(rows),cache


def main():
    fg=dist.favorite_games(core.load_games())
    summaries=[]; caches={}
    for mode in ['raw_margin','residual_centered']:
        s,c=evaluate(fg,mode); summaries.append(s); caches[mode]=c
    summary=pd.concat(summaries,ignore_index=True)
    print('=== EMPIRICAL KERNEL FULL-MARGIN MODELS: 2011-2025 ===')
    print(summary.to_csv(index=False))
    print('=== BEST EMPIRICAL MODEL BY METRIC ===')
    for c in ['mae','rmse','brier_loss','brier_win10','brier_win20','brier_win30','recent_mae','recent_brier_loss','recent_brier_win10','recent_brier_win20','recent_brier_win30']:
        r=summary.loc[summary[c].idxmin()]
        print(f'{c}: mode={r["mode"]} bandwidth={r.bandwidth} value={r[c]}')

    print('=== BUCKET CALIBRATION: RESIDUAL-CENTERED BW=1.5 ===')
    pred=caches['residual_centered'][1.5].copy()
    bins=[-0.001,2.99,4.49,6.49,7.49,9.49,11.49,13.49,99]
    labels=['0-2.5','3-4','4.5-6','6.5-7','7.5-9','9.5-11','11.5-13','13.5+']
    pred['bucket']=pd.cut(pred.favorite_spread,bins=bins,labels=labels,include_lowest=True)
    bucket=pred.groupby('bucket',observed=True).agg(games=('game_id','count'),avg_spread=('favorite_spread','mean'),pred_margin=('expected_margin','mean'),actual_margin=('favorite_margin','mean'),pred_loss=('p_loss','mean'),actual_loss=('favorite_margin',lambda s:(s<0).mean()),pred_20=('p_win20','mean'),actual_20=('favorite_margin',lambda s:(s>=20).mean())).reset_index()
    print(bucket.to_csv(index=False))


if __name__=='__main__':
    main()
