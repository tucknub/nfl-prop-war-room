from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


INJURY_MENTION_PATTERN = re.compile(
    r"\b(?P<team>[A-Z]{2,3})-(?P<jersey>\d{1,3})-"
    r"(?P<abbreviation>[A-Za-z][A-Za-z.'\-]*) was injured during the play",
    flags=re.IGNORECASE,
)
RETURN_STATUS_PATTERN = re.compile(
    r"(?:He|She) is (?P<out>Out)|(?:His|Her) return is (?P<return_status>Probable|Questionable|Doubtful)",
    flags=re.IGNORECASE,
)


@dataclass
class PartialGameResult:
    canonical: pd.DataFrame
    evidence_ledger: pd.DataFrame
    source_coverage: pd.DataFrame


def _normalize_team(team: str, season: int) -> str:
    normalized = str(team).upper().strip()
    if normalized == "LV" and season <= 2019:
        return "OAK"
    if normalized == "STL":
        return "LA"
    return normalized


def load_explicit_injury_sources(
    seasons: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load only the requested seasons from nflverse for explicit PBP evidence."""
    allowed = {2018, 2019, 2020, 2021, 2022, 2023, 2024}
    if not set(seasons).issubset(allowed):
        raise ValueError(f"Explicit injury evidence is restricted to {sorted(allowed)}")
    import nflreadpy as nfl

    pbp_parts: list[pd.DataFrame] = []
    roster_parts: list[pd.DataFrame] = []
    for season in seasons:
        pbp = nfl.load_pbp([season]).select(
            ["season", "week", "season_type", "game_id", "play_id", "desc"]
        ).to_pandas()
        pbp_parts.append(pbp.loc[pbp["season_type"].eq("REG")].copy())
        roster = nfl.load_rosters_weekly([season]).select(
            [
                "season",
                "week",
                "game_type",
                "team",
                "jersey_number",
                "gsis_id",
                "full_name",
                "position",
            ]
        ).to_pandas()
        roster_parts.append(roster.loc[roster["game_type"].eq("REG")].copy())
    schedules = nfl.load_schedules(seasons).select(
        [
            "season",
            "week",
            "game_type",
            "game_id",
            "gameday",
            "gametime",
            "home_team",
            "away_team",
        ]
    ).to_pandas()
    schedules = schedules.loc[schedules["game_type"].eq("REG")].copy()
    for name, frame in {
        "pbp": pd.concat(pbp_parts, ignore_index=True),
        "rosters": pd.concat(roster_parts, ignore_index=True),
        "schedules": schedules,
    }.items():
        observed = set(pd.to_numeric(frame["season"], errors="raise").astype(int).unique())
        if observed != set(seasons):
            raise AssertionError(
                f"{name} seasons differ from requested seasons: {sorted(observed)}"
            )
    return (
        pd.concat(pbp_parts, ignore_index=True),
        pd.concat(roster_parts, ignore_index=True),
        schedules,
    )


def extract_explicit_injury_mentions(
    pbp_descriptions: pd.DataFrame,
    rosters: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse official PBP injury statements and resolve jersey/team to GSIS."""
    parsed_columns = [
        "season",
        "week",
        "game_id",
        "injury_play_id",
        "team",
        "jersey_number_normalized",
        "pbp_player_abbreviation",
        "pbp_return_status",
        "pbp_description",
        "evidence_source",
        "evidence_type",
    ]
    mentions: list[dict[str, Any]] = []
    for row in pbp_descriptions.itertuples(index=False):
        description = "" if pd.isna(row.desc) else str(row.desc)
        for match in INJURY_MENTION_PATTERN.finditer(description):
            sentence_tail = description[match.end() : match.end() + 140]
            status_match = RETURN_STATUS_PATTERN.search(sentence_tail)
            if status_match and status_match.group("out"):
                return_status = "Out"
            elif status_match:
                return_status = str(status_match.group("return_status")).title()
            else:
                return_status = "Unspecified"
            season = int(row.season)
            mentions.append(
                {
                    "season": season,
                    "week": int(row.week),
                    "game_id": row.game_id,
                    "injury_play_id": float(row.play_id),
                    "team": _normalize_team(match.group("team"), season),
                    "jersey_number_normalized": str(int(match.group("jersey"))),
                    "pbp_player_abbreviation": match.group("abbreviation"),
                    "pbp_return_status": return_status,
                    "pbp_description": description,
                    "evidence_source": "nflverse official play-by-play description",
                    "evidence_type": "EXPLICIT_IN_GAME_INJURY_MENTION",
                }
            )
    parsed = pd.DataFrame(mentions, columns=parsed_columns).drop_duplicates(
        [
            "season",
            "week",
            "game_id",
            "injury_play_id",
            "team",
            "jersey_number_normalized",
            "pbp_player_abbreviation",
        ]
    )
    if parsed.empty:
        joined = parsed.assign(
            player_id=pd.Series(dtype="object"),
            roster_player_name=pd.Series(dtype="object"),
            roster_position=pd.Series(dtype="object"),
            identity_resolution=pd.Series(dtype="object"),
        )
        coverage = pd.DataFrame(
            [
                {
                    "parsed_injury_mentions": 0,
                    "resolved_injury_mentions": 0,
                    "unresolved_injury_mentions": 0,
                    "resolution_rate": np.nan,
                    "ambiguous_roster_universe_keys_excluded": 0,
                }
            ]
        )
        return joined, coverage
    roster = rosters.copy()
    roster["team"] = [
        _normalize_team(team, int(season))
        for team, season in zip(roster["team"], roster["season"])
    ]
    roster["jersey_number_normalized"] = (
        pd.to_numeric(roster["jersey_number"], errors="coerce")
        .astype("Int64")
        .astype(str)
        .replace("<NA>", "")
    )
    roster = roster.loc[
        roster["gsis_id"].notna() & roster["jersey_number_normalized"].ne("")
    ].copy()
    roster_key = ["season", "week", "team", "jersey_number_normalized"]
    identities = roster[
        [*roster_key, "gsis_id", "full_name", "position"]
    ].drop_duplicates([*roster_key, "gsis_id"])
    identities["_identity_count"] = identities.groupby(
        roster_key, dropna=False
    )["gsis_id"].transform("nunique")
    ambiguous_keys = int(
        identities.loc[identities["_identity_count"].gt(1), roster_key]
        .drop_duplicates()
        .shape[0]
    )
    resolved = (
        identities.loc[identities["_identity_count"].eq(1)]
        .drop_duplicates(roster_key)
        .rename(
            columns={
                "gsis_id": "player_id",
                "full_name": "roster_player_name",
                "position": "roster_position",
            }
        )
        .drop(columns="_identity_count")
    )
    joined = parsed.merge(resolved, on=roster_key, how="left", indicator=True)
    joined["identity_resolution"] = np.select(
        [joined["player_id"].notna()],
        ["GSIS_TEAM_WEEK_JERSEY"],
        default="UNRESOLVED",
    )
    coverage = pd.DataFrame(
        [
            {
                "parsed_injury_mentions": len(parsed),
                "resolved_injury_mentions": int(joined["player_id"].notna().sum()),
                "unresolved_injury_mentions": int(joined["player_id"].isna().sum()),
                "resolution_rate": float(joined["player_id"].notna().mean()) if len(joined) else np.nan,
                "ambiguous_roster_universe_keys_excluded": ambiguous_keys,
            }
        ]
    )
    return joined, coverage


def _confirmed_no_return_mask(frame: pd.DataFrame) -> pd.Series:
    """Require global play ordering and five later focal-team offensive plays."""
    return frame["last_offensive_play_id"].le(frame["injury_play_id"]) & frame[
        "focal_team_offensive_plays_after_injury"
    ].ge(5)


def _schedule_with_kickoffs(schedules: pd.DataFrame) -> pd.DataFrame:
    schedule = schedules.copy()
    if "game_type" in schedule:
        schedule = schedule.loc[schedule["game_type"].eq("REG")].copy()
    local = pd.to_datetime(
        schedule["gameday"].astype(str) + " " + schedule["gametime"].astype(str),
        errors="coerce",
    )
    # nflverse schedule times are Eastern. A conservative six-hour availability
    # proxy ensures the official PBP evidence is treated as available after game end.
    schedule["trigger_kickoff_utc"] = local.dt.tz_localize(
        ZoneInfo("America/New_York"), ambiguous="NaT", nonexistent="shift_forward"
    ).dt.tz_convert("UTC")
    schedule["trigger_end_proxy_utc"] = schedule["trigger_kickoff_utc"] + pd.Timedelta(
        hours=6
    )
    return schedule[
        [
            "season",
            "week",
            "game_id",
            "home_team",
            "away_team",
            "trigger_kickoff_utc",
            "trigger_end_proxy_utc",
        ]
    ].drop_duplicates("game_id")


def build_participation_sequence(
    selected_pbp: pd.DataFrame,
    participation: pd.DataFrame,
    seasons: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build player first/last offensive appearance from GSIS-native participation."""
    import polars as pl

    plays = selected_pbp.loc[
        pd.to_numeric(selected_pbp["season"], errors="coerce").isin(seasons)
    ].copy()
    if "season_type" in plays:
        plays = plays.loc[plays["season_type"].eq("REG")]
    numeric = lambda column: pd.to_numeric(plays[column], errors="coerce").fillna(0).eq(1)
    valid = (
        plays["posteam"].notna()
        & (numeric("rush_attempt") | numeric("pass_attempt"))
        & ~numeric("play_deleted")
        & ~numeric("aborted_play")
        & ~numeric("two_point_attempt")
    )
    play_context = plays.loc[
        valid, ["season", "week", "game_id", "play_id", "posteam"]
    ].drop_duplicates(["game_id", "play_id"])
    play_context = play_context.sort_values(["game_id", "posteam", "play_id"])
    play_context["team_play_ordinal"] = (
        play_context.groupby(["game_id", "posteam"]).cumcount() + 1
    )
    play_context["team_offensive_plays"] = play_context.groupby(
        ["game_id", "posteam"]
    )["play_id"].transform("count")
    part = participation.rename(columns={"nflverse_game_id": "game_id"})[
        ["game_id", "play_id", "offense_players"]
    ].copy()
    joined = pl.from_pandas(play_context).join(
        pl.from_pandas(part), on=["game_id", "play_id"], how="left"
    ).with_columns(
        pl.col("offense_players")
        .fill_null("")
        .ne("")
        .alias("participation_available")
    )
    expanded = (
        joined.filter(pl.col("participation_available"))
        .with_columns(
            pl.col("offense_players")
            .str.split(";")
            .alias("player_id")
        )
        .explode("player_id")
        .with_columns(pl.col("player_id").str.strip_chars())
        .filter(pl.col("player_id").ne(""))
    )
    player = (
        expanded.group_by(
            ["season", "week", "game_id", "posteam", "player_id"],
            maintain_order=True,
        )
        .agg(
            pl.col("play_id").n_unique().alias("participation_offense_plays"),
            pl.col("play_id").max().alias("last_offensive_play_id"),
            pl.col("team_play_ordinal").min().alias("first_team_play_ordinal"),
            pl.col("team_play_ordinal").max().alias("last_team_play_ordinal"),
            pl.col("team_offensive_plays").max().alias("team_offensive_plays"),
        )
        .rename({"posteam": "team"})
        .to_pandas()
    )
    player["last_appearance_fraction"] = (
        player["last_team_play_ordinal"] / player["team_offensive_plays"].replace(0, np.nan)
    )
    player["trailing_team_plays"] = (
        player["team_offensive_plays"] - player["last_team_play_ordinal"]
    )
    team_coverage = (
        joined.group_by(
            ["season", "week", "game_id", "posteam"], maintain_order=True
        )
        .agg(
            pl.col("play_id").n_unique().alias("team_offensive_plays"),
            pl.col("participation_available").mean().alias("participation_play_coverage"),
        )
        .rename({"posteam": "team"})
        .to_pandas()
    )
    return player, team_coverage


def _prior_snap_features(
    canonical: pd.DataFrame, schedule: pd.DataFrame
) -> pd.DataFrame:
    unique = canonical.drop_duplicates(
        ["season", "week", "game_id", "player_id", "team"]
    ).merge(
        schedule[["game_id", "trigger_kickoff_utc"]],
        on="game_id",
        how="left",
        validate="many_to_one",
    ).sort_values(
        ["player_id", "season", "trigger_kickoff_utc", "week", "team"]
    )
    unique["prior_snap_n"] = 0
    unique["prior_three_median_snap_share"] = np.nan
    for _, indices in unique.groupby(["player_id", "season"], sort=False).groups.items():
        history: list[float] = []
        for index in indices:
            eligible_history = history[-3:]
            unique.at[index, "prior_snap_n"] = len(eligible_history)
            if eligible_history:
                unique.at[index, "prior_three_median_snap_share"] = float(
                    np.median(eligible_history)
                )
            value = pd.to_numeric(unique.at[index, "snap_share"], errors="coerce")
            if pd.notna(value) and bool(unique.at[index, "data_quality_pass"]):
                history.append(float(value))
    return unique[
        [
            "season",
            "week",
            "game_id",
            "player_id",
            "team",
            "prior_snap_n",
            "prior_three_median_snap_share",
        ]
    ]


def _next_player_game(canonical: pd.DataFrame, schedule: pd.DataFrame) -> pd.DataFrame:
    """Attach the current team's next scheduled regular-season kickoff.

    The temporal boundary is the team's following scheduled game, including games
    the player later missed. Using the player's next appearance would make the
    evidence window too permissive for players who were inactive for several weeks.
    """
    unique = canonical[
        ["season", "week", "game_id", "player_id", "team"]
    ].drop_duplicates()
    home = schedule[
        [
            "season",
            "game_id",
            "home_team",
            "trigger_kickoff_utc",
            "trigger_end_proxy_utc",
        ]
    ].rename(columns={"home_team": "team"})
    away = schedule[
        [
            "season",
            "game_id",
            "away_team",
            "trigger_kickoff_utc",
            "trigger_end_proxy_utc",
        ]
    ].rename(columns={"away_team": "team"})
    team_games = pd.concat([home, away], ignore_index=True).sort_values(
        ["season", "team", "trigger_kickoff_utc", "game_id"]
    )
    team_games["_team_join"] = [
        _normalize_team(team, int(season))
        for team, season in zip(team_games["team"], team_games["season"])
    ]
    team_games["next_game_kickoff_utc"] = team_games.groupby(
        ["season", "_team_join"], sort=False
    )["trigger_kickoff_utc"].shift(-1)
    team_games = team_games.drop(columns="team")
    unique["_team_join"] = [
        _normalize_team(team, int(season))
        for team, season in zip(unique["team"], unique["season"])
    ]
    unique = unique.merge(
        team_games,
        on=["season", "game_id", "_team_join"],
        how="left",
        validate="many_to_one",
    ).drop(columns="_team_join").sort_values(
        ["player_id", "season", "week", "game_id"]
    )
    return unique


def _postgame_injury_report_evidence(
    player_games: pd.DataFrame,
    injuries: pd.DataFrame,
) -> pd.DataFrame:
    injury = injuries.copy()
    if "game_type" in injury:
        injury = injury.loc[injury["game_type"].eq("REG")]
    injury["injury_report_timestamp_utc"] = pd.to_datetime(
        injury["date_modified"], errors="coerce", utc=True
    )
    injury = injury.loc[
        injury["gsis_id"].notna() & injury["injury_report_timestamp_utc"].notna()
    ]
    grouped = {
        (int(season), player_id): group.sort_values("injury_report_timestamp_utc")
        for (season, player_id), group in injury.groupby(["season", "gsis_id"])
    }
    rows: list[dict[str, Any]] = []
    for row in player_games.itertuples(index=False):
        matches = grouped.get((int(row.season), row.player_id))
        if matches is None or pd.isna(row.trigger_end_proxy_utc) or pd.isna(
            row.next_game_kickoff_utc
        ):
            continue
        window = matches.loc[
            matches["injury_report_timestamp_utc"].gt(row.trigger_end_proxy_utc)
            & matches["injury_report_timestamp_utc"].lt(row.next_game_kickoff_utc)
        ].copy()
        if window.empty:
            continue
        explicit = window.loc[window["report_status"].notna()]
        chosen = (explicit if not explicit.empty else window).iloc[0]
        rows.append(
            {
                "season": int(row.season),
                "week": int(row.week),
                "game_id": row.game_id,
                "player_id": row.player_id,
                "postgame_injury_report": True,
                "injury_report_status": chosen["report_status"],
                "injury_report_timestamp_utc": chosen["injury_report_timestamp_utc"],
                "injury_report_team": chosen["team"],
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "season",
            "week",
            "game_id",
            "player_id",
            "postgame_injury_report",
            "injury_report_status",
            "injury_report_timestamp_utc",
            "injury_report_team",
        ],
    )


def build_partial_game_status(
    canonical: pd.DataFrame,
    *,
    selected_pbp: pd.DataFrame,
    participation: pd.DataFrame,
    injuries: pd.DataFrame,
    explicit_pbp: pd.DataFrame,
    full_rosters: pd.DataFrame,
    schedules: pd.DataFrame,
    seasons: list[int],
) -> PartialGameResult:
    """Create confirmed/suspected flags without treating usage alone as confirmed."""
    data = canonical.loc[canonical["season"].isin(seasons)].copy()
    schedule = _schedule_with_kickoffs(schedules)
    player_games = _next_player_game(data, schedule)
    participation_player, participation_coverage = build_participation_sequence(
        selected_pbp, participation, seasons
    )
    snap_features = _prior_snap_features(data, schedule)
    mentions, mention_coverage = extract_explicit_injury_mentions(
        explicit_pbp, full_rosters
    )
    reports = _postgame_injury_report_evidence(player_games, injuries)

    enriched = data.merge(
        participation_player,
        on=["season", "week", "game_id", "player_id", "team"],
        how="left",
    ).merge(
        snap_features,
        on=["season", "week", "game_id", "player_id", "team"],
        how="left",
    ).merge(
        player_games[
            [
                "season",
                "week",
                "game_id",
                "player_id",
                "team",
                "trigger_kickoff_utc",
                "trigger_end_proxy_utc",
                "next_game_kickoff_utc",
            ]
        ],
        on=["season", "week", "game_id", "player_id", "team"],
        how="left",
    ).merge(
        reports,
        on=["season", "week", "game_id", "player_id"],
        how="left",
    )

    mention_columns = [
        "season",
        "week",
        "game_id",
        "player_id",
        "injury_play_id",
        "pbp_return_status",
        "pbp_description",
        "evidence_source",
        "evidence_type",
        "identity_resolution",
    ]
    resolved_mentions = mentions.loc[mentions["player_id"].notna(), mention_columns].copy()
    # Multiple explicit mentions for one player-game are collapsed to the strongest
    # return designation and earliest play, with all descriptions retained.
    status_rank = {"Out": 4, "Doubtful": 3, "Questionable": 2, "Probable": 1, "Unspecified": 0}
    resolved_mentions["_status_rank"] = resolved_mentions["pbp_return_status"].map(status_rank).fillna(0)
    mention_rows: list[dict[str, Any]] = []
    for key, group in resolved_mentions.groupby(
        ["season", "week", "game_id", "player_id"], sort=False
    ):
        strongest = group.sort_values(
            ["_status_rank", "injury_play_id"], ascending=[False, True]
        ).iloc[0]
        mention_rows.append(
            {
                "season": key[0],
                "week": key[1],
                "game_id": key[2],
                "player_id": key[3],
                "explicit_pbp_injury": True,
                "injury_play_id": float(group["injury_play_id"].min()),
                "pbp_return_status": strongest["pbp_return_status"],
                "pbp_description": " || ".join(group["pbp_description"].drop_duplicates()),
                "evidence_source": strongest["evidence_source"],
                "evidence_type": strongest["evidence_type"],
                "identity_resolution": strongest["identity_resolution"],
            }
        )
    mention_game = pd.DataFrame(
        mention_rows,
        columns=[
            "season",
            "week",
            "game_id",
            "player_id",
            "explicit_pbp_injury",
            "injury_play_id",
            "pbp_return_status",
            "pbp_description",
            "evidence_source",
            "evidence_type",
            "identity_resolution",
        ],
    )
    enriched = enriched.merge(
        mention_game,
        on=["season", "week", "game_id", "player_id"],
        how="left",
    )

    enriched["snap_share_drop"] = (
        pd.to_numeric(enriched["prior_three_median_snap_share"], errors="coerce")
        - pd.to_numeric(enriched["snap_share"], errors="coerce")
    )
    enriched["suspected_partial_game"] = (
        enriched["prior_snap_n"].ge(2)
        & enriched["prior_three_median_snap_share"].ge(0.50)
        & pd.to_numeric(enriched["snap_share"], errors="coerce").le(0.50)
        & enriched["snap_share_drop"].ge(0.30)
        & enriched["last_appearance_fraction"].le(0.75)
        & enriched["trailing_team_plays"].ge(5)
        & enriched["data_quality_pass"].fillna(False).astype(bool)
    )
    enriched["suspected_partial_corroborated"] = (
        enriched["suspected_partial_game"]
        & (
            enriched["explicit_pbp_injury"].fillna(False).astype(bool)
            | enriched["postgame_injury_report"].fillna(False).astype(bool)
        )
    )
    explicit = enriched["explicit_pbp_injury"].fillna(False).astype(bool)
    # Use global play_id ordering for the player's return check. Team-specific play
    # ordinals cannot be compared when an injury occurs on defense or special teams.
    ordinal_source = selected_pbp.loc[selected_pbp["season"].isin(seasons)].copy()
    ordinal_numeric = lambda column: pd.to_numeric(
        ordinal_source[column], errors="coerce"
    ).fillna(0).eq(1)
    ordinal_valid = (
        ordinal_source["posteam"].notna()
        & (ordinal_numeric("rush_attempt") | ordinal_numeric("pass_attempt"))
        & ~ordinal_numeric("play_deleted")
        & ~ordinal_numeric("aborted_play")
        & ~ordinal_numeric("two_point_attempt")
    )
    focal_offensive_plays = (
        ordinal_source.loc[ordinal_valid, ["game_id", "play_id", "posteam"]]
        .drop_duplicates(["game_id", "play_id"])
        .rename(columns={"posteam": "team"})
    )
    injury_keys = enriched.loc[
        enriched["injury_play_id"].notna(), ["game_id", "team", "injury_play_id"]
    ].drop_duplicates()
    play_arrays = {
        key: np.sort(pd.to_numeric(group["play_id"], errors="coerce").dropna().to_numpy())
        for key, group in focal_offensive_plays.groupby(["game_id", "team"], sort=False)
    }
    injury_keys["focal_team_offensive_plays_after_injury"] = [
        int(
            len(play_arrays.get((game_id, team), np.array([], dtype=float)))
            - np.searchsorted(
                play_arrays.get((game_id, team), np.array([], dtype=float)),
                float(injury_play_id),
                side="right",
            )
        )
        for game_id, team, injury_play_id in injury_keys.itertuples(index=False, name=None)
    ]
    enriched = enriched.merge(
        injury_keys,
        on=["game_id", "team", "injury_play_id"],
        how="left",
    )
    no_return_after_injury = _confirmed_no_return_mask(enriched)
    explicit_out = enriched["pbp_return_status"].isin(["Out", "Doubtful"])
    temporal_window_valid = (
        enriched["trigger_end_proxy_utc"].notna()
        & enriched["next_game_kickoff_utc"].notna()
        & enriched["trigger_end_proxy_utc"].lt(enriched["next_game_kickoff_utc"])
    )
    representative_role_drop = (
        enriched["prior_snap_n"].ge(2)
        & enriched["prior_three_median_snap_share"].ge(0.35)
        & enriched["snap_share_drop"].ge(0.20)
        & pd.to_numeric(enriched["snap_share"], errors="coerce").le(0.65)
    )
    enriched["confirmed_partial_game"] = (
        explicit
        & no_return_after_injury
        & (explicit_out | enriched["suspected_partial_game"])
        & temporal_window_valid
        & representative_role_drop
    )
    confirmed = enriched.loc[enriched["confirmed_partial_game"]]
    if not confirmed.empty:
        confirmed_integrity = (
            confirmed["explicit_pbp_injury"].fillna(False).astype(bool)
            & confirmed["player_id"].notna()
            & confirmed["last_offensive_play_id"].le(confirmed["injury_play_id"])
            & confirmed["focal_team_offensive_plays_after_injury"].ge(5)
            & confirmed["trigger_end_proxy_utc"].lt(
                confirmed["next_game_kickoff_utc"]
            )
        )
        if not confirmed_integrity.all():
            raise AssertionError("A confirmed partial game violates evidence integrity")
    # Confirmation is a stronger subset; all other usage patterns remain suspected.
    enriched.loc[enriched["confirmed_partial_game"], "suspected_partial_game"] = False
    enriched["partial_game_status"] = np.select(
        [
            enriched["confirmed_partial_game"],
            enriched["suspected_partial_game"]
            & enriched["suspected_partial_corroborated"],
            enriched["suspected_partial_game"],
        ],
        ["confirmed", "suspected_corroborated", "suspected_statistical"],
        default="none",
    )
    enriched["partial_game_reason"] = np.select(
        [
            enriched["confirmed_partial_game"],
            enriched["suspected_partial_corroborated"],
            enriched["suspected_partial_game"],
        ],
        [
            "EXPLICIT_PBP_INJURY_NO_OFFENSIVE_RETURN_AND_ROLE_DROP",
            "SNAP_AND_PLAY_SEQUENCE_DROP_WITH_CORROBORATING_EVIDENCE",
            "STATISTICAL_SNAP_AND_PLAY_SEQUENCE_DROP_ONLY",
        ],
        default="NONE",
    )
    enriched["evidence_available_at_utc"] = enriched["trigger_end_proxy_utc"].where(
        enriched["explicit_pbp_injury"].fillna(False)
    )
    enriched["evidence_timestamp_basis"] = np.where(
        enriched["explicit_pbp_injury"].fillna(False),
        "conservative game-end proxy (kickoff + 6 hours)",
        np.where(
            enriched["postgame_injury_report"].fillna(False),
            "injury report date_modified",
            "none",
        ),
    )

    role_game = enriched.drop_duplicates(
        ["season", "week", "game_id", "player_id", "team", "position"]
    )
    teammate = role_game[
        [
            "season",
            "week",
            "game_id",
            "team",
            "position",
            "player_id",
            "confirmed_partial_game",
            "suspected_partial_game",
        ]
    ].copy()
    teammate_counts = (
        teammate.groupby(["season", "week", "game_id", "team", "position"], as_index=False)
        .agg(
            confirmed_role_partial_count=("confirmed_partial_game", "sum"),
            suspected_role_partial_count=("suspected_partial_game", "sum"),
        )
    )
    enriched = enriched.merge(
        teammate_counts,
        on=["season", "week", "game_id", "team", "position"],
        how="left",
    )
    enriched["confirmed_teammate_exit"] = (
        enriched["confirmed_role_partial_count"]
        - enriched["confirmed_partial_game"].astype(int)
    ).gt(0)
    enriched["suspected_teammate_exit"] = (
        enriched["suspected_role_partial_count"]
        - enriched["suspected_partial_game"].astype(int)
    ).gt(0)

    evidence_columns = [
        "season",
        "week",
        "game_id",
        "player_id",
        "player_name",
        "team",
        "position",
        "role_family",
        "partial_game_status",
        "partial_game_reason",
        "confirmed_partial_game",
        "suspected_partial_game",
        "suspected_partial_corroborated",
        "explicit_pbp_injury",
        "pbp_return_status",
        "pbp_description",
        "postgame_injury_report",
        "injury_report_status",
        "injury_report_timestamp_utc",
        "snap_share",
        "prior_snap_n",
        "prior_three_median_snap_share",
        "snap_share_drop",
        "last_offensive_play_id",
        "injury_play_id",
        "focal_team_offensive_plays_after_injury",
        "last_appearance_fraction",
        "trailing_team_plays",
        "evidence_available_at_utc",
        "evidence_timestamp_basis",
        "trigger_end_proxy_utc",
        "next_game_kickoff_utc",
        "identity_resolution",
        "evidence_source",
    ]
    for column in evidence_columns:
        if column not in enriched:
            enriched[column] = np.nan
    evidence = enriched.loc[
        enriched["partial_game_status"].ne("none")
        | enriched["explicit_pbp_injury"].fillna(False)
        | enriched["postgame_injury_report"].fillna(False),
        evidence_columns,
    ].copy()
    temporal_games = enriched.drop_duplicates(["season", "game_id", "team"])
    if temporal_games["trigger_kickoff_utc"].isna().any():
        raise AssertionError("Canonical team-game lacks a normalized schedule timestamp")
    temporal_games = temporal_games.assign(
        _team_join=[
            _normalize_team(team, int(season))
            for team, season in zip(temporal_games["team"], temporal_games["season"])
        ]
    )
    missing_by_team_season = (
        temporal_games.groupby(["season", "_team_join"])["next_game_kickoff_utc"]
        .apply(lambda values: int(values.isna().sum()))
    )
    if not missing_by_team_season.eq(1).all():
        raise AssertionError(
            "Each team-season must have exactly one final regular-season boundary"
        )
    canonical_key = ["season", "week", "player_id", "team", "role_family"]
    if len(enriched) != len(data) or enriched.duplicated(canonical_key).any():
        raise AssertionError("Partial-game enrichment changed canonical row grain")
    source_coverage = mention_coverage.assign(
        participation_team_games=len(participation_coverage),
        participation_coverage_below_099=int(
            participation_coverage["participation_play_coverage"].lt(0.99).sum()
        ),
        canonical_rows=len(enriched),
        confirmed_partial_rows=int(enriched["confirmed_partial_game"].sum()),
        suspected_partial_rows=int(enriched["suspected_partial_game"].sum()),
        statistical_corroboration_rows_pre_promotion=int(
            enriched["suspected_partial_corroborated"].sum()
        ),
        suspected_corroborated_status_rows=int(
            enriched["partial_game_status"].eq("suspected_corroborated").sum()
        ),
        canonical_team_games=len(temporal_games),
        trigger_timestamp_missing_team_games=int(
            temporal_games["trigger_kickoff_utc"].isna().sum()
        ),
        next_boundary_missing_team_games=int(
            temporal_games["next_game_kickoff_utc"].isna().sum()
        ),
    )
    return PartialGameResult(
        canonical=enriched,
        evidence_ledger=evidence,
        source_coverage=source_coverage,
    )
