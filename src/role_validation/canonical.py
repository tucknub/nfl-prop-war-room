from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from role_validation.normal_game import classify_play_context


ROLE_FAMILIES = {
    "RB": ["rb_carry_share", "rb_opportunity_share"],
    "WR": ["wr_target_share"],
    "TE": ["te_target_share"],
}


@dataclass
class CanonicalBuildResult:
    canonical: pd.DataFrame
    exclusions: pd.DataFrame
    join_coverage: pd.DataFrame
    source_coverage: pd.DataFrame
    context_sensitivity: pd.DataFrame


def _regular(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in frame.columns:
        return frame.copy()
    return frame.loc[frame[column].fillna("").astype(str).str.upper().eq("REG")].copy()


def _numeric_bool(frame: pd.DataFrame, column: str, default: int = 0) -> pd.Series:
    if column not in frame:
        return pd.Series(bool(default), index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).eq(1)


def _identity_table(stats: pd.DataFrame, rosters: pd.DataFrame) -> pd.DataFrame:
    stats = _regular(stats, "season_type")
    roster = _regular(rosters, "game_type")
    stat_identity = pd.DataFrame(
        {
            "season": stats.get("season"),
            "week": stats.get("week"),
            "player_id": stats.get("player_id"),
            "team": stats.get("team"),
            "stat_player_name": stats.get("player_display_name", stats.get("player_name")),
            "stat_position": stats.get("position"),
        }
    ).drop_duplicates(["season", "week", "player_id", "team"])
    roster_identity = pd.DataFrame(
        {
            "season": roster.get("season"),
            "week": roster.get("week"),
            "player_id": roster.get("gsis_id"),
            "team": roster.get("team"),
            "roster_player_name": roster.get("full_name"),
            "roster_position": roster.get("position"),
            "active_status": roster.get("status"),
        }
    )
    roster_identity = roster_identity.drop_duplicates(
        ["season", "week", "player_id", "team"], keep="last"
    )
    identity = stat_identity.merge(
        roster_identity, on=["season", "week", "player_id", "team"], how="outer"
    )
    identity["player_name"] = identity["stat_player_name"].fillna(
        identity["roster_player_name"]
    )
    identity["position"] = (
        identity["stat_position"].fillna(identity["roster_position"])
        .fillna("").astype(str).str.upper().str.strip()
    )
    identity["identity_joined"] = (
        identity["player_id"].notna()
        & identity["player_name"].fillna("").astype(str).str.strip().ne("")
        & identity["position"].fillna("").astype(str).str.strip().ne("")
    )
    identity["identity_resolved"] = identity["identity_joined"] & identity["position"].isin(ROLE_FAMILIES)
    return identity[
        ["season", "week", "player_id", "team", "player_name", "position",
         "active_status", "identity_joined", "identity_resolved"]
    ]


def _prepare_plays(pbp: pd.DataFrame, q3_threshold: int, q4_threshold: int) -> pd.DataFrame:
    plays = _regular(pbp, "season_type")
    plays["season"] = pd.to_numeric(plays["season"], errors="coerce").astype("Int64")
    plays["week"] = pd.to_numeric(plays["week"], errors="coerce").astype("Int64")
    deleted = _numeric_bool(plays, "play_deleted")
    aborted = _numeric_bool(plays, "aborted_play")
    two_point = _numeric_bool(plays, "two_point_attempt")
    rush = _numeric_bool(plays, "rush_attempt")
    passed = _numeric_bool(plays, "pass_attempt")
    plays["valid_scrimmage_play"] = (
        plays["posteam"].notna() & ~deleted & ~aborted & ~two_point & (rush | passed)
    )
    plays = classify_play_context(plays, q3_threshold=q3_threshold, q4_threshold=q4_threshold)
    plays["is_carry"] = (
        plays["valid_scrimmage_play"] & rush & ~_numeric_bool(plays, "qb_kneel")
        & plays["rusher_player_id"].notna()
    )
    plays["is_target"] = (
        plays["valid_scrimmage_play"] & passed & ~_numeric_bool(plays, "qb_spike")
        & plays["receiver_player_id"].notna()
    )
    return plays


def _opportunities(plays: pd.DataFrame) -> pd.DataFrame:
    carry = plays.loc[plays["is_carry"], [
        "season", "week", "game_id", "play_id", "posteam", "rusher_player_id",
        "context_normal_game",
    ]].rename(columns={"posteam": "team", "rusher_player_id": "player_id"})
    carry["opportunity_type"] = "carry"
    target = plays.loc[plays["is_target"], [
        "season", "week", "game_id", "play_id", "posteam", "receiver_player_id",
        "context_normal_game",
    ]].rename(columns={"posteam": "team", "receiver_player_id": "player_id"})
    target["opportunity_type"] = "target"
    return pd.concat([carry, target], ignore_index=True)


def _participation_universe(plays: pd.DataFrame, participation: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    part = participation.rename(columns={"nflverse_game_id": "game_id"}).copy()
    part = part[[column for column in ["game_id", "play_id", "offense_players"] if column in part]]
    play_context = plays.loc[plays["valid_scrimmage_play"], [
        "season", "week", "game_id", "play_id", "posteam", "context_normal_game"
    ]].drop_duplicates(["game_id", "play_id"])
    joined = play_context.merge(part, on=["game_id", "play_id"], how="left")
    joined["participation_available"] = joined["offense_players"].fillna("").astype(str).ne("")
    expanded = joined.loc[joined["participation_available"]].copy()
    expanded["player_id"] = expanded["offense_players"].astype(str).str.split(";")
    expanded = expanded.explode("player_id")
    expanded["player_id"] = expanded["player_id"].fillna("").astype(str).str.strip()
    expanded = expanded.loc[expanded["player_id"].ne("")]
    expanded = expanded.rename(columns={"posteam": "team"})
    player_counts = (
        expanded.groupby(["season", "week", "game_id", "team", "player_id"], as_index=False)
        .agg(
            offense_plays_all=("play_id", "nunique"),
            offense_plays_normal=("context_normal_game", "sum"),
        )
    )
    team_counts = (
        joined.groupby(["season", "week", "game_id", "posteam"], as_index=False)
        .agg(
            team_offense_plays_all=("play_id", "nunique"),
            team_offense_plays_normal=("context_normal_game", "sum"),
            participation_play_coverage=("participation_available", "mean"),
        )
        .rename(columns={"posteam": "team"})
    )
    return player_counts, team_counts


def _schedule_team_rows(schedules: pd.DataFrame) -> pd.DataFrame:
    schedules = _regular(schedules, "game_type")
    home = schedules[["season", "week", "game_id", "home_team"]].rename(columns={"home_team": "team"})
    away = schedules[["season", "week", "game_id", "away_team"]].rename(columns={"away_team": "team"})
    return pd.concat([home, away], ignore_index=True).drop_duplicates(
        ["season", "week", "game_id", "team"]
    )


def _source_coverage(
    sources: dict[str, pd.DataFrame], plays: pd.DataFrame, team_participation: pd.DataFrame
) -> pd.DataFrame:
    seasons = sorted(pd.to_numeric(sources["schedules"]["season"], errors="coerce").dropna().astype(int).unique())
    rows: list[dict[str, Any]] = []
    pbp = sources["pbp"]
    stats = sources["player_stats"]
    rosters = sources["rosters_weekly"]
    schedules = _regular(sources["schedules"], "game_type")
    snaps = _regular(sources["snap_counts"], "game_type")
    injuries = _regular(sources["injuries"], "game_type")
    for season in seasons:
        p = _regular(pbp.loc[pbp["season"].eq(season)], "season_type")
        prepared = plays.loc[plays["season"].eq(season)]
        s = _regular(stats.loc[stats["season"].eq(season)], "season_type")
        r = _regular(rosters.loc[rosters["season"].eq(season)], "game_type")
        sc = schedules.loc[schedules["season"].eq(season)]
        sn = snaps.loc[snaps["season"].eq(season)]
        inj = injuries.loc[injuries["season"].eq(season)]
        tp = team_participation.loc[team_participation["season"].eq(season)]
        rows.append(
            {
                "season": season,
                "pbp_rows": len(p),
                "pbp_games": p["game_id"].nunique(),
                "schedule_games": sc["game_id"].nunique(),
                "regular_weeks": prepared["week"].nunique(),
                "player_stat_rows": len(s),
                "player_stats_game_id_missing_rate": float(s["game_id"].isna().mean()) if len(s) else np.nan,
                "roster_rows": len(r),
                "snap_rows": len(sn),
                "injury_rows": len(inj),
                "scrimmage_plays": int(prepared["valid_scrimmage_play"].sum()),
                "participation_play_coverage": float(
                    np.average(tp["participation_play_coverage"], weights=tp["team_offense_plays_all"])
                ) if len(tp) else np.nan,
                "carry_player_id_coverage": float(
                    prepared.loc[
                        prepared["valid_scrimmage_play"]
                        & _numeric_bool(prepared, "rush_attempt")
                        & ~_numeric_bool(prepared, "qb_kneel"),
                        "rusher_player_id",
                    ].notna().mean()
                ),
                "target_player_id_coverage": float(
                    prepared.loc[
                        prepared["valid_scrimmage_play"]
                        & _numeric_bool(prepared, "pass_attempt")
                        & ~_numeric_bool(prepared, "qb_spike"),
                        "receiver_player_id",
                    ].notna().mean()
                ),
            }
        )
    result = pd.DataFrame(rows)
    result["complete_schema_and_games"] = (
        result["pbp_games"].eq(result["schedule_games"])
        & result["participation_play_coverage"].ge(0.99)
        & result["carry_player_id_coverage"].ge(0.99)
    )
    return result


def context_sensitivity_table(pbp: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    base = _regular(pbp.loc[pbp["season"].isin(seasons)], "season_type")
    rows = []
    for q3 in [21, 24, 28]:
        for q4 in [14, 17, 21]:
            classified = classify_play_context(base, q3_threshold=q3, q4_threshold=q4)
            valid = (
                classified["posteam"].notna()
                & (_numeric_bool(classified, "rush_attempt") | _numeric_bool(classified, "pass_attempt"))
                & ~_numeric_bool(classified, "play_deleted")
                & ~_numeric_bool(classified, "aborted_play")
                & ~_numeric_bool(classified, "two_point_attempt")
            )
            rows.append(
                {
                    "q3_threshold": q3,
                    "q4_threshold": q4,
                    "valid_scrimmage_plays": int(valid.sum()),
                    "normal_game_plays": int((valid & classified["context_normal_game"]).sum()),
                    "garbage_time_plays": int((valid & classified["context_garbage_time"]).sum()),
                    "overtime_plays": int((valid & classified["context_overtime"]).sum()),
                    "competitive_two_minute_plays": int(
                        (valid & classified["context_two_minute"] & ~classified["context_garbage_time"]).sum()
                    ),
                }
            )
    return pd.DataFrame(rows)


def build_canonical_player_week_role(
    sources: dict[str, pd.DataFrame],
    seasons: list[int],
    q3_threshold: int = 24,
    q4_threshold: int = 17,
    source_version: str = "nflverse via nflreadpy",
) -> CanonicalBuildResult:
    """Build one row per season-week-player-team-role family.

    The required partial-game field is populated, but marked unreliable because
    the supplied nflverse tables contain no trustworthy in-game exit indicator.
    This limitation blocks a public persistence claim and is emitted separately.
    """
    plays = _prepare_plays(sources["pbp"], q3_threshold, q4_threshold)
    plays = plays.loc[plays["season"].isin(seasons)].copy()
    opportunities = _opportunities(plays)
    identity = _identity_table(sources["player_stats"], sources["rosters_weekly"])
    identity = identity.loc[identity["season"].isin(seasons)]
    player_participation, team_participation = _participation_universe(
        plays, sources["participation"]
    )

    opportunity_counts = (
        opportunities.assign(normal=lambda x: x["context_normal_game"].astype(int))
        .pivot_table(
            index=["season", "week", "game_id", "team", "player_id"],
            columns="opportunity_type",
            values=["play_id", "normal"],
            aggfunc={"play_id": "count", "normal": "sum"},
            fill_value=0,
        )
    )
    opportunity_counts.columns = [
        f"{kind}_{opp}" for kind, opp in opportunity_counts.columns.to_flat_index()
    ]
    opportunity_counts = opportunity_counts.reset_index().rename(
        columns={
            "play_id_carry": "carries_all", "normal_carry": "carries_normal",
            "play_id_target": "targets_all", "normal_target": "targets_normal",
        }
    )
    for column in ["carries_all", "carries_normal", "targets_all", "targets_normal"]:
        if column not in opportunity_counts:
            opportunity_counts[column] = 0

    universe_keys = pd.concat(
        [
            player_participation[["season", "week", "game_id", "team", "player_id"]],
            opportunity_counts[["season", "week", "game_id", "team", "player_id"]],
        ],
        ignore_index=True,
    ).drop_duplicates()
    players = universe_keys.merge(
        player_participation,
        on=["season", "week", "game_id", "team", "player_id"],
        how="left",
    ).merge(
        opportunity_counts,
        on=["season", "week", "game_id", "team", "player_id"],
        how="left",
    ).merge(identity, on=["season", "week", "player_id", "team"], how="left")
    count_columns = [
        "offense_plays_all", "offense_plays_normal", "carries_all", "carries_normal",
        "targets_all", "targets_normal",
    ]
    players[count_columns] = players[count_columns].fillna(0)

    team_opportunities = (
        opportunities.assign(normal=lambda x: x["context_normal_game"].astype(int))
        .pivot_table(
            index=["season", "week", "game_id", "team"],
            columns="opportunity_type",
            values=["play_id", "normal"],
            aggfunc={"play_id": "count", "normal": "sum"},
            fill_value=0,
        )
    )
    team_opportunities.columns = [
        f"team_{kind}_{opp}" for kind, opp in team_opportunities.columns.to_flat_index()
    ]
    team_opportunities = team_opportunities.reset_index().rename(
        columns={
            "team_play_id_carry": "team_carries_all",
            "team_normal_carry": "team_carries_normal",
            "team_play_id_target": "team_targets_all",
            "team_normal_target": "team_targets_normal",
        }
    )
    for column in ["team_carries_all", "team_carries_normal", "team_targets_all", "team_targets_normal"]:
        if column not in team_opportunities:
            team_opportunities[column] = 0

    opportunity_identity = opportunities.merge(
        identity[["season", "week", "player_id", "team", "position", "identity_joined", "identity_resolved"]],
        on=["season", "week", "player_id", "team"], how="left"
    )
    rb_opps = opportunity_identity.loc[opportunity_identity["position"].eq("RB")].copy()
    rb_team = (
        rb_opps.groupby(["season", "week", "game_id", "team"], as_index=False)
        .agg(
            team_rb_opportunities_all=("play_id", "count"),
            team_rb_opportunities_normal=("context_normal_game", "sum"),
        )
    )
    players = players.merge(team_opportunities, on=["season", "week", "game_id", "team"], how="left")
    players = players.merge(rb_team, on=["season", "week", "game_id", "team"], how="left")
    players = players.merge(team_participation, on=["season", "week", "game_id", "team"], how="left")
    schedule_team = _schedule_team_rows(sources["schedules"])
    schedule_team = schedule_team.loc[schedule_team["season"].isin(seasons)]
    players = players.merge(
        schedule_team.assign(schedule_match=True),
        on=["season", "week", "game_id", "team"], how="left"
    )
    players["game_partition_complete"] = (
        players["schedule_match"].fillna(False)
        & players["participation_play_coverage"].fillna(0).ge(0.99)
    )
    players["snap_share"] = (
        players["offense_plays_all"] / players["team_offense_plays_all"].replace(0, np.nan)
    )

    eligible_players = players.loc[players["position"].isin(ROLE_FAMILIES)].copy()
    family_rows = []
    for position, families in ROLE_FAMILIES.items():
        subset = eligible_players.loc[eligible_players["position"].eq(position)].copy()
        for family in families:
            row = subset.copy()
            row["role_family"] = family
            if family == "rb_carry_share":
                row["raw_opportunities_all"] = row["carries_all"]
                row["raw_opportunities_normal"] = row["carries_normal"]
                row["team_opportunities_all"] = row["team_carries_all"]
                row["team_opportunities_normal"] = row["team_carries_normal"]
            elif family == "rb_opportunity_share":
                row["raw_opportunities_all"] = row["carries_all"] + row["targets_all"]
                row["raw_opportunities_normal"] = row["carries_normal"] + row["targets_normal"]
                row["team_opportunities_all"] = row["team_rb_opportunities_all"]
                row["team_opportunities_normal"] = row["team_rb_opportunities_normal"]
            else:
                row["raw_opportunities_all"] = row["targets_all"]
                row["raw_opportunities_normal"] = row["targets_normal"]
                row["team_opportunities_all"] = row["team_targets_all"]
                row["team_opportunities_normal"] = row["team_targets_normal"]
            family_rows.append(row)
    canonical = pd.concat(family_rows, ignore_index=True)
    canonical["metric_all"] = canonical["raw_opportunities_all"] / canonical["team_opportunities_all"].replace(0, np.nan)
    canonical["metric_normal"] = canonical["raw_opportunities_normal"] / canonical["team_opportunities_normal"].replace(0, np.nan)
    canonical["partial_game_flag"] = False
    canonical["partial_game_flag_reliable"] = False
    canonical["late_backup_flag"] = False
    canonical["late_backup_flag_reliable"] = False
    canonical["identity_resolved"] = canonical["identity_resolved"].fillna(False)
    canonical["data_quality_pass"] = (
        canonical["identity_resolved"]
        & canonical["game_partition_complete"]
        & canonical["team_opportunities_all"].gt(0)
        & canonical["team_opportunities_normal"].gt(0)
        & canonical["metric_all"].between(0, 1)
        & canonical["metric_normal"].between(0, 1)
    )
    canonical["qualifying_game"] = canonical["data_quality_pass"]
    canonical["source_version"] = source_version

    output_columns = [
        "season", "week", "game_id", "player_id", "player_name", "team", "position",
        "role_family", "metric_all", "metric_normal", "raw_opportunities_all",
        "raw_opportunities_normal", "team_opportunities_all", "team_opportunities_normal",
        "qualifying_game", "partial_game_flag", "data_quality_pass", "active_status",
        "snap_share", "late_backup_flag", "partial_game_flag_reliable",
        "late_backup_flag_reliable", "identity_resolved", "game_partition_complete",
        "participation_play_coverage", "source_version",
    ]
    canonical = canonical[output_columns].sort_values(
        ["season", "week", "player_id", "team", "role_family"]
    ).reset_index(drop=True)

    excluded = canonical.loc[~canonical["data_quality_pass"]].copy()
    if len(excluded):
        excluded["reason_code"] = np.select(
            [
                ~excluded["identity_resolved"].fillna(False).astype(bool).to_numpy(),
                ~excluded["game_partition_complete"].fillna(False).astype(bool).to_numpy(),
                excluded["team_opportunities_all"].le(0).fillna(True).to_numpy(dtype=bool),
                excluded["team_opportunities_normal"].le(0).fillna(True).to_numpy(dtype=bool),
            ],
            ["IDENTITY_UNRESOLVED", "INCOMPLETE_GAME_PARTITION", "ZERO_ALL_DENOMINATOR", "ZERO_NORMAL_DENOMINATOR"],
            default="INVALID_SHARE",
        )
    exclusions = excluded[[
        "season", "week", "game_id", "player_id", "player_name", "team", "position",
        "role_family", "reason_code",
    ]] if len(excluded) else pd.DataFrame(columns=[
        "season", "week", "game_id", "player_id", "player_name", "team", "position",
        "role_family", "reason_code",
    ])

    coverage_rows = []
    for season in seasons:
        opp = opportunity_identity.loc[opportunity_identity["season"].eq(season)]
        part_players = players.loc[players["season"].eq(season)]
        coverage_rows.extend(
            [
                {
                    "season": season, "join": "opportunity_to_identity", "rows": len(opp),
                    "matched_rows": int(opp["identity_joined"].fillna(False).sum()),
                },
                {
                    "season": season, "join": "participating_player_to_identity", "rows": len(part_players),
                    "matched_rows": int(part_players["identity_joined"].fillna(False).sum()),
                },
            ]
        )
    join_coverage = pd.DataFrame(coverage_rows)
    join_coverage["coverage_rate"] = join_coverage["matched_rows"] / join_coverage["rows"].replace(0, np.nan)

    all_prepared_plays = _prepare_plays(sources["pbp"], q3_threshold, q4_threshold)
    _, all_team_participation = _participation_universe(all_prepared_plays, sources["participation"])
    source_coverage = _source_coverage(sources, all_prepared_plays, all_team_participation)
    sensitivity = context_sensitivity_table(sources["pbp"], [season for season in seasons if 2018 <= season <= 2020])
    return CanonicalBuildResult(canonical, exclusions, join_coverage, source_coverage, sensitivity)
