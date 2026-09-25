from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FREEZE_PATH = ROOT / "validation" / "margin_model_freeze_2026.json"

from src.margin import live_engine as base  # noqa: E402
from src.margin import live_engine_v2 as v2  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_freeze(path: Path = FREEZE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_frozen_sources(freeze: dict) -> None:
    mismatches = []
    for rel, expected in freeze["source_sha256"].items():
        actual = sha256_file(ROOT / rel)
        if actual != expected:
            mismatches.append((rel, expected, actual))
    if mismatches:
        raise RuntimeError(f"Frozen model source drift detected: {mismatches}")

def apply_frozen_policy(freeze: dict) -> dict:
    policy = freeze["authoritative_expected_points_policy"]
    v2.LONG_SLOW_WINDOW_PERIODS = int(policy["window_periods"])
    v2.LONG_SLOW_HALF_LIFE = float(policy["half_life"])
    v2.LONG_SLOW_RIDGE = float(policy["ridge"])
    base.DEFAULT_CAP = float(policy["current_spread_sacrifice_cap"])
    base.EV_THRESHOLD = float(policy["anchor_ev_threshold"])
    base.BANDWIDTH = float(policy["margin_sampler_bandwidth"])
    return policy


def df_records(df: pd.DataFrame, columns: list[str] | None = None) -> list[dict]:
    out = df if columns is None else df[columns]
    return json.loads(out.to_json(orient="records"))


def build_expected_points_audit(state: dict, games: pd.DataFrame, freeze: dict) -> dict:
    policy = apply_frozen_policy(freeze)
    season = int(state["season"])
    week = int(state["current_week"])
    if season != 2026:
        raise RuntimeError(f"Prospective ledger is frozen for 2026, not {season}")
    if week < int(freeze["prospective_start"]["week"]):
        raise RuntimeError(f"Prospective validation starts Week {freeze['prospective_start']['week']}; state is Week {week}")

    base.SEASON = season
    season_games = base.prepare_games(games, season)
    current_games = season_games[season_games.week.eq(week)]
    if current_games.empty or current_games.spread_line.isna().any():
        raise RuntimeError("Current-week market is incomplete; snapshot fails closed")

    used = set(str(team) for team in state.get("used_teams", []))
    raw_rows, forecast = v2.build_team_values(games, season_games, week, "current_week_only")
    historical_favorites = base.favorite_games(games)
    all_rows = base.add_calibration(raw_rows, historical_favorites)
    rows = all_rows[all_rows.week.ge(week) & ~all_rows.team.isin(used)].copy()
    board, routes = base.score_current_candidates(rows, week, used)
    pick, reason = base.choose_expected_points_pick(
        board,
        week,
        float(policy["current_spread_sacrifice_cap"]),
        float(policy["anchor_ev_threshold"]),
    )
    anchor = str(board.anchor_team.iloc[0])

    shadows = {}
    for shadow in freeze.get("shadow_policies", []):
        shadow_pick, shadow_reason = base.choose_expected_points_pick(
            board,
            week,
            float(policy["current_spread_sacrifice_cap"]),
            float(shadow["anchor_ev_threshold"]),
        )
        shadows[shadow["name"]] = {
            "pick": str(shadow_pick),
            "reason": shadow_reason,
            "anchor_ev_threshold": float(shadow["anchor_ev_threshold"]),
        }

    board_columns = [
        "team", "opponent", "current_spread", "calibrated_margin", "p_loss",
        "p_win10", "p_win20", "p_win30", "future_cost", "total_season_ev",
        "total_season_ev_delta_vs_anchor", "current_sacrifice_vs_anchor",
        "current_value_source", "game_id",
    ]
    route_columns = [
        "week", "team", "opponent", "raw_value_spread", "calibrated_ev",
        "value_source", "game_id",
    ]
    pick_row = board[board.team.eq(str(pick))].iloc[0]
    return {
        "season": season,
        "week": week,
        "used_teams": sorted(used),
        "completed_week": int(state.get("completed_week", 0)),
        "cumulative_score": float(state.get("cumulative_score", 0.0)),
        "pool_size": state.get("pool", {}).get("size"),
        "anchor": anchor,
        "expected_points_pick": str(pick),
        "expected_points_reason": reason,
        "pick": {
            "team": str(pick),
            "opponent": str(pick_row.opponent),
            "current_spread": float(pick_row.current_spread),
            "calibrated_margin": float(pick_row.calibrated_margin),
            "future_cost": float(pick_row.future_cost),
            "total_season_ev": float(pick_row.total_season_ev),
            "delta_vs_anchor": float(pick_row.total_season_ev_delta_vs_anchor),
        },
        "shadow_policies": shadows,
        "forecast": {
            "model": forecast.get("forecast_model"),
            "window_periods": forecast.get("window_periods"),
            "half_life": forecast.get("half_life"),
            "ridge": forecast.get("ridge"),
            "training_market_rows": forecast.get("training_market_rows"),
        },
        "board": df_records(board.sort_values(["total_season_ev", "current_spread"], ascending=[False, False]), board_columns),
        "route": df_records(routes[str(pick)], route_columns),
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--state-source-sha", required=True)
    parser.add_argument("--stage", choices=["research", "pre_lock"], default="research")
    parser.add_argument("--output-dir", default=str(ROOT / "outputs" / "margin_prospective"))
    args = parser.parse_args()

    freeze = load_freeze()
    assert_frozen_sources(freeze)
    state_path = Path(args.state)
    state_bytes = state_path.read_bytes()
    state = json.loads(state_bytes.decode("utf-8-sig"))

    captured = datetime.now(timezone.utc)
    stamp = captured.strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir)
    snapshot_dir = output_dir / "source_snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    games = base.load_games()
    audit = build_expected_points_audit(state, games, freeze)
    games_path = snapshot_dir / f"{stamp}_games.csv.gz"
    games.to_csv(games_path, index=False, compression="gzip")

    git_sha = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    record = {
        "schema_version": "margin_prospective_snapshot_v1",
        "captured_at_utc": captured.isoformat(),
        "stage": args.stage,
        "model_freeze_sha256": sha256_file(FREEZE_PATH),
        "model_git_sha": git_sha,
        "state_source_sha": args.state_source_sha,
        "state_sha256": sha256_bytes(state_bytes),
        "games_source": base.DATA_URL,
        "games_snapshot_file": str(games_path.relative_to(ROOT)),
        "games_snapshot_sha256": sha256_file(games_path),
        "private_field_state_persisted": False,
        "expected_points_audit": audit,
    }
    filename = f"2026_week{audit['week']:02d}_{args.stage}_{stamp}.json"
    out_path = output_dir / filename
    out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out_path)
    print(f"pick={audit['expected_points_pick']} anchor={audit['anchor']} week={audit['week']}")


if __name__ == "__main__":
    main()
