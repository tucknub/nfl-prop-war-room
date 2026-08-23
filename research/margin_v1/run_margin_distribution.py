from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss, log_loss

import run_margin_research as core

TEST_SEASONS = list(range(2011, 2026))
THRESHOLDS = {
    'loss': lambda m: m < 0,
    'win10': lambda m: m >= 10,
    'win20': lambda m: m >= 20,
    'win30': lambda m: m >= 30,
}


def favorite_games(games: pd.DataFrame) -> pd.DataFrame:
    g = games[(games['game_type'].eq('REG')) & games['season'].between(2006, 2025)].copy()
    for c in ['season', 'week', 'home_score', 'away_score', 'spread_line', 'total_line']:
        g[c] = pd.to_numeric(g[c], errors='coerce')
    g = g.dropna(subset=['home_score', 'away_score', 'spread_line', 'total_line']).copy()
    # nflverse convention used in this project: positive spread_line => home favored.
    home_fav = g.spread_line >= 0
    g['favorite'] = np.where(home_fav, g.home_team, g.away_team)
    g['underdog'] = np.where(home_fav, g.away_team, g.home_team)
    g['favorite_spread'] = g.spread_line.abs().astype(float)
    g['favorite_margin'] = np.where(home_fav, g.home_score - g.away_score, g.away_score - g.home_score).astype(float)
    g['favorite_home'] = home_fav.astype(int)
    # pick'em games are retained with deterministic home-side perspective.
    return g[['season','week','game_id','favorite','underdog','favorite_home','favorite_spread','total_line','favorite_margin']].reset_index(drop=True)


def x_spread(df: pd.DataFrame) -> np.ndarray:
    s = df.favorite_spread.to_numpy(float)
    return np.column_stack([s, s**2])


def x_spread_total(df: pd.DataFrame) -> np.ndarray:
    s = df.favorite_spread.to_numpy(float)
    t = df.total_line.to_numpy(float)
    return np.column_stack([s, s**2, t, t**2, s*t])


def safe_logloss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(log_loss(y, p, labels=[0,1]))


def fit_binary(train: pd.DataFrame, test: pd.DataFrame, target: str, features: str) -> np.ndarray:
    y = THRESHOLDS[target](train.favorite_margin.to_numpy(float)).astype(int)
    Xtr = x_spread(train) if features == 'spread' else x_spread_total(train)
    Xte = x_spread(test) if features == 'spread' else x_spread_total(test)
    if len(np.unique(y)) < 2:
        return np.full(len(test), float(y.mean()))
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, solver='lbfgs'))
    model.fit(Xtr, y)
    return model.predict_proba(Xte)[:,1]


def normal_probs(train: pd.DataFrame, test: pd.DataFrame, target: str) -> np.ndarray:
    residual = train.favorite_margin.to_numpy(float) - train.favorite_spread.to_numpy(float)
    sigma = float(np.std(residual, ddof=1))
    mu = test.favorite_spread.to_numpy(float)
    if target == 'loss':
        return norm.cdf(0, loc=mu, scale=sigma)
    threshold = {'win10':10, 'win20':20, 'win30':30}[target]
    return 1.0 - norm.cdf(threshold - 1e-9, loc=mu, scale=sigma)


def bootstrap_mean_ci(values: np.ndarray, n=50000, seed=42):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n, len(values)), replace=True).mean(axis=1)
    return tuple(np.quantile(means, [0.025, 0.975]))


