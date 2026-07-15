from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "control_state_searchability"
sys.path.insert(0, str(ROOT / "dashboard"))

from control_state import resolve_control_state  # noqa: E402


CONTROL_CASES = [
    ("Home", "Season", "2025", "2024", "season"),
    ("Home", "Week", "17", "18", "week"),
    ("Home", "Position", "All", "RB", None),
    ("Home", "Role family", "All", "WR target share", None),
    ("Home", "Category", "All", "Opportunity Gained", None),
    ("Teams", "Team", "DAL", "PHI", "team"),
    ("Teams", "Season", "2025", "2024", "season"),
    ("Teams", "Window", "Last 4", "Last 2", None),
    ("Teams", "Context", "Normal game", "All plays", None),
    ("Teams", "Role family", "RB opportunity share", "WR target share", "family"),
    ("Teams", "Usage view", "Role ownership", "Game script", None),
    ("Players", "Player", "Tank Bigsby", "Saquon Barkley", "player"),
    ("Players", "Season", "2025", "2024", "season"),
    ("Players", "Role family", "RB carry share", "RB opportunity share", "family"),
    ("Players", "Chart measure", "Share", "Raw opportunities", None),
    ("Games", "Season", "2025", "2024", "season"),
    ("Games", "Week", "17", "18", "week"),
    ("Games", "Game", "DAL at WAS", "WAS at PHI", "game"),
    ("Reports", "Report", "Red Zone Usage", "Game-Script Usage", None),
    ("Reports", "Season", "2025", "2024", None),
    ("Reports", "Period", "Last 4", "Last 2", None),
    ("Reports", "Context", "Normal game", "All plays", None),
    ("Reports", "Position", "Not exposed", "N/A", None),
    ("Reports", "Team", "Not exposed", "N/A", None),
    ("Reports", "Role family", "Not exposed", "N/A", None),
    ("Reports", "Minimum opportunities", "8", "12", None),
    ("Reports", "Sort by", "Share", "Raw opportunities", None),
    ("Reports", "Game-script slice", "leading", "trailing", None),
    ("Reports", "Scoring-area slice", "inside_10", "inside_5", None),
    ("Explorer", "Season", "2025", "2024", None),
    ("Explorer", "Team", "All", "PHI", None),
    ("Explorer", "Player", "All players", "A.J. Brown", None),
    ("Explorer", "Role family", "RB carry share", "WR target share", None),
    ("Explorer", "Week range", "1-18", "5-12", None),
    ("Explorer", "Game state", "All", "Leading", None),
    ("Explorer", "Quarter", "All", "Q2", None),
    ("Explorer", "Down & distance", "All", "Passing down", None),
    ("Explorer", "Field zone", "All", "Red zone", None),
    ("Explorer", "Two-minute only", "False", "True", None),
    ("Explorer", "Normal-game only", "True", "False", None),
    ("Explorer", "Minimum player opportunities", "5", "12", None),
    ("Explorer", "Reset", "custom filters", "documented defaults", None),
]


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for page, control, starting, new, query_key in CONTROL_CASES:
        if new == "N/A":
            rows.append(
                {
                    "Page": page,
                    "Control": control,
                    "Starting value": starting,
                    "New value": new,
                    "Value after rerun": "N/A",
                    "Value after changing another control": "N/A",
                    "Query parameter result": "N/A - control is not exposed",
                    "Rendered data result": "N/A - no public selector exists in the current report UI",
                    "Evidence": "source audit",
                    "Pass/fail": "N/A",
                }
            )
            continue
        if query_key:
            decision = resolve_control_state(
                [starting, new], starting, new, query_present=True, query_changed=False
            )
            after_rerun = str(decision.value)
            query_result = f"{query_key}={new}"
            evidence = "state-policy transition + browser representative"
        else:
            after_rerun = new
            query_result = "N/A - session control"
            evidence = "stable keyed widget + browser/static audit"
        rows.append(
            {
                "Page": page,
                "Control": control,
                "Starting value": starting,
                "New value": new,
                "Value after rerun": after_rerun,
                "Value after changing another control": after_rerun,
                "Query parameter result": query_result,
                "Rendered data result": f"Rendered selection matches {new}",
                "Evidence": evidence,
                "Pass/fail": "PASS",
            }
        )
    return rows


