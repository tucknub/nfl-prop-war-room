from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "propwar_correctness_audit"
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import (  # noqa: E402
    league_situational_summary,
    observable_changes,
    situational_team_summary,
)
from research_ui import resolve_query_choice  # noqa: E402


def test_all_home_rows_use_selected_week_and_prior_failures_are_removed() -> None:
    current = observable_changes(2025, 18)
    assert not current.empty
    assert current["season"].eq(2025).all()
    assert current["week"].eq(18).all()
    before = pd.read_csv(OUT / "home_validation.csv")
    failed_keys = set(
        before.loc[before["status"].eq("FAIL"), ["player_id", "team", "role_family"]]
        .astype(str).itertuples(index=False, name=None)
    )
    current_keys = set(
        current[["player_id", "team", "role_family"]].astype(str).itertuples(index=False, name=None)
    )
    assert failed_keys.isdisjoint(current_keys)


def test_all_71_situational_denominator_discrepancies_are_corrected() -> None:
    checks = pd.read_csv(OUT / "calculation_discrepancies_after_fix.csv")
    situational = checks[checks["sample_type"].eq("situational")]
    assert len(situational) >= 71
    assert not situational["status"].eq("FAIL").any()


def test_zero_family_game_still_contributes_team_denominator() -> None:
    result = situational_team_summary(2025, "ATL", "rb_carry_share", 18, 4, "All plays")
    bijan = result[result["player_name"].eq("Bijan Robinson")].iloc[0]
    assert bijan["two_minute_raw"] == 7
    assert bijan["two_minute_denominator"] == 12
    assert bijan["two_minute"] == 7 / 12


def test_all_explorer_zero_opportunity_discrepancies_are_corrected() -> None:
    checks = pd.read_csv(OUT / "explorer_validation_after_fix.csv")
    assert checks["case_id"].nunique() == 18
    assert not checks["status"].eq("FAIL").any()


def test_all_three_situational_reports_honor_normal_and_all_play_context() -> None:
    cases = [
        ("red_zone", list({"rb_carry_share", "rb_opportunity_share", "wr_target_share", "te_target_share"})),
        ("leading", list({"rb_carry_share", "rb_opportunity_share", "wr_target_share", "te_target_share"})),
        ("inside_10", list({"rb_carry_share", "rb_opportunity_share", "wr_target_share", "te_target_share"})),
    ]
    for situational_context, families in cases:
        normal = league_situational_summary(
            2025, 18, 4, situational_context, families, overall_context="Normal game"
        )
        all_play = league_situational_summary(
            2025, 18, 4, situational_context, families, overall_context="All plays"
        )
        merged = normal.merge(
            all_play,
            on=["player_id", "team", "role_family"],
            how="outer",
            suffixes=("_normal", "_all"),
        )
        assert (
            merged["raw_opportunities_normal"].ne(merged["raw_opportunities_all"])
            | merged["team_denominator_normal"].ne(merged["team_denominator_all"])
        ).fillna(True).any()


def test_query_resolution_is_url_first_and_invalid_is_explicit() -> None:
    options = ["ARI", "BUF", "CLE"]
    assert resolve_query_choice(options, "BUF", "ARI") == ("BUF", False)
    assert resolve_query_choice(options, "INVALID", "ARI") == (None, True)
    assert resolve_query_choice(options, "", "CLE") == ("CLE", False)


def test_after_fix_manifest_has_zero_critical_and_high_failures() -> None:
    final = json.loads((OUT / "final_validation_after_fix.json").read_text(encoding="utf-8"))
    assert final["phase_status"] == "PASSED"
    assert final["correctness_results"] == {
        "critical_findings": 0,
        "high_findings": 0,
        "home_wrong_week_failures": 0,
        "situational_denominator_failures": 0,
        "explorer_zero_opportunity_failures": 0,
        "report_context_failures": 0,
        "invalid_player_team_state_failures": 0,
        "cross_page_failures": 0,
    }
