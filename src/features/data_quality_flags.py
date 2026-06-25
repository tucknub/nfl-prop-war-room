from __future__ import annotations

import pandas as pd


PENALTIES = {
    "ROUTE_PROXY_UNVALIDATED": -10,
    "LOW_CURRENT_SAMPLE": -15,
    "LOW_PLAYER_SAMPLE": -15,
    "ROLE_UNCERTAIN": -20,
    "INJURY_UNCLEAR": -20,
    "MISSING_KEY_FEATURE": -30,
}


def add_data_quality_flags(features: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = features.copy()
    flags: list[list[str]] = []
    for _, row in df.iterrows():
        row_flags: list[str] = []
        if row.get("team") in (None, "", "UNK") or pd.isna(row.get("team")):
            row_flags.append("TEAM_VERIFY")
        if row.get("route_proxy_status") == "ROUTE_PROXY_UNVALIDATED":
            row_flags.append("ROUTE_PROXY_UNVALIDATED")
        if row.get("current_season_games_entering", 0) < config["features"]["low_current_sample_games"]:
            row_flags.append("LOW_CURRENT_SAMPLE")
        if row.get("career_targets_entering", 0) < config["features"]["low_player_sample_targets"]:
            row_flags.append("LOW_PLAYER_SAMPLE")
        if pd.isna(row.get("projected_target_share")) or pd.isna(row.get("projected_catch_rate")):
            row_flags.append("MISSING_KEY_FEATURE")
        flags.append(row_flags)

    df["quality_flags"] = ["|".join(items) if items else "" for items in flags]
    df["confidence_score"] = [
        None if "TEAM_VERIFY" in items else max(0, min(100, 100 + sum(PENALTIES.get(item, 0) for item in items)))
        for items in flags
    ]
    df["confidence_bucket"] = [
        "unusable" if "TEAM_VERIFY" in items else ("High" if score >= 80 else "Medium" if score >= 55 else "Low")
        for items, score in zip(flags, df["confidence_score"].fillna(0))
    ]
    report = (
        df.assign(flag=df["quality_flags"].str.split("|"))
        .explode("flag")
        .query("flag != ''")
        .groupby("flag", as_index=False)
        .size()
        .rename(columns={"size": "row_count"})
    )
    return df, report
