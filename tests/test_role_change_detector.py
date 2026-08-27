from __future__ import annotations

import pandas as pd

from dashboard.role_change import (
    INSUFFICIENT,
    STABLE,
    STRONGLY_RISING,
    SURGE,
    build_role_change_signal,
    build_team_role_change_table,
)


def _windows(l8: float, l4: float, l2: float, *, g8: int = 8, g4: int = 4, g2: int = 2):
    return pd.DataFrame(
        [
            {"Window": "Season", "Normal share": 0.20, "Games": 12},
            {"Window": "Last 8", "Normal share": l8, "Games": g8},
            {"Window": "Last 4", "Normal share": l4, "Games": g4},
            {"Window": "Last 2", "Normal share": l2, "Games": g2},
        ]
    )


def _team(rows):
    return pd.DataFrame(rows)


def test_role_change_detector_calls_consistent_large_gain_a_surge():
    signal = build_role_change_signal(
        player_id="p1",
        position="WR",
        windows=_windows(0.18, 0.22, 0.29),
        team_last8=_team(
            [
                {"player_id": "p2", "player_name": "Alpha", "share": 0.30, "raw_opportunities": 30},
                {"player_id": "p3", "player_name": "Beta", "share": 0.24, "raw_opportunities": 24},
                {"player_id": "p1", "player_name": "Player", "share": 0.18, "raw_opportunities": 18},
            ]
        ),
        team_last2=_team(
            [
                {"player_id": "p2", "player_name": "Alpha", "share": 0.31, "raw_opportunities": 12},
                {"player_id": "p1", "player_name": "Player", "share": 0.29, "raw_opportunities": 11},
                {"player_id": "p3", "player_name": "Beta", "share": 0.17, "raw_opportunities": 7},
            ]
        ),
        profile=pd.DataFrame(
            [{"week": week, "team": "IND"} for week in range(5, 13)]
        ),
    )

    assert signal.classification == SURGE
    assert signal.trend == STRONGLY_RISING
    assert signal.shift_pp == 11.0
    assert signal.rank_label_last8 == "WR3"
    assert signal.rank_label_last2 == "WR2"
    assert signal.confidence == "HIGH"


def test_role_change_detector_does_not_overcall_small_noise():
    signal = build_role_change_signal(
        player_id="p1",
        position="RB",
        windows=_windows(0.43, 0.44, 0.45),
        team_last8=_team(
            [{"player_id": "p1", "player_name": "Player", "share": 0.43, "raw_opportunities": 40}]
        ),
        team_last2=_team(
            [{"player_id": "p1", "player_name": "Player", "share": 0.45, "raw_opportunities": 12}]
        ),
    )

    assert signal.classification == STABLE
    assert signal.trend == "Stable"


def test_role_change_detector_marks_thin_two_game_context_low_confidence():
    signal = build_role_change_signal(
        player_id="p1",
        position="TE",
        windows=_windows(0.10, 0.18, 0.30, g8=3, g4=3, g2=1),
        team_last8=_team(
            [{"player_id": "p1", "player_name": "Player", "share": 0.10, "raw_opportunities": 5}]
        ),
        team_last2=_team(
            [{"player_id": "p1", "player_name": "Player", "share": 0.30, "raw_opportunities": 3}]
        ),
    )

    assert signal.classification == INSUFFICIENT
    assert signal.confidence == "LOW"


def test_role_change_detector_suppresses_rank_movement_across_team_change():
    signal = build_role_change_signal(
        player_id="p1",
        position="WR",
        windows=_windows(0.18, 0.22, 0.29),
        team_last8=_team(
            [{"player_id": "p1", "player_name": "Player", "share": 0.18, "raw_opportunities": 18}]
        ),
        team_last2=_team(
            [{"player_id": "p1", "player_name": "Player", "share": 0.29, "raw_opportunities": 10}]
        ),
        profile=pd.DataFrame(
            [
                {"week": 5, "team": "AAA"},
                {"week": 6, "team": "AAA"},
                {"week": 7, "team": "BBB"},
                {"week": 8, "team": "BBB"},
            ]
        ),
    )

    assert signal.rank_comparable is False
    assert any("suppressed" in item for item in signal.evidence)


def test_team_role_change_table_prioritizes_role_surges():
    last8 = _team(
        [
            {"player_id": "up", "player_name": "Up", "position": "WR", "share": 0.15, "sample_games": 8, "raw_opportunities": 15},
            {"player_id": "flat", "player_name": "Flat", "position": "WR", "share": 0.25, "sample_games": 8, "raw_opportunities": 25},
        ]
    )
    last4 = _team(
        [
            {"player_id": "up", "player_name": "Up", "position": "WR", "share": 0.21, "sample_games": 4, "raw_opportunities": 10},
            {"player_id": "flat", "player_name": "Flat", "position": "WR", "share": 0.25, "sample_games": 4, "raw_opportunities": 12},
        ]
    )
    last2 = _team(
        [
            {"player_id": "up", "player_name": "Up", "position": "WR", "share": 0.28, "sample_games": 2, "raw_opportunities": 8},
            {"player_id": "flat", "player_name": "Flat", "position": "WR", "share": 0.25, "sample_games": 2, "raw_opportunities": 6},
        ]
    )

    table = build_team_role_change_table(
        role_family="wr_target_share",
        last8=last8,
        last4=last4,
        last2=last2,
    )

    assert table.iloc[0]["player_id"] == "up"
    assert table.iloc[0]["classification"] == SURGE
    assert round(float(table.iloc[0]["shift_pp"]), 1) == 13.0
