from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd


SOURCE_COLUMNS = {
    "pbp": [
        "season", "week", "season_type", "game_id", "play_id", "posteam",
        "qtr", "score_differential", "half_seconds_remaining", "qb_kneel",
        "qb_spike", "rush_attempt", "pass_attempt", "two_point_attempt", "rusher_player_id",
        "rusher_player_name", "receiver_player_id", "receiver_player_name",
        "play_type", "play_deleted", "aborted_play",
    ],
    "player_stats": [
        "season", "week", "season_type", "game_id", "player_id",
        "player_name", "player_display_name", "position", "team", "carries",
        "targets",
    ],
    "rosters_weekly": [
        "season", "week", "game_type", "gsis_id", "full_name", "team",
        "position", "status", "pfr_id",
    ],
    "participation": [
        "nflverse_game_id", "play_id", "possession_team", "offense_players",
        "n_offense",
    ],
    "schedules": [
        "season", "week", "game_type", "game_id", "home_team", "away_team",
    ],
    "snap_counts": [
        "season", "week", "game_type", "game_id", "pfr_player_id", "player",
        "position", "team", "offense_snaps", "offense_pct",
    ],
    "injuries": [
        "season", "week", "game_type", "team", "gsis_id", "position",
        "full_name", "report_status", "date_modified",
    ],
}


def _to_pandas_selected(frame: object, columns: list[str]) -> pd.DataFrame:
    """Select before collect so multi-season play-by-play stays memory bounded."""
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
    return frame


def _cache_path(cache_dir: Path, name: str, seasons: list[int]) -> Path:
    return cache_dir / f"{name}_{min(seasons)}_{max(seasons)}.csv.gz"


def _load_one(
    name: str,
    loader: Callable[[Iterable[int]], object],
    seasons: list[int],
    cache_dir: Path | None,
    refresh: bool,
) -> pd.DataFrame:
    path = _cache_path(cache_dir, name, seasons) if cache_dir else None
    if path and path.exists() and not refresh:
        try:
            cached = pd.read_csv(path, low_memory=False)
            if set(SOURCE_COLUMNS[name]).issubset(cached.columns):
                return cached
            path.unlink(missing_ok=True)
        except (EOFError, OSError, ValueError):
            path.unlink(missing_ok=True)
    frame = _to_pandas_selected(loader(seasons), SOURCE_COLUMNS[name])
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        frame.to_csv(
            temporary,
            index=False,
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
        )
        temporary.replace(path)
    return frame


def load_nflverse_role_sources(
    seasons: Iterable[int],
    cache_dir: str | Path | None = None,
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load the source tables required for the role-validation data contract."""
    import nflreadpy

    season_list = sorted({int(season) for season in seasons})
    cache = Path(cache_dir) if cache_dir else None
    loaders = {
        "pbp": nflreadpy.load_pbp,
        "player_stats": nflreadpy.load_player_stats,
        "rosters_weekly": nflreadpy.load_rosters_weekly,
        "participation": nflreadpy.load_participation,
        "schedules": nflreadpy.load_schedules,
        "snap_counts": nflreadpy.load_snap_counts,
        "injuries": nflreadpy.load_injuries,
    }
    return {
        name: _load_one(name, loader, season_list, cache, refresh)
        for name, loader in loaders.items()
    }


def source_cache_manifest(cache_dir: str | Path) -> pd.DataFrame:
    rows = []
    for path in sorted(Path(cache_dir).glob("*.csv.gz")):
        digest = sha256(path.read_bytes()).hexdigest()
        rows.append({"file": str(path), "bytes": path.stat().st_size, "sha256": digest})
    return pd.DataFrame(rows)
