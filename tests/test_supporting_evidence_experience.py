from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import (  # noqa: E402
    explorer_usage, game_usage, load_situational_data, player_profile,
    player_selector_rows, player_window_table, primary_rows, team_window_summary,
)
from research_ui import weekly_report_html  # noqa: E402
from supporting_evidence import (  # noqa: E402
    EXPLORER_PRESETS, REPORT_DEFINITIONS, active_filter_summary, apply_explorer_preset,
    apply_home_wording, game_team_totals, home_selection_signature, matchup_from_game_id,
    home_evidence_message, player_role_sentence, role_fingerprint_contexts, role_leader,
    situational_leader, validated_data_status,
)
from weekly_report import DISPLAY_CATEGORIES, build_weekly_role_report  # noqa: E402


REPLAY_WEEKS = [2, 5, 8, 11, 14, 17, 18]


def test_home_wording_does_not_change_selection_or_categories() -> None:
    for week in REPLAY_WEEKS:
        cards, _ = build_weekly_role_report(2025, week)
        revised = apply_home_wording(cards)
        assert home_selection_signature(revised) == home_selection_signature(cards)
        assert list(revised.index) == list(cards.index)


def test_reciprocal_home_headlines_are_team_situations_without_duplicate_formula() -> None:
    cards, _ = build_weekly_role_report(2025, 17)
    revised = apply_home_wording(cards)
    reciprocal = revised[revised["situation_type"].eq("reciprocal_transfer")]
    assert not reciprocal.empty
    assert reciprocal["headline"].str.contains("gained .*;", regex=True).sum() == 0
    assert reciprocal["headline"].str.count("share").le(1).all()


def test_home_expanded_evidence_omits_no_issue_audit_copy() -> None:
    cards, _ = build_weekly_role_report(2025, 8)
    html = weekly_report_html(apply_home_wording(cards), DISPLAY_CATEGORIES)
    assert "No participation exclusion applied" not in html
    assert "Selected-week normal-game share materially" not in html
    assert "Suspected partial-game row remains included" in html or not cards["suspected_partial_game"].any()


def test_home_evidence_links_are_explicit_and_context_reuses_verified_headline() -> None:
    cards, _ = build_weekly_role_report(2025, 17)
    revised = apply_home_wording(cards)
    html = weekly_report_html(revised, DISPLAY_CATEGORIES)
    row = revised.iloc[0]
    assert "origin=home" in html and f"focus={row['player_id']}" in html
    message = home_evidence_message(
        2025,
        17,
        str(row["player_id"]),
        str(row["role_family"]),
        team=str(row["team"]),
        game_id=str(row["game_id"]),
    )
    assert message == f"From Home Week 17: {row['headline']}"
    assert home_evidence_message(2025, 17, "invalid", str(row["role_family"])) is None
    for page in ["01_Teams.py", "02_Players.py"]:
        source = (ROOT / "dashboard/pages" / page).read_text(encoding="utf-8")
        assert 'query_value("focus_family") == role_family' in source


def test_role_leader_reconciles_and_suppresses_zero_denominators() -> None:
    sample = pd.DataFrame([
        {"player_id": "a", "player_name": "A", "position": "RB", "raw_opportunities": 5, "team_denominator": 10, "share": .5, "change": .1, "sample_games": 2},
        {"player_id": "b", "player_name": "B", "position": "RB", "raw_opportunities": 9, "team_denominator": 0, "share": np.nan, "change": .2, "sample_games": 2},
    ])
    leader = role_leader(sample, label="Carry leader")
    assert leader is not None and leader["player_id"] == "a"
    assert leader["share"] == leader["raw"] / leader["denominator"]


def test_team_role_and_situational_leaders_use_verified_counts() -> None:
    overall = team_window_summary(2025, "MIN", "rb_opportunity_share", 8, 4, "Normal game")
    leader = role_leader(overall, label="RB opportunity leader")
    assert leader and leader["denominator"] > 0
    situ = load_situational_data()
    situ = situ[(situ["season"].eq(2025)) & (situ["week"].between(5, 8)) & situ["team"].eq("MIN") & situ["role_family"].eq("rb_opportunity_share")]
    pivot = situ.groupby(["player_id", "player_name", "position", "context"], as_index=False).agg(raw=("raw_opportunities", "sum"), den=("team_opportunities", "sum"))
    passing = pivot[pivot["context"].eq("passing_down")].rename(columns={"raw": "passing_down_raw", "den": "passing_down_denominator"})
    passing["passing_down"] = passing["passing_down_raw"] / passing["passing_down_denominator"].replace(0, np.nan)
    situ_leader = situational_leader(passing, "passing_down", "Passing-down leader")
    assert situ_leader is None or situ_leader["denominator"] > 0


def test_player_window_and_plain_language_summary_reconcile() -> None:
    profile = player_profile("00-0033293", 2025, "rb_opportunity_share")
    windows = player_window_table(profile, int(profile["week"].max())).set_index("Window")
    sentence = player_role_sentence("Test Player", "MIN", "RB", "RB opportunity share", 1, 3, float(windows.loc["Season", "Normal share"]), float(windows.loc["Last 4", "Normal share"]), int(windows.loc["Last 4", "Games"]))
    assert "ranks 1 of 3" in sentence and "season share" in sentence
    assert windows.loc["Last 4", "Normal share"] == windows.loc["Last 4", "Normal raw"] / windows.loc["Last 4", "Normal denominator"]


