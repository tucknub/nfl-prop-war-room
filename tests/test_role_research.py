from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT))

from dashboard.research_data import (  # noqa: E402
    KEY_COLUMNS,
    available_seasons,
    canonical_quality_profile,
    explorer_usage,
    load_role_data,
    load_situational_data,
    observable_changes,
    primary_rows,
    situational_team_summary,
    team_window_summary,
)
from scripts.build_role_research_data import build_context_rows  # noqa: E402


def test_committed_canonical_data_is_unique_complete_and_ends_in_2025() -> None:
    profile = canonical_quality_profile()
    assert profile["seasons"] == list(range(2018, 2026))
    assert profile["latest_completed_season"] == 2025
    assert available_seasons()[0] == 2025
    assert profile["duplicate_keys"] == 0
    assert profile["required_missing_cells"] == 0
    assert profile["identity_coverage"] == 1.0


def test_public_primary_policy_excludes_confirmed_and_keeps_suspected() -> None:
    all_rows = load_role_data()
    public = primary_rows()
    assert not public["confirmed_partial_game"].any()
    assert public["suspected_partial_game"].any()
    assert set(public[KEY_COLUMNS].itertuples(index=False, name=None)).issubset(
        set(all_rows[KEY_COLUMNS].itertuples(index=False, name=None))
    )


def test_observable_changes_use_same_season_prior_games_only() -> None:
    changes = observable_changes(2025, 18, baseline_games=4)
    assert not changes.empty
    assert changes["season"].eq(2025).all()
    assert changes["week"].le(18).all()
    assert changes["baseline_games"].between(2, 4).all()
    assert changes["recent_share"].between(0, 1).all()
    assert changes["baseline_share"].between(0, 1).all()


def test_situational_archive_is_unique_bounded_and_has_valid_shares() -> None:
    frame = load_situational_data()
    key = ["season", "week", "game_id", "team", "player_id", "role_family", "context"]
    assert sorted(frame["season"].unique().tolist()) == [2023, 2024, 2025]
    assert frame.duplicated(key).sum() == 0
    assert frame["team_opportunities"].gt(0).all()
    assert frame["raw_opportunities"].le(frame["team_opportunities"]).all()
    assert frame["share"].between(0, 1).all()


def test_situational_all_and_normal_counts_reconcile_to_canonical() -> None:
    canonical = primary_rows()
    canonical = canonical[canonical["season"].isin([2023, 2024, 2025])]
    situational = load_situational_data()
    key = ["season", "week", "game_id", "team", "player_id", "role_family"]
    for context, suffix in [("all_play", "all"), ("normal_game", "normal")]:
        split = situational[situational["context"].eq(context)][
            key + ["raw_opportunities", "team_opportunities"]
        ]
        joined = canonical.merge(split, on=key, how="inner")
        assert joined["raw_opportunities"].eq(joined[f"raw_opportunities_{suffix}"]).all()
        assert joined["team_opportunities"].eq(joined[f"team_opportunities_{suffix}"]).all()


def test_team_window_uses_full_team_denominator() -> None:
    canonical = team_window_summary(2025, "ARI", "rb_carry_share", 18, 4, "Normal game")
    situational = situational_team_summary(2025, "ARI", "rb_carry_share", 18, 4)
    joined = canonical.merge(situational[["player_id", "normal_game"]], on="player_id", how="inner")
    assert (joined["share"] - joined["normal_game"]).abs().max() < 1e-12


def test_explorer_player_filter_does_not_change_team_denominator_universe() -> None:
    all_players, weekly = explorer_usage(2025, 1, 18, "rb_carry_share", team="ATL", normal_game=True)
    assert not all_players.empty
    player_id = str(all_players.iloc[0]["player_id"])
    selected, selected_weekly = explorer_usage(
        2025, 1, 18, "rb_carry_share", team="ATL", player_id=player_id, normal_game=True
    )
    assert len(selected) == 1
    expected = weekly.loc[weekly["player_id"].astype(str).eq(player_id), "team_denominator"].sum()
    assert selected.iloc[0]["team_denominator"] == expected
    assert selected_weekly["team_denominator"].equals(
        weekly.loc[weekly["player_id"].astype(str).eq(player_id), "team_denominator"].reset_index(drop=True)
    )


def test_builder_accepts_completed_2025_and_uses_same_game_denominators() -> None:
    rows = []
    for season, play_id, player_id, player_name, rush, passed in [
        (2024, 1, "rb1", "R. One", 1, 0),
        (2024, 2, "rb2", "R. Two", 1, 0),
        (2024, 3, "wr1", "W. One", 0, 1),
        (2025, 4, "rb1", "R. One", 1, 0),
    ]:
        rows.append({
            "season": season, "week": 1, "season_type": "REG", "game_id": f"{season}_01_A_B",
            "play_id": play_id, "posteam": "A", "qtr": 1, "down": 1, "ydstogo": 10,
            "yardline_100": 50, "score_differential": 0, "half_seconds_remaining": 1700,
            "qb_kneel": 0, "qb_spike": 0, "rush_attempt": rush, "pass_attempt": passed,
            "two_point_attempt": 0, "rusher_player_id": player_id if rush else None,
            "rusher_player_name": player_name if rush else None,
            "receiver_player_id": player_id if passed else None, "receiver_player_name": player_name if passed else None,
            "play_type": "run" if rush else "pass", "play_deleted": 0, "aborted_play": 0,
            "air_yards": 5 if passed else None, "complete_pass": passed,
            "rushing_yards": 4 if rush else None, "receiving_yards": 5 if passed else None,
            "rush_touchdown": 0, "pass_touchdown": 0,
        })
    identity = pd.DataFrame([
        {"season": 2024, "week": 1, "player_id": "rb1", "team": "A", "player_name": "R. One", "position": "RB"},
        {"season": 2024, "week": 1, "player_id": "rb2", "team": "A", "player_name": "R. Two", "position": "RB"},
        {"season": 2024, "week": 1, "player_id": "wr1", "team": "A", "player_name": "W. One", "position": "WR"},
        {"season": 2025, "week": 1, "player_id": "rb1", "team": "A", "player_name": "R. One", "position": "RB"},
    ])
    situational, production, events = build_context_rows(pd.DataFrame(rows), identity)
    assert set(situational["season"]) == {2024, 2025}
    carry = situational[
        situational["season"].eq(2024)
        & situational["role_family"].eq("rb_carry_share")
        & situational["context"].eq("all_play")
    ]
    assert set(carry["team_opportunities"]) == {2}
    assert set(production["season"]) == {2024, 2025}
    assert set(events["season"]) == {2024, 2025}
