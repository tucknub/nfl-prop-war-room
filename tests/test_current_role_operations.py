from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.operations.current_role_pipeline import (
    build_current_role_outputs,
    build_identity_table,
    build_snap_spine,
    detect_completed_regular_weeks,
    validate_current_role_build,
    write_current_role_build,
)


SEASON = 2026
GAME_1 = "2026_01_AAA_BBB"
GAME_2 = "2026_02_CCC_DDD"


def schedules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": SEASON,
                "week": 1,
                "game_type": "REG",
                "game_id": GAME_1,
                "home_team": "BBB",
                "away_team": "AAA",
                "home_score": 24,
                "away_score": 20,
                "result": 4,
            },
            {
                "season": SEASON,
                "week": 2,
                "game_type": "REG",
                "game_id": GAME_2,
                "home_team": "DDD",
                "away_team": "CCC",
                "home_score": np.nan,
                "away_score": np.nan,
                "result": np.nan,
            },
        ]
    )


def player_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for team, prefix in (("AAA", "A"), ("BBB", "B")):
        rows.extend(
            [
                {"team": team, "player_id": f"{prefix}-RB1", "name": f"{team} Lead RB", "position": "RB", "pfr_id": f"{prefix}RB1"},
                {"team": team, "player_id": f"{prefix}-RB2", "name": f"{team} Backup RB", "position": "RB", "pfr_id": f"{prefix}RB2"},
                {"team": team, "player_id": f"{prefix}-WR1", "name": f"{team} Wideout", "position": "WR", "pfr_id": f"{prefix}WR1"},
                {"team": team, "player_id": f"{prefix}-TE1", "name": f"{team} Tight End", "position": "TE", "pfr_id": f"{prefix}TE1"},
            ]
        )
    return rows


def rosters() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": SEASON,
                "week": 1,
                "game_type": "REG",
                "gsis_id": row["player_id"],
                "full_name": row["name"],
                "team": row["team"],
                "position": row["position"],
                "status": "ACT",
                "pfr_id": row["pfr_id"],
            }
            for row in player_rows()
        ]
    )


def player_stats() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": SEASON,
                "week": 1,
                "season_type": "REG",
                "game_id": GAME_1,
                "player_id": row["player_id"],
                "player_name": row["name"],
                "player_display_name": row["name"],
                "position": row["position"],
                "team": row["team"],
                "carries": 0,
                "targets": 0,
            }
            for row in player_rows()
        ]
    )


def snap_counts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": SEASON,
                "week": 1,
                "game_type": "REG",
                "game_id": GAME_1,
                "pfr_player_id": row["pfr_id"],
                "player": row["name"],
                "position": row["position"],
                "team": row["team"],
                "offense_snaps": 40 if row["position"] != "TE" else 30,
                "offense_pct": "80%" if row["position"] != "TE" else "60%",
            }
            for row in player_rows()
        ]
    )


