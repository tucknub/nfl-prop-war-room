from copy import deepcopy
from pathlib import Path
import sys

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.fold2 import (  # noqa: E402
    PRIMARY_POLICY,
    assert_temporal_integrity,
    canonical_audit,
    method_results,
)
from role_validation.fold3 import (  # noqa: E402
    EXPECTED_CONFIG_SHA256,
    assert_fold3_config_integrity,
    cross_season_direction_results,
    fold3_release_gate_table,
    pooled_untouched_results,
)
from role_validation.redevelopment import (  # noqa: E402
    EXPECTED_METHODS,
    ROLE_FAMILIES,
    run_candidate,
)
from role_validation.synthetic import make_synthetic_player_week_data  # noqa: E402


def frozen_candidate() -> dict:
    document = yaml.safe_load(
        (ROOT / "config" / "role_change_fold2_candidate.yaml").read_text(encoding="utf-8")
    )
    return deepcopy(document["candidate"])


def run_synthetic(season: int, seed: int) -> pd.DataFrame:
    data = make_synthetic_player_week_data(
        seasons=[season], weeks=range(1, 19), players_per_family=22, seed=seed
    )
    result = run_candidate(
        data,
        frozen_candidate(),
        partial_policy=PRIMARY_POLICY,
        allowed_seasons=[season],
    )
    verification = result["equal_volume"]
    assert len(verification) == len(ROLE_FAMILIES) * 18
    assert verification["equal_volume"].all()
    assert verification["observed_method_count"].eq(len(EXPECTED_METHODS)).all()
    return result["alerts"]


def test_fold3_config_is_byte_identical_to_fold2_frozen_copy():
    result = assert_fold3_config_integrity(
        ROOT / "config" / "role_change_fold2_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_role_change_fold2_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_config_fingerprint.json",
    )
    assert result["sha256"] == EXPECTED_CONFIG_SHA256
    assert all(result["checks"].values())


def test_2023_canonical_audit_uses_explicit_expected_season():
    rows = []
    for week in range(1, 19):
        rows.append(
            {
                "season": 2023,
                "week": week,
                "game_id": f"g{week}",
                "player_id": "p1",
                "player_name": "Player One",
                "team": "A",
                "position": "RB",
                "role_family": "rb_carry_share",
                "metric_all": 0.5,
                "metric_normal": 0.5,
                "raw_opportunities_all": 10,
                "raw_opportunities_normal": 10,
                "team_opportunities_all": 20,
                "team_opportunities_normal": 20,
                "qualifying_game": True,
                "partial_game_flag": False,
                "data_quality_pass": True,
                "identity_resolved": True,
            }
        )
    required = [
        "season", "week", "player_id", "player_name", "team", "position",
        "role_family", "metric_all", "metric_normal", "raw_opportunities_all",
        "raw_opportunities_normal", "team_opportunities_all",
        "team_opportunities_normal", "qualifying_game", "partial_game_flag",
        "data_quality_pass",
    ]
    audit = canonical_audit(pd.DataFrame(rows), required, expected_season=2023)
    assert audit.at[0, "season"] == 2023
    assert audit.at[0, "duplicate_key_rows"] == 0


def test_fold3_equal_volume_temporal_pooled_and_retired_semantics():
    alerts_2022 = run_synthetic(2022, 861)
    alerts_2023 = run_synthetic(2023, 862)
    temporal = assert_temporal_integrity(alerts_2023, expected_season=2023)
    assert temporal["passed"].all()

    pooled, pooled_direction, pooled_weekly = pooled_untouched_results(
        alerts_2022, alerts_2023
    )
    assert set(pooled["role_family"]) == set(ROLE_FAMILIES)
    assert set(pooled_direction["role_family"]) == set(ROLE_FAMILIES)
    assert pooled_weekly["season_weeks"].eq(36).all()

    directions = cross_season_direction_results(
        {
            "redeveloped_2021": alerts_2022.assign(season=2021),
            "untouched_2022": alerts_2022,
            "untouched_2023": alerts_2023,
        }
    )
    release_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    gates = fold3_release_gate_table(
        method_results(alerts_2023),
        release_config["release_gates"]["full_release"],
        directions,
    ).set_index("role_family")
    assert gates.at["rb_carry_share", "fold3_candidate_status"] in {
        "PASSES_FOLD_3_POINT_GATES", "FAILS_FOLD_3_POINT_GATES", "INSUFFICIENT_EVIDENCE"
    }
    assert gates.at["rb_opportunity_share", "fold3_candidate_status"] in {
        "PASSES_FOLD_3_POINT_GATES", "FAILS_FOLD_3_POINT_GATES", "INSUFFICIENT_EVIDENCE"
    }
    assert gates.at["wr_target_share", "fold3_candidate_status"] == "NOT_APPLICABLE_RETIRED"
    assert gates.at["te_target_share", "fold3_candidate_status"] == "NOT_APPLICABLE_RETIRED"
