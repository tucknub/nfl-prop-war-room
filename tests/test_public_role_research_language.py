from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = [
    ROOT / "dashboard" / "Home.py",
    ROOT / "dashboard" / "app.py",
    ROOT / "dashboard" / "research_ui.py",
    ROOT / "dashboard" / "pages" / "01_Teams.py",
    ROOT / "dashboard" / "pages" / "02_Players.py",
    ROOT / "dashboard" / "pages" / "03_Games.py",
    ROOT / "dashboard" / "pages" / "04_Reports.py",
    ROOT / "dashboard" / "pages" / "05_Explorer.py",
]
PROHIBITED = [
    r"\boverall_signal_score\b",
    r"\bmatchup_score\b",
    r"\brecommended_user_action\b",
    r"\bconfidence grade\b",
    r"\bsportsbook\b",
    r"\bbetting\b",
    r"\bodds\b",
    r"\bsustainable\b",
    r"\bpersistent\b",
    r"\bemerging\b",
    r"\bdeteriorating\b",
    r"\bsignal command center\b",
    r"\btop 5\b",
    r"\btop 25\b",
]


def test_public_files_exclude_prohibited_product_language() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_FILES).lower()
    failures = [pattern for pattern in PROHIBITED if re.search(pattern, text)]
    assert not failures, failures


def test_navigation_registers_only_requested_public_pages_plus_admin() -> None:
    app = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    for title in ["Home", "Teams", "Players", "Games", "Reports", "Explorer"]:
        assert f'title="{title}"' in app
    for retired_page in ["Signal_Command_Center", "Matchup_Board", "Position_Signal_Boards", "Blocked_Review"]:
        assert retired_page not in app


def test_admin_has_exact_nonvalidation_label() -> None:
    admin = (ROOT / "dashboard" / "pages" / "90_Admin_Research.py").read_text(encoding="utf-8")
    assert "Experimental Shadow Research — Not Validated" in admin