def test_player_page_handles_sparse_chart_and_week_bounds() -> None:
    source = (ROOT / "dashboard/pages/02_Players.py").read_text(encoding="utf-8")
    assert 'nunique() < 2' in source
    assert "Fewer than two qualifying weekly points" in source
    assert "domain=[1, 18]" in source
    assert "Week 0" not in source


def test_player_role_fingerprint_is_compact_and_contextual() -> None:
    rb_contexts = role_fingerprint_contexts("rb_opportunity_share")
    target_contexts = role_fingerprint_contexts("wr_target_share")
    assert len(rb_contexts) == 5
    assert len(target_contexts) == 6
    assert "inside_10" not in rb_contexts and "inside_10" not in target_contexts
    assert "end_zone" not in rb_contexts and "end_zone" in target_contexts
    source = (ROOT / "dashboard/pages/02_Players.py").read_text(encoding="utf-8")
    assert 'section("Role fingerprint"' in source
    assert 'isin(role_fingerprint_contexts(role_family))' in source


def test_validated_data_status_uses_complete_game_partitions_without_refresh_claim() -> None:
    status = validated_data_status()
    assert status["status"] == "AVAILABLE"
    assert (status["season"], status["week"]) == (2025, 18)
    assert status["completed_games"] == 16
    assert status["label"] == "Data through 2025 Week 18"
    assert status["refresh_timestamp"] is None


def test_all_six_multi_team_selector_identities_remain_correct() -> None:
    data = primary_rows().loc[lambda frame: frame["season"].eq(2025)]
    labels = player_selector_rows(data, 18).set_index("player_id")
    expected = {"00-0030035": "PIT", "00-0031236": "BUF", "00-0032211": "LV", "00-0032394": "LA", "00-0034272": "PIT", "00-0038555": "PHI"}
    assert labels.loc[list(expected), "team"].to_dict() == expected


def test_game_matchup_and_team_totals_are_human_readable_and_reconcile() -> None:
    matchup, away, home = matchup_from_game_id("2025_17_DAL_WAS")
    assert (matchup, away, home) == ("DAL at WAS", "DAL", "WAS")
    usage = game_usage(2025, 17, "2025_17_DAL_WAS")
    for team in [away, home]:
        totals = game_team_totals(usage, team)
        assert totals["normal_rb_opportunities"] <= totals["rb_opportunities"]
        assert totals["normal_targets"] <= totals["targets"]


def test_inside_five_is_displayed_only_from_validated_source() -> None:
    page = (ROOT / "dashboard/pages/03_Games.py").read_text(encoding="utf-8")
    assert 'context_values("inside_5")' in page
    assert "Final score is omitted" in page
    assert "one-play production concentration are omitted" in page
    assert "page_intro(\"Game Usage Review\"" in page


def test_reports_are_distinct_and_high_value_duplicate_is_merged() -> None:
    assert len(REPORT_DEFINITIONS) == 6
    assert "High-Value Opportunities" not in REPORT_DEFINITIONS
    assert len(set(REPORT_DEFINITIONS.values())) == len(REPORT_DEFINITIONS)
    source = (ROOT / "dashboard/pages/04_Reports.py").read_text(encoding="utf-8")
    assert "High-Value Opportunities was merged into Scoring-Area Usage" in source


def test_explorer_presets_set_documented_filters_and_summary() -> None:
    assert len(EXPLORER_PRESETS) == 6
    for name, expected in EXPLORER_PRESETS.items():
        state: dict[str, object] = {}
        apply_explorer_preset(state, name)
        assert state == expected
    summary = active_filter_summary({"team": "PHI", "game_state": "Leading", "quarter": "Q2", "down_distance": "All", "field_zone": "All", "two_minute": False, "normal_game": True}, "RB opportunity share")
    assert summary == "PHI · RB opportunity share · Leading · Q2 · Normal game"


def test_explorer_zero_opportunity_players_remain_eligible() -> None:
    summary, weekly = explorer_usage(2025, 1, 18, "rb_carry_share", game_state="Leading", normal_game=True)
    assert (weekly["raw_opportunities"] == 0).any()
    assert (weekly["team_denominator"] > 0).all()
    assert np.allclose(summary["share"], summary["raw_opportunities"] / summary["team_denominator"])


def test_supporting_page_links_preserve_state() -> None:
    for filename in ["01_Teams.py", "02_Players.py", "03_Games.py", "04_Reports.py", "05_Explorer.py"]:
        source = (ROOT / "dashboard/pages" / filename).read_text(encoding="utf-8")
        assert "/players?player=" in source or filename == "02_Players.py"
    assert "/teams?team=" in (ROOT / "dashboard/pages/04_Reports.py").read_text(encoding="utf-8")


def test_primary_supporting_page_questions_precede_methodology() -> None:
    expected = {"01_Teams.py": "Who currently controls", "02_Players.py": "What role does this player", "03_Games.py": "What happened to each player", "05_Explorer.py": "Build a custom situational view"}
    for filename, phrase in expected.items():
        source = (ROOT / "dashboard/pages" / filename).read_text(encoding="utf-8")
        assert phrase in source
        assert source.index(phrase) < source.index("methodology_expander") if source.count("methodology_expander") == 1 else True
