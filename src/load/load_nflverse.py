from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common import ensure_dirs, load_config, raw_path


def _try_import_nflreadpy():
    try:
        import nflreadpy  # type: ignore

        return nflreadpy
    except ImportError:
        return None


def to_pandas_df(df):
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    if hasattr(df, "collect"):
        df = df.collect()
        if hasattr(df, "to_pandas"):
            return df.to_pandas()
    return df


def _cache_frame(df, csv_path: Path) -> pd.DataFrame:
    df = to_pandas_df(df)
    if hasattr(df, "write_csv") and not hasattr(df, "to_csv"):
        df.write_csv(csv_path)
        return pd.read_csv(csv_path, low_memory=False)
    df.to_csv(csv_path, index=False)
    return df


def _has_usable_receiving_columns(df: pd.DataFrame) -> bool:
    required = {"targets", "receptions", "receiving_yards"}
    return required.issubset(set(df.columns))


def _derive_weekly_from_pbp(pbp: pd.DataFrame) -> pd.DataFrame:
    required = {"season", "week", "posteam"}
    missing = required.difference(pbp.columns)
    if missing:
        raise RuntimeError(f"Cannot derive weekly from PBP. Missing columns: {sorted(missing)}")

    receiver_id_col = next(
        (col for col in ["receiver_player_id", "receiver_id", "player_id"] if col in pbp.columns),
        None,
    )
    receiver_name_col = next(
        (col for col in ["receiver_player_name", "receiver", "player_name"] if col in pbp.columns),
        None,
    )
    if receiver_id_col is None:
        raise RuntimeError("Cannot derive weekly from PBP. Missing receiver player id column.")

    df = pbp[pbp[receiver_id_col].notna()].copy()
    if df.empty:
        raise RuntimeError("Cannot derive weekly from PBP. No receiver rows found.")

    df["player_id"] = df[receiver_id_col]
    df["player_name"] = df[receiver_name_col] if receiver_name_col else df["player_id"]
    df["recent_team"] = df["posteam"]
    df["targets"] = 1
    df["receptions"] = df.get("complete_pass", 0).fillna(0).astype(float)
    if "receiving_yards" in df.columns:
        df["receiving_yards"] = df["receiving_yards"].fillna(0).astype(float)
    elif "yards_gained" in df.columns:
        df["receiving_yards"] = (df["yards_gained"].fillna(0) * df["receptions"]).astype(float)
    else:
        df["receiving_yards"] = 0.0
    if "receiver_touchdown" in df.columns:
        df["receiving_tds"] = df["receiver_touchdown"].fillna(0).astype(float)
    elif "touchdown" in df.columns:
        df["receiving_tds"] = (df["touchdown"].fillna(0) * df["receptions"]).astype(float)
    else:
        df["receiving_tds"] = 0.0
    if "air_yards" not in df.columns:
        df["air_yards"] = 0.0
    df["air_yards"] = df["air_yards"].fillna(0).astype(float)

    weekly = (
        df.groupby(["season", "week", "player_id", "player_name", "recent_team"], as_index=False)
        .agg(
            targets=("targets", "sum"),
            receptions=("receptions", "sum"),
            receiving_yards=("receiving_yards", "sum"),
            receiving_tds=("receiving_tds", "sum"),
            air_yards=("air_yards", "sum"),
        )
    )
    weekly["games"] = 1
    return weekly


def _read_or_fetch(
    name: str,
    seasons: list[int],
    config: dict,
    fallback_pbp: pd.DataFrame | None = None,
) -> pd.DataFrame:
    csv_path = raw_path(f"{name}.csv", config)
    if csv_path.exists():
        df = pd.read_csv(csv_path, low_memory=False)
        if name != "weekly" or _has_usable_receiving_columns(df):
            return df
        if fallback_pbp is not None:
            df = _derive_weekly_from_pbp(fallback_pbp)
            if config["data"].get("cache_raw_csv", True):
                df = _cache_frame(df, csv_path)
            return df

    nflreadpy = _try_import_nflreadpy()
    if nflreadpy is None:
        raise RuntimeError(
            f"Missing {csv_path}. Install nflreadpy or place a compatible {name}.csv in data/raw."
        )

    loader_map = {
        "pbp": ("load_pbp",),
        "weekly": ("load_player_stats",),
        "rosters": ("load_rosters",),
        "schedules": ("load_schedules",),
    }
    load_error: Exception | None = None
    for attr in loader_map[name]:
        if hasattr(nflreadpy, attr):
            try:
                df = getattr(nflreadpy, attr)(seasons)
                df = to_pandas_df(df)
                if name == "weekly" and not _has_usable_receiving_columns(df):
                    raise RuntimeError("load_player_stats returned no usable receiving stat columns.")
                break
            except Exception as exc:
                load_error = exc
                if name == "weekly" and fallback_pbp is not None:
                    df = _derive_weekly_from_pbp(fallback_pbp)
                    break
                raise
    else:
        raise RuntimeError(f"nflreadpy does not expose a supported loader for {name}.")

    if config["data"].get("cache_raw_csv", True):
        df = _cache_frame(df, csv_path)
    return df


def load_nflverse(config_path: str | Path | None = None) -> dict[str, pd.DataFrame]:
    config = load_config(config_path) if config_path else load_config()
    ensure_dirs(config)
    seasons = [int(season) for season in config["data"]["seasons"]]
    pbp = _read_or_fetch("pbp", seasons, config)
    weekly = _read_or_fetch("weekly", seasons, config, fallback_pbp=pbp)
    rosters = _read_or_fetch("rosters", seasons, config)
    if hasattr(_try_import_nflreadpy(), "load_schedules"):
        schedules_path = raw_path("schedules.csv", config)
        if not schedules_path.exists():
            _read_or_fetch("schedules", seasons, config)
    return {"pbp": pbp, "weekly": weekly, "rosters": rosters}


def main() -> None:
    data = load_nflverse()
    for name, df in data.items():
        print(f"{name}: {len(df):,} rows")


if __name__ == "__main__":
    main()
