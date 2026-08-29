from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teams_default_view_does_not_eagerly_load_play_level_situational_data() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "01_Teams.py"
    ).read_text(encoding="utf-8")

    assert "_combined_family_summary" not in source
    assert "family: team_window_summary(" in source

    view_index = source.index('view_mode = st.segmented_control(')
    situational_call = source.index("situational_team_summary(", view_index)
    assert situational_call > view_index

    before_view = source[:view_index]
    assert "situational_team_summary(" not in before_view
    assert "situational_leader(" not in before_view


def test_teams_situational_view_preserves_selected_family_context() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "01_Teams.py"
    ).read_text(encoding="utf-8")

    assert 'if view_mode != "Role ownership":' in source
    assert "role_family," in source
    assert "view_summary = summary.merge(" in source
    assert 'on=["player_id", "player_name", "position"]' in source
