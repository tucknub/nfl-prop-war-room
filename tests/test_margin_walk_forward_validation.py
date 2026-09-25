from __future__ import annotations

import pandas as pd
import pytest

from scripts import margin_walk_forward_validation as wf


def _decision_frame(board: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "team",
        "current_spread",
        "calibrated_margin",
        "future_cost",
        "total_season_ev",
        "total_season_ev_delta_vs_anchor",
    ]
    return board[cols].sort_values("team").reset_index(drop=True)


def test_future_results_and_lines_do_not_change_asof_decision() -> None:
    games = wf.GAMES.copy(deep=True)
    season, week = 2024, 8
    used = {"BAL", "BUF", "DAL", "KC", "MIA", "PHI", "SF"}
    config = wf.Config()
    season_games = wf.base.prepare_games(games, season)
    pick_a, reason_a, board_a = wf.optimizer_decision_asof(
        games, season_games, season, week, used, config
    )
    assert board_a is not None
    mutated = games.copy(deep=True)
    seasons = pd.to_numeric(mutated["season"], errors="coerce")
    weeks = pd.to_numeric(mutated["week"], errors="coerce")
    future = seasons.eq(season) & weeks.gt(week)
    mutated.loc[future, "home_score"] = 999
    mutated.loc[future, "away_score"] = -999
    mutated.loc[future, "spread_line"] = 37.0
    mutated.loc[future, "total_line"] = 1.0

    mutated_season = wf.base.prepare_games(mutated, season)
    pick_b, reason_b, board_b = wf.optimizer_decision_asof(
        mutated, mutated_season, season, week, used, config
    )
    assert board_b is not None
    assert pick_b == pick_a
    assert reason_b == reason_a
    pd.testing.assert_frame_equal(
        _decision_frame(board_a),
        _decision_frame(board_b),
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def test_2022_cancelled_buf_cin_game_is_not_treated_as_normal_game() -> None:
    season_games = wf.base.prepare_games(wf.GAMES, 2022)
    assert len(season_games) == 271
    week17 = wf.current_team_board(season_games, 17)
    assert len(week17) == 30
    assert "BUF" not in set(week17.team)
    assert "CIN" not in set(week17.team)
    pick, _, _ = wf.optimizer_decision_asof(
        wf.GAMES,
        season_games,
        2022,
        17,
        set(),
        wf.Config(),
    )
    assert pick not in {"BUF", "CIN"}
    with pytest.raises(RuntimeError, match="Expected one game"):
        wf.actual_margin(season_games, 17, "BUF")
