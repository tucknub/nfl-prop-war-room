from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "propwar_correctness_audit"
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import (  # noqa: E402
    KEY_COLUMNS,
    available_seasons,
    league_window_summary,
    load_role_data,
    observable_changes,
    player_profile,
    player_window_table,
    primary_rows,
    team_window_summary,
)
from research_ui import nfl_week_axis_values, numeric_percent_sort, player_href  # noqa: E402


def _final() -> dict:
    return json.loads((OUT / "final_validation.json").read_text(encoding="utf-8"))


def test_share_audit_records_formula_and_player_windows_pass() -> None:
    checks = pd.read_csv(OUT / "calculation_discrepancies.csv")
    displayed = checks[checks["displayed_percentage"].notna()].copy()
    expected_formula = displayed["numerator"] / displayed["denominator"].replace(0, pd.NA)
    assert (expected_formula.fillna(-1) - displayed["expected_percentage"].fillna(-1)).abs().max() < 1e-12
    assert not checks.loc[checks["audit_area"].eq("Player"), "status"].eq("FAIL").any()


def test_windows_use_summed_counts_and_correct_qualifying_games() -> None:
    data = primary_rows()
    sample = data[(data["season"].eq(2025)) & data["role_family"].eq("wr_target_share")]
    player_id = str(sample.groupby("player_id")["raw_opportunities_normal"].sum().idxmax())
    profile = player_profile(player_id, 2025, "wr_target_share")
    table = player_window_table(profile, int(profile["week"].max())).set_index("Window")
    for label, count in [("Season", None), ("Last 8", 8), ("Last 4", 4), ("Last 2", 2)]:
        rows = profile if count is None else profile.tail(count)
        raw = rows["raw_opportunities_normal"].sum()
        denominator = rows["team_opportunities_normal"].sum()
        assert table.loc[label, "Normal raw"] == raw
        assert table.loc[label, "Normal denominator"] == denominator
        assert table.loc[label, "Normal share"] == pytest.approx(raw / denominator)


def test_home_has_no_future_leakage_but_known_stale_week_defect_is_recorded() -> None:
    home = pd.read_csv(OUT / "home_validation.csv")
    assert home["no_future_leakage"].all()
    assert home["same_season"].all()
    assert (home["baseline_games"] >= 2).all()
    assert home["status"].eq("FAIL").sum() == _final()["results"]["home_failures"]


def test_numeric_percentage_sort_is_numeric_and_nulls_last() -> None:
    source = pd.DataFrame({"share": [0.083, None, 0.25, "0.125"]})
    result = numeric_percent_sort(source, "share", ascending=False)
    assert result["share"].dropna().tolist() == [0.25, 0.125, 0.083]
    assert pd.isna(result.iloc[-1]["share"])


def test_no_duplicate_canonical_keys_and_no_week_zero() -> None:
    role = load_role_data()
    assert not role.duplicated(KEY_COLUMNS).any()
    assert role["week"].between(1, 18).all()
    assert nfl_week_axis_values() == list(range(1, 19))


def test_player_links_round_trip_parameters() -> None:
    href = player_href("00-0031234", 2025, "wr_target_share")
    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    assert parsed.path == "/players"
    assert query == {"player": ["00-0031234"], "season": ["2025"], "family": ["wr_target_share"]}


def test_cross_page_values_agree_for_identical_filters() -> None:
    result = pd.read_csv(OUT / "cross_page_reconciliation.csv")
    assert not result["status"].eq("FAIL").any()
    team = team_window_summary(2025, "ATL", "rb_carry_share", 18, 4, "Normal game")
    league = league_window_summary(2025, 18, 4, "Normal game", ["rb_carry_share"])
    merged = team.merge(league[league["team"].eq("ATL")], on=["player_id", "team"], suffixes=("_team", "_league"))
    assert (merged["share_team"] - merged["share_league"]).abs().max() < 1e-12


def test_default_completed_season_and_public_navigation() -> None:
    assert available_seasons()[0] == 2025
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    for title in ["Home", "Teams", "Players", "Games", "Reports", "Explorer"]:
        assert f'title="{title}"' in app
    assert 'title="Research Admin"' not in app


def test_explorer_reset_defaults_are_complete() -> None:
    tree = ast.parse((ROOT / "dashboard" / "pages" / "05_Explorer.py").read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_reset_explorer")
    assignment = next(node for node in function.body if isinstance(node, ast.Assign))
    defaults = ast.literal_eval(assignment.value)
    assert defaults == {
        "explorer_season": 2025, "explorer_team": "All", "explorer_player": "All",
        "explorer_family": "rb_carry_share", "explorer_weeks": (1, 18),
        "explorer_game_state": "All", "explorer_quarter": "All", "explorer_down": "All",
        "explorer_zone": "All", "explorer_two_minute": False, "explorer_normal": True,
        "explorer_minimum": 5,
    }


@pytest.mark.xfail(strict=True, reason="Known High: invalid player and team query values lack explicit invalid states")
def test_invalid_state_handling_is_explicit() -> None:
    players = (ROOT / "dashboard" / "pages" / "02_Players.py").read_text(encoding="utf-8")
    teams = (ROOT / "dashboard" / "pages" / "01_Teams.py").read_text(encoding="utf-8")
    assert "Invalid player" in players
    assert "query_params" in teams and "Invalid team" in teams


@pytest.mark.xfail(strict=True, reason="Known High: Home retains each player's latest row at or before selected week")
def test_home_only_contains_selected_week() -> None:
    rows = observable_changes(2025, 18)
    assert rows["week"].eq(18).all()


@pytest.mark.xfail(strict=True, reason="Known High: Explorer omits eligible zero-opportunity player-games")
def test_explorer_zero_opportunity_games_reconcile() -> None:
    result = pd.read_csv(OUT / "explorer_validation.csv")
    assert not result["status"].eq("FAIL").any()


def test_public_language_guardrail_and_protected_gate_metadata() -> None:
    language = pd.read_csv(OUT / "public_language_scan.csv")
    assert not language["status"].eq("FAIL").any()
    assert _final()["baseline_commit"] == "8b759f18c34708300acf5e3ef84d0e4cbbbde597"
