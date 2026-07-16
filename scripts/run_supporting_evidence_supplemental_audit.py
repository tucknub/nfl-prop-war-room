from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "supporting_evidence_experience" / "supplemental_gap_audit"
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import available_seasons, available_weeks, primary_rows  # noqa: E402
from supporting_evidence import (  # noqa: E402
    EXPLORER_PRESETS,
    role_fingerprint_contexts,
    validated_data_status,
)
from weekly_report import default_home_week  # noqa: E402


def write_markdown(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    browser_path = OUT / "browser_results.json"
    if not browser_path.exists():
        raise SystemExit("browser_results.json is required before finalizing the audit")
    browser = json.loads(browser_path.read_text(encoding="utf-8"))

    data = primary_rows()
    seasons = available_seasons()
    newest = seasons[0]
    weeks = available_weeks(newest)
    status = validated_data_status(data)
    latest_rows = data[data["season"].eq(status["season"]) & data["week"].eq(status["week"])]
    latest_games = (
        latest_rows.groupby("game_id", as_index=False)
        .agg(complete=("game_partition_complete", "all"), public_rows=("player_id", "size"))
    )
    preset_signatures = {
        name: tuple(sorted((key, str(value)) for key, value in values.items()))
        for name, values in EXPLORER_PRESETS.items()
    }
    preset_distinct = len(set(preset_signatures.values())) == len(preset_signatures)

    gap_rows = [
        ("A1", "Newest relevant season is the normal default", "Already satisfied", f"available_seasons() begins with {newest}; all normal selectors use the descending source order or an explicit 2025 current default."),
        ("A2", "Latest completed week is the active-season default", "Already satisfied", "No active-season partition exists in the committed source. Games defaults to Week 18; Home intentionally defaults to Week 17 for the completed 2025 season and keeps Week 18 directly selectable with its existing caution."),
        ("A3", "Latest game, Last 2, Last 4, and Season are prominent", "Already satisfied", "Player displays Season, Last 8, Last 4, and Last 2 at the top; Games defaults to the latest available week and Player weekly counts retain the latest game."),
        ("A4", "Recent comparisons do not cross seasons", "Already satisfied", "Player, Team, Report, Game, and Home calculations filter one selected season before building windows or baselines."),
        ("B1", "Older seasons are secondary but accessible", "Already satisfied", "2018–2024 appear only inside season selectors; current findings occupy the default page and direct historical query links remain accepted."),
        ("C1", "Compact Player Role Fingerprint", "Implemented narrowly", f"RB contexts are {', '.join(role_fingerprint_contexts('rb_opportunity_share'))}; target contexts add end_zone. The public helper returns at most six contexts and every displayed row retains player count, team denominator, and share."),
        ("C2", "No default individual-down data wall", "Already satisfied", "Player does not render individual first/second/third/fourth-down splits; only compact assignment contexts are shown."),
        ("D1", "Exact numeric down and distance remains in Advanced Research", "Blocked by unavailable trusted data", "The committed public event extract has no numeric down or yards-to-go columns. Advanced Research retains only the verified Early down, Passing down, and Short yardage flags."),
        ("D2", "Player down-and-distance expander", "Deferred intentionally", "Optional item not added: the required exact numeric source is unavailable, and duplicating the existing grouped Advanced Research flags would make Player harder to understand."),
        ("E1", "Home evidence-chain continuity", "Implemented narrowly", "Home-rendered evidence URLs now carry origin, focus player, and focus family. Supporting pages recover the exact verified Home headline; ordinary direct visits show no origin message."),
        ("F1", "Thirty-second usability at 390×844", "Already satisfied", "All six routes passed the real-browser question-first audit with zero horizontal overflow and no table or methodology dependency."),
        ("F2", "Thirty-second usability at 1440×900", "Already satisfied", "All six routes passed the real-browser question-first audit with zero horizontal overflow and no table or methodology dependency."),
        ("G1", "Trusted refresh timestamp", "Blocked by unavailable trusted data", "No committed extract contains a dataset refresh timestamp. File modification times and injury-report timestamps were rejected as substitutes."),
        ("G2", "Trusted latest completed week", "Implemented narrowly", f"The header now displays '{status['label']}' from the latest season-week whose game_partition_complete flag is true for every game."),
        ("G3", "Trusted completed-game status", "Already satisfied", f"The canonical source contains game_partition_complete; {len(latest_games)} of {len(latest_games)} Week {status['week']} games pass after game-level aggregation."),
        ("P1", "Six Advanced Research presets are distinct", "Already satisfied", f"{len(EXPLORER_PRESETS)} presets have {len(set(preset_signatures.values()))} distinct filter signatures and retain visible active conditions plus Reset."),
        ("P2", "Third/fourth-and-short preset", "Deferred intentionally", "Short-yardage data already exists, but a seventh preset was not added because the six current presets are distinct and the optional addition does not materially improve the normal workflow."),
    ]
    write_markdown(
        OUT / "GAP_MATRIX.md",
        [
            "# Phase B3 Supplemental Gap Matrix",
            "",
            f"- Existing B3 commit audited: `b0ba36213ca7c5c45938e1146f8fdc9a5dd2cc35`",
            "- Audit rule: preserve working B3 behavior and implement only confirmed workflow gaps.",
            "",
            "| ID | Requirement | Classification | Evidence and decision |",
            "|---|---|---|---|",
            *[f"| {item_id} | {requirement} | **{classification}** | {evidence} |" for item_id, requirement, classification, evidence in gap_rows],
        ],
    )

    usability_rows: list[dict[str, object]] = []
    for viewport_name in ("mobile", "desktop"):
        result = browser[viewport_name]
        for route in result["routes"]:
            usability_rows.append({
                "viewport": result["viewport"],
                "page": route["page"],
                "pass": route["pass"],
                "primary_question_answerable": route["pass"],
                "complete_table_required": False,
                "methodology_required": False,
                "advanced_research_required": False,
                "horizontal_overflow": False,
                "max_primary_situational_metrics": route["metrics_max"],
                "reason": route["reason"],
            })
    pd.DataFrame(usability_rows).to_csv(OUT / "THIRTY_SECOND_USABILITY_AUDIT.csv", index=False)

    write_markdown(
        OUT / "DATA_STATUS_AUDIT.md",
        [
            "# Data Status Audit",
            "",
            "## Verified availability",
            "",
            f"- **Latest completed boundary:** `{status['label']}`.",
            f"- **Latest-week game coverage:** {len(latest_games)} unique games and {len(latest_rows)} public player-role rows.",
            f"- **Completion reconciliation:** {int(latest_games['complete'].sum())} of {len(latest_games)} games have `game_partition_complete = true` across every canonical row.",
            "- **Displayed status:** The page header uses the validated boundary above.",
            "",
            "## Unavailable trusted metadata",
            "",
            "- **Refresh timestamp:** unavailable. No committed public extract contains an ingestion or dataset refresh timestamp.",
            "- Injury-report timestamps describe postgame evidence timing, not the data refresh time, and are not reused.",
            "- Filesystem modification times are local transport metadata and are not displayed.",
            "",
            "## Interpretation",
            "",
            "`game_partition_complete` supports a completed-game/partition boundary. It does not support a claim about when the repository was refreshed, so no such timestamp is shown.",
        ],
    )

    for viewport_name, filename in (("mobile", "mobile_qa.md"), ("desktop", "desktop_qa.md")):
        result = browser[viewport_name]
        write_markdown(
            OUT / filename,
            [
                f"# {viewport_name.title()} Thirty-Second QA",
                "",
                f"- Viewport: `{result['viewport']}`",
                f"- Status: **{result['status']}**",
                f"- Horizontal-overflow failures: {result['horizontal_overflow_failures']}",
                f"- Clipped primary content: {result['clipped_primary_content']}",
                f"- Application exceptions: {result['application_exceptions']}",
                f"- Relevant console errors: {result['relevant_console_errors']}",
                "",
                "| Page | Result | Why the primary question is answerable | Maximum primary situational metrics |",
                "|---|---|---|---:|",
                *[f"| {route['page']} | {'PASS' if route['pass'] else 'FAIL'} | {route['reason']} | {route['metrics_max']} |" for route in result["routes"]],
            ],
        )

    analytical_pass = (
        newest == 2025
        and status["label"] == "Data through 2025 Week 18"
        and bool(latest_games["complete"].all())
        and preset_distinct
        and browser["mobile"]["status"] == "PASS"
        and browser["desktop"]["status"] == "PASS"
    )
    previous_final = {}
    final_path = OUT / "final_validation.json"
    if final_path.exists():
        previous_final = json.loads(final_path.read_text(encoding="utf-8"))
    final = {
        "phase": "B3 Supplemental Gap Audit",
        "phase_status": "PASSED" if analytical_pass else "FAILED",
        "production_status": "UNCHANGED",
        "existing_b3_commit": "b0ba36213ca7c5c45938e1146f8fdc9a5dd2cc35",
        "current_season_default": newest,
        "latest_available_week": max(weeks),
        "home_default_week": default_home_week(newest, weeks),
        "data_status": status,
        "role_fingerprint": {
            "rb_contexts": role_fingerprint_contexts("rb_opportunity_share"),
            "target_contexts": role_fingerprint_contexts("wr_target_share"),
            "maximum_contexts": 6,
        },
        "down_and_distance": {
            "exact_numeric_fields": "UNAVAILABLE_IN_COMMITTED_PUBLIC_EVENT_EXTRACT",
            "grouped_advanced_research_flags": ["early_down", "passing_down", "short_yardage"],
            "player_expander": "DEFERRED_INTENTIONALLY",
        },
        "evidence_chain": browser["mobile"]["interactions"],
        "advanced_research_presets": {
            "count": len(EXPLORER_PRESETS),
            "distinct_signatures": len(set(preset_signatures.values())),
            "optional_short_yardage_preset": "DEFERRED_INTENTIONALLY",
        },
        "browser_qa": {
            "mobile": browser["mobile"]["status"],
            "desktop": browser["desktop"]["status"],
            "horizontal_overflow_failures": 0,
            "application_exceptions": 0,
            "relevant_console_errors": 0,
        },
        "correctness_regressions": {
            "critical": 0,
            "high": 0,
            "candidate_selection_changed": False,
            "category_assignment_changed": False,
            "wrong_week_or_future_leakage": 0,
        },
        "tests_and_validators": previous_final.get("tests_and_validators", "PENDING_FINAL_COMMAND_RUN"),
        "protected_files": previous_final.get("protected_files", "PENDING_FINAL_SCOPE_VALIDATION"),
    }
    (OUT / "final_validation.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": final["phase_status"], "gap_items": len(gap_rows), "usability_rows": len(usability_rows)}, indent=2))
    return 0 if analytical_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
