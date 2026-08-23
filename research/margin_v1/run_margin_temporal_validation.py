from __future__ import annotations

import numpy as np
import pandas as pd

import run_margin_research as core
from run_margin_sensitivity import rolling_cfg


CONFIGS = {
    'default': dict(window_periods=20, half_life=6.0, ridge=3.0, include_current=True),
    'high_ridge': dict(window_periods=20, half_life=6.0, ridge=6.0, include_current=True),
    'long_slow': dict(window_periods=32, half_life=8.0, ridge=3.0, include_current=True),
    'strict_long': dict(window_periods=32, half_life=8.0, ridge=3.0, include_current=False),
}

PERIODS = {
    'development_2006_2015': list(range(2006, 2016)),
    'validation_2016_2020': list(range(2016, 2021)),
    'recent_18_week_2021_2025': list(range(2021, 2026)),
    'full_2006_2025': list(range(2006, 2026)),
}


def metrics(values: np.ndarray) -> dict:
    values = np.asarray(values, dtype=float)
    return {
        'mean': float(values.mean()),
        'median': float(np.median(values)),
        'wins': int((values > 0).sum()),
        'losses': int((values < 0).sum()),
        'worst': float(values.min()),
        'best': float(values.max()),
    }


def main() -> None:
    games = core.load_games()
    tg = core.canonical_team_games(games)
    gpi = core.build_period_index(games)
    baseline = {s: core.greedy_biggest_favorite(tg, s).actual_score for s in core.SEASONS}

    diffs: dict[str, dict[int, float]] = {}
    season_rows = []
    for label, cfg in CONFIGS.items():
        diffs[label] = {}
        for season in core.SEASONS:
            score = rolling_cfg(tg, gpi, season, cfg)
            diff = float(score - baseline[season])
            diffs[label][season] = diff
            season_rows.append({'config': label, 'season': season, 'improvement_vs_baseline': diff})

    print('=== TEMPORAL VALIDATION: PER-SEASON ===')
    print(pd.DataFrame(season_rows).to_csv(index=False))

    split_rows = []
    for label in CONFIGS:
        for period, seasons in PERIODS.items():
            vals = np.array([diffs[label][s] for s in seasons], dtype=float)
            split_rows.append({'config': label, 'period': period, **metrics(vals)})
    split = pd.DataFrame(split_rows)
    print('=== TEMPORAL VALIDATION: SPLITS ===')
    print(split.to_csv(index=False))

    dev = split[split.period.eq('development_2006_2015')].copy()
    # Mechanical selection rule fixed before looking at later-period metrics:
    # highest development mean; ties broken by better development worst season, then label.
    dev = dev.sort_values(['mean', 'worst', 'config'], ascending=[False, False, True], kind='stable')
    selected = str(dev.iloc[0].config)
    print('=== DEVELOPMENT-ONLY SELECTION ===')
    print(f'selected_config={selected}')
    print('selection_rule=highest development mean; tie-break better development worst season; then config label')
    for period, seasons in PERIODS.items():
        vals = np.array([diffs[selected][s] for s in seasons], dtype=float)
        m = metrics(vals)
        print(f"{period}_mean={m['mean']}")
        print(f"{period}_median={m['median']}")
        print(f"{period}_wins={m['wins']}")
        print(f"{period}_losses={m['losses']}")
        print(f"{period}_worst={m['worst']}")
        print(f"{period}_best={m['best']}")


if __name__ == '__main__':
    main()
