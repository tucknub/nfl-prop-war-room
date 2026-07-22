from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from src.role_validation.normal_game import classify_play_context


ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "RB": ("rb_carry_share", "rb_opportunity_share"),
    "WR": ("wr_target_share",),
    "TE": ("te_target_share",),
}
CANONICAL_KEY = ["season", "week", "player_id", "team", "role_family"]
PUBLIC_COLUMNS = [
    "season", "week", "game_id", "player_id", "player_name", "team", "position",
    "role_family", "metric_all", "metric_normal", "raw_opportunities_all",
    "raw_opportunities_normal", "team_opportunities_all", "team_opportunities_normal",
    "qualifying_game", "data_quality_pass", "active_status", "snap_share",
    "identity_resolved", "game_partition_complete", "participation_play_coverage",
    "source_version", "confirmed_partial_game", "suspected_partial_game",
    "suspected_partial_corroborated", "partial_game_status", "partial_game_reason",
]
REQUIRED_CANONICAL_COLUMNS = [
    "season", "week", "game_id", "player_id", "player_name", "team", "position",
    "role_family", "metric_all", "metric_normal", "raw_opportunities_all",
    "raw_opportunities_normal", "team_opportunities_all", "team_opportunities_normal",
    "qualifying_game", "data_quality_pass", "identity_resolved",
]
CONTEXT_COLUMNS = [
    "normal_game", "early_down", "passing_down", "short_yardage", "two_minute",
    "red_zone", "inside_10", "inside_5", "end_zone", "leading", "trailing", "close",
    "quarter_1", "quarter_2", "quarter_3", "quarter_4",
]
EVENT_COLUMNS = [
    "season", "week", "game_id", "play_id", "team", "player_id", "player_name",
    "position", "opportunity_type", *CONTEXT_COLUMNS,
]


@dataclass(frozen=True)
class CompletionGate:
    season: int
    through_week: int | None
    completed_game_ids: tuple[str, ...]
    completed_weeks: tuple[int, ...]
    blocked_weeks: tuple[int, ...]
    game_checks: pd.DataFrame


