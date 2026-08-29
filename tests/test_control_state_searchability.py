from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))

from control_state import resolve_control_state  # noqa: E402
from research_data import player_selector_rows, primary_rows  # noqa: E402


PUBLIC_FILES = [
    ROOT / "dashboard" / "home_page.py",
    *sorted((ROOT / "dashboard" / "pages").glob("0[1-5]_*.py")),
]


def test_query_initializes_then_widget_change_beats_stale_url() -> None:
    initial = resolve_control_state(
        ["DAL", "PHI"], "DAL", None, query_present=True, query_changed=True
    )
    assert (initial.value, initial.source, initial.invalid_query) == ("DAL", "query", False)

    after_widget_change = resolve_control_state(
        ["DAL", "PHI"], "DAL", "PHI", query_present=True, query_changed=False
    )
    assert (after_widget_change.value, after_widget_change.source) == ("PHI", "widget")

    after_url_sync = resolve_control_state(
        ["DAL", "PHI"], "PHI", "PHI", query_present=True, query_changed=True
    )
    assert after_url_sync.value == "PHI"


def test_browser_url_change_can_restore_dal_after_phi() -> None:
    back_navigation = resolve_control_state(
        ["DAL", "PHI"], "DAL", "PHI", query_present=True, query_changed=True
    )
    assert (back_navigation.value, back_navigation.source) == ("DAL", "query")
    state_source = (ROOT / "dashboard" / "control_state.py").read_text(encoding="utf-8")
    assert 'addEventListener("popstate"' in state_source
    for filename in ["home_page.py", "02_Players.py", "03_Games.py"]:
        path = next(path for path in PUBLIC_FILES if path.name == filename)
        assert "enable_browser_history_sync()" in path.read_text(encoding="utf-8")

    teams = next(path for path in PUBLIC_FILES if path.name == "01_Teams.py").read_text(encoding="utf-8")
    assert "enable_browser_history_sync()" not in teams
    assert 'key="team"' in teams
    assert 'bind="query-params"' in teams


def test_second_control_rerun_does_not_revert_first_control() -> None:
    preserved = resolve_control_state(
        ["DAL", "PHI", "MIN"], "PHI", "PHI", query_present=True, query_changed=False
    )
    assert (preserved.value, preserved.source, preserved.invalid_query) == ("PHI", "widget", False)


def test_invalid_query_is_explicit_and_recoverable() -> None:
    invalid = resolve_control_state(
        ["DAL", "PHI"], "INVALID", "DAL", query_present=True, query_changed=True
    )
    assert invalid.invalid_query is True
    assert invalid.value == "DAL"
    recovered = resolve_control_state(
        ["DAL", "PHI"], "PHI", "PHI", query_present=True, query_changed=True
    )
    assert recovered.invalid_query is False
    assert recovered.value == "PHI"


def test_deep_link_pages_update_query_params_from_widget_callbacks() -> None:
    expected = {
        "home_page.py": [("season", "home_season"), ("week", "home_week")],
        "02_Players.py": [("season", "players_season"), ("player", "players_player"), ("family", "players_family")],
        "03_Games.py": [("season", "games_season"), ("week", "games_week"), ("game", "games_game")],
    }
    for filename, pairs in expected.items():
        path = next(path for path in PUBLIC_FILES if path.name == filename)
        source = path.read_text(encoding="utf-8")
        assert "initialize_query_control" in source
        assert "update_query_from_widget" in source
        for query_key, widget_key in pairs:
            assert f'("{query_key}", "{widget_key}")' in source

    teams = next(path for path in PUBLIC_FILES if path.name == "01_Teams.py").read_text(encoding="utf-8")
    assert "initialize_query_control" not in teams
    assert "update_query_from_widget" not in teams
    for key in ("season", "team", "family"):
        assert f'key="{key}"' in teams
    assert teams.count('bind="query-params"') == 3


def test_search_affordances_are_visible_and_consistent() -> None:
    ui = (ROOT / "dashboard" / "research_ui.py").read_text(encoding="utf-8")
    teams = (ROOT / "dashboard" / "pages" / "01_Teams.py").read_text(encoding="utf-8")
    players = (ROOT / "dashboard" / "pages" / "02_Players.py").read_text(encoding="utf-8")
    games = (ROOT / "dashboard" / "pages" / "03_Games.py").read_text(encoding="utf-8")
    explorer = (ROOT / "dashboard" / "pages" / "05_Explorer.py").read_text(encoding="utf-8")
    assert "Start typing to filter options." in ui
    assert "Search or select team" in teams
    assert "Search or select player" in players
    assert "Search or select game" in games
    assert "Search or select team" in explorer and "Search or select player" in explorer
    assert " at " in games and "game_id" in games


def test_public_widget_keys_are_explicit_and_unique() -> None:
    calls = {"selectbox", "select_slider", "segmented_control", "checkbox", "slider", "number_input", "button"}
    found: list[tuple[str, str]] = []
    for path in PUBLIC_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in calls:
                continue
            key = next((item.value for item in node.keywords if item.arg == "key"), None)
            assert isinstance(key, ast.Constant) and isinstance(key.value, str), (
                f"{path.name}:{node.lineno} lacks a stable literal key"
            )
            found.append((path.name, key.value))
    keys = [key for _, key in found]
    assert len(keys) == len(set(keys))


def test_reports_context_and_explorer_reset_guards_remain_present() -> None:
    reports = (ROOT / "dashboard" / "pages" / "04_Reports.py").read_text(encoding="utf-8")
    explorer = (ROOT / "dashboard" / "pages" / "05_Explorer.py").read_text(encoding="utf-8")
    assert 'key="reports_report"' in reports
    assert 'key="reports_context"' in reports
    assert 'key="reports_sort"' in reports and 'sort_options[0]' in reports
    assert 'key="explorer_reset"' in explorer
    assert 'st.session_state["explorer_player"] = "All"' in explorer


def test_multi_team_labels_still_use_week_eighteen_team() -> None:
    data = primary_rows().loc[lambda frame: frame["season"].eq(2025)]
    labels = player_selector_rows(data, 18).set_index("player_id")
    expected = {
        "00-0030035": "PIT",
        "00-0031236": "BUF",
        "00-0032211": "LV",
        "00-0032394": "LA",
        "00-0034272": "PIT",
        "00-0038555": "PHI",
    }
    assert labels.loc[list(expected), "team"].to_dict() == expected