def pbp(*, include_week_two_partial: bool = False) -> pd.DataFrame:
    identities = {(row["team"], row["position"], row["player_id"].endswith("2")): row for row in player_rows()}
    rows: list[dict[str, object]] = []
    play_id = 1
    for team in ("AAA", "BBB"):
        rb1 = identities[(team, "RB", False)]
        rb2 = identities[(team, "RB", True)]
        wr = identities[(team, "WR", False)]
        te = identities[(team, "TE", False)]
        for index in range(20):
            is_pass = index >= 14
            receiver = wr if index < 19 or team == "BBB" else te
            rusher = rb1 if index < 10 else rb2
            rows.append(
                {
                    "season": SEASON,
                    "week": 1,
                    "season_type": "REG",
                    "game_id": GAME_1,
                    "play_id": play_id,
                    "posteam": team,
                    "qtr": min(4, index // 5 + 1),
                    "down": index % 4 + 1,
                    "ydstogo": 1 if index % 7 == 0 else 8,
                    "yardline_100": 10 if index % 9 == 0 else 50,
                    "score_differential": 0,
                    "half_seconds_remaining": 100 if index in {9, 19} else 800,
                    "qb_kneel": 0,
                    "qb_spike": 0,
                    "rush_attempt": 0 if is_pass else 1,
                    "pass_attempt": 1 if is_pass else 0,
                    "two_point_attempt": 0,
                    "rusher_player_id": None if is_pass else rusher["player_id"],
                    "rusher_player_name": None if is_pass else rusher["name"],
                    "receiver_player_id": receiver["player_id"] if is_pass else None,
                    "receiver_player_name": receiver["name"] if is_pass else None,
                    "play_type": "pass" if is_pass else "run",
                    "play_deleted": 0,
                    "aborted_play": 0,
                    "air_yards": 12 if is_pass else np.nan,
                    "complete_pass": 1 if is_pass and index % 2 == 0 else 0,
                    "rushing_yards": 4 if not is_pass else np.nan,
                    "receiving_yards": 12 if is_pass and index % 2 == 0 else 0,
                    "rush_touchdown": 0,
                    "pass_touchdown": 0,
                }
            )
            play_id += 1
    if include_week_two_partial:
        for team in ("CCC", "DDD"):
            for index in range(5):
                rows.append(
                    {
                        "season": SEASON,
                        "week": 2,
                        "season_type": "REG",
                        "game_id": GAME_2,
                        "play_id": play_id,
                        "posteam": team,
                        "qtr": 1,
                        "down": 1,
                        "ydstogo": 10,
                        "yardline_100": 60,
                        "score_differential": 0,
                        "half_seconds_remaining": 1000,
                        "qb_kneel": 0,
                        "qb_spike": 0,
                        "rush_attempt": 1,
                        "pass_attempt": 0,
                        "two_point_attempt": 0,
                        "rusher_player_id": "PARTIAL",
                        "rusher_player_name": "Partial Player",
                        "receiver_player_id": None,
                        "receiver_player_name": None,
                        "play_type": "run",
                        "play_deleted": 0,
                        "aborted_play": 0,
                        "air_yards": np.nan,
                        "complete_pass": 0,
                        "rushing_yards": 3,
                        "receiving_yards": 0,
                        "rush_touchdown": 0,
                        "pass_touchdown": 0,
                    }
                )
                play_id += 1
    return pd.DataFrame(rows)


def test_completion_gate_admits_only_consecutive_complete_week() -> None:
    gate = detect_completed_regular_weeks(pbp(include_week_two_partial=True), schedules(), SEASON)
    assert gate.through_week == 1
    assert gate.completed_weeks == (1,)
    assert gate.blocked_weeks == (2,)
    assert set(gate.completed_game_ids) == {GAME_1}
    assert bool(gate.game_checks.loc[gate.game_checks["game_id"].eq(GAME_1), "complete"].iloc[0])
    assert not bool(gate.game_checks.loc[gate.game_checks["game_id"].eq(GAME_2), "complete"].iloc[0])


def test_completion_gate_waits_when_no_game_is_complete() -> None:
    empty = pd.DataFrame(columns=pbp().columns)
    gate = detect_completed_regular_weeks(empty, schedules(), SEASON)
    assert gate.through_week is None
    assert gate.completed_game_ids == ()
    assert gate.completed_weeks == ()


def build() -> object:
    return build_current_role_outputs(
        season=SEASON,
        through_week=1,
        completed_game_ids=[GAME_1],
        pbp=pbp(),
        player_stats=player_stats(),
        rosters_weekly=rosters(),
        snap_counts=snap_counts(),
        schedules=schedules(),
        generated_at_utc="2026-09-15T12:00:00Z",
    )


def test_current_role_build_includes_zero_opportunity_snap_player() -> None:
    result = build()
    te = result.canonical.loc[
        result.canonical["player_id"].eq("A-TE1")
        & result.canonical["role_family"].eq("te_target_share")
    ].iloc[0]
    assert te["raw_opportunities_all"] == 1
    zero_te = result.canonical.loc[
        result.canonical["player_id"].eq("B-TE1")
        & result.canonical["role_family"].eq("te_target_share")
    ].iloc[0]
    assert zero_te["raw_opportunities_all"] == 0
    assert zero_te["metric_all"] == 0
    assert zero_te["data_quality_pass"]
    assert result.canonical["data_quality_pass"].all()


def test_non_role_opportunity_reconciles_to_full_snap_spine() -> None:
    quarterback = {
        "season": SEASON,
        "week": 1,
        "season_type": "REG",
        "game_id": GAME_1,
        "player_id": "A-QB1",
        "player_name": "AAA Quarterback",
        "player_display_name": "AAA Quarterback",
        "position": "QB",
        "team": "AAA",
        "carries": 1,
        "targets": 0,
    }
    roster_qb = {
        "season": SEASON,
        "week": 1,
        "game_type": "REG",
        "gsis_id": "A-QB1",
        "full_name": "AAA Quarterback",
        "team": "AAA",
        "position": "QB",
        "status": "ACT",
        "pfr_id": "AQB1",
    }
    snap_qb = {
        "season": SEASON,
        "week": 1,
        "game_type": "REG",
        "game_id": GAME_1,
        "pfr_player_id": "AQB1",
        "player": "AAA Quarterback",
        "position": "QB",
        "team": "AAA",
        "offense_snaps": 50,
        "offense_pct": "100%",
    }
    plays = pbp()
    play_index = plays.index[plays["posteam"].eq("AAA") & plays["rush_attempt"].eq(1)][0]
    plays.loc[play_index, "rusher_player_id"] = "A-QB1"
    plays.loc[play_index, "rusher_player_name"] = "AAA Quarterback"
    result = build_current_role_outputs(
        season=SEASON,
        through_week=1,
        completed_game_ids=[GAME_1],
        pbp=plays,
        player_stats=pd.concat([player_stats(), pd.DataFrame([quarterback])], ignore_index=True),
        rosters_weekly=pd.concat([rosters(), pd.DataFrame([roster_qb])], ignore_index=True),
        snap_counts=pd.concat([snap_counts(), pd.DataFrame([snap_qb])], ignore_index=True),
        schedules=schedules(),
    )
    assert not result.canonical["player_id"].eq("A-QB1").any()
    coverage = result.join_coverage.loc[
        result.join_coverage["join"].eq("opportunity_to_snap_spine"), "coverage_rate"
    ].iloc[0]
    assert coverage == 1.0


def test_current_role_build_validates_and_writes_deterministically(tmp_path: Path) -> None:
    result = build()
    checks = validate_current_role_build(result)
    assert all(item["passed"] for item in checks), checks
    files = write_current_role_build(result, tmp_path)
    expected = {
        "canonical", "situational", "production", "events", "partial", "join", "source", "manifest", "validation"
    }
    assert set(files) == expected
    import json
    validation = json.loads(Path(files["validation"]).read_text(encoding="utf-8"))
    assert validation["status"] == "PASS"
    canonical = pd.read_csv(files["canonical"], compression="gzip")
    assert canonical["season"].eq(SEASON).all()
    assert canonical["week"].eq(1).all()


def test_manual_confirmed_partial_override_is_applied() -> None:
    overrides = pd.DataFrame(
        [
            {
                "season": SEASON,
                "week": 1,
                "game_id": GAME_1,
                "player_id": "A-RB1",
                "team": "AAA",
                "status": "CONFIRMED_PARTIAL",
                "reason": "Reviewed injury exit",
                "reviewed_at": "2026-09-15T11:00:00Z",
            }
        ]
    )
    result = build_current_role_outputs(
        season=SEASON,
        through_week=1,
        completed_game_ids=[GAME_1],
        pbp=pbp(),
        player_stats=player_stats(),
        rosters_weekly=rosters(),
        snap_counts=snap_counts(),
        schedules=schedules(),
        partial_overrides=overrides,
    )
    rows = result.canonical.loc[result.canonical["player_id"].eq("A-RB1")]
    assert rows["confirmed_partial_game"].all()
    assert rows["partial_game_reason"].eq("Reviewed injury exit").all()


def test_published_partition_independent_validation(tmp_path: Path) -> None:
    import json

    from src.operations.published_validation import validate_published_role_outputs

    result = build()
    write_current_role_build(result, tmp_path)
    pd.DataFrame(
        [
            {
                "source": name,
                "rows": 10,
                "weeks": "1",
                "latest_week": 1,
                "cache_hit": False,
                "cache_path": f"{name}_{SEASON}.csv.gz",
                "cache_mtime_utc": "2026-09-15T12:00:00Z",
                "fetched_at_utc": "2026-09-15T12:00:00Z",
                "nflreadpy_version": "0.1.5",
                "error": "",
            }
            for name in ("pbp", "player_stats", "rosters_weekly", "schedules", "snap_counts")
        ]
    ).to_csv(tmp_path / f"source_input_manifest_{SEASON}_live.csv", index=False)
    pd.DataFrame(
        [
            {
                "season": SEASON,
                "week": 1,
                "game_id": GAME_1,
                "home_team": "AAA",
                "away_team": "BBB",
                "schedule_final": True,
                "pbp_present": True,
                "fourth_quarter_reached": True,
                "home_scrimmage_plays": 20,
                "away_scrimmage_plays": 20,
                "complete": True,
            }
        ]
    ).to_csv(tmp_path / f"completion_gate_{SEASON}.csv", index=False)
    (tmp_path / f"role_research_status_{SEASON}.json").write_text(
        json.dumps(
            {
                "season": SEASON,
                "status": "PUBLISHED",
                "published_through_week": 1,
                "completed_games": 1,
            }
        ),
        encoding="utf-8",
    )

    report = validate_published_role_outputs(SEASON, tmp_path)
    assert report["status"] == "PASS", report["checks"]


def test_resolved_snap_rows_are_not_reported_unresolved() -> None:
    identity = build_identity_table(player_stats(), rosters(), SEASON, 1)
    spine, unresolved, coverage = build_snap_spine(
        snap_counts(), identity, SEASON, 1, [GAME_1]
    )
    assert unresolved.empty
    assert len(spine) == len(snap_counts())
    assert coverage["resolved_snap_rows"].sum() == coverage["snap_rows"].sum()
