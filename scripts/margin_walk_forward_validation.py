from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.margin import live_engine as base
from src.margin import live_engine_v2 as v2

OUT_DIR = ROOT / "outputs" / "margin_validation"
GAMES = base.load_games()


@dataclass(frozen=True)
class Config:
    window: int = 32
    half_life: float = 8.0
    ridge: float = 3.0
    cap: float = 3.0
    threshold: float = 0.5


def apply_config(config: Config) -> None:
    v2.LONG_SLOW_WINDOW_PERIODS = int(config.window)
    v2.LONG_SLOW_HALF_LIFE = float(config.half_life)
    v2.LONG_SLOW_RIDGE = float(config.ridge)
    base.DEFAULT_CAP = float(config.cap)
    base.EV_THRESHOLD = float(config.threshold)


def favorite_training_asof(games: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    s = pd.to_numeric(games["season"], errors="coerce")
    w = pd.to_numeric(games["week"], errors="coerce")
    d = games[
        games["game_type"].eq("REG")
        & (s >= 2006)
        & ((s < season) | ((s == season) & (w < week)))
    ].copy()
    for col in ["home_score", "away_score", "spread_line", "total_line"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=["home_score", "away_score", "spread_line", "total_line"])
    assert not (((pd.to_numeric(d.season) == season) & (pd.to_numeric(d.week) >= week))).any()
    home_fav = d.spread_line >= 0
    d["favorite_spread"] = d.spread_line.abs().astype(float)
    d["favorite_margin"] = np.where(home_fav, d.home_score - d.away_score, d.away_score - d.home_score).astype(float)
    return d[["season", "week", "game_id", "favorite_spread", "favorite_margin"]].reset_index(drop=True)


def current_team_board(season_games: pd.DataFrame, week: int) -> pd.DataFrame:
    d = season_games[season_games.week.eq(week)].copy()
    if d.spread_line.isna().any():
        raise RuntimeError(f"Missing current-week spread in Week {week}")
    home = pd.DataFrame({"team": d.home_team.astype(str), "spread": d.spread_line.astype(float), "total_line": d.total_line.astype(float)})
    away = pd.DataFrame({"team": d.away_team.astype(str), "spread": -d.spread_line.astype(float), "total_line": d.total_line.astype(float)})
    return pd.concat([home, away], ignore_index=True)


def actual_margin(season_games: pd.DataFrame, week: int, team: str) -> float:
    d = season_games[season_games.week.eq(week)]
    row = d[(d.home_team.astype(str) == team) | (d.away_team.astype(str) == team)]
    if len(row) != 1:
        raise RuntimeError(f"Expected one game for {team} in Week {week}; got {len(row)}")
    r = row.iloc[0]
    if pd.isna(r.home_score) or pd.isna(r.away_score):
        raise RuntimeError(f"Missing final score for {team} Week {week}")
    margin = float(r.home_score - r.away_score)
    return margin if str(r.home_team) == team else -margin


def perfect_foresight(season_games: pd.DataFrame, weeks: list[int]) -> float:
    rows = []
    for _, r in season_games.dropna(subset=["home_score", "away_score"]).iterrows():
        margin = float(r.home_score - r.away_score)
        rows.append({"week": int(r.week), "team": str(r.home_team), "calibrated_ev": margin})
        rows.append({"week": int(r.week), "team": str(r.away_team), "calibrated_ev": -margin})
    _, total = base.exact_assignment(pd.DataFrame(rows), weeks, set())
    return float(total)


def choose_biggest(board: pd.DataFrame, used: set[str]) -> str:
    d = board[~board.team.isin(used)].copy()
    if d.empty:
        raise RuntimeError("No available current-week team")
    return str(d.sort_values(["spread", "total_line", "team"], ascending=[False, False, True], kind="stable").iloc[0].team)


def optimizer_decision_asof(
    games: pd.DataFrame,
    season_games: pd.DataFrame,
    season: int,
    week: int,
    used: set[str],
    config: Config,
) -> tuple[str, str, pd.DataFrame | None]:
    apply_config(config)
    base.SEASON = season
    current = current_team_board(season_games, week)
    if week <= 3:
        return choose_biggest(current, used), "WEEKS_1_TO_3_BIGGEST_FAVORITE_DEFAULT", None
    raw_rows, _ = v2.build_team_values(games, season_games, week, "current_week_only")
    train = favorite_training_asof(games, season, week)
    rows = base.add_calibration(raw_rows, train)
    opt_rows = rows[rows.week.ge(week) & ~rows.team.isin(used)].copy()
    board, _ = base.score_current_candidates(opt_rows, week, used)
    team, reason = base.choose_expected_points_pick(board, week, config.cap, config.threshold)
    return str(team), reason, board


def run_season(season: int, config: Config) -> tuple[dict, pd.DataFrame]:
    apply_config(config)
    base.SEASON = season
    sg = base.prepare_games(GAMES, season)
    weeks = sorted(int(x) for x in sg.week.dropna().unique())
    if sg[sg.week.isin(weeks)].spread_line.isna().any():
        raise RuntimeError(f"Season {season} has missing regular-season spreads")

    used = {"biggest_favorite": set(), "optimizer": set()}
    totals = {k: 0.0 for k in used}
    pick_rows: list[dict] = []

    for week in weeks:
        current = current_team_board(sg, week)
        bf_team = choose_biggest(current, used["biggest_favorite"])

        opt_team, reason, _ = optimizer_decision_asof(
            GAMES, sg, season, week, used["optimizer"], config
        )

        for strategy, team in {"biggest_favorite": bf_team, "optimizer": str(opt_team)}.items():
            margin = actual_margin(sg, week, team)
            totals[strategy] += margin
            used[strategy].add(team)

        pick_rows.append({"season": season, "week": week, "biggest_favorite": bf_team,
                          "optimizer": str(opt_team), "optimizer_reason": reason,
                          "different": str(opt_team) != bf_team})

    summary = {
        "season": season,
        **asdict(config),
        **totals,
        "perfect_foresight": perfect_foresight(sg, weeks),
        "optimizer_minus_biggest": totals["optimizer"] - totals["biggest_favorite"],
        "optimizer_diff_weeks": int(sum(row["different"] for row in pick_rows)),
    }
    return summary, pd.DataFrame(pick_rows)


def run_suite(seasons: list[int], config: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    summaries, picks = [], []
    for season in seasons:
        summary, season_picks = run_season(season, config)
        summaries.append(summary)
        picks.append(season_picks)
        print(summary, flush=True)
    return pd.DataFrame(summaries), pd.concat(picks, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", default="2016-2025")
    parser.add_argument("--window", type=int, default=32)
    parser.add_argument("--half-life", type=float, default=8.0)
    parser.add_argument("--ridge", type=float, default=3.0)
    parser.add_argument("--cap", type=float, default=3.0)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--label", default="default")
    args = parser.parse_args()

    start, end = [int(x) for x in args.seasons.split("-")]
    seasons = list(range(start, end + 1))
    config = Config(args.window, args.half_life, args.ridge, args.cap, args.threshold)
    summaries, picks = run_suite(seasons, config)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{args.label}_{start}_{end}"
    summaries.to_csv(OUT_DIR / f"{stem}_summary.csv", index=False)
    picks.to_csv(OUT_DIR / f"{stem}_picks.csv", index=False)
    metadata = {
        "label": args.label,
        "seasons": seasons,
        "config": asdict(config),
        "future_posted_mode": "current_week_only",
        "weeks_1_to_3_policy": "biggest_favorite_default",
        "calibration_cutoff": "strictly before target week",
    }
    (OUT_DIR / f"{stem}_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("\nSUMMARY")
    print(summaries.to_string(index=False))
    print("\nAGGREGATE")
    print("mean_optimizer_minus_biggest", float(summaries.optimizer_minus_biggest.mean()))
    print("median_optimizer_minus_biggest", float(summaries.optimizer_minus_biggest.median()))
    print("optimizer_beats_biggest", int((summaries.optimizer_minus_biggest > 0).sum()), "of", len(summaries))
    print("optimizer_ties_biggest", int((summaries.optimizer_minus_biggest == 0).sum()), "of", len(summaries))


if __name__ == "__main__":
    main()