@dataclass(frozen=True)
class CurrentRoleBuild:
    canonical: pd.DataFrame
    situational: pd.DataFrame
    production: pd.DataFrame
    events: pd.DataFrame
    partial_status: pd.DataFrame
    join_coverage: pd.DataFrame
    source_coverage: pd.DataFrame
    manifest: dict[str, object]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_id(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return re.sub(r"\.0$", "", text)


def normalize_name(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _regular(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame.empty or column not in frame:
        return frame.copy()
    return frame.loc[frame[column].fillna("").astype(str).str.upper().eq("REG")].copy()


def _flag(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(False, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0).eq(1)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def _parse_share(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.strip()
    percent = text.str.endswith("%")
    values = pd.to_numeric(text.str.rstrip("%"), errors="coerce")
    values = values.where(~percent, values / 100.0)
    return values.where(values.le(1), values / 100.0)


def _schedule_complete_mask(schedules: pd.DataFrame) -> pd.Series:
    if schedules.empty:
        return pd.Series(False, index=schedules.index)
    score_columns = [column for column in ("home_score", "away_score") if column in schedules]
    if len(score_columns) == 2:
        return schedules[score_columns].notna().all(axis=1)
    if "result" in schedules:
        return pd.to_numeric(schedules["result"], errors="coerce").notna()
    return pd.Series(True, index=schedules.index)


def detect_completed_regular_weeks(
    pbp: pd.DataFrame,
    schedules: pd.DataFrame,
    season: int,
    *,
    requested_through_week: int | None = None,
    min_team_scrimmage_plays: int = 15,
) -> CompletionGate:
    """Admit only consecutive regular-season weeks whose entire scheduled slate is complete.

    A game must have a final schedule result, fourth-quarter-or-later PBP, and a
    reasonable number of valid scrimmage plays for both scheduled teams. This
    prevents a Sunday-afternoon or partially ingested game from entering a
    weekly report before the complete slate is available.
    """
    schedule = _regular(schedules, "game_type")
    schedule = schedule.loc[pd.to_numeric(schedule.get("season"), errors="coerce").eq(season)].copy()
    if schedule.empty:
        return CompletionGate(season, None, (), (), (), pd.DataFrame())
    schedule["week"] = pd.to_numeric(schedule["week"], errors="coerce").astype("Int64")
    schedule["game_id"] = schedule["game_id"].astype(str)
    if requested_through_week is not None:
        schedule = schedule.loc[schedule["week"].le(int(requested_through_week))].copy()

    plays = _regular(pbp, "season_type")
    if plays.empty:
        checks = schedule[["week", "game_id", "home_team", "away_team"]].copy()
        checks["schedule_final"] = _schedule_complete_mask(schedule).to_numpy()
        checks["pbp_present"] = False
        checks["fourth_quarter_reached"] = False
        checks["home_scrimmage_plays"] = 0
        checks["away_scrimmage_plays"] = 0
        checks["complete"] = False
        return CompletionGate(season, None, (), (), tuple(sorted(checks["week"].dropna().astype(int).unique())), checks)

    plays = plays.loc[pd.to_numeric(plays.get("season"), errors="coerce").eq(season)].copy()
    plays["week"] = pd.to_numeric(plays["week"], errors="coerce").astype("Int64")
    plays["game_id"] = plays["game_id"].astype(str)
    rush = _flag(plays, "rush_attempt")
    passed = _flag(plays, "pass_attempt")
    valid = (
        plays.get("posteam", pd.Series(index=plays.index, dtype=object)).notna()
        & ~_flag(plays, "play_deleted")
        & ~_flag(plays, "aborted_play")
        & ~_flag(plays, "two_point_attempt")
        & (rush | passed)
    )
    valid_plays = plays.loc[valid].copy()
    game_summary = plays.groupby("game_id", as_index=False).agg(
        pbp_rows=("play_id", "nunique"),
        max_quarter=("qtr", lambda x: pd.to_numeric(x, errors="coerce").max()),
    )
    team_plays = valid_plays.groupby(["game_id", "posteam"], as_index=False).agg(
        scrimmage_plays=("play_id", "nunique")
    )
    team_lookup = team_plays.set_index(["game_id", "posteam"])["scrimmage_plays"].to_dict()

    rows: list[dict[str, object]] = []
    final_mask = _schedule_complete_mask(schedule)
    for row_index, game in schedule.iterrows():
        game_id = str(game["game_id"])
        summary = game_summary.loc[game_summary["game_id"].eq(game_id)]
        home = str(game["home_team"])
        away = str(game["away_team"])
        pbp_present = not summary.empty
        max_quarter = float(summary.iloc[0]["max_quarter"]) if pbp_present and pd.notna(summary.iloc[0]["max_quarter"]) else 0.0
        home_plays = int(team_lookup.get((game_id, home), 0))
        away_plays = int(team_lookup.get((game_id, away), 0))
        schedule_final = bool(final_mask.loc[row_index])
        complete = (
            schedule_final
            and pbp_present
            and max_quarter >= 4
            and home_plays >= min_team_scrimmage_plays
            and away_plays >= min_team_scrimmage_plays
        )
        rows.append(
            {
                "season": season,
                "week": int(game["week"]),
                "game_id": game_id,
                "home_team": home,
                "away_team": away,
                "schedule_final": schedule_final,
                "pbp_present": pbp_present,
                "fourth_quarter_reached": max_quarter >= 4,
                "home_scrimmage_plays": home_plays,
                "away_scrimmage_plays": away_plays,
                "complete": complete,
            }
        )
    checks = pd.DataFrame(rows).sort_values(["week", "game_id"]).reset_index(drop=True)
    completed_weeks: list[int] = []
    blocked_weeks: list[int] = []
    for week in sorted(checks["week"].unique().tolist()):
        week_rows = checks.loc[checks["week"].eq(week)]
        if bool(week_rows["complete"].all()) and (not completed_weeks or week == completed_weeks[-1] + 1):
            completed_weeks.append(int(week))
        else:
            blocked_weeks.extend(int(value) for value in sorted(checks.loc[checks["week"].ge(week), "week"].unique()))
            break
    through_week = completed_weeks[-1] if completed_weeks else None
    complete_ids = tuple(
        checks.loc[checks["week"].isin(completed_weeks) & checks["complete"], "game_id"].astype(str).tolist()
    )
    return CompletionGate(
        season=season,
        through_week=through_week,
        completed_game_ids=complete_ids,
        completed_weeks=tuple(completed_weeks),
        blocked_weeks=tuple(sorted(set(blocked_weeks))),
        game_checks=checks,
    )


def build_identity_table(player_stats: pd.DataFrame, rosters_weekly: pd.DataFrame, season: int, through_week: int) -> pd.DataFrame:
    stats = _regular(player_stats, "season_type")
    stats = stats.loc[
        pd.to_numeric(stats.get("season"), errors="coerce").eq(season)
        & pd.to_numeric(stats.get("week"), errors="coerce").le(through_week)
    ].copy()
    roster = _regular(rosters_weekly, "game_type")
    roster = roster.loc[
        pd.to_numeric(roster.get("season"), errors="coerce").eq(season)
        & pd.to_numeric(roster.get("week"), errors="coerce").le(through_week)
    ].copy()

    stat_team = stats.get("team", pd.Series(index=stats.index, dtype=object)).copy()
    if "recent_team" in stats:
        stat_team = stat_team.fillna(stats["recent_team"])
    stat_identity = pd.DataFrame(
        {
            "season": pd.to_numeric(stats.get("season"), errors="coerce"),
            "week": pd.to_numeric(stats.get("week"), errors="coerce"),
            "player_id": stats.get("player_id", pd.Series(index=stats.index, dtype=object)).map(normalize_id),
            "team": stat_team.fillna("").astype(str).str.upper().str.strip(),
            "stat_player_name": stats.get("player_display_name", stats.get("player_name")),
            "stat_position": stats.get("position"),
        }
    ).drop_duplicates(["season", "week", "player_id", "team"], keep="last")
    roster_identity = pd.DataFrame(
        {
            "season": pd.to_numeric(roster.get("season"), errors="coerce"),
            "week": pd.to_numeric(roster.get("week"), errors="coerce"),
            "player_id": roster.get("gsis_id", pd.Series(index=roster.index, dtype=object)).map(normalize_id),
            "team": roster.get("team", pd.Series(index=roster.index, dtype=object)).fillna("").astype(str).str.upper().str.strip(),
            "roster_player_name": roster.get("full_name"),
            "roster_position": roster.get("position"),
            "active_status": roster.get("status"),
            "pfr_id": roster.get("pfr_id", pd.Series(index=roster.index, dtype=object)).map(normalize_id),
        }
    ).drop_duplicates(["season", "week", "player_id", "team"], keep="last")
    identity = stat_identity.merge(
        roster_identity, on=["season", "week", "player_id", "team"], how="outer"
    )
    identity["player_name"] = identity["stat_player_name"].fillna(identity["roster_player_name"])
    identity["position"] = (
        identity["stat_position"].fillna(identity["roster_position"]).fillna("")
        .astype(str).str.upper().str.strip()
    )
    identity["normalized_name"] = identity["player_name"].map(normalize_name)
    identity["identity_resolved"] = (
        identity["player_id"].astype(str).str.strip().ne("")
        & identity["player_name"].fillna("").astype(str).str.strip().ne("")
        & identity["position"].fillna("").astype(str).str.strip().ne("")
    )
    return identity[
        ["season", "week", "player_id", "team", "player_name", "normalized_name", "position", "active_status", "pfr_id", "identity_resolved"]
    ].drop_duplicates(["season", "week", "player_id", "team"], keep="last")


def prepare_events(pbp: pd.DataFrame, identity: pd.DataFrame, season: int, through_week: int, game_ids: Iterable[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = _regular(pbp, "season_type")
    frame = frame.loc[
        pd.to_numeric(frame.get("season"), errors="coerce").eq(season)
        & pd.to_numeric(frame.get("week"), errors="coerce").le(through_week)
        & frame.get("game_id", pd.Series(index=frame.index, dtype=object)).astype(str).isin(set(game_ids))
    ].copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").astype(int)
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce").astype(int)
    frame = classify_play_context(frame, q3_threshold=24, q4_threshold=17)
    rush = _flag(frame, "rush_attempt")
    passed = _flag(frame, "pass_attempt")
    valid = (
        frame["posteam"].notna()
        & ~_flag(frame, "play_deleted")
        & ~_flag(frame, "aborted_play")
        & ~_flag(frame, "two_point_attempt")
        & (rush | passed)
    )
    qtr = _numeric(frame, "qtr").fillna(0)
    score = _numeric(frame, "score_differential").fillna(0)
    half_seconds = _numeric(frame, "half_seconds_remaining")
    down = _numeric(frame, "down")
    ydstogo = _numeric(frame, "ydstogo")
    yardline = _numeric(frame, "yardline_100")
    air_yards = _numeric(frame, "air_yards")
    frame["normal_game"] = frame["context_normal_game"].fillna(False).astype(bool)
    frame["early_down"] = down.isin([1, 2])
    frame["passing_down"] = down.isin([3, 4])
    frame["short_yardage"] = down.isin([3, 4]) & ydstogo.le(2)
    frame["two_minute"] = half_seconds.le(120) & qtr.le(4)
    frame["red_zone"] = yardline.le(20)
    frame["inside_10"] = yardline.le(10)
    frame["inside_5"] = yardline.le(5)
    frame["leading"] = score.gt(0)
    frame["trailing"] = score.lt(0)
    frame["close"] = score.abs().le(7)
    for quarter in range(1, 5):
        frame[f"quarter_{quarter}"] = qtr.eq(quarter)
    frame["end_zone"] = passed & air_yards.notna() & yardline.notna() & air_yards.ge(yardline)

    base = ["season", "week", "game_id", "posteam", "play_id"]
    carries = frame.loc[
        valid & rush & ~_flag(frame, "qb_kneel") & frame["rusher_player_id"].notna(),
        base + ["rusher_player_id", "rusher_player_name", "rushing_yards", "rush_touchdown", *CONTEXT_COLUMNS],
    ].rename(columns={"posteam": "team", "rusher_player_id": "player_id", "rusher_player_name": "event_player_name"})
    carries["opportunity_type"] = "carry"
    targets = frame.loc[
        valid & passed & ~_flag(frame, "qb_spike") & frame["receiver_player_id"].notna(),
        base + ["receiver_player_id", "receiver_player_name", "complete_pass", "receiving_yards", "pass_touchdown", *CONTEXT_COLUMNS],
    ].rename(columns={"posteam": "team", "receiver_player_id": "player_id", "receiver_player_name": "event_player_name"})
    targets["opportunity_type"] = "target"
    events = pd.concat([carries, targets], ignore_index=True, sort=False)
    if events.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS), pd.DataFrame()
    events["player_id"] = events["player_id"].map(normalize_id)
    identity_join = identity[["season", "week", "player_id", "team", "player_name", "position", "identity_resolved"]]
    events = events.merge(identity_join, on=["season", "week", "player_id", "team"], how="left")
    events["player_name"] = events["player_name"].fillna(events["event_player_name"])
    unresolved = events.loc[
        events["position"].fillna("").astype(str).str.strip().eq("")
        | ~events["identity_resolved"].fillna(False)
    ].copy()
    return events, unresolved


def build_snap_spine(
    snap_counts: pd.DataFrame,
    identity: pd.DataFrame,
    season: int,
    through_week: int,
    completed_game_ids: Iterable[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    snaps = _regular(snap_counts, "game_type")
    snaps = snaps.loc[
        pd.to_numeric(snaps.get("season"), errors="coerce").eq(season)
        & pd.to_numeric(snaps.get("week"), errors="coerce").le(through_week)
        & snaps.get("game_id", pd.Series(index=snaps.index, dtype=object)).astype(str).isin(set(completed_game_ids))
    ].copy()
    if snaps.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    snaps["season"] = pd.to_numeric(snaps["season"], errors="coerce").astype(int)
    snaps["week"] = pd.to_numeric(snaps["week"], errors="coerce").astype(int)
    snaps["pfr_id"] = snaps.get("pfr_player_id", pd.Series(index=snaps.index, dtype=object)).map(normalize_id)
    snaps["normalized_name"] = snaps.get("player", pd.Series(index=snaps.index, dtype=object)).map(normalize_name)
    snaps["offense_snaps"] = pd.to_numeric(snaps.get("offense_snaps"), errors="coerce").fillna(0)
    snaps["snap_share"] = _parse_share(snaps.get("offense_pct", pd.Series(index=snaps.index, dtype=object)))
    snaps = snaps.loc[snaps["offense_snaps"].gt(0)].copy()

    pfr_identity = identity.loc[identity["pfr_id"].astype(str).str.strip().ne("")][
        ["season", "week", "team", "pfr_id", "player_id", "player_name", "position", "active_status", "identity_resolved"]
    ].drop_duplicates(["season", "week", "team", "pfr_id"], keep="last")
    direct = snaps.merge(
        pfr_identity,
        on=["season", "week", "team", "pfr_id"],
        how="left",
        suffixes=("_snap", ""),
    )
    direct["match_method"] = np.where(direct["player_id"].notna(), "PFR_ID", "")

    missing = direct["player_id"].isna()
    if missing.any():
        name_candidates = identity[["season", "week", "team", "normalized_name", "player_id", "player_name", "position", "active_status", "identity_resolved"]].copy()
        counts = name_candidates.groupby(["season", "week", "team", "normalized_name"])["player_id"].transform("nunique")
        name_candidates = name_candidates.loc[counts.eq(1)]
        fallback = direct.loc[missing].drop(columns=["player_id", "player_name", "position", "active_status", "identity_resolved"], errors="ignore").merge(
            name_candidates,
            on=["season", "week", "team", "normalized_name"],
            how="left",
        )
        fallback["match_method"] = np.where(fallback["player_id"].notna(), "UNIQUE_NAME", "UNMATCHED")
        direct = pd.concat([direct.loc[~missing], fallback], ignore_index=True, sort=False)

    direct["position"] = direct["position"].fillna(direct.get("position_snap")).fillna("").astype(str).str.upper().str.strip()
    direct["player_name"] = direct["player_name"].fillna(direct.get("player"))
    direct["identity_resolved"] = direct["identity_resolved"].fillna(False).astype(bool)
    unresolved = direct.loc[direct["player_id"].isna() | ~direct["identity_resolved"]].copy()
    spine = direct.loc[
        direct["player_id"].notna() & direct["identity_resolved"]
    ].copy()
    spine["player_id"] = spine["player_id"].map(normalize_id)
    spine = spine[
        ["season", "week", "game_id", "team", "player_id", "player_name", "position", "active_status", "snap_share", "offense_snaps", "match_method"]
    ].drop_duplicates(["season", "week", "game_id", "team", "player_id"], keep="last")
    coverage = direct.groupby(["season", "week", "game_id", "team"], as_index=False).agg(
        snap_rows=("pfr_id", "size"),
        resolved_snap_rows=("identity_resolved", "sum"),
    )
    coverage["snap_identity_coverage"] = coverage["resolved_snap_rows"] / coverage["snap_rows"].replace(0, np.nan)
    return spine, unresolved, coverage


def _team_denominators(events: pd.DataFrame, normal: bool) -> dict[str, pd.DataFrame]:
    subset = events.loc[events["normal_game"]] if normal else events
    keys = ["season", "week", "game_id", "team"]
    carries = subset.loc[subset["opportunity_type"].eq("carry")].groupby(keys, as_index=False).agg(value=("play_id", "nunique"))
    targets = subset.loc[subset["opportunity_type"].eq("target")].groupby(keys, as_index=False).agg(value=("play_id", "nunique"))
    rb = subset.loc[subset["position"].eq("RB")].groupby(keys, as_index=False).agg(value=("play_id", "nunique"))
    return {"carry": carries, "target": targets, "rb_opportunity": rb}


def _player_counts(events: pd.DataFrame, normal: bool) -> dict[str, pd.DataFrame]:
    subset = events.loc[events["normal_game"]] if normal else events
    keys = ["season", "week", "game_id", "team", "player_id"]
    carry = subset.loc[subset["opportunity_type"].eq("carry")].groupby(keys, as_index=False).agg(value=("play_id", "nunique"))
    target = subset.loc[subset["opportunity_type"].eq("target")].groupby(keys, as_index=False).agg(value=("play_id", "nunique"))
    total = subset.groupby(keys, as_index=False).agg(value=("play_id", "nunique"))
    return {"carry": carry, "target": target, "total": total}


def load_partial_overrides(path: Path | None, season: int, through_week: int) -> pd.DataFrame:
    columns = ["season", "week", "game_id", "player_id", "team", "status", "reason", "reviewed_at"]
    if path is None or not path.exists():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, low_memory=False)
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"Partial-game override file missing columns: {sorted(missing)}")
    frame = frame.loc[
        pd.to_numeric(frame["season"], errors="coerce").eq(season)
        & pd.to_numeric(frame["week"], errors="coerce").le(through_week)
    ].copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    frame["week"] = pd.to_numeric(frame["week"], errors="raise").astype(int)
    frame["game_id"] = frame["game_id"].fillna("").astype(str).str.strip()
    frame["team"] = frame["team"].fillna("").astype(str).str.upper().str.strip()
    frame["player_id"] = frame["player_id"].map(normalize_id)
    frame["status"] = frame["status"].fillna("").astype(str).str.upper().str.strip()
    allowed = {"CLEAR", "SUSPECTED_PARTIAL", "CONFIRMED_PARTIAL"}
    invalid = sorted(set(frame["status"]).difference(allowed))
    if invalid:
        raise ValueError(f"Invalid partial-game override status: {invalid}")
    key = ["season", "week", "game_id", "player_id", "team"]
    if frame.duplicated(key).any():
        raise ValueError("Partial-game override key is not unique")
    return frame[columns]


def build_current_role_outputs(
    *,
    season: int,
    through_week: int,
    completed_game_ids: Iterable[str],
    pbp: pd.DataFrame,
    player_stats: pd.DataFrame,
    rosters_weekly: pd.DataFrame,
    snap_counts: pd.DataFrame,
    schedules: pd.DataFrame,
    partial_overrides: pd.DataFrame | None = None,
    source_version: str | None = None,
    generated_at_utc: str | None = None,
) -> CurrentRoleBuild:
    game_ids = tuple(str(value) for value in completed_game_ids)
    if not game_ids:
        raise ValueError("At least one completed game is required")
    generated_at = generated_at_utc or utc_now_iso()
    identity = build_identity_table(player_stats, rosters_weekly, season, through_week)
    events_raw, unresolved_events = prepare_events(pbp, identity, season, through_week, game_ids)
    if events_raw.empty:
        raise ValueError("Completed games produced no role opportunities")
    spine, unresolved_snaps, snap_coverage = build_snap_spine(
        snap_counts, identity, season, through_week, game_ids
    )
    if spine.empty:
        raise ValueError("Snap counts are unavailable for completed games; current-season publication is blocked")
    expected_game_teams = pd.concat(
        [
            schedules.loc[schedules["game_id"].astype(str).isin(game_ids), ["season", "week", "game_id", "home_team"]].rename(columns={"home_team": "team"}),
            schedules.loc[schedules["game_id"].astype(str).isin(game_ids), ["season", "week", "game_id", "away_team"]].rename(columns={"away_team": "team"}),
        ],
        ignore_index=True,
    ).drop_duplicates(["season", "week", "game_id", "team"])
    snap_game_teams = spine[["season", "week", "game_id", "team"]].drop_duplicates()
    missing_snap_game_teams = expected_game_teams.merge(
        snap_game_teams.assign(_present=True), on=["season", "week", "game_id", "team"], how="left"
    )
    missing_snap_game_teams = missing_snap_game_teams.loc[missing_snap_game_teams["_present"].isna()].drop(columns="_present")
    if not missing_snap_game_teams.empty:
        raise ValueError(
            "Snap counts are missing for completed game-team partitions: "
            + ", ".join(f"{row.game_id}:{row.team}" for row in missing_snap_game_teams.itertuples())
        )
    if not unresolved_events.empty:
        sample = unresolved_events[["game_id", "team", "player_id", "event_player_name"]].head(10).to_dict("records")
        raise ValueError(f"Opportunity player identity is unresolved: {sample}")

    events = events_raw.copy()
    events["position"] = events["position"].fillna("").astype(str).str.upper().str.strip()
    event_player_keys = events[["season", "week", "game_id", "team", "player_id"]].drop_duplicates()
    spine_keys = spine[["season", "week", "game_id", "team", "player_id"]].drop_duplicates()
    event_snap_coverage = event_player_keys.merge(
        spine_keys.assign(_in_snap=True), on=["season", "week", "game_id", "team", "player_id"], how="left"
    )
    missing_event_snap = int(event_snap_coverage["_in_snap"].isna().sum())
    event_snap_rate = float(event_snap_coverage["_in_snap"].fillna(False).mean()) if len(event_snap_coverage) else 1.0
    if event_snap_rate < 0.995:
        raise ValueError(f"Opportunity-to-snap coverage below 99.5%: {event_snap_rate:.3%}")

    all_den = _team_denominators(events, normal=False)
    normal_den = _team_denominators(events, normal=True)
    all_player = _player_counts(events, normal=False)
    normal_player = _player_counts(events, normal=True)
    join_team = ["season", "week", "game_id", "team"]
    join_player = join_team + ["player_id"]

    family_rows: list[pd.DataFrame] = []
    for position, families in ROLE_FAMILIES.items():
        players = spine.loc[spine["position"].eq(position)].copy()
        for family in families:
            row = players.copy()
            row["role_family"] = family
            if family == "rb_carry_share":
                numerator_key, denominator_key = "carry", "carry"
            elif family == "rb_opportunity_share":
                numerator_key, denominator_key = "total", "rb_opportunity"
            else:
                numerator_key, denominator_key = "target", "target"
            row = row.merge(
                all_player[numerator_key].rename(columns={"value": "raw_opportunities_all"}),
                on=join_player,
                how="left",
            ).merge(
                normal_player[numerator_key].rename(columns={"value": "raw_opportunities_normal"}),
                on=join_player,
                how="left",
            ).merge(
                all_den[denominator_key].rename(columns={"value": "team_opportunities_all"}),
                on=join_team,
                how="left",
            ).merge(
                normal_den[denominator_key].rename(columns={"value": "team_opportunities_normal"}),
                on=join_team,
                how="left",
            )
            family_rows.append(row)
    canonical = pd.concat(family_rows, ignore_index=True)
    for column in ("raw_opportunities_all", "raw_opportunities_normal"):
        canonical[column] = pd.to_numeric(canonical[column], errors="coerce").fillna(0).astype(int)
    for column in ("team_opportunities_all", "team_opportunities_normal"):
        canonical[column] = pd.to_numeric(canonical[column], errors="coerce")
    canonical["metric_all"] = canonical["raw_opportunities_all"] / canonical["team_opportunities_all"].replace(0, np.nan)
    canonical["metric_normal"] = canonical["raw_opportunities_normal"] / canonical["team_opportunities_normal"].replace(0, np.nan)
    canonical["identity_resolved"] = True
    canonical["game_partition_complete"] = True
    canonical["participation_play_coverage"] = np.nan
    canonical["data_quality_pass"] = (
        canonical["team_opportunities_all"].gt(0)
        & canonical["team_opportunities_normal"].gt(0)
        & canonical["metric_all"].between(0, 1)
        & canonical["metric_normal"].between(0, 1)
    )
    canonical["qualifying_game"] = canonical["data_quality_pass"]
    canonical["source_version"] = source_version or f"nflverse {season} current-season PBP + weekly rosters + snap counts"

    overrides = partial_overrides.copy() if partial_overrides is not None else pd.DataFrame()
    override_key = ["season", "week", "game_id", "player_id", "team"]
    if not overrides.empty:
        overrides["player_id"] = overrides["player_id"].map(normalize_id)
        canonical = canonical.merge(
            overrides[override_key + ["status", "reason"]], on=override_key, how="left"
        )
    else:
        canonical["status"] = pd.NA
        canonical["reason"] = pd.NA
    status = canonical["status"].fillna("").astype(str).str.upper()
    canonical["confirmed_partial_game"] = status.eq("CONFIRMED_PARTIAL")
    canonical["suspected_partial_game"] = status.eq("SUSPECTED_PARTIAL")
    canonical["suspected_partial_corroborated"] = False
    canonical["partial_game_status"] = np.select(
        [status.eq("CONFIRMED_PARTIAL"), status.eq("SUSPECTED_PARTIAL"), status.eq("CLEAR")],
        ["confirmed", "suspected", "clear"],
        default="unreviewed",
    )
    canonical["partial_game_reason"] = canonical["reason"].fillna("CURRENT_SEASON_MANUAL_PARTIAL_REVIEW_NOT_PROVIDED")
    canonical = canonical.drop(columns=["status", "reason"], errors="ignore")
    canonical = canonical[PUBLIC_COLUMNS].sort_values(CANONICAL_KEY).reset_index(drop=True)

    event_output = events[EVENT_COLUMNS].copy().sort_values(["season", "week", "game_id", "play_id", "team", "player_id"]).reset_index(drop=True)
    production = events.groupby(
        ["season", "week", "game_id", "team", "player_id", "player_name", "position"], as_index=False
    ).agg(
        carries=("opportunity_type", lambda x: int(x.eq("carry").sum())),
        targets=("opportunity_type", lambda x: int(x.eq("target").sum())),
        receptions=("complete_pass", lambda x: int(pd.to_numeric(x, errors="coerce").fillna(0).sum())),
        rushing_yards=("rushing_yards", lambda x: float(pd.to_numeric(x, errors="coerce").fillna(0).sum())),
        receiving_yards=("receiving_yards", lambda x: float(pd.to_numeric(x, errors="coerce").fillna(0).sum())),
        rushing_tds=("rush_touchdown", lambda x: int(pd.to_numeric(x, errors="coerce").fillna(0).sum())),
        receiving_tds=("pass_touchdown", lambda x: int(pd.to_numeric(x, errors="coerce").fillna(0).sum())),
    )

    situational_rows: list[pd.DataFrame] = []
    context_map = ["all_play", *CONTEXT_COLUMNS]
    for family, position in (("rb_carry_share", "RB"), ("rb_opportunity_share", "RB"), ("wr_target_share", "WR"), ("te_target_share", "TE")):
        if family == "rb_carry_share":
            numerator_universe = events.loc[events["position"].eq(position) & events["opportunity_type"].eq("carry")]
            denominator_universe = events.loc[events["opportunity_type"].eq("carry")]
        elif family == "rb_opportunity_share":
            numerator_universe = events.loc[events["position"].eq(position)]
            denominator_universe = events.loc[events["position"].eq("RB")]
        else:
            numerator_universe = events.loc[events["position"].eq(position) & events["opportunity_type"].eq("target")]
            denominator_universe = events.loc[events["opportunity_type"].eq("target")]
        for context in context_map:
            numerator = numerator_universe if context == "all_play" else numerator_universe.loc[numerator_universe[context]]
            denominator = denominator_universe if context == "all_play" else denominator_universe.loc[denominator_universe[context]]
            nums = numerator.groupby(
                ["season", "week", "game_id", "team", "player_id", "player_name", "position"], as_index=False
            ).agg(raw_opportunities=("play_id", "nunique"))
            dens = denominator.groupby(join_team, as_index=False).agg(team_opportunities=("play_id", "nunique"))
            if nums.empty or dens.empty:
                continue
            rows = nums.merge(dens, on=join_team, how="inner")
            rows["share"] = rows["raw_opportunities"] / rows["team_opportunities"].replace(0, np.nan)
            rows["role_family"] = family
            rows["context"] = context
            situational_rows.append(rows)
    situational = pd.concat(situational_rows, ignore_index=True) if situational_rows else pd.DataFrame()

    partial_status = canonical[
        ["season", "week", "game_id", "player_id", "player_name", "team", "position", "role_family",
         "partial_game_status", "partial_game_reason", "confirmed_partial_game", "suspected_partial_game"]
    ].copy()
    partial_status["evidence_source"] = np.where(
        partial_status["partial_game_status"].eq("unreviewed"), "none", "manual_override"
    )
    partial_status["evidence_timestamp_basis"] = "manual_reviewed_at_or_unavailable"

    opportunity_players = events[["season", "week", "game_id", "team", "player_id"]].drop_duplicates()
    opportunity_identity_rate = float(events["identity_resolved"].fillna(False).mean())
    snap_identity_rate = float(snap_coverage["resolved_snap_rows"].sum() / snap_coverage["snap_rows"].sum())
    report_positions = set(ROLE_FAMILIES)
    resolved_report_snap_rows = int(spine["position"].isin(report_positions).sum())
    unresolved_report_snap_rows = int(
        unresolved_snaps["position"].fillna("").astype(str).str.upper().str.strip().isin(report_positions).sum()
    )
    report_snap_rows = resolved_report_snap_rows + unresolved_report_snap_rows
    report_snap_identity_rate = (
        float(resolved_report_snap_rows / report_snap_rows) if report_snap_rows else 1.0
    )
    join_coverage = pd.DataFrame(
        [
            {"season": season, "join": "opportunity_to_identity", "rows": len(events), "matched_rows": int(events["identity_resolved"].fillna(False).sum()), "coverage_rate": opportunity_identity_rate},
            {"season": season, "join": "snap_to_identity_all_offense", "rows": int(snap_coverage["snap_rows"].sum()), "matched_rows": int(snap_coverage["resolved_snap_rows"].sum()), "coverage_rate": snap_identity_rate},
            {"season": season, "join": "snap_to_identity_report_positions", "rows": report_snap_rows, "matched_rows": resolved_report_snap_rows, "coverage_rate": report_snap_identity_rate},
            {"season": season, "join": "opportunity_to_snap_spine", "rows": len(opportunity_players), "matched_rows": len(opportunity_players) - missing_event_snap, "coverage_rate": event_snap_rate},
        ]
    )
    source_coverage = pd.DataFrame(
        [
            {
                "season": season,
                "through_week": through_week,
                "completed_games": len(game_ids),
                "canonical_rows": len(canonical),
                "opportunity_events": len(event_output),
                "snap_game_teams": len(snap_game_teams),
                "expected_game_teams": len(expected_game_teams),
                "unresolved_event_rows": len(unresolved_events),
                "unresolved_snap_rows": len(unresolved_snaps),
                "report_snap_rows": report_snap_rows,
                "unresolved_report_snap_rows": unresolved_report_snap_rows,
                "opportunity_identity_coverage": opportunity_identity_rate,
                "snap_identity_coverage": snap_identity_rate,
                "report_snap_identity_coverage": report_snap_identity_rate,
                "opportunity_to_snap_coverage": event_snap_rate,
                "partial_game_evidence_mode": "manual_overrides_only",
            }
        ]
    )
    manifest = {
        "schema_version": 1,
        "season": season,
        "published_through_week": through_week,
        "completed_game_ids": list(game_ids),
        "generated_at_utc": generated_at,
        "canonical_rows": int(len(canonical)),
        "situational_rows": int(len(situational)),
        "production_rows": int(len(production)),
        "opportunity_event_rows": int(len(event_output)),
        "quality_pass_rows": int(canonical["data_quality_pass"].sum()),
        "confirmed_partial_rows": int(canonical["confirmed_partial_game"].sum()),
        "suspected_partial_rows": int(canonical["suspected_partial_game"].sum()),
        "limitations": [
            "Current-season participation data is unavailable in-season and is not used.",
            "Current-season nflverse injury data is unavailable; partial-game exclusions require a manual reviewed override.",
            "Snap counts are required before a completed week can publish.",
            "RB, WR, and TE snap identity coverage gates publication; all-offense coverage remains a diagnostic.",
            "Only consecutive fully completed regular-season weeks are admitted.",
        ],
    }
    return CurrentRoleBuild(
        canonical=canonical,
        situational=situational,
        production=production,
        events=event_output,
        partial_status=partial_status,
        join_coverage=join_coverage,
        source_coverage=source_coverage,
        manifest=manifest,
    )


def validate_current_role_build(build: CurrentRoleBuild) -> list[dict[str, object]]:
    canonical = build.canonical
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, observed: object, expected: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "observed": observed, "expected": expected})

    add("canonical_not_empty", not canonical.empty, len(canonical), "> 0")
    add("canonical_unique_key", not canonical.duplicated(CANONICAL_KEY).any(), int(canonical.duplicated(CANONICAL_KEY).sum()), 0)
    add("canonical_required_columns", set(REQUIRED_CANONICAL_COLUMNS).issubset(canonical.columns), sorted(set(REQUIRED_CANONICAL_COLUMNS).difference(canonical.columns)), [])
    add("canonical_required_complete", not canonical[REQUIRED_CANONICAL_COLUMNS].isna().any().any(), int(canonical[REQUIRED_CANONICAL_COLUMNS].isna().sum().sum()), 0)
    add("all_share_range", canonical["metric_all"].between(0, 1).all(), [float(canonical["metric_all"].min()), float(canonical["metric_all"].max())], "[0, 1]")
    add("normal_share_range", canonical["metric_normal"].between(0, 1).all(), [float(canonical["metric_normal"].min()), float(canonical["metric_normal"].max())], "[0, 1]")
    add("all_numerator_le_denominator", canonical["raw_opportunities_all"].le(canonical["team_opportunities_all"]).all(), int((canonical["raw_opportunities_all"] > canonical["team_opportunities_all"]).sum()), 0)
    add("normal_numerator_le_denominator", canonical["raw_opportunities_normal"].le(canonical["team_opportunities_normal"]).all(), int((canonical["raw_opportunities_normal"] > canonical["team_opportunities_normal"]).sum()), 0)
    add("quality_pass_all", canonical["data_quality_pass"].all(), int((~canonical["data_quality_pass"]).sum()), 0)
    add("event_unique_grain", not build.events.duplicated(["season", "week", "game_id", "play_id", "team", "player_id", "opportunity_type"]).any(), int(build.events.duplicated(["season", "week", "game_id", "play_id", "team", "player_id", "opportunity_type"]).sum()), 0)
    add("production_unique_grain", not build.production.duplicated(["season", "week", "game_id", "team", "player_id"]).any(), int(build.production.duplicated(["season", "week", "game_id", "team", "player_id"]).sum()), 0)
    add("situational_share_range", build.situational.empty or build.situational["share"].between(0, 1).all(), None if build.situational.empty else [float(build.situational["share"].min()), float(build.situational["share"].max())], "[0, 1]")
    add("opportunity_identity_coverage", float(build.source_coverage.iloc[0]["opportunity_identity_coverage"]) == 1.0, float(build.source_coverage.iloc[0]["opportunity_identity_coverage"]), 1.0)
    add("all_offense_snap_identity_coverage", float(build.source_coverage.iloc[0]["snap_identity_coverage"]) >= 0.95, float(build.source_coverage.iloc[0]["snap_identity_coverage"]), ">= 0.95 diagnostic floor")
    add("report_snap_identity_coverage", float(build.source_coverage.iloc[0]["report_snap_identity_coverage"]) >= 0.99, float(build.source_coverage.iloc[0]["report_snap_identity_coverage"]), ">= 0.99")
    add("opportunity_to_snap_coverage", float(build.source_coverage.iloc[0]["opportunity_to_snap_coverage"]) >= 0.995, float(build.source_coverage.iloc[0]["opportunity_to_snap_coverage"]), ">= 0.995")
    return checks


def write_current_role_build(build: CurrentRoleBuild, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    season = int(build.manifest["season"])
    paths = {
        "canonical": output_dir / f"canonical_role_{season}_live.csv.gz",
        "situational": output_dir / f"situational_player_week_{season}_live.csv.gz",
        "production": output_dir / f"game_player_usage_{season}_live.csv.gz",
        "events": output_dir / f"opportunity_events_{season}_live.csv.gz",
        "partial": output_dir / f"partial_game_status_{season}_live.csv.gz",
        "join": output_dir / f"join_coverage_{season}_live.csv",
        "source": output_dir / f"source_coverage_{season}_live.csv",
        "manifest": output_dir / f"role_research_manifest_{season}.json",
        "validation": output_dir / f"role_research_validation_{season}.json",
    }
    gzip_options = {"method": "gzip", "compresslevel": 9, "mtime": 0}
    for key, frame in (
        ("canonical", build.canonical),
        ("situational", build.situational),
        ("production", build.production),
        ("events", build.events),
        ("partial", build.partial_status),
    ):
        frame.to_csv(paths[key], index=False, compression=gzip_options, lineterminator="\n")
    build.join_coverage.to_csv(paths["join"], index=False, lineterminator="\n")
    build.source_coverage.to_csv(paths["source"], index=False, lineterminator="\n")
    validation_checks = validate_current_role_build(build)
    validation = {
        "status": "PASS" if all(item["passed"] for item in validation_checks) else "FAIL",
        "season": season,
        "published_through_week": build.manifest["published_through_week"],
        "checks": validation_checks,
    }
    manifest = dict(build.manifest)
    hashes: dict[str, str] = {}
    for key in ("canonical", "situational", "production", "events", "partial", "join", "source"):
        hashes[f"{key}_sha256"] = sha256(paths[key])
    manifest["output_hashes"] = hashes
    paths["manifest"].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    paths["validation"].write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    if validation["status"] != "PASS":
        failed = [item for item in validation_checks if not item["passed"]]
        raise AssertionError(f"Current-season role output validation failed: {failed}")
    return {key: str(path) for key, path in paths.items()}