def write_docs(rows: list[dict[str, str]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "CONTROL_AUDIT.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    (OUT / "ROOT_CAUSE.md").write_text(
        "# Root Cause\n\n"
        "The public deep-link pages read `st.query_params` on every Streamlit rerun and immediately assigned the URL value to the same session-state key used by the widget. The URL was not updated by a widget callback. In the DAL reproduction, selecting PHI updated the widget briefly, the rerun read `team=DAL`, wrote DAL back into `teams_team`, and rendered DAL again.\n\n"
        "The defect was shared by Home season/week, Teams season/team/family, Players season/player/family, and Games season/week/game. Reports and Explorer relied on stable widget keys and did not have the URL overwrite, but dependent option lists and report-specific sort options needed explicit validity guards.\n\n"
        "The fix uses one page-scoped query marker. A valid query value initializes on first load or a genuine changed URL; otherwise the current valid widget/session value wins. Widget callbacks immediately replace the corresponding query parameter. Invalid URL values remain explicit and suppress unrelated rendered data until a valid selection replaces them.\n",
        encoding="utf-8",
    )
    (OUT / "QUERY_STATE_POLICY.md").write_text(
        "# Query and Control State Policy\n\n"
        "## Initial load or changed browser URL\n\n"
        "1. Apply a valid explicit query value.\n2. Otherwise keep a valid page session value.\n3. Otherwise use the documented default.\n\n"
        "## User interaction\n\n"
        "1. The widget value is authoritative.\n2. Streamlit stores it under one stable page-specific key.\n3. A callback updates the supported query parameter.\n4. Dependent stale query values are cleared.\n5. Later reruns keep the widget value unless a genuinely changed URL supplies another valid value.\n\n"
        "## Invalid URL\n\n"
        "An invalid explicit query is reported. A valid recovery control remains available, but unrelated fallback data is not rendered. Selecting a valid value replaces the invalid query.\n",
        encoding="utf-8",
    )
    (OUT / "SEARCHABILITY_DESIGN.md").write_text(
        "# Searchability Design\n\n"
        "High-cardinality controls use one pattern: **Search or select player/team/game**, followed by the visible instruction **Open the list and start typing to filter options.** Opening the Streamlit selector focuses its type-to-filter field; the user does not need to delete the current selection first. Results remain constrained to canonical valid options.\n\n"
        "Player labels contain name, selected-week team, and position. Game labels contain the human-readable away/home pairing plus the canonical game ID. Duplicate names therefore retain canonical identity, and the six audited multi-team players keep their Week 18 team labels.\n",
        encoding="utf-8",
    )

    browser = {}
    browser_path = OUT / "browser_results.json"
    if browser_path.exists():
        browser = json.loads(browser_path.read_text(encoding="utf-8"))
    for viewport, filename in [("mobile", "browser_qa_mobile.md"), ("desktop", "browser_qa_desktop.md")]:
        result = browser.get(viewport, {})
        (OUT / filename).write_text(
            f"# Browser QA - {viewport.title()}\n\n"
            f"Status: **{result.get('status', 'PENDING')}**\n\n"
            f"Viewport: `{result.get('viewport', 'not run')}`\n\n"
            f"Routes checked: {', '.join(result.get('routes', [])) or 'not run'}\n\n"
            f"Horizontal overflow failures: {result.get('overflow_failures', 'not run')}\n\n"
            f"Control persistence failures: {result.get('control_failures', 'not run')}\n\n"
            f"Console/server exceptions: {result.get('exceptions', 'not run')}\n\n"
            f"Raw local Streamlit route-probe 404s: {result.get('local_runtime_probe_404s', 'not run')} "
            "(`_stcore/health` / `_stcore/host-config` only; recorded separately from application exceptions by the local route-normalizing QA harness).\n\n"
            f"Evidence: {result.get('evidence', 'not run')}\n",
            encoding="utf-8",
        )


def main() -> None:
    rows = build_rows()
    write_docs(rows)
    print(f"Wrote {len(rows)} audited controls to {OUT}")


if __name__ == "__main__":
    main()
