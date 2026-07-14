from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROLE_FAMILIES = {
    "rb_carry_share": ("RB", "carry"),
    "rb_opportunity_share": ("RB", "rb_opportunity"),
    "wr_target_share": ("WR", "target"),
    "te_target_share": ("TE", "target"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _flag(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").fillna(0).eq(1)


def build_context_rows(pbp: pd.DataFrame, identity: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = pbp.loc[
        pd.to_numeric(pbp["season"], errors="coerce").between(2023, 2025)
        & pbp["season_type"].eq("REG")
    ].copy()
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").astype(int)
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce").astype(int)
    deleted = _flag(frame, "play_deleted")
    aborted = _flag(frame, "aborted_play")
    two_point = _flag(frame, "two_point_attempt")
    rush = _flag(frame, "rush_attempt")
    passed = _flag(frame, "pass_attempt")
    kneel = _flag(frame, "qb_kneel")
    spike = _flag(frame, "qb_spike")
    valid = frame["posteam"].notna() & ~deleted & ~aborted & ~two_point & (rush | passed)

    qtr = pd.to_numeric(frame["qtr"], errors="coerce").fillna(0)
    score = pd.to_numeric(frame["score_differential"], errors="coerce").fillna(0)
    half_seconds = pd.to_numeric(frame["half_seconds_remaining"], errors="coerce")
    down = pd.to_numeric(frame["down"], errors="coerce")
    ydstogo = pd.to_numeric(frame["ydstogo"], errors="coerce")
    yardline = pd.to_numeric(frame["yardline_100"], errors="coerce")
    air_yards = pd.to_numeric(frame["air_yards"], errors="coerce")
    garbage = (qtr.eq(3) & score.abs().ge(24)) | (qtr.eq(4) & score.abs().ge(17))
    frame["normal_game"] = ~(qtr.gt(4) | garbage | kneel | spike)
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
    context_columns = [
        "normal_game", "early_down", "passing_down", "short_yardage", "two_minute",
        "red_zone", "inside_10", "inside_5", "end_zone", "leading", "trailing", "close",
        "quarter_1", "quarter_2", "quarter_3", "quarter_4",
    ]
    carries = frame.loc[valid & rush & ~kneel & frame["rusher_player_id"].notna(), base + [
        "rusher_player_id", "rusher_player_name", "rushing_yards", "rush_touchdown", *context_columns
    ]].rename(columns={
        "posteam": "team", "rusher_player_id": "player_id", "rusher_player_name": "event_player_name",
    })
    carries["opportunity_type"] = "carry"
    targets = frame.loc[valid & passed & ~spike & frame["receiver_player_id"].notna(), base + [
        "receiver_player_id", "receiver_player_name", "complete_pass", "receiving_yards",
        "pass_touchdown", *context_columns
    ]].rename(columns={
        "posteam": "team", "receiver_player_id": "player_id", "receiver_player_name": "event_player_name",
    })
    targets["opportunity_type"] = "target"
    events = pd.concat([carries, targets], ignore_index=True, sort=False)
    events = events.merge(identity, on=["season", "week", "player_id", "team"], how="left")
    events["player_name"] = events["player_name"].fillna(events["event_player_name"])

    context_map = {"all_play": pd.Series(True, index=events.index)}
    context_map.update({name: events[name].fillna(False).astype(bool) for name in context_columns})
    outputs: list[pd.DataFrame] = []
    for family, (position, denominator_type) in ROLE_FAMILIES.items():
        if family == "rb_carry_share":
            numerator_universe = events[events["position"].eq(position) & events["opportunity_type"].eq("carry")]
            denominator_universe = events[events["opportunity_type"].eq("carry")]
        elif family == "rb_opportunity_share":
            numerator_universe = events[events["position"].eq(position)]
            denominator_universe = events[events["position"].eq("RB")]
        else:
            numerator_universe = events[events["position"].eq(position) & events["opportunity_type"].eq("target")]
            denominator_universe = events[events["opportunity_type"].eq("target")]
        for context in context_map:
            if context == "all_play":
                numerator = numerator_universe
                denominator = denominator_universe
            else:
                numerator = numerator_universe[numerator_universe[context].fillna(False).astype(bool)]
                denominator = denominator_universe[denominator_universe[context].fillna(False).astype(bool)]
            nums = numerator.groupby(
                ["season", "week", "game_id", "team", "player_id", "player_name", "position"],
                as_index=False,
            ).agg(raw_opportunities=("play_id", "nunique"))
            dens = denominator.groupby(["season", "week", "game_id", "team"], as_index=False).agg(
                team_opportunities=("play_id", "nunique")
            )
            if nums.empty:
                continue
            joined = nums.merge(dens, on=["season", "week", "game_id", "team"], how="left")
            joined["share"] = joined["raw_opportunities"] / joined["team_opportunities"].replace(0, np.nan)
            joined["role_family"] = family
            joined["context"] = context
            outputs.append(joined)
    situational = pd.concat(outputs, ignore_index=True)

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
    event_columns = [
        "season", "week", "game_id", "play_id", "team", "player_id", "player_name", "position",
        "opportunity_type", *context_columns,
    ]
    return situational, production, events[event_columns].copy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbp", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/role_research"))
    args = parser.parse_args()
    usecols = [
        "season", "week", "season_type", "game_id", "play_id", "posteam", "qtr", "down",
        "ydstogo", "yardline_100", "score_differential", "half_seconds_remaining", "qb_kneel",
        "qb_spike", "rush_attempt", "pass_attempt", "two_point_attempt", "rusher_player_id",
        "rusher_player_name", "receiver_player_id", "receiver_player_name", "play_type",
        "play_deleted", "aborted_play", "air_yards", "complete_pass", "rushing_yards",
        "receiving_yards", "rush_touchdown", "pass_touchdown",
    ]
    pbp = pd.read_csv(args.pbp, usecols=usecols, low_memory=False)
    canonical_parts = []
    canonical_inputs = []
    for path in args.canonical:
        part = pd.read_csv(path, compression="infer", low_memory=False)
        canonical_parts.append(part)
        canonical_inputs.append({
            "path": str(path),
            "sha256": sha256(path),
            "seasons_physically_opened": sorted(
                pd.to_numeric(part["season"], errors="coerce").dropna().astype(int).unique().tolist()
            ),
        })
    canonical = pd.concat(canonical_parts, ignore_index=True)
    identity = canonical[["season", "week", "player_id", "team", "player_name", "position"]].drop_duplicates(
        ["season", "week", "player_id", "team"]
    )
    situational, production, events = build_context_rows(pbp, identity)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    situation_path = args.output_dir / "situational_player_week.csv.gz"
    production_path = args.output_dir / "game_player_usage.csv.gz"
    events_path = args.output_dir / "opportunity_events.csv.gz"
    deterministic_gzip = {"method": "gzip", "mtime": 0}
    situational.to_csv(situation_path, index=False, compression=deterministic_gzip)
    production.to_csv(production_path, index=False, compression=deterministic_gzip)
    events.to_csv(events_path, index=False, compression=deterministic_gzip)
    manifest = {
        "source_pbp": str(args.pbp.resolve()),
        "source_pbp_sha256": sha256(args.pbp),
        "source_seasons_physically_opened": sorted(pd.to_numeric(pbp["season"], errors="coerce").dropna().astype(int).unique().tolist()),
        "canonical_source_inputs": canonical_inputs,
        "canonical_seasons_physically_opened": sorted(
            pd.to_numeric(canonical["season"], errors="coerce").dropna().astype(int).unique().tolist()
        ),
        "seasons_admitted": sorted(situational["season"].unique().astype(int).tolist()),
        "situational_rows": int(len(situational)),
        "production_rows": int(len(production)),
        "opportunity_event_rows": int(len(events)),
        "situational_sha256": sha256(situation_path),
        "production_sha256": sha256(production_path),
        "opportunity_events_sha256": sha256(events_path),
        "definitions": {
            "normal_game": "Regulation plays excluding score-differential garbage time, kneels, and spikes; thresholds q3 >=24 and q4 >=17.",
            "early_down": "Down 1 or 2.",
            "passing_down": "Down 3 or 4.",
            "short_yardage": "Down 3 or 4 with 2 or fewer yards to go.",
            "two_minute": "Final 120 seconds of either half in regulation.",
            "red_zone": "Opponent 20-yard line or closer.",
            "inside_10": "Opponent 10-yard line or closer.",
            "inside_5": "Opponent 5-yard line or closer.",
            "end_zone": "Target air yards at least the remaining distance to the goal line.",
        },
    }
    (args.output_dir / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