def main():
    games = core.load_games()
    fg = favorite_games(games)
    print('=== FAVORITE GAME DATA ===')
    print(f'games={len(fg)} seasons={fg.season.min()}-{fg.season.max()}')
    print(f'mean_spread={fg.favorite_spread.mean():.3f} mean_margin={fg.favorite_margin.mean():.3f} mean_total={fg.total_line.mean():.3f}')

    prediction_rows = []
    for season in TEST_SEASONS:
        train = fg[fg.season < season].copy()
        test = fg[fg.season == season].copy()
        for target in THRESHOLDS:
            y = THRESHOLDS[target](test.favorite_margin.to_numpy(float)).astype(int)
            preds = {
                'normal_spread': normal_probs(train, test, target),
                'logit_spread': fit_binary(train, test, target, 'spread'),
                'logit_spread_total': fit_binary(train, test, target, 'spread_total'),
            }
            for model_name, p in preds.items():
                for i, (_, r) in enumerate(test.iterrows()):
                    prediction_rows.append({
                        'season': season, 'game_id': r.game_id, 'target': target, 'model': model_name,
                        'y': int(y[i]), 'p': float(p[i]), 'spread': float(r.favorite_spread),
                        'total': float(r.total_line), 'margin': float(r.favorite_margin),
                    })
    pred = pd.DataFrame(prediction_rows)

    rows=[]
    for (target, model), d in pred.groupby(['target','model']):
        rows.append({
            'target':target,'model':model,'n':len(d),
            'event_rate':d.y.mean(),
            'brier':brier_score_loss(d.y,d.p),
            'logloss':safe_logloss(d.y.to_numpy(),d.p.to_numpy()),
            'calibration_bias':float((d.p-d.y).mean()),
        })
    metrics=pd.DataFrame(rows).sort_values(['target','brier'])
    print('=== WALK-FORWARD PROBABILITY METRICS: 2011-2025 ===')
    print(metrics.to_csv(index=False))

    recent=pred[pred.season>=2021]
    rows=[]
    for (target, model), d in recent.groupby(['target','model']):
        rows.append({'target':target,'model':model,'n':len(d),'brier':brier_score_loss(d.y,d.p),'logloss':safe_logloss(d.y.to_numpy(),d.p.to_numpy()),'calibration_bias':float((d.p-d.y).mean())})
    print('=== RECENT 18-WEEK ERA: 2021-2025 ===')
    print(pd.DataFrame(rows).sort_values(['target','brier']).to_csv(index=False))

    print('=== SPREAD+TOTAL VS SPREAD-ONLY: PAIRED BRIER DELTA ===')
    comparison=[]
    for target in THRESHOLDS:
        a=pred[(pred.target==target)&(pred.model=='logit_spread')].sort_values(['season','game_id']).reset_index(drop=True)
        b=pred[(pred.target==target)&(pred.model=='logit_spread_total')].sort_values(['season','game_id']).reset_index(drop=True)
        assert (a[['season','game_id']].values == b[['season','game_id']].values).all()
        diff=(b.p-b.y)**2 - (a.p-a.y)**2  # negative = spread+total better
        ci=bootstrap_mean_ci(diff.to_numpy())
        recent_mask=a.season>=2021
        comparison.append({'target':target,'mean_brier_delta_total_minus_spread':float(diff.mean()),'ci_low':ci[0],'ci_high':ci[1],
                           'recent_mean_delta':float(diff[recent_mask].mean())})
    print(pd.DataFrame(comparison).to_csv(index=False))

    # Empirical descriptive buckets for user-facing interpretation. These are descriptive only, not used by the model.
    bins=[-0.001,2.99,4.49,6.49,7.49,9.49,11.49,13.49,99]
    labels=['0-2.5','3-4','4.5-6','6.5-7','7.5-9','9.5-11','11.5-13','13.5+']
    fg['spread_bucket']=pd.cut(fg.favorite_spread,bins=bins,labels=labels,include_lowest=True)
    bucket=[]
    for label,d in fg.groupby('spread_bucket',observed=True):
        bucket.append({'spread_bucket':str(label),'games':len(d),'avg_spread':d.favorite_spread.mean(),'avg_margin':d.favorite_margin.mean(),
                       'loss_rate':(d.favorite_margin<0).mean(),'win10_rate':(d.favorite_margin>=10).mean(),
                       'win20_rate':(d.favorite_margin>=20).mean(),'win30_rate':(d.favorite_margin>=30).mean()})
    print('=== DESCRIPTIVE FAVORITE MARGIN BUCKETS: 2006-2025 ===')
    print(pd.DataFrame(bucket).to_csv(index=False))

    # Check whether independent threshold models violate nested probability ordering.
    for model in ['logit_spread','logit_spread_total']:
        wide=pred[pred.model.eq(model)].pivot_table(index=['season','game_id'],columns='target',values='p').reset_index()
        violations=((wide.win30>wide.win20+1e-9)|(wide.win20>wide.win10+1e-9)).mean()
        print(f'MONOTONIC_VIOLATION_RATE_{model}={violations:.6f}')


if __name__ == '__main__':
    main()
