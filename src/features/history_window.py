from __future__ import annotations

import pandas as pd


def target_sort_value(season: int, week: int) -> int:
    return int(season) * 100 + int(week)


def get_history_config(config: dict) -> tuple[int, int, int, int, str]:
    data_cfg = config["data"]
    target_season = int(data_cfg.get("target_season", data_cfg.get("projection_season")))
    target_week = int(data_cfg.get("target_week", data_cfg.get("projection_week")))
    history_start = int(data_cfg.get("history_start_season", min(data_cfg["seasons"])))
    history_end = int(data_cfg.get("history_end_season", target_season if target_week > 1 else target_season - 1))
    projection_mode = data_cfg.get("projection_mode", "historical_test")
    return history_start, history_end, target_season, target_week, projection_mode


def before_target_mask(df: pd.DataFrame, target_season: int, target_week: int) -> pd.Series:
    return (df["season"] < target_season) | ((df["season"] == target_season) & (df["week"] < target_week))


def filter_history(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    history_start, history_end, target_season, target_week, _ = get_history_config(config)
    history = df[
        (df["season"] >= history_start)
        & (df["season"] <= history_end)
        & before_target_mask(df, target_season, target_week)
    ].copy()
    return history


def latest_rows_for_target(
    history: pd.DataFrame,
    group_cols: list[str],
    target_season: int,
    target_week: int,
    zero_cols: list[str],
) -> pd.DataFrame:
    if history.empty:
        return history.copy()
    ordered = history.sort_values(group_cols + ["season", "week"])
    latest = ordered.groupby(group_cols, dropna=False).tail(1).copy()
    latest["season"] = target_season
    latest["week"] = target_week
    for col in zero_cols:
        if col in latest.columns:
            latest[col] = 0
    return latest


def add_history_audit_columns(features: pd.DataFrame, source_history: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    history_start, history_end, target_season, target_week, projection_mode = get_history_config(config)
    df = features.copy()
    if source_history.empty:
        max_training_season = pd.NA
        max_training_week = pd.NA
        seasons_used: list[int] = []
    else:
        ordered = source_history.sort_values(["season", "week"])
        max_training_season = int(ordered["season"].iloc[-1])
        max_training_week = int(ordered["week"].iloc[-1])
        seasons_used = sorted(int(season) for season in source_history["season"].dropna().unique())

    leakage_exists = False
    if not source_history.empty:
        leakage_exists = not source_history[~before_target_mask(source_history, target_season, target_week)].empty

    if leakage_exists:
        leakage_status = "FAIL"
        leakage_check = "Target-week or future-week data found in feature history."
    elif len(seasons_used) <= 1:
        leakage_status = "WARNING"
        leakage_check = "Only one historical season is available before target week."
    else:
        leakage_status = "PASS"
        leakage_check = "All feature history is before target season/week."

    player_seasons = (
        source_history.groupby("player_id", dropna=False)["season"].nunique().rename("player_history_seasons")
        if "player_id" in source_history.columns and not source_history.empty
        else pd.Series(dtype="float64", name="player_history_seasons")
    )
    if not player_seasons.empty:
        df = df.merge(player_seasons.reset_index(), on="player_id", how="left")
    else:
        df["player_history_seasons"] = 0
    df["player_history_seasons"] = df["player_history_seasons"].fillna(0).astype(int)
    df["history_depth_bucket"] = pd.cut(
        df["player_history_seasons"],
        bins=[-1, 0, 1, 2, 99],
        labels=["no player history", "1 season", "2 seasons", "3+ seasons"],
    ).astype(str)

    df["history_start_season"] = history_start
    df["history_end_season"] = history_end
    df["max_training_season"] = max_training_season
    df["max_training_week"] = max_training_week
    df["target_season"] = target_season
    df["target_week"] = target_week
    df["projection_mode"] = projection_mode
    df["leakage_check"] = leakage_check
    df["leakage_status"] = leakage_status

    counts = df["history_depth_bucket"].value_counts().to_dict()
    audit = pd.DataFrame(
        [
            {
                "seasons_loaded": ",".join(str(season) for season in config["data"]["seasons"]),
                "seasons_used_for_features": ",".join(str(season) for season in seasons_used),
                "target_season": target_season,
                "target_week": target_week,
                "max_training_season": max_training_season,
                "max_training_week": max_training_week,
                "leakage_exists": leakage_exists,
                "leakage_status": leakage_status,
                "rows_3_plus_seasons": counts.get("3+ seasons", 0),
                "rows_2_seasons": counts.get("2 seasons", 0),
                "rows_1_season": counts.get("1 season", 0),
                "rows_no_player_history": counts.get("no player history", 0),
            }
        ]
    )
    return df, audit
