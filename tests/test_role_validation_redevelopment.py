from copy import deepcopy
from pathlib import Path
import sys

import pandas as pd
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.detector import add_comparison_features, select_equal_volume_alerts
from role_validation.diagnostics import (
    deduplicated_feed,
    rb_family_overlap,
    repeat_alert_summary,
)
from role_validation.partial_game import (
    _confirmed_no_return_mask,
    _next_player_game,
    _schedule_with_kickoffs,
    extract_explicit_injury_mentions,
)
from role_validation.redevelopment import (
    EXPECTED_METHODS,
    ROLE_FAMILIES,
    _apply_repeat_suppression,
    _disjoint_features,
    build_full_candidate_alerts,
    load_canonical_seasons,
    partial_exclusion_mask,
    select_equal_volume_candidate_comparators,
)
from role_validation.synthetic import make_synthetic_player_week_data


def _feature_rows(values, *, seasons=None, weeks=None):
    size = len(values)
    seasons = seasons or [2018] * size
    weeks = weeks or list(range(1, size + 1))
    return pd.DataFrame(
        {
            "season": seasons,
            "week": weeks,
            "game_id": [f"g{i}" for i in range(size)],
            "player_id": ["p1"] * size,
            "player_name": ["Player One"] * size,
            "team": ["A"] * size,
            "position": ["RB"] * size,
            "role_family": ["rb_carry_share"] * size,
            "metric_normal": values,
            "raw_opportunities_normal": [10] * size,
            "team_opportunities_normal": [24] * size,
            "qualifying_game": [True] * size,
            "data_quality_pass": [True] * size,
            "confirmed_partial_game": [False] * size,
            "suspected_partial_game": [False] * size,
        }
    )


def _features(frame, *, reset_each_season=True):
    return _disjoint_features(
        frame,
        metric_column="metric_normal",
        raw_opportunity_column="raw_opportunities_normal",
        team_denominator_column="team_opportunities_normal",
        baseline_window=3,
        confirmation_games=2,
        baseline_type="recent",
        recent_weight=1.0,
        season_weight=0.0,
        reset_each_season=reset_each_season,
        partial_policy="PRIMARY_CONFIRMED_EXCLUDED",
    )


def test_disjoint_baseline_ends_before_confirmation_window():
    featured = _features(_feature_rows([0.1, 0.2, 0.3, 0.4, 0.8, 0.8]))
    trigger = featured.loc[featured["week"].eq(6)].iloc[0]
    assert trigger["baseline_value"] == pytest.approx(0.3)
    assert trigger["detected_value"] == pytest.approx(0.8)
    assert trigger["baseline_n"] == 3
    assert trigger["confirmation_n"] == 2


def test_strict_confirmation_rejects_opposite_prior_game():
    featured = _features(_feature_rows([0.2, 0.2, 0.2, 0.1, 0.6]))
    trigger = featured.loc[featured["week"].eq(5)].iloc[0]
    assert trigger["detected_delta"] > 0
    assert bool(trigger["legacy_confirmation_pass"])
    assert not bool(trigger["strict_confirmation_pass"])


def test_season_reset_prevents_cross_season_week_one_features():
    frame = _feature_rows(
        [0.2, 0.2, 0.8, 0.8],
        seasons=[2018, 2018, 2019, 2019],
        weeks=[17, 18, 1, 2],
    )
    reset = _features(frame, reset_each_season=True)
    carried = _features(frame, reset_each_season=False)
    assert reset.loc[(reset["season"].eq(2019)) & reset["week"].eq(1), "baseline_n"].iloc[0] == 0
    assert carried.loc[(carried["season"].eq(2019)) & carried["week"].eq(1), "baseline_n"].iloc[0] == 1


