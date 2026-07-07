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
        frame.to_csv(output_path(f"signal_boards/{name}.csv"), index=False)
    return boards


def main() -> None:
    boards = export_signal_board_views()
    for name, frame in boards.items():
        print(f"{name}: {len(frame):,} rows")


if __name__ == "__main__":
    main()
