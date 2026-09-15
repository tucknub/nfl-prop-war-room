from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
for value in (ROOT, DASHBOARD):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from weekly_report import (  # noqa: E402
    CATEGORY_GAINED,
    CATEGORY_LOST,
    CATEGORY_OVERSTATED,
    CATEGORY_WEAK_PRODUCTION,
    WEEKLY_REPORT_CONFIG,
    build_weekly_role_report,
)


def _record_check(checks: list[dict[str, object]], name: str, passed: bool, observed: object, expected: object) -> None:
    checks.append(
        {
            "check": name,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
        }
    )


def _top_signals(frame: pd.DataFrame, limit: int = 20) -> list[dict[str, object]]:
    if frame.empty:
        return []
    ranked = frame.copy()
    ranked["audit_magnitude"] = pd.to_numeric(
        ranked.get("absolute_share_change", ranked.get("share_change", 0)),
        errors="coerce",
    ).fillna(0).abs()
    ranked = ranked.sort_values(
        ["audit_magnitude", "current_raw"],
        ascending=[False, False],
        kind="stable",
    ).head(limit)
    columns = [
        "category",
        "player_name",
        "team",
        "position",
        "role_family",
        "current_raw",
        "current_denominator",
        "current_share",
        "baseline_raw",
        "baseline_denominator",
        "baseline_share",
        "share_change",
        "baseline_games",
        "all_play_share",
        "outside_normal_opportunities",
        "production_rate",
    ]
    available = [column for column in columns if column in ranked]
    clean = ranked[available].copy()
    clean = clean.where(pd.notna(clean), None)
    return clean.to_dict("records")


