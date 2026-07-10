from __future__ import annotations

import pandas as pd
import streamlit as st

from signal_ui import build_signal_heatmap, inject_signal_css, load_signal_csv, player_context_text, render_spotlight_card
from utils import inject_global_styles, page_header, section_header, sidebar_status


SLATE = "outputs/signal_boards/slate_signal_board.csv"
BY_GAME = "outputs/signal_boards/by_game_signal_board.csv"
RECEIVING = "outputs/signal_boards/receiving_signal_board.csv"
RUSHING = "outputs/signal_boards/rushing_signal_board.csv"
PASSING = "outputs/signal_boards/passing_signal_board.csv"


def top_rows(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    if frame.empty or "overall_signal_score" not in frame.columns:
        return pd.DataFrame()
    scores = pd.to_numeric(frame["overall_signal_score"], errors="coerce")
    return frame.assign(_score=scores).sort_values("_score", ascending=False).head(count)


def first_matchup(frame: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    if frame.empty:
        return "Matchup TBD", frame
    group_column = "game_id" if "game_id" in frame.columns else None
    if group_column and frame[group_column].notna().any():
        key = frame[group_column].dropna().astype(str).iloc[0]
        return key, frame[frame[group_column].astype(str).eq(key)]
    first = frame.iloc[0]
    opponent = str(first.get("opponent", "") or "").strip()
    return (player_context_text(first) if opponent else "Matchup context unavailable"), frame.head(8)


def main() -> None:
    st.set_page_config(page_title="Today’s Board | PropWar NFL", layout="wide")
    inject_global_styles()
    inject_signal_css()
    sidebar_status()
    page_header("Today’s Board", "The strongest player signals and one matchup worth a closer look.")

    slate = load_signal_csv(SLATE)
    by_game = load_signal_csv(BY_GAME)
    receiving = load_signal_csv(RECEIVING)
    rushing = load_signal_csv(RUSHING)
    passing = load_signal_csv(PASSING)

    if slate.empty:
        st.warning("Today’s board is not available yet.")
        st.stop()

    section_header("Top 5 Overall", "Start with these players, then open Player Details for the full context.")
    top_five = top_rows(slate, 5)
    columns = st.columns(5)
    for index, (_, row) in enumerate(top_five.iterrows()):
        with columns[index]:
            render_spotlight_card(row, rank=index + 1, action_key=f"today_top_{index}")

    section_header("Top 25 Board", "Scan the full slate before drilling into prop-type detail.")
    table_columns = [
        column
        for column in [
            "player_name",
            "team",
            "opponent",
            "position",
            "overall_signal_score",
            "signal_tier",
            "recommended_user_action",
            "top_signal_reason",
        ]
        if column in slate.columns
    ]
    st.dataframe(
        build_signal_heatmap(top_rows(slate, 25)[table_columns], ["overall_signal_score"], ["signal_tier", "recommended_user_action"]),
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "overall_signal_score": "Board Score",
            "signal_tier": "Strength",
            "recommended_user_action": "Action",
            "top_signal_reason": "Why",
        },
    )

    section_header("Best by Prop Type")
    family_columns = st.columns(3)
    for column, (label, frame) in zip(
        family_columns,
        [("Receiving", receiving), ("Rushing", rushing), ("Passing", passing)],
    ):
        with column:
            st.markdown(f"#### {label}")
            top = top_rows(frame, 1)
            if top.empty:
                st.info("No player available.")
            else:
                render_spotlight_card(top.iloc[0], action_key=f"today_{label.lower()}")

    section_header("Matchup Spotlight")
    matchup_name, matchup_rows = first_matchup(by_game if not by_game.empty else slate)
    st.markdown(f"#### {matchup_name}")
    matchup_view = top_rows(matchup_rows, 6)
    matchup_columns = [
        column
        for column in ["player_name", "team", "opponent", "position", "overall_signal_score", "signal_tier", "top_signal_reason"]
        if column in matchup_view.columns
    ]
    if matchup_view.empty:
        st.info("Matchup context is not available yet.")
    else:
        st.dataframe(
            build_signal_heatmap(matchup_view[matchup_columns], ["overall_signal_score"], ["signal_tier"]),
            use_container_width=True,
            hide_index=True,
            height=260,
            column_config={
                "overall_signal_score": "Board Score",
                "signal_tier": "Strength",
                "top_signal_reason": "Why",
            },
        )
    st.page_link("pages/02_By_Game_Matchup_Board.py", label="View all matchups →")


if __name__ == "__main__":
    main()
