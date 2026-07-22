from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from src.operations.current_role_pipeline import utc_now_iso


SOURCE_COLUMNS: dict[str, list[str]] = {
    "pbp": [
        "season", "week", "season_type", "game_id", "play_id", "posteam", "qtr", "down",
        "ydstogo", "yardline_100", "score_differential", "half_seconds_remaining", "qb_kneel",
        "qb_spike", "rush_attempt", "pass_attempt", "two_point_attempt", "rusher_player_id",
        "rusher_player_name", "receiver_player_id", "receiver_player_name", "play_type",
        "play_deleted", "aborted_play", "air_yards", "complete_pass", "rushing_yards",
        "receiving_yards", "rush_touchdown", "pass_touchdown",
    ],
    "player_stats": [
        "season", "week", "season_type", "game_id", "player_id", "player_name",
        "player_display_name", "position", "team", "recent_team", "carries", "targets",
    ],
    "rosters_weekly": [
        "season", "week", "game_type", "gsis_id", "full_name", "team", "position",
        "status", "pfr_id",
    ],
    "schedules": [
        "season", "week", "game_type", "game_id", "gameday", "gametime", "home_team",
        "away_team", "home_score", "away_score", "result",
    ],
    "snap_counts": [
        "season", "week", "game_type", "game_id", "pfr_player_id", "player", "position",
        "team", "offense_snaps", "offense_pct",
    ],
}


@dataclass(frozen=True)
class SourceLoad:
    name: str
    frame: pd.DataFrame
    cache_hit: bool
    fetched_at_utc: str
    error: str | None
    cache_path: str
    cache_mtime_utc: str | None


def _to_pandas_selected(frame: object, columns: list[str]) -> pd.DataFrame:
    if hasattr(frame, "collect_schema"):
        available = set(frame.collect_schema().names())
    elif hasattr(frame, "columns"):
        available = set(frame.columns)
    else:
        available = set(columns)
    selected = [column for column in columns if column in available]
    if hasattr(frame, "select"):
        frame = frame.select(selected)
    if hasattr(frame, "collect"):
        frame = frame.collect()
    if hasattr(frame, "to_pandas"):
        frame = frame.to_pandas()
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(frame)
    for column in columns:
        if column not in frame:
            frame[column] = pd.NA
    return frame[columns]




def _mtime_utc(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def _cache_path(cache_dir: Path, name: str, season: int) -> Path:
    return cache_dir / f"{name}_{season}.csv.gz"


def _read_cache(path: Path, columns: list[str]) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path, low_memory=False)
    except (EOFError, OSError, ValueError):
        return None
    if not set(columns).issubset(frame.columns):
        return None
    return frame[columns]


def load_source(
    *,
    name: str,
    season: int,
    loader: Callable[[Iterable[int]], object],
    cache_dir: Path,
    refresh: bool,
    allow_stale_cache: bool = False,
) -> SourceLoad:
    path = _cache_path(cache_dir, name, season)
    cached = _read_cache(path, SOURCE_COLUMNS[name])
    fetched_at = utc_now_iso()
    if cached is not None and not refresh:
        return SourceLoad(name, cached, True, fetched_at, None, str(path), _mtime_utc(path))
    try:
        frame = _to_pandas_selected(loader([season]), SOURCE_COLUMNS[name])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        frame.to_csv(
            temporary,
            index=False,
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
            lineterminator="\n",
        )
        temporary.replace(path)
        return SourceLoad(name, frame, False, fetched_at, None, str(path), _mtime_utc(path))
    except Exception as exc:  # Network/data availability is reported, not hidden.
        if cached is not None and allow_stale_cache:
            return SourceLoad(name, cached, True, fetched_at, f"STALE_CACHE_AFTER_FETCH_ERROR: {exc}", str(path), _mtime_utc(path))
        return SourceLoad(
            name,
            pd.DataFrame(columns=SOURCE_COLUMNS[name]),
            False,
            fetched_at,
            f"{type(exc).__name__}: {exc}",
            str(path),
            _mtime_utc(path),
        )


def load_current_nflverse_sources(
    season: int,
    *,
    cache_dir: str | Path,
    refresh: bool = True,
    allow_stale_cache: bool = False,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    import nflreadpy

    loaders = {
        "pbp": nflreadpy.load_pbp,
        "player_stats": nflreadpy.load_player_stats,
        "rosters_weekly": nflreadpy.load_rosters_weekly,
        "schedules": nflreadpy.load_schedules,
        "snap_counts": nflreadpy.load_snap_counts,
    }
    cache = Path(cache_dir)
    results = {
        name: load_source(
            name=name,
            season=season,
            loader=loader,
            cache_dir=cache,
            refresh=refresh,
            allow_stale_cache=allow_stale_cache,
        )
        for name, loader in loaders.items()
    }
    frames = {name: result.frame for name, result in results.items()}
    rows: list[dict[str, object]] = []
    for name, result in results.items():
        frame = result.frame
        weeks = (
            sorted(pd.to_numeric(frame["week"], errors="coerce").dropna().astype(int).unique().tolist())
            if "week" in frame
            else []
        )
        rows.append(
            {
                "source": name,
                "rows": int(len(frame)),
                "weeks": ",".join(str(value) for value in weeks),
                "latest_week": max(weeks) if weeks else None,
                "cache_hit": result.cache_hit,
                "cache_path": result.cache_path,
                "cache_mtime_utc": result.cache_mtime_utc,
                "fetched_at_utc": result.fetched_at_utc,
                "nflreadpy_version": _package_version("nflreadpy"),
                "error": result.error,
            }
        )
    return frames, pd.DataFrame(rows)
