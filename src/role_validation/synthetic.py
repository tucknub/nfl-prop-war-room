from __future__ import annotations

import numpy as np
import pandas as pd


def make_synthetic_player_week_data(
    seasons=range(2018, 2026),
    weeks=range(1, 19),
    players_per_family: int = 18,
    seed: int = 850,
) -> pd.DataFrame:
    """Generate deterministic smoke-test data.

    This is not football evidence and must never be reported as PropWar results.
    """
    rng = np.random.default_rng(seed)
    families = {
        "rb_carry_share": "RB",
        "rb_opportunity_share": "RB",
        "wr_target_share": "WR",
        "te_target_share": "TE",
    }
    rows = []

    for family, position in families.items():
        for player_num in range(players_per_family):
            player_id = f"{position}_{family}_{player_num:02d}"
            baseline = rng.uniform(0.12, 0.55)
            persistent_shift = 0.0
            shift_weeks_left = 0

            for season in seasons:
                for week in weeks:
                    if shift_weeks_left <= 0 and rng.random() < 0.045:
                        persistent_shift = rng.choice([-1, 1]) * rng.uniform(0.08, 0.20)
                        shift_weeks_left = int(rng.integers(3, 8))
                    if shift_weeks_left > 0:
                        shift_weeks_left -= 1
                    else:
                        persistent_shift *= 0.3

                    metric_normal = np.clip(
                        baseline + persistent_shift + rng.normal(0, 0.035), 0.01, 0.90
                    )
                    distortion = rng.normal(0, 0.08) if rng.random() < 0.08 else 0.0
                    metric_all = np.clip(metric_normal + distortion, 0.01, 0.95)

                    team_opp = int(rng.integers(18, 45))
                    raw_normal = int(round(metric_normal * team_opp))
                    raw_all = max(0, int(round(metric_all * team_opp)))
                    partial = rng.random() < 0.015
                    quality = rng.random() >= 0.01

                    rows.append(
                        {
                            "season": season,
                            "week": week,
                            "player_id": player_id,
                            "player_name": player_id,
                            "team": f"T{player_num % 8}",
                            "position": position,
                            "role_family": family,
                            "metric_all": metric_all,
                            "metric_normal": metric_normal,
                            "raw_opportunities_all": raw_all,
                            "raw_opportunities_normal": raw_normal,
                            "team_opportunities_all": team_opp,
                            "team_opportunities_normal": team_opp,
                            "qualifying_game": True,
                            "partial_game_flag": partial,
                            "data_quality_pass": quality,
                        }
                    )
    return pd.DataFrame(rows)
