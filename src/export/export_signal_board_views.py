from __future__ import annotations

import pandas as pd

from src.common import output_path


def read_master() -> pd.DataFrame:
    path = output_path("signal_boards/player_week_signal_master.csv")
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def sort_board(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.sort_values(["overall_signal_score", "projection_score"], ascending=[False, False])


VIEW_COLUMNS = {
    "receiving_signal_board": [
        "l3_targets", "l5_targets", "l8_targets", "l3_receptions", "l5_receptions",
        "l3_receiving_yards", "l5_receiving_yards", "opp_receiving_fit_score",
        "defense_fit_reliability", "pass_volume_environment", "game_script_score",
        "recent_form_score",
    ],
    "rushing_signal_board": [
        "l3_carries", "l5_carries", "l8_carries", "l3_rushing_yards", "l5_rushing_yards",
        "opp_rushing_fit_score", "defense_fit_reliability", "rush_volume_environment",
        "game_script_score", "recent_form_score",
    ],
    "passing_signal_board": [
        "l3_pass_attempts", "l5_pass_attempts", "l3_passing_yards", "l5_passing_yards",
        "opp_passing_fit_score", "defense_fit_reliability", "pass_volume_environment",
        "game_script_score", "recent_form_score",
    ],
    "by_game_signal_board": [
        "game_id", "home_team", "away_team", "is_home", "spread_line", "total_line",
        "team_implied_total", "favorite_status", "spread_bucket", "game_total_bucket",
        "pass_volume_environment", "rush_volume_environment", "game_environment_reliability",
    ],
}


def keep_existing(frame: pd.DataFrame, preferred: list[str]) -> pd.DataFrame:
    base = [column for column in frame.columns if column not in preferred]
    ordered = base + [column for column in preferred if column in frame.columns and column not in base]
    return frame[ordered]


def export_signal_board_views() -> dict[str, pd.DataFrame]:
    master = read_master()
    boards: dict[str, pd.DataFrame] = {}
    boards["slate_signal_board"] = sort_board(master).head(250)
    if not master.empty:
        by_game = master.copy()
        by_game["game_key"] = by_game.apply(lambda row: "UNKNOWN" if pd.isna(row.get("opponent")) or not str(row.get("opponent")).strip() else "-".join(sorted([str(row.get("team", "")), str(row.get("opponent", ""))])), axis=1)
        boards["by_game_signal_board"] = sort_board(by_game)
        boards["receiving_signal_board"] = sort_board(master[master["receiving_market_available"].astype(str).str.lower().eq("true")].copy())
        boards["rushing_signal_board"] = sort_board(master[master["rushing_market_available"].astype(str).str.lower().eq("true")].copy())
        boards["passing_signal_board"] = sort_board(master[master["passing_market_available"].astype(str).str.lower().eq("true")].copy())
        review_mask = master["signal_tier"].astype(str).isin(["REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]) | master["review_reason"].fillna("").astype(str).ne("") | master["blocked_reason"].fillna("").astype(str).ne("")
        boards["blocked_review_board"] = sort_board(master[review_mask].copy())
    else:
        for name in ["by_game_signal_board", "receiving_signal_board", "rushing_signal_board", "passing_signal_board", "blocked_review_board"]:
            boards[name] = master.copy()
    for name, frame in boards.items():
        if name in VIEW_COLUMNS and not frame.empty:
            frame = keep_existing(frame, VIEW_COLUMNS[name])
            boards[name] = frame
        frame.to_csv(output_path(f"signal_boards/{name}.csv"), index=False)
    return boards


def main() -> None:
    boards = export_signal_board_views()
    for name, frame in boards.items():
        print(f"{name}: {len(frame):,} rows")


if __name__ == "__main__":
    main()
