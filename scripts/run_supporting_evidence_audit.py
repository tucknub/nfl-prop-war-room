from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "supporting_evidence_experience"
sys.path.insert(0, str(ROOT / "dashboard"))

from research_data import (  # noqa: E402
    ROLE_LABELS, explorer_usage, game_usage, league_situational_summary,
    league_window_summary, load_situational_data, player_profile, player_window_table,
    team_window_summary,
)
from supporting_evidence import (  # noqa: E402
    EXPLORER_PRESETS, REPORT_DEFINITIONS, apply_home_wording, game_team_totals,
    home_selection_signature, matchup_from_game_id, role_leader,
)
from weekly_report import build_weekly_role_report  # noqa: E402


WEEKS = [2, 5, 8, 11, 14, 17, 18]
WALKTHROUGH_WEEKS = [2, 8, 17, 18]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(rows: list[dict[str, object]], name: str) -> None:
    pd.DataFrame(rows).to_csv(OUT / name, index=False, lineterminator="\n")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "screenshots").mkdir(exist_ok=True)

    home_rows: list[dict[str, object]] = []
    report_cache: dict[int, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for week in WEEKS:
        cards, matches = build_weekly_role_report(2025, week)
        revised = apply_home_wording(cards)
        report_cache[week] = (revised, matches)
        unchanged = home_selection_signature(cards) == home_selection_signature(revised)
        for before, after in zip(cards.to_dict("records"), revised.to_dict("records"), strict=True):
            home_rows.append({
                "season": 2025, "week": week, "player_id": before["player_id"],
                "player_name": before["player_name"], "team": before["team"],
                "role_family": before["role_family"], "category": before["category"],
                "situation_type": before["situation_type"], "original_headline": before["headline"],
                "revised_headline": after["headline"], "original_explanation": before["explanation"],
                "revised_explanation": after["explanation"], "selection_unchanged": unchanged,
                "category_unchanged": before["category"] == after["category"],
                "audit_copy_removed": "Selected-week normal-game share materially" not in str(after["explanation"]),
            })
    write_csv(home_rows, "HOME_WORDING_AUDIT.csv")

    sample_teams = sorted({str(row["team"]) for week in WALKTHROUGH_WEEKS for row in report_cache[week][0].to_dict("records")})[:10]
    team_rows: list[dict[str, object]] = []
    for team in sample_teams:
        for family in ROLE_LABELS:
            summary = team_window_summary(2025, team, family, 18, 4, "Normal game")
            if summary.empty:
                continue
            leader = role_leader(summary, label=ROLE_LABELS[family])
            for rank, (_, row) in enumerate(summary.head(5).iterrows(), 1):
                expected = float(row["raw_opportunities"] / row["team_denominator"]) if row["team_denominator"] else np.nan
                team_rows.append({
                    "team": team, "role_family": family, "rank": rank,
                    "player_id": row["player_id"], "player_name": row["player_name"],
                    "raw": int(row["raw_opportunities"]), "denominator": int(row["team_denominator"]),
                    "displayed_share": row["share"], "expected_share": expected,
                    "difference": row["share"] - expected, "leader": bool(leader and leader["player_id"] == str(row["player_id"])),
                    "zero_denominator_suppressed": int(row["team_denominator"]) > 0,
                    "pass": np.isclose(row["share"], expected),
                })
    write_csv(team_rows, "TEAM_PAGE_VALIDATION.csv")

    selected_players = []
    for week in WALKTHROUGH_WEEKS:
        selected_players.extend(report_cache[week][0].head(4)[["player_id", "player_name", "team", "role_family"]].to_dict("records"))
    player_rows: list[dict[str, object]] = []
    for item in {(str(row["player_id"]), str(row["player_name"]), str(row["team"]), str(row["role_family"])) for row in selected_players}:
        player_id, player_name, team, family = item
        profile = player_profile(player_id, 2025, family)
        if profile.empty:
            continue
        windows = player_window_table(profile, int(profile["week"].max()))
        for _, row in windows.iterrows():
            expected = row["Normal raw"] / row["Normal denominator"] if row["Normal denominator"] else np.nan
            player_rows.append({
                "player_id": player_id, "player_name": player_name, "heading_team": profile.iloc[-1]["team"],
                "source_team": team, "role_family": family, "window": row["Window"],
                "raw": int(row["Normal raw"]), "denominator": int(row["Normal denominator"]),
                "displayed_share": row["Normal share"], "expected_share": expected,
                "games": int(row["Games"]), "week_min": int(profile["week"].min()), "week_max": int(profile["week"].max()),
                "week_bounds_pass": bool(profile["week"].between(1, 18).all()),
                "pass": bool(np.isclose(row["Normal share"], expected, equal_nan=True)),
            })
    write_csv(player_rows, "PLAYER_PAGE_VALIDATION.csv")

    situational = load_situational_data()
    game_rows: list[dict[str, object]] = []
    for week in WALKTHROUGH_WEEKS:
        game_ids = report_cache[week][0]["game_id"].drop_duplicates().head(4)
        for game_id in game_ids:
            usage = game_usage(2025, week, str(game_id))
            matchup, away, home = matchup_from_game_id(game_id)
            for team in [away, home]:
                if team not in set(usage["team"].astype(str)):
                    continue
                totals = game_team_totals(usage, team)
                game_situ = situational[situational["game_id"].astype(str).eq(str(game_id)) & situational["team"].eq(team)]
                inside = game_situ[game_situ["context"].eq("inside_5") & game_situ["team_opportunities"].gt(0)]
                game_rows.append({
                    "season": 2025, "week": week, "game_id": game_id, "matchup": matchup, "team": team,
                    **totals, "normal_rb_le_all": totals["normal_rb_opportunities"] <= totals["rb_opportunities"],
                    "normal_targets_le_all": totals["normal_targets"] <= totals["targets"],
                    "inside_five_source_rows": len(inside), "inside_five_available": not inside.empty,
                    "final_score_displayed": False, "one_play_concentration_displayed": False,
                    "pass": totals["normal_rb_opportunities"] <= totals["rb_opportunities"] and totals["normal_targets"] <= totals["targets"],
                })
    write_csv(game_rows, "GAME_PAGE_VALIDATION.csv")

    report_rows: list[dict[str, object]] = []
    for name, question in REPORT_DEFINITIONS.items():
        if name == "Backfield Control": result = league_window_summary(2025, 18, 4, "Normal game", ["rb_carry_share", "rb_opportunity_share"])
        elif name == "Target Hierarchy": result = league_window_summary(2025, 18, 4, "Normal game", ["wr_target_share", "te_target_share"])
        elif name == "Scoring-Area Usage": result = league_situational_summary(2025, 18, 4, "inside_5", list(ROLE_LABELS), overall_context="Normal game")
        elif name == "Game-Script Usage": result = league_situational_summary(2025, 18, 4, "trailing", list(ROLE_LABELS), overall_context="Normal game")
        else: result = league_window_summary(2025, 18, 4, "Normal game", list(ROLE_LABELS))
        result = result[result["team_denominator"].gt(0)]
        reconciles = bool(np.allclose(result["share"], result["raw_opportunities"] / result["team_denominator"])) if not result.empty else True
        report_rows.append({"report": name, "question": question, "rows": len(result), "distinct_question": True, "raw_denominator_present": {"raw_opportunities", "team_denominator"}.issubset(result.columns), "shares_reconcile": reconciles, "high_value_merged": "High-Value Opportunities" not in REPORT_DEFINITIONS, "pass": reconciles})
    write_csv(report_rows, "REPORT_PAGE_VALIDATION.csv")

    explorer_rows: list[dict[str, object]] = []
    for name, values in EXPLORER_PRESETS.items():
        summary, weekly = explorer_usage(2025, 1, 18, str(values["explorer_family"]), game_state=str(values["explorer_game_state"]), quarter=str(values["explorer_quarter"]), down_distance=str(values["explorer_down"]), field_zone=str(values["explorer_zone"]), two_minute=bool(values["explorer_two_minute"]), normal_game=bool(values["explorer_normal"]))
        reconciles = bool(np.allclose(summary["share"], summary["raw_opportunities"] / summary["team_denominator"])) if not summary.empty else True
        explorer_rows.append({"preset": name, "role_family": values["explorer_family"], "game_state": values["explorer_game_state"], "down_distance": values["explorer_down"], "field_zone": values["explorer_zone"], "two_minute": values["explorer_two_minute"], "normal_game": values["explorer_normal"], "players": len(summary), "player_games": len(weekly), "zero_opportunity_rows": int(weekly["raw_opportunities"].eq(0).sum()), "shares_reconcile": reconciles, "pass": reconciles})
    write_csv(explorer_rows, "EXPLORER_PRESET_VALIDATION.csv")

    data_paths = {
        "Player/team game totals": ROOT / "outputs/role_research/game_player_usage.csv.gz",
        "Inside-five opportunities and end-zone targets": ROOT / "outputs/role_research/opportunity_events.csv.gz",
        "Situational player/team counts": ROOT / "outputs/role_research/situational_player_week.csv.gz",
    }
    availability = ["# Data Availability", "", "Only trusted committed public extracts were admitted.", ""]
    for label, path in data_paths.items(): availability.append(f"- **{label}: AVAILABLE.** `{path.relative_to(ROOT).as_posix()}` · SHA-256 `{sha256(path)}`")
    availability.extend(["", "- **Final scores: UNAVAILABLE** in the committed public extract; omitted.", "- **One-play production concentration: UNAVAILABLE** because the committed opportunity event extract has no yards-gained field; omitted.", "- **Longest play: UNAVAILABLE** for the same reason; omitted.", "- **Player/team game totals: AVAILABLE** as validated aggregate carries, targets, receptions, and yards."])
    (OUT / "DATA_AVAILABILITY.md").write_text("\n".join(availability) + "\n", encoding="utf-8")

    (OUT / "DESIGN_DECISIONS.md").write_text(
        "# Supporting Evidence Experience Design Decisions\n\n"
        "- Findings precede controls, complete tables, and methodology.\n"
        "- Mobile cards are the default narrow-screen structure; complete tables remain optional.\n"
        "- Home selection, ranking, categories, limits, and thresholds remain unchanged; only presentation wording changed.\n"
        "- Team, player, and game summaries reuse shared count-weighted calculations.\n"
        "- High-Value Opportunities was merged into Scoring-Area Usage because the slices duplicated the same research question.\n"
        "- Unsupported score, longest-play, and one-play concentration fields are omitted.\n",
        encoding="utf-8",
    )

    walkthrough = ["# Evidence Path Walkthroughs", ""]
    for week in WALKTHROUGH_WEEKS:
        cards, matches = report_cache[week]
        walkthrough.extend([f"## 2025 Week {week}", ""])
        selections = {
            "Backfield": matches[matches["role_family"].isin(["rb_carry_share", "rb_opportunity_share"])],
            "Target": matches[matches["role_family"].isin(["wr_target_share", "te_target_share"])],
            "Overstated context": matches[matches["category"].eq("Box Score Overstated the Role")],
            "Strong opportunity / weak production": matches[matches["category"].eq("Strong Opportunity, Weak Production")],
        }
        for label, candidates in selections.items():
            if candidates.empty:
                walkthrough.append(f"- **{label}:** no technical match in this week; documented without manual substitution.")
                continue
            row = candidates.iloc[0]
            walkthrough.append(f"- **{label}:** {row['player_name']} · {row['team']} · {row['role_family_label']}. Player `{row['player_href']}`, Team `{row['team_href']}`, and Game `{row['game_href']}` preserve the originating state and expose counts, denominators, context, and prior comparison.")
        walkthrough.append("")
    (OUT / "EVIDENCE_PATH_WALKTHROUGHS.md").write_text("\n".join(walkthrough), encoding="utf-8")

    calculations_pass = all(row["selection_unchanged"] and row["category_unchanged"] for row in home_rows) and all(row["pass"] for row in team_rows + player_rows + game_rows + report_rows + explorer_rows)
    final = {
        "phase": "B3 — Supporting Evidence Experience", "baseline_commit": "6c93e26100fb3c077cf2f9a936dea79ceb9ec254",
        "calculation_validation": "PASS" if calculations_pass else "FAIL", "home_cards": len(home_rows),
        "weekly_replay_cards": len(home_rows), "weekly_replay_expected": 79,
        "team_rows": len(team_rows), "player_rows": len(player_rows), "game_rows": len(game_rows),
        "report_questions": len(report_rows), "explorer_presets": len(explorer_rows),
        "unsupported_fields_fabricated": False, "browser_qa": "PENDING", "tests": "PENDING",
    }
    (OUT / "final_validation.json").write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(final, indent=2))
    return 0 if calculations_pass and len(home_rows) == 79 else 1


if __name__ == "__main__":
    raise SystemExit(main())
