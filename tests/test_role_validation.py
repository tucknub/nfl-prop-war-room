from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.audit import audit_player_week_table
from role_validation.detector import (
    add_comparison_features,
    add_detection_features,
    select_equal_volume_alerts,
    verify_equal_volume,
)
from role_validation.evaluation import attach_future_outcomes
from role_validation.normal_game import classify_play_context
from role_validation.synthetic import make_synthetic_player_week_data


def test_normal_game_flags_garbage_and_overtime():
    plays = pd.DataFrame(
        {
            "qtr": [2, 3, 4, 5],
            "score_differential": [7, 24, -17, 0],
            "qb_kneel": [0, 0, 0, 0],
            "qb_spike": [0, 0, 0, 0],
            "half_seconds_remaining": [500, 500, 500, 500],
        }
    )
    result = classify_play_context(plays)
    assert result["context_normal_game"].tolist() == [True, False, False, False]


def test_audit_rejects_duplicate_grain():
    data = make_synthetic_player_week_data(
        seasons=[2018], weeks=[1, 2], players_per_family=1
    )
    duplicate = pd.concat([data, data.iloc[[0]]], ignore_index=True)
    audit = audit_player_week_table(
        duplicate,
        required_columns=[
            "season", "week", "player_id", "player_name", "team", "position",
            "role_family", "metric_all", "metric_normal",
            "raw_opportunities_all", "raw_opportunities_normal",
            "team_opportunities_all", "team_opportunities_normal",
            "qualifying_game", "partial_game_flag", "data_quality_pass",
        ],
        key_columns=["season", "week", "player_id", "team", "role_family"],
        share_columns=["metric_all", "metric_normal"],
    )
    assert not audit.passed


def test_equal_volume_methods_match_weekly_counts():
    data = make_synthetic_player_week_data(
        seasons=[2018], weeks=range(1, 9), players_per_family=5
    )
    scored = add_detection_features(data, "metric_normal", baseline_window=3, min_baseline_games=2)
    alerts = select_equal_volume_alerts(scored, "rb_carry_share", min_abs_delta=0.01)
    counts = alerts.groupby(["season", "week", "method"]).size().unstack(fill_value=0)
    assert (counts.nunique(axis=1) == 1).all()


def test_comparison_uses_four_distinct_methods_with_equal_volume():
    data = make_synthetic_player_week_data(
        seasons=[2018], weeks=range(1, 10), players_per_family=5
    )
    scored = add_comparison_features(data, baseline_window=3, min_baseline_games=2)
    alerts = select_equal_volume_alerts(scored, "rb_carry_share", min_abs_delta=0.01)
    assert set(alerts["method"]) == {
        "naive_spike", "two_week_raw", "normal_game_trend", "full_propwar"
    }
    assert verify_equal_volume(alerts)["equal_volume"].all()


def test_previous_metric_skips_nonqualifying_rows():
    data = make_synthetic_player_week_data(
        seasons=[2018], weeks=[1, 2, 3], players_per_family=1
    )
    player = data["player_id"].iloc[0]
    family = data["role_family"].iloc[0]
    mask = data["player_id"].eq(player) & data["role_family"].eq(family)
    rows = data.loc[mask].sort_values("week")
    data.loc[rows.index[1], "partial_game_flag"] = True
    scored = add_detection_features(data, "metric_normal", baseline_window=3, min_baseline_games=1)
    selected = scored.loc[
        scored["player_id"].eq(player) & scored["role_family"].eq(family)
    ].sort_values("week")
    assert selected.iloc[2]["previous_metric"] == selected.iloc[0]["current_metric"]


def test_retention_uses_detected_value_and_does_not_cross_season():
    weekly = make_synthetic_player_week_data(
        seasons=[2021, 2022], weeks=[17, 18], players_per_family=1
    )
    row = weekly.loc[weekly["role_family"].eq("rb_carry_share")].iloc[0]
    alerts = pd.DataFrame(
        [{
            **row.to_dict(),
            "season": 2021,
            "week": 17,
            "method": "full_propwar",
            "method_score": 0.01,
            "baseline_value": 0.20,
            "detected_value": 0.40,
        }]
    )
    evaluated = attach_future_outcomes(alerts, weekly, "metric_normal", horizon=2)
    assert evaluated.loc[0, "future_n"] == 1
    assert pd.isna(evaluated.loc[0, "persistent"])
    expected = (evaluated.loc[0, "next_game_value"] - 0.20) / 0.20
    assert evaluated.loc[0, "next_game_retention"] == expected