def test_partial_policy_never_promotes_usage_only_suspicion_to_confirmation():
    frame = pd.DataFrame(
        {
            "confirmed_partial_game": [False, True],
            "suspected_partial_game": [True, False],
        }
    )
    assert partial_exclusion_mask(frame, "PRIMARY_CONFIRMED_EXCLUDED").tolist() == [False, True]
    assert partial_exclusion_mask(frame, "STRICT_SUSPECTED_EXCLUDED").tolist() == [True, True]
    assert partial_exclusion_mask(frame, "ALL_INCLUDED").tolist() == [False, False]


def test_temporal_window_uses_next_team_game_not_next_player_appearance():
    schedules = pd.DataFrame(
        {
            "season": [2018, 2018, 2018],
            "week": [1, 2, 3],
            "game_id": ["g1", "g2", "g3"],
            "gameday": ["2018-09-09", "2018-09-16", "2018-09-23"],
            "gametime": ["13:00", "13:00", "13:00"],
            "home_team": ["A", "C", "A"],
            "away_team": ["B", "A", "D"],
        }
    )
    canonical = pd.DataFrame(
        {
            "season": [2018, 2018],
            "week": [1, 3],
            "game_id": ["g1", "g3"],
            "player_id": ["p1", "p1"],
            "team": ["A", "A"],
        }
    )
    result = _next_player_game(canonical, _schedule_with_kickoffs(schedules))
    first = result.loc[result["game_id"].eq("g1")].iloc[0]
    assert first["next_game_kickoff_utc"] == pd.Timestamp("2018-09-16 17:00:00+00:00")


def test_temporal_window_normalizes_historic_raiders_alias():
    schedules = pd.DataFrame(
        {
            "season": [2018, 2018],
            "week": [1, 2],
            "game_type": ["REG", "REG"],
            "game_id": ["g1", "g2"],
            "gameday": ["2018-09-09", "2018-09-16"],
            "gametime": ["13:00", "16:00"],
            "home_team": ["OAK", "DEN"],
            "away_team": ["LA", "OAK"],
        }
    )
    canonical = pd.DataFrame(
        {
            "season": [2018],
            "week": [1],
            "game_id": ["g1"],
            "player_id": ["p1"],
            "team": ["LV"],
        }
    )
    result = _next_player_game(canonical, _schedule_with_kickoffs(schedules))
    assert result["trigger_kickoff_utc"].notna().all()
    assert result.loc[0, "next_game_kickoff_utc"] == pd.Timestamp(
        "2018-09-16 20:00:00+00:00"
    )


def test_empty_injury_mentions_have_stable_schema():
    pbp = pd.DataFrame(columns=["season", "week", "game_id", "play_id", "desc"])
    rosters = pd.DataFrame(
        columns=[
            "season",
            "week",
            "team",
            "jersey_number",
            "gsis_id",
            "full_name",
            "position",
        ]
    )
    mentions, coverage = extract_explicit_injury_mentions(pbp, rosters)
    assert mentions.empty
    assert {"player_id", "identity_resolution", "pbp_description"}.issubset(
        mentions.columns
    )
    assert coverage.loc[0, "parsed_injury_mentions"] == 0


def test_global_play_order_rejects_return_after_opponent_possession_injury():
    evidence = pd.DataFrame(
        {
            # Row 1: injury occurs on the opponent's possession at play 20, but the
            # focal player later appears on offense at play 30 and must not confirm.
            "last_offensive_play_id": [30.0, 10.0, 10.0],
            "injury_play_id": [20.0, 20.0, 20.0],
            "focal_team_offensive_plays_after_injury": [6, 6, 4],
        }
    )
    assert _confirmed_no_return_mask(evidence).tolist() == [False, True, False]


def test_repeat_suppression_is_direction_sensitive():
    alerts = pd.DataFrame(
        {
            "season": [2021, 2021, 2021],
            "week": [5, 6, 7],
            "player_id": ["p1"] * 3,
            "team": ["A"] * 3,
            "role_family": ["rb_carry_share"] * 3,
            "direction": ["increase", "increase", "decrease"],
        }
    )
    candidate = {
        "name": "test",
        "repeat_suppression": {
            "enabled": True,
            "scope": "player_role_family",
            "cooldown_calendar_weeks": 1,
            "direction_sensitive": True,
        },
    }
    kept, suppressed = _apply_repeat_suppression(alerts, candidate)
    assert kept["week"].tolist() == [5, 7]
    assert suppressed["week"].tolist() == [6]


