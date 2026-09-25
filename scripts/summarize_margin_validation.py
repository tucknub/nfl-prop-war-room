from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import margin_walk_forward_validation as wf

OUT_DIR = ROOT / "outputs" / "margin_validation"
PICK_FILES = [
    OUT_DIR / "older_default_2009_2015_picks.csv",
    OUT_DIR / "frozen_recheck_2016_2025_picks.csv",
]
SUMMARY_FILES = [
    OUT_DIR / "older_default_2009_2015_summary.csv",
    OUT_DIR / "frozen_recheck_2016_2025_summary.csv",
]


def team_spread(games: pd.DataFrame, season: int, week: int, team: str) -> float:
    d = games[
        (pd.to_numeric(games.season, errors="coerce") == season)
        & games.game_type.eq("REG")
        & (pd.to_numeric(games.week, errors="coerce") == week)
    ]
    row = d[(d.home_team.astype(str) == team) | (d.away_team.astype(str) == team)]
    if len(row) != 1:
        raise RuntimeError(f"Expected one game for {team}, {season} Week {week}; got {len(row)}")
    r = row.iloc[0]
    spread = float(r.spread_line)
    return spread if str(r.home_team) == team else -spread


def bootstrap_interval(values: np.ndarray, seed: int = 20260925) -> list[float]:
    rng = np.random.default_rng(seed)
    means = np.array([
        rng.choice(values, size=len(values), replace=True).mean()
        for _ in range(100_000)
    ])
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def stats_block(values: pd.Series) -> dict:
    x = values.to_numpy(float)
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "wins": int((x > 0).sum()),
        "ties": int((x == 0).sum()),
        "losses": int((x < 0).sum()),
        "bootstrap_95_mean": bootstrap_interval(x),
        "one_sided_t_p": float(stats.ttest_1samp(x, 0, alternative="greater").pvalue),
        "one_sided_wilcoxon_p": float(stats.wilcoxon(x, alternative="greater", zero_method="wilcox").pvalue),
    }

def main() -> None:
    games = wf.GAMES
    picks = pd.concat([pd.read_csv(path) for path in PICK_FILES], ignore_index=True)
    realized = pd.concat([pd.read_csv(path) for path in SUMMARY_FILES], ignore_index=True)

    rows = []
    for season, season_picks in picks.groupby("season"):
        market = {"greedy": 0.0, "optimizer": 0.0}
        calibrated = {"greedy": 0.0, "optimizer": 0.0}
        for _, pick in season_picks.iterrows():
            train = wf.favorite_training_asof(games, int(season), int(pick.week))
            for label, column in [
                ("greedy", "biggest_favorite"),
                ("optimizer", "optimizer"),
            ]:
                spread = team_spread(games, int(season), int(pick.week), str(pick[column]))
                market[label] += spread
                calibrated[label] += float(
                    wf.base.signed_distribution(train, spread)["calibrated_ev"]
                )
        rows.append({
            "season": int(season),
            "greedy_market_sum": market["greedy"],
            "optimizer_market_sum": market["optimizer"],
            "market_delta": market["optimizer"] - market["greedy"],
            "greedy_calibrated_ev": calibrated["greedy"],
            "optimizer_calibrated_ev": calibrated["optimizer"],
            "calibrated_ev_delta": calibrated["optimizer"] - calibrated["greedy"],
        })

    structural = pd.DataFrame(rows).sort_values("season").reset_index(drop=True)
    structural.to_csv(OUT_DIR / "structural_allocation_summary.csv", index=False)

    report = {
        "schema_version": "margin_validation_statistics_v1",
        "seasons": [int(x) for x in structural.season.tolist()],
        "realized_margin_delta": stats_block(realized.optimizer_minus_biggest),
        "eventual_market_allocation_delta": stats_block(structural.market_delta),
        "calibrated_expected_margin_delta": stats_block(structural.calibrated_ev_delta),
        "interpretation": {
            "status": "PROMISING_BUT_INCONCLUSIVE",
            "performance_claim_allowed": False,
            "note": "Structural allocation advantage is modest and uncertainty intervals touch zero.",
        },
    }
    (OUT_DIR / "validation_statistics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(structural.to_string(index=False))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
