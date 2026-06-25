from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.models.receptions_model import build_week_projection


def simulate_receptions_distribution(
    projection: pd.DataFrame,
    iterations: int,
    random_seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(random_seed)
    rows: list[pd.DataFrame] = []
    for _, player in projection.iterrows():
        attempts_lambda = max(float(player["projected_team_pass_attempts"]), 0.1)
        target_share = float(player["projected_target_share"])
        catch_rate = float(player["projected_catch_rate"])
        team_attempts = rng.poisson(attempts_lambda, size=iterations)
        targets = rng.binomial(team_attempts, min(max(target_share, 0), 1))
        receptions = rng.binomial(targets, min(max(catch_rate, 0), 1))
        rows.append(
            pd.DataFrame(
                {
                    "season": player["season"],
                    "week": player["week"],
                    "team": player["team"],
                    "player_id": player["player_id"],
                    "player_name": player["player_name"],
                    "iteration": np.arange(1, iterations + 1),
                    "simulated_receptions": receptions,
                }
            )
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main() -> None:
    cfg = load_config()
    projection = build_week_projection(cfg)
    sim_cfg = cfg["simulation"]
    distribution = simulate_receptions_distribution(
        projection,
        int(sim_cfg["iterations"]),
        int(sim_cfg["random_seed"]),
    )
    path = output_path("receptions_simulation_distribution.csv", cfg)
    distribution.to_csv(path, index=False)
    print(f"Wrote {path} with {len(distribution):,} simulated rows")


if __name__ == "__main__":
    main()