def audit_role_change_signals(season: int, week: int) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    payload: dict[str, object] = {
        "schema_version": 1,
        "season": int(season),
        "week": int(week),
        "status": "SKIPPED" if week < 2 else "PASS",
        "message": (
            "Week 1 establishes the in-season baseline; role-change comparisons begin in Week 2."
            if week < 2
            else "Role-change signal structure passed the post-publication sanity audit."
        ),
        "checks": checks,
        "top_signals": [],
    }
    if week < 2:
        return payload

    default_cards, all_matches = build_weekly_role_report(int(season), int(week))
    payload["default_card_count"] = int(len(default_cards))
    payload["all_match_count"] = int(len(all_matches))
    payload["category_counts"] = (
        all_matches["category"].value_counts().sort_index().to_dict()
        if not all_matches.empty and "category" in all_matches
        else {}
    )
    payload["top_signals"] = _top_signals(all_matches)

    if all_matches.empty:
        _record_check(checks, "zero_signals_allowed", True, 0, ">= 0")
        payload["message"] = (
            "No Week 2+ situations met the documented thresholds; the empty result is structurally valid."
        )
        return payload

    required_columns = {
        "category",
        "player_id",
        "player_name",
        "team",
        "position",
        "role_family",
        "current_raw",
        "current_denominator",
        "current_share",
        "baseline_raw",
        "baseline_denominator",
        "baseline_share",
        "share_change",
        "baseline_games",
        "all_play_share",
    }
    missing = sorted(required_columns - set(all_matches.columns))
    _record_check(checks, "required_columns", not missing, missing, [])
    if missing:
        payload["status"] = "FAIL"
        payload["message"] = "Role-change audit could not evaluate the published frame because required columns are missing."
        return payload

    finite_columns = [
        "current_share",
        "baseline_share",
        "share_change",
        "current_raw",
        "current_denominator",
        "baseline_raw",
        "baseline_denominator",
        "baseline_games",
    ]
    null_rows = int(all_matches[finite_columns].isna().any(axis=1).sum())
    _record_check(checks, "core_fields_complete", null_rows == 0, null_rows, 0)

    range_bad = int(
        (~all_matches["current_share"].between(0, 1))
        .pipe(lambda mask: mask | ~all_matches["baseline_share"].between(0, 1))
        .sum()
    )
    _record_check(checks, "share_ranges", range_bad == 0, range_bad, 0)

    denominator_bad = int(
        (
            (all_matches["current_denominator"] <= 0)
            | (all_matches["baseline_denominator"] <= 0)
            | (all_matches["current_raw"] < 0)
            | (all_matches["baseline_raw"] < 0)
            | (all_matches["current_raw"] > all_matches["current_denominator"])
            | (all_matches["baseline_raw"] > all_matches["baseline_denominator"])
        ).sum()
    )
    _record_check(checks, "count_denominator_integrity", denominator_bad == 0, denominator_bad, 0)

    minimum_baseline = (
        WEEKLY_REPORT_CONFIG.early_season_minimum_baseline_games
        if week == WEEKLY_REPORT_CONFIG.early_season_week
        else WEEKLY_REPORT_CONFIG.minimum_baseline_games
    )
    baseline_bad = int((all_matches["baseline_games"] < minimum_baseline).sum())
    _record_check(
        checks,
        "baseline_sample_floor",
        baseline_bad == 0,
        baseline_bad,
        f">= {minimum_baseline} prior qualifying game(s)",
    )
    if week == 2:
        week_two_bad = int((all_matches["baseline_games"] != 1).sum())
        _record_check(checks, "week_two_uses_week_one_baseline", week_two_bad == 0, week_two_bad, 0)

    gain_bad = int(
        (
            all_matches["category"].eq(CATEGORY_GAINED)
            & (all_matches["share_change"] < WEEKLY_REPORT_CONFIG.minimum_share_change)
        ).sum()
    )
    _record_check(checks, "gained_direction_and_threshold", gain_bad == 0, gain_bad, 0)

    loss_bad = int(
        (
            all_matches["category"].eq(CATEGORY_LOST)
            & (all_matches["share_change"] > -WEEKLY_REPORT_CONFIG.minimum_share_change)
        ).sum()
    )
    _record_check(checks, "lost_direction_and_threshold", loss_bad == 0, loss_bad, 0)

    if "all_play_normal_gap" in all_matches and "outside_normal_opportunities" in all_matches:
        overstated_bad = int(
            (
                all_matches["category"].eq(CATEGORY_OVERSTATED)
                & (
                    (all_matches["all_play_normal_gap"] < WEEKLY_REPORT_CONFIG.minimum_all_play_normal_gap)
                    | (
                        all_matches["outside_normal_opportunities"]
                        < WEEKLY_REPORT_CONFIG.minimum_outside_normal_opportunities
                    )
                )
            ).sum()
        )
        _record_check(checks, "overstated_context_thresholds", overstated_bad == 0, overstated_bad, 0)

    if "production_rate" in all_matches:
        weak_bad = int(
            (
                all_matches["category"].eq(CATEGORY_WEAK_PRODUCTION)
                & (
                    (all_matches["current_share"] < WEEKLY_REPORT_CONFIG.minimum_strong_share)
                    | (
                        all_matches["production_rate"]
                        > WEEKLY_REPORT_CONFIG.maximum_role_specific_production_rate
                    )
                )
            ).sum()
        )
        _record_check(checks, "weak_production_thresholds", weak_bad == 0, weak_bad, 0)

    if "confirmed_partial_game" in all_matches:
        partial_bad = int(all_matches["confirmed_partial_game"].fillna(False).astype(bool).sum())
        _record_check(checks, "confirmed_partial_games_excluded", partial_bad == 0, partial_bad, 0)

    duplicate_key = [column for column in ("player_id", "team", "role_family", "category") if column in all_matches]
    duplicate_rows = int(all_matches.duplicated(duplicate_key).sum()) if duplicate_key else 0
    _record_check(checks, "category_rows_unique", duplicate_rows == 0, duplicate_rows, 0)

    failed = [check for check in checks if not check["passed"]]
    if failed:
        payload["status"] = "FAIL"
        payload["message"] = "One or more role-change structural sanity checks failed."
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit published PropWar role-change signals after a weekly publication.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional report path; defaults to outputs/run_reports/role_research/role_change_audit_<season>_week_<week>.json",
    )
    args = parser.parse_args()

    payload = audit_role_change_signals(args.season, args.week)
    output = args.output or (
        ROOT
        / "outputs"
        / "run_reports"
        / "role_research"
        / f"role_change_audit_{args.season}_week_{args.week}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