def test_equal_volume_verification_includes_zero_alert_family_weeks():
    data = make_synthetic_player_week_data(
        seasons=[2018], weeks=range(1, 7), players_per_family=2
    )
    config = yaml.safe_load((ROOT / "config" / "role_change_fold2_candidate.yaml").read_text())
    candidate = deepcopy(config["candidate"])
    candidate["name"] = "zero-alert-test"
    for family in ROLE_FAMILIES:
        for direction in ("increase", "decrease"):
            candidate["thresholds"][family][direction]["min_abs_delta"] = 2.0
    full, _ = build_full_candidate_alerts(data, candidate)
    alerts, verification = select_equal_volume_candidate_comparators(data, candidate, full)
    assert alerts.empty
    assert len(verification) == len(ROLE_FAMILIES) * 6
    assert verification["equal_volume"].all()
    assert verification["observed_method_count"].eq(len(EXPECTED_METHODS)).all()
    assert verification[[f"{method}_count" for method in EXPECTED_METHODS]].to_numpy().sum() == 0


def test_feed_deduplication_rb_overlap_and_consecutive_repeat():
    common = {
        "player_name": "Player One",
        "position": "RB",
        "detected_delta": 0.2,
        "normal_baseline_n": 4,
        "raw_opportunities_normal": 10,
        "team_opportunities_normal": 24,
        "confirmed_partial_game": False,
        "suspected_partial_game": False,
        "persistent": True,
        "immediate_reversion": False,
        "retention": 0.8,
    }
    alerts = pd.DataFrame(
        [
            {**common, "season": 2021, "week": 5, "player_id": "p1", "team": "A", "role_family": "rb_carry_share"},
            {**common, "season": 2021, "week": 5, "player_id": "p1", "team": "A", "role_family": "rb_opportunity_share"},
            {**common, "season": 2021, "week": 6, "player_id": "p1", "team": "A", "role_family": "rb_carry_share"},
        ]
    )
    feed = deduplicated_feed(alerts)
    overlap = rb_family_overlap(alerts).iloc[0]
    repeats = repeat_alert_summary(alerts).set_index("grain")
    assert len(feed) == 2
    assert feed["consecutive_player_repeat"].sum() == 1
    assert overlap["overlap_alerts"] == 1
    assert overlap["direction_conflicts"] == 0
    assert repeats.loc["deduplicated_player_week", "repeat_alerts"] == 1


def test_legacy_full_membership_ignores_score_weights():
    data = make_synthetic_player_week_data(
        seasons=[2018], weeks=range(1, 10), players_per_family=5
    )
    scored = add_comparison_features(data, baseline_window=3, min_baseline_games=2)
    before = select_equal_volume_alerts(scored, "rb_carry_share", min_abs_delta=0.0)
    mutated = scored.copy()
    mutated["normal_full_score"] = -999.0
    after = select_equal_volume_alerts(mutated, "rb_carry_share", min_abs_delta=0.0)
    key = ["season", "week", "player_id", "team", "role_family"]
    before_keys = set(map(tuple, before.loc[before["method"].eq("full_propwar"), key].to_numpy()))
    after_keys = set(map(tuple, after.loc[after["method"].eq("full_propwar"), key].to_numpy()))
    assert before_keys == after_keys


def test_loader_allows_explicit_fold2_but_rejects_post_2022_request(tmp_path):
    path = tmp_path / "canonical.csv"
    pd.DataFrame({"season": [2018, 2022, 2023], "value": [1, 2, 3]}).to_csv(path, index=False)
    fold2 = load_canonical_seasons(str(path), seasons=[2022])
    assert fold2["season"].tolist() == [2022]
    with pytest.raises(ValueError, match="2018.*2022"):
        load_canonical_seasons(str(path), seasons=[2023])
