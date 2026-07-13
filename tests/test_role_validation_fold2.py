from copy import deepcopy
from pathlib import Path
import sys

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.fold2 import (  # noqa: E402
    PRIMARY_POLICY,
    assert_frozen_config_integrity,
    canonical_audit,
    generalization_direction_table,
    method_results,
    release_gate_table,
)
from role_validation.redevelopment import (  # noqa: E402
    EXPECTED_METHODS,
    ROLE_FAMILIES,
    run_candidate,
)
from role_validation.synthetic import make_synthetic_player_week_data  # noqa: E402


CONFIG_SHA256 = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"


def test_frozen_config_matches_fold1_report_and_fingerprint():
    result = assert_frozen_config_integrity(
        ROOT / "config" / "role_change_fold2_candidate.yaml",
        ROOT
        / "outputs"
        / "role_validation"
        / "fold_1_diagnostics"
        / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md",
        expected_sha256=CONFIG_SHA256,
    )
    assert result["sha256"] == CONFIG_SHA256
    assert all(result["checks"].values())


def test_fold2_canonical_audit_enforces_grain_completeness_and_coverage():
    rows = []
    for week in range(1, 19):
        rows.append(
            {
                "season": 2022,
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
    audit = canonical_audit(pd.DataFrame(rows), required)
    assert audit.loc[0, "canonical_rows"] == 18
    assert audit.loc[0, "duplicate_key_rows"] == 0
    assert audit.loc[0, "identity_coverage"] == 1.0


def test_frozen_candidate_equal_volume_for_every_2022_family_week():
    data = make_synthetic_player_week_data(
        seasons=[2022], weeks=range(1, 19), players_per_family=20, seed=851
    )
    document = yaml.safe_load(
        (ROOT / "config" / "role_change_fold2_candidate.yaml").read_text(encoding="utf-8")
    )
    candidate = deepcopy(document["candidate"])
    result = run_candidate(
        data,
        candidate,
        partial_policy=PRIMARY_POLICY,
        allowed_seasons=[2022],
    )
    verification = result["equal_volume"]
    assert len(verification) == len(ROLE_FAMILIES) * 18
    assert verification["equal_volume"].all()
    assert verification["observed_method_count"].eq(len(EXPECTED_METHODS)).all()
    count_columns = [f"{method}_count" for method in EXPECTED_METHODS]
    assert verification[count_columns].nunique(axis=1).eq(1).all()
    assert set(result["alerts"]["season"].astype(int).unique()).issubset({2022})

    methods = method_results(result["alerts"])
    direction = generalization_direction_table(result["alerts"], result["alerts"])
    release_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    gates = release_gate_table(
        methods,
        release_config["release_gates"]["full_release"],
        direction,
    )
    assert set(gates["role_family"]) == set(ROLE_FAMILIES)
    assert gates["status"].isin(
        {
            "PASSES_FOLD_2_POINT_GATES",
            "FAILS_FOLD_2_POINT_GATES",
            "INSUFFICIENT_EVIDENCE",
        }
    ).all()
