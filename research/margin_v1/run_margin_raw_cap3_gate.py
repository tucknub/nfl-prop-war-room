from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
import run_margin_distribution as dist
import run_margin_anchor_policy as anchor
import run_margin_anchor_safeguards as safeguards

SEASONS = list(range(2011, 2026))
RECENT = list(range(2021, 2026))
CAP = 3.0
BW = 3.0


def bootstrap_ci(values, n=100000, seed=20260823):
    a = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = rng.choice(a, size=(n, len(a)), replace=True).mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [0.025, 0.975]))


def summarize(label: str, d: pd.DataFrame) -> None:
    actual = d.actual_delta_vs_bf.to_numpy(float)
    market = d.market_delta_vs_bf.to_numpy(float)
    ev = d.ev_delta_vs_bf.to_numpy(float)
    print(f"=== {label} ===")
    print(f"seasons={len(d)}")
    print(f"mean_actual_delta={actual.mean()}")
    print(f"median_actual_delta={np.median(actual)}")
    print(f"actual_ci={bootstrap_ci(actual)}")
    print(f"actual_wins={(actual > 0).sum()} ties={(actual == 0).sum()} losses={(actual < 0).sum()}")
    print(f"mean_market_delta={market.mean()}")
    print(f"market_ci={bootstrap_ci(market)}")
    print(f"mean_calibrated_ev_delta={ev.mean()}")
    print(f"calibrated_ev_ci={bootstrap_ci(ev)}")
    print(f"avg_deviations={d.deviations.mean()}")
    print(f"max_current_sacrifice={d.max_sacrifice.max()}")


def main() -> None:
    games = core.load_games()
    tg = core.canonical_team_games(games)
    gpi = core.build_period_index(games)
    fg = dist.favorite_games(games)

    rows = []
    for season in SEASONS:
        bf = core.greedy_biggest_favorite(tg, season)
        # Empty future-line lookup deliberately invokes the raw long/slow market-power
        # fallback in anchor.build_remaining_values(). Current week still uses its
        # actual sportsbook market line; Weeks 1-3 remain Biggest Favorite by policy.
        picks = safeguards.capped_anchored_policy(
            tg, gpi, fg, season, CAP, style_lookup={}
        )
        train_fav = fg[fg.season < season].copy()

        if picks.team.duplicated().any():
            raise AssertionError(f"{season}: team reused")
        expected_weeks = sorted(int(x) for x in tg[tg.season.eq(season)].week.unique())
        if sorted(picks.week.astype(int).tolist()) != expected_weeks:
            raise AssertionError(f"{season}: bad week coverage")
        if float(picks.current_sacrifice.fillna(0).max()) > CAP + 1e-12:
            raise AssertionError(f"{season}: cap exceeded")

        bf_first3 = bf.selections[bf.selections.week.le(3)][['week', 'team']].reset_index(drop=True)
        raw_first3 = picks[picks.week.le(3)][['week', 'team']].reset_index(drop=True)
        if not bf_first3.equals(raw_first3):
            raise AssertionError(f"{season}: Weeks 1-3 did not retain Biggest Favorite path")

        bf_ev = anchor.add_eval_ev(bf.selections, train_fav, BW)
        raw_ev = anchor.add_eval_ev(picks, train_fav, BW)
        rows.append({
            'season': season,
            'biggest_favorite_actual': float(bf.actual_score),
            'raw_cap3_actual': float(picks.actual_margin.sum()),
            'actual_delta_vs_bf': float(picks.actual_margin.sum() - bf.actual_score),
            'biggest_favorite_market': float(bf.selections.market_expected_margin.sum()),
            'raw_cap3_market': float(picks.market_expected_margin.sum()),
            'market_delta_vs_bf': float(picks.market_expected_margin.sum() - bf.selections.market_expected_margin.sum()),
            'biggest_favorite_calibrated_ev': float(bf_ev),
            'raw_cap3_calibrated_ev': float(raw_ev),
            'ev_delta_vs_bf': float(raw_ev - bf_ev),
            'deviations': int(picks.deviated.fillna(False).sum()),
            'max_sacrifice': float(picks.current_sacrifice.fillna(0).max()),
        })

    out = pd.DataFrame(rows)
    print('=== RAW LONG/SLOW FUTURE POWER + FROZEN CAP-3 POLICY ===')
    print(out.to_csv(index=False))
    summarize('FULL 2011-2025', out)
    summarize('MODERN 2021-2025', out[out.season.isin(RECENT)].copy())
    print('invariant_weeks_1_to_3_biggest_favorite=PASS')
    print('invariant_one_pick_per_week=PASS')
    print('invariant_one_use_per_team=PASS')
    print('invariant_current_sacrifice_cap3=PASS')


if __name__ == '__main__':
    main()
