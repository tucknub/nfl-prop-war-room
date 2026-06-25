from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.data_quality_flags import add_data_quality_flags
from src.features.history_window import (
    add_history_audit_columns,
    filter_history,
    get_history_config,
    latest_rows_for_target,
)
from src.features.opponent_adjustments import add_opponent_adjustments
from src.features.player_catch_rate_model import build_catch_rate_projection
from src.features.player_opportunity_shares import build_player_week_features
from src.features.route_participation_proxy import build_route_proxy
from src.features.team_pace_model import build_team_week_features
from src.load.load_nflverse import load_nflverse


def build_receptions_feature_table(config: dict | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    data = load_nflverse()
    _, _, target_season, target_week, _ = get_history_config(cfg)
    pbp_history = filter_history(data["pbp"], cfg)
    weekly_history = filter_history(data["weekly"], cfg)

    team_history = build_team_week_features(pbp_history, cfg["features"]["recent_games"])
    target_team_rows = latest_rows_for_target(
        team_history,
        ["team"],
        target_season,
        target_week,
        ["team_plays", "team_pass_attempts", "team_rush_attempts", "team_tds"],
    )
    for stat in ["team_plays", "team_pass_attempts", "team_rush_attempts", "team_tds"]:
        hist_mean = (
            team_history.sort_values(["team", "season", "week"])
            .groupby("team", dropna=False)[stat]
            .apply(lambda s: s.tail(cfg["features"]["recent_games"]).mean())
            .rename(f"projected_{stat}")
            .reset_index()
        )
        target_team_rows = target_team_rows.drop(columns=[f"projected_{stat}"], errors="ignore").merge(
            hist_mean,
            on="team",
            how="left",
        )
    total_attempts = target_team_rows["projected_team_pass_attempts"] + target_team_rows["projected_team_rush_attempts"]
    target_team_rows["projected_pass_rate"] = (target_team_rows["projected_team_pass_attempts"] / total_attempts).fillna(0.58)
    target_team_rows["projected_rush_rate"] = (target_team_rows["projected_team_rush_attempts"] / total_attempts).fillna(0.42)
    target_team_rows["projected_team_tds_placeholder"] = target_team_rows["projected_team_tds"].fillna(0.0)
    team = pd.concat([team_history, target_team_rows], ignore_index=True)
    target_weekly_rows = latest_rows_for_target(
        weekly_history,
        ["player_id"],
        target_season,
        target_week,
        [
            "targets",
            "receptions",
            "receiving_yards",
            "receiving_tds",
            "air_yards",
            "games",
        ],
    )
    weekly_for_features = pd.concat([weekly_history, target_weekly_rows], ignore_index=True)
    players = build_player_week_features(
        weekly_for_features,
        cfg["features"]["min_current_games"],
        cfg["features"]["strong_current_games"],
    )
    players = build_route_proxy(players, team, cfg)
    players, catch_report = build_catch_rate_projection(players, cfg)

    target_share = players["player_week_target_share_last_4"].fillna(players["player_week_target_share_last_8"])
    prior_share = players.groupby("position", dropna=False)["player_week_target_share"].transform("median").fillna(0.04)
    games = players["current_season_games_entering"].fillna(0)
    current_weight = np.select([games >= 6, games >= 3], [0.70, 0.50], default=0.25)
    players["projected_target_share"] = (
        target_share.fillna(prior_share) * current_weight + prior_share * (1 - current_weight)
    ).clip(cfg["model"]["target_share_floor"], cfg["model"]["target_share_ceiling"])

    features = players.merge(
        team[
            [
                "season",
                "week",
                "team",
                "projected_team_plays",
                "projected_team_pass_attempts",
                "projected_team_rush_attempts",
                "projected_pass_rate",
                "projected_rush_rate",
                "projected_team_tds_placeholder",
            ]
        ],
        on=["season", "week", "team"],
        how="left",
    )
    features = add_opponent_adjustments(features)
    features, quality_report = add_data_quality_flags(features, cfg)
    features, history_audit = add_history_audit_columns(features, weekly_history, cfg)
    route_status = features.groupby("route_proxy_status", as_index=False).size().rename(columns={"size": "row_count"})

    team.to_csv(output_path("team_week_features.csv", cfg), index=False)
    players.to_csv(output_path("player_week_features.csv", cfg), index=False)
    features.to_csv(output_path("receptions_feature_table.csv", cfg), index=False)
    quality_report.to_csv(output_path("feature_quality_report.csv", cfg), index=False)
    route_status.to_csv(output_path("route_proxy_status.csv", cfg), index=False)
    catch_report.to_csv(output_path("catch_rate_model_report.csv", cfg), index=False)
    history_audit.to_csv(output_path("history_window_audit.csv", cfg), index=False)
    return features


def main() -> None:
    features = build_receptions_feature_table()
    print(f"Built receptions feature table: {len(features):,} rows")


if __name__ == "__main__":
    main()
