from copy import deepcopy
from pathlib import Path
import sys

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.fold2 import PRIMARY_POLICY, assert_temporal_integrity, method_results  # noqa: E402
from role_validation.fold3 import cross_season_direction_results  # noqa: E402
from role_validation.fold4 import (  # noqa: E402
    ACTIVE_FAMILIES,
    EXPECTED_CONFIG_SHA256,
    assert_fold4_config_integrity,
    fold4_release_gate_table,
    pooled_period_results,
    recommendation_table,
)
from role_validation.redevelopment import EXPECTED_METHODS, run_candidate  # noqa: E402
from role_validation.synthetic import make_synthetic_player_week_data  # noqa: E402


def frozen_candidate() -> dict:
    document = yaml.safe_load(
        (ROOT / "config" / "role_change_fold2_candidate.yaml").read_text(
            encoding="utf-8"
        )
    )
    return deepcopy(document["candidate"])


def run_active_synthetic(season: int, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = make_synthetic_player_week_data(
        seasons=[season], weeks=range(1, 19), players_per_family=22, seed=seed
    )
    data = data.loc[data["role_family"].isin(ACTIVE_FAMILIES)].copy()
    result = run_candidate(
        data,
        frozen_candidate(),
        partial_policy=PRIMARY_POLICY,
        allowed_seasons=[season],
        role_families=ACTIVE_FAMILIES,
    )
    return result["alerts"], result["equal_volume"]


def test_fold4_config_is_byte_identical_to_prior_frozen_copies():
    result = assert_fold4_config_integrity(
        ROOT / "config" / "role_change_fold2_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_role_change_fold2_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_config_fingerprint.json",
        ROOT / "outputs" / "role_validation" / "fold_3"
        / "frozen_role_change_fold3_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_3"
        / "frozen_config_fingerprint.json",
    )
    assert result["sha256"] == EXPECTED_CONFIG_SHA256
    assert all(result["checks"].values())


def test_fold4_active_family_scope_equal_volume_and_temporal_integrity():
    alerts, equal = run_active_synthetic(2024, 864)
    assert set(alerts["season"]) == {2024}
    assert set(alerts["role_family"]) == set(ACTIVE_FAMILIES)
    assert len(equal) == len(ACTIVE_FAMILIES) * 18
    assert equal["equal_volume"].all()
    assert equal["observed_method_count"].eq(len(EXPECTED_METHODS)).all()
    assert assert_temporal_integrity(alerts, expected_season=2024)["passed"].all()


def test_fold4_pooled_raw_seasons_and_locked_recommendation_mapping():
    alerts_2022, _ = run_active_synthetic(2022, 865)
    alerts_2023, _ = run_active_synthetic(2023, 866)
    alerts_2024, _ = run_active_synthetic(2024, 867)
    family, direction, weekly = pooled_period_results(
        [alerts_2022, alerts_2023, alerts_2024],
        period="pooled_untouched_2022_2024",
        expected_seasons=[2022, 2023, 2024],
    )
    assert set(family["role_family"]) == set(ACTIVE_FAMILIES)
    assert set(direction["role_family"]) == set(ACTIVE_FAMILIES)
    assert weekly["season_weeks"].eq(54).all()

    cross_direction = cross_season_direction_results(
        {
            "redeveloped_2021": alerts_2022.assign(season=2021),
            "untouched_2022": alerts_2022,
            "untouched_2023": alerts_2023,
            "untouched_2024": alerts_2024,
        }
    )
    validation = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    gates = fold4_release_gate_table(
        method_results(alerts_2024),
        validation["release_gates"]["full_release"],
        cross_direction,
    ).set_index("role_family")
    for family in ACTIVE_FAMILIES:
        assert gates.at[family, "fold4_candidate_status"] in {
            "PASSES_FOLD_4_POINT_GATES",
            "FAILS_FOLD_4_POINT_GATES",
            "INSUFFICIENT_EVIDENCE",
        }
    assert gates.at["wr_target_share", "fold4_candidate_status"] == "NOT_APPLICABLE_RETIRED"
    assert gates.at["te_target_share", "fold4_candidate_status"] == "NOT_APPLICABLE_RETIRED"

    recommendations = recommendation_table(gates.reset_index(), integrity_passed=True)
    assert recommendations.loc[
        recommendations["role_family"].eq("wr_target_share"), "recommendation"
    ].item() == "REMAIN_RETIRED"
    assert recommendations.loc[
        recommendations["role_family"].eq("te_target_share"), "recommendation"
    ].item() == "REMAIN_RETIRED"
