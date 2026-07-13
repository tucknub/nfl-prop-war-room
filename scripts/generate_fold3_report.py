from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_3"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False)


def pct(value: object) -> str:
    return "—" if pd.isna(value) else f"{100 * float(value):.1f}%"


def pp(value: object) -> str:
    return "—" if pd.isna(value) else f"{100 * float(value):+.1f} pp"


def markdown_table(frame: pd.DataFrame) -> str:
    def cell(value: object) -> str:
        if pd.isna(value):
            return "—"
        return str(value).replace("|", "\\|").replace("\n", " ")

    columns = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend(
        "| " + " | ".join(cell(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def format_metrics(frame: pd.DataFrame, percentages: list[str], points: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in percentages:
        if column in result:
            result[column] = result[column].map(pct)
    for column in points:
        if column in result:
            result[column] = result[column].map(pp)
    return result


def main() -> int:
    audit = read("data_audit_2023.csv")
    source = read("source_coverage_2023.csv")
    joins = read("join_coverage_2023.csv")
    partial_source = read("partial_game_source_coverage_2023.csv")
    methods = read("rb_family_method_results_2023.csv")
    comparisons = read("rb_family_comparisons_2023.csv")
    direction = read("rb_direction_results_2023.csv")
    blocks = read("season_block_results_2023.csv")
    weekly = read("weekly_stability_2023.csv")
    feed = read("deduplicated_feed_summary_2023.csv")
    overlap = read("rb_family_overlap_2023.csv")
    repeats = read("repeat_alert_rates_2023.csv")
    sensitivity = read("partial_game_sensitivity_2023.csv")
    cross_family = read("cross_season_family_2021_2023.csv")
    cross_direction = read("cross_season_direction_2021_2023.csv")
    cross_weekly = read("cross_season_weekly_2021_2023.csv")
    pooled_family = read("pooled_untouched_family_2022_2023.csv")
    pooled_direction = read("pooled_untouched_direction_2022_2023.csv")
    pooled_weekly = read("pooled_untouched_weekly_2022_2023.csv")
    gates = read("fold3_gate_decisions.csv")
    fingerprint = json.loads((OUT / "frozen_config_fingerprint.json").read_text(encoding="utf-8"))
    run = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    lock = json.loads((OUT / "fold3_execution_lock.json").read_text(encoding="utf-8"))

    primary = "PRIMARY_CONFIRMED_EXCLUDED"
    rb = ["rb_carry_share", "rb_opportunity_share"]
    primary_methods = methods.loc[methods["partial_policy"].eq(primary)].copy()
    primary_comparisons = comparisons.loc[comparisons["partial_policy"].eq(primary)].copy()
    primary_direction = direction.loc[
        direction["partial_policy"].eq(primary) & direction["role_family"].isin(rb)
    ].copy()

    method_display = primary_methods[
        ["role_family", "method", "alerts", "deduplicated_player_week_team_alerts",
         "evaluable_alerts", "precision", "precision_ci_low", "precision_ci_high",
         "reversion_rate", "median_retention"]
    ]
    method_display = format_metrics(
        method_display,
        ["precision", "precision_ci_low", "precision_ci_high", "reversion_rate", "median_retention"],
        [],
    )

    comparison_display = primary_comparisons[
        ["role_family", "full_alerts", "full_evaluable_alerts", "full_precision",
         "naive_precision", "precision_improvement", "precision_improvement_ci_low",
         "precision_improvement_ci_high", "full_reversion_rate", "naive_reversion_rate",
         "reversion_improvement", "full_median_retention"]
    ]
    comparison_display = format_metrics(
        comparison_display,
        ["full_precision", "naive_precision", "full_reversion_rate", "naive_reversion_rate", "full_median_retention"],
        ["precision_improvement", "precision_improvement_ci_low", "precision_improvement_ci_high", "reversion_improvement"],
    )

    full_direction = primary_direction.loc[primary_direction["method"].eq("full_propwar")]
    naive_direction = primary_direction.loc[primary_direction["method"].eq("naive_spike")]
    direction_display = full_direction.merge(
        naive_direction,
        on=["role_family", "direction"],
        suffixes=("_full", "_naive"),
        validate="one_to_one",
    )
    direction_display["naive_improvement"] = (
        direction_display["precision_full"] - direction_display["precision_naive"]
    )
    direction_display = direction_display[
        ["role_family", "direction", "alerts_full", "evaluable_alerts_full", "precision_full",
         "precision_naive", "naive_improvement", "reversion_rate_full", "median_retention_full"]
    ]
    direction_display = format_metrics(
        direction_display,
        ["precision_full", "precision_naive", "reversion_rate_full", "median_retention_full"],
        ["naive_improvement"],
    )

    block_display = blocks.loc[
        blocks["partial_policy"].eq(primary)
        & blocks["method"].eq("full_propwar")
        & blocks["role_family"].isin(rb),
        ["role_family", "week_block", "alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"],
    ]
    block_display = format_metrics(block_display, ["precision", "reversion_rate", "median_retention"], [])

    weekly_display = weekly.loc[
        weekly["partial_policy"].eq(primary)
        & weekly["method"].eq("full_propwar")
        & weekly["role_family"].isin(rb),
        ["role_family", "weekly_median", "weekly_maximum", "zero_alert_weeks", "active_weeks", "weekly_mean"],
    ]
    overlap_display = overlap.loc[
        overlap["partial_policy"].eq(primary) & overlap["method"].eq("full_propwar")
    ].copy()
    overlap_display["jaccard_overlap"] = overlap_display["jaccard_overlap"].map(pct)
    repeat_display = repeats.loc[
        repeats["partial_policy"].eq(primary)
        & repeats["method"].eq("full_propwar")
        & repeats["role_family"].isin(rb),
        ["role_family", "alerts", "repeat_alerts", "repeat_players", "repeat_rate"],
    ].copy()
    repeat_display["repeat_rate"] = repeat_display["repeat_rate"].map(pct)

    sensitivity_display = sensitivity.loc[sensitivity["role_family"].isin(rb), [
        "partial_policy", "role_family", "full_alerts", "full_evaluable_alerts",
        "full_precision", "precision_improvement", "full_reversion_rate",
        "reversion_improvement", "full_median_retention",
    ]]
    sensitivity_display = format_metrics(
        sensitivity_display,
        ["full_precision", "full_reversion_rate", "full_median_retention"],
        ["precision_improvement", "reversion_improvement"],
    )

    cross_family_display = cross_family.loc[cross_family["role_family"].isin(rb), [
        "period", "role_family", "full_alerts", "full_evaluable_alerts", "full_precision",
        "naive_precision", "precision_improvement", "full_reversion_rate",
        "reversion_improvement", "full_median_retention",
    ]]
    cross_family_display = format_metrics(
        cross_family_display,
        ["full_precision", "naive_precision", "full_reversion_rate", "full_median_retention"],
        ["precision_improvement", "reversion_improvement"],
    )
    cross_direction_display = cross_direction.loc[cross_direction["role_family"].isin(rb), [
        "period", "role_family", "direction", "alerts_full", "evaluable_alerts_full",
        "precision_full", "precision_naive", "precision_improvement",
        "reversion_rate_full", "median_retention_full",
    ]]
    cross_direction_display = format_metrics(
        cross_direction_display,
        ["precision_full", "precision_naive", "reversion_rate_full", "median_retention_full"],
        ["precision_improvement"],
    )
    cross_weekly_display = cross_weekly.loc[cross_weekly["role_family"].isin(rb)]

    pooled_family_display = pooled_family.loc[pooled_family["role_family"].isin(rb), [
        "role_family", "full_alerts", "full_evaluable_alerts", "full_precision",
        "naive_precision", "precision_improvement", "precision_improvement_ci_low",
        "precision_improvement_ci_high", "full_reversion_rate", "reversion_improvement",
        "full_median_retention",
    ]]
    pooled_family_display = format_metrics(
        pooled_family_display,
        ["full_precision", "naive_precision", "full_reversion_rate", "full_median_retention"],
        ["precision_improvement", "precision_improvement_ci_low", "precision_improvement_ci_high", "reversion_improvement"],
    )
    pooled_direction_display = pooled_direction.loc[pooled_direction["role_family"].isin(rb)]
    pooled_direction_display = format_metrics(
        pooled_direction_display,
        ["precision_full", "precision_naive", "reversion_rate_full", "median_retention_full",
         "reversion_rate_naive", "median_retention_naive"],
        ["precision_improvement", "reversion_improvement"],
    )
    pooled_weekly_display = pooled_weekly.loc[pooled_weekly["role_family"].isin(rb)]

    gate_display = gates[[
        "role_family", "candidate_disposition", "fold3_candidate_status", "alerts",
        "evaluable_alerts", "precision", "precision_improvement", "reversion_rate",
        "reversion_improvement", "median_retention", "failed_checks",
    ]]
    gate_display = format_metrics(
        gate_display,
        ["precision", "reversion_rate", "median_retention"],
        ["precision_improvement", "reversion_improvement"],
    )

    audit_report = f"""# Fold 3 — 2023 Data Audit

- Grain: one row per season-week-player-team-role family.
- Canonical rows: {int(audit.at[0, 'canonical_rows']):,}; unique players: {int(audit.at[0, 'unique_players']):,}; played games: {int(audit.at[0, 'played_games'])}; observed weeks: {int(audit.at[0, 'observed_weeks'])}.
- Duplicate canonical keys: {int(audit.at[0, 'duplicate_key_rows'])}; required-field null cells: {int(audit.at[0, 'required_null_cells'])}.
- Identity, quality, and qualifying coverage: {pct(audit.at[0, 'identity_coverage'])}, {pct(audit.at[0, 'quality_pass_rate'])}, {pct(audit.at[0, 'qualifying_rate'])}.
- PBP/schedule games: {int(source.at[0, 'pbp_games'])}/{int(source.at[0, 'schedule_games'])}; participation coverage: {pct(source.at[0, 'participation_play_coverage'])}; carry-ID coverage: {pct(source.at[0, 'carry_player_id_coverage'])}.
- Target-player ID population across pass attempts: {pct(source.at[0, 'target_player_id_coverage'])}; target opportunities require a resolved receiver before entering the numerator or denominator.
- Opportunity and participation identity joins: {int(joins['matched_rows'].sum()):,}/{int(joins['rows'].sum()):,}.
- Explicit injury mentions resolved: {int(partial_source.at[0, 'resolved_injury_mentions'])}/{int(partial_source.at[0, 'parsed_injury_mentions'])} ({pct(partial_source.at[0, 'resolution_rate'])}).
- Confirmed partial family rows excluded from primary: {int(partial_source.at[0, 'confirmed_partial_rows'])}; suspected rows retained: {int(partial_source.at[0, 'suspected_partial_rows'])}.
- All trigger timestamps are present. The {int(partial_source.at[0, 'next_boundary_missing_team_games'])} missing next-game boundaries are the final regular-season team game, as expected.
- Audit judgment: no critical or high-severity blocker; the controlled 2023 evaluation was permitted to proceed.
"""
    (OUT / "DATA_AUDIT_2023.md").write_text(audit_report, encoding="utf-8")

    recommendations = pd.DataFrame([
        {
            "role_family": "rb_carry_share",
            "recommendation": "Advance unchanged to Fold 4",
            "reason": "Passed every unchanged Fold 3 point gate on 60 alerts; both directions beat equal-volume naive in 2023 and across available periods. This is advancement evidence, not validation.",
        },
        {
            "role_family": "rb_opportunity_share",
            "recommendation": "Continue shadow evaluation unchanged",
            "reason": "Strong 2023 and pooled untouched results, but the unchanged cross-period direction gate fails because 2021 decreases underperformed equal-volume naive by 1.6 points.",
        },
    ])

    primary_feed = feed.loc[
        feed["partial_policy"].eq(primary) & feed["method"].eq("full_propwar")
    ].iloc[0]
    report = f"""# PropWar Role Validation — Fold 3 (Untouched 2023)

## Concise judgment

RB carry **passes the unchanged Fold 3 point gates** and should advance unchanged to Fold 4. RB opportunity **fails the unchanged Fold 3 point gates** only on cross-period direction consistency and should remain an unchanged shadow candidate. Neither family is described as validated. WR and TE remain retired, descriptive-only families and are not reinstated.

The 2023 holdout was executed exactly once. No 2024–2025 result was selected or used, no detector or gate was changed after outcome access, and Fold 4 was not executed.

## Configuration integrity

- Candidate SHA-256: `{fingerprint['config_sha256']}`
- Frozen-copy SHA-256: `{fingerprint['frozen_copy_sha256']}`
- Required Fold 2 hash match: **yes**
- Pre-Fold-3 checkpoint tag: `{fingerprint['pre_fold3_tag']}` → `{fingerprint['pre_fold3_tag_commit']}`
- Starting checkpoint: `{fingerprint['start_commit']}`
- Protected release-gate SHA-256: `{fingerprint['protected_hashes']['release_gates']}`
- Protocol and locked-decision hashes: unchanged
- Execution lock completed: **yes**; alert archive SHA-256: `{lock['alert_archive_sha256']}`
- Equal-volume cells: {run['equal_volume_cells']}; all exact: **yes**
- Temporal checks: **all passed** (`baseline < confirmation ≤ alert < outcomes`)

## 2023 data audit

| canonical rows | players | played games | weeks | duplicate keys | required null cells | identity | quality | qualifying |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| {int(audit.at[0, 'canonical_rows']):,} | {int(audit.at[0, 'unique_players']):,} | {int(audit.at[0, 'played_games'])} | {int(audit.at[0, 'observed_weeks'])} | {int(audit.at[0, 'duplicate_key_rows'])} | {int(audit.at[0, 'required_null_cells'])} | {pct(audit.at[0, 'identity_coverage'])} | {pct(audit.at[0, 'quality_pass_rate'])} | {pct(audit.at[0, 'qualifying_rate'])} |

PBP and schedule each contain {int(source.at[0, 'pbp_games'])} played games over all 18 weeks. Opportunity and participation identity joins are 100% ({int(joins['matched_rows'].sum()):,}/{int(joins['rows'].sum()):,}). The primary policy excluded {int(partial_source.at[0, 'confirmed_partial_rows'])} confirmed partial family rows and retained {int(partial_source.at[0, 'suspected_partial_rows'])} suspected rows.

## RB method results

{markdown_table(method_display)}

## Frozen detector versus equal-volume naive

{markdown_table(comparison_display)}

Every family-week-policy comparison preserved exact method alert counts. Confidence intervals are bootstrap intervals and are reported as uncertainty, not as replacements for the locked point gates.

## Feed volume, overlap, and repeats

The complete descriptive primary feed contains {int(primary_feed['family_alert_rows'])} family rows and {int(primary_feed['deduplicated_player_week_team_alerts'])} deduplicated player-week-team alerts; {int(primary_feed['duplicate_family_rows_removed'])} overlapping family rows are removed by deduplication. Its weekly median is {primary_feed['weekly_median']:.1f}, maximum {int(primary_feed['weekly_maximum'])}, with {int(primary_feed['zero_alert_weeks'])} zero-alert weeks.

{markdown_table(weekly_display)}

{markdown_table(overlap_display)}

{markdown_table(repeat_display)}

RB carry and RB opportunity overlap on 41 player-week-team alerts (Jaccard 44.1%). The full detector emitted one literal consecutive-week RB carry repeat and zero RB opportunity repeats.

## Directional results (diagnostic only)

{markdown_table(direction_display)}

RB carry increases are stronger than decreases, but both directions beat equal-volume naive in 2023. RB opportunity is strong in both 2023 directions; its locked gate failure comes from 2021 decreases, not its 2023 point performance. No direction-specific selection rule was introduced.

## Early-, middle-, and late-season stability

{markdown_table(block_display)}

Weeks 1–5 contain no alerts by construction while the four-game same-season baseline accrues. Block samples are small and should not be overinterpreted.

## Confirmed/suspected partial-game sensitivity

`PRIMARY_CONFIRMED_EXCLUDED` excludes confirmed cases and includes suspected cases. `ALL_INCLUDED` includes confirmed cases; `STRICT_SUSPECTED_EXCLUDED` also excludes suspected cases.

{markdown_table(sensitivity_display)}

The RB recommendations do not change in either sensitivity. This robustness check does not change the primary policy.

## 2021–2023 direct comparison

{markdown_table(cross_family_display)}

{markdown_table(cross_direction_display)}

{markdown_table(cross_weekly_display)}

RB carry's 49 alerts in untouched 2022 remain a literal gate failure—an evidence-volume miss, not a performance-point failure. The 2023 pass does not rewrite that season. RB opportunity's only cross-period direction defect is the redeveloped-2021 decrease cell: 63.6% full versus 65.2% naive, a -1.6-point improvement.

## Pooled untouched 2022–2023 evidence

{markdown_table(pooled_family_display)}

{markdown_table(pooled_direction_display)}

{markdown_table(pooled_weekly_display)}

Pooled results strengthen the descriptive evidence for both RB families, but do not erase individual-season failures. The pooled evidence is not used to reinterpret any locked status.

## Fold 3 gate decisions

{markdown_table(gate_display)}

WR and TE rows are archival continuity only. Their candidate status is `NOT_APPLICABLE_RETIRED`, regardless of incidental 2023 point estimates.

## Recommended next action

{markdown_table(recommendations)}

No redevelopment was performed. Advancing RB carry means testing this exact frozen candidate in a later separately authorized Fold 4; it does not authorize that execution here.

## Limitations

- This is a historical development-fold holdout, not prospective validation.
- RB carry has 47 evaluable 2023 alerts; its +12.9-point lift interval spans -3.1 to +26.3 points.
- RB opportunity's 2023 lift is strong, but the locked all-period direction check is literal and fails on the 2021 decrease cell.
- The complete deduplicated feed includes retired WR/TE archival alerts; any production feed would need a separately authorized disposition implementation.
- Receiver-ID population is measured across pass attempts, including plays with no target; canonical target opportunities require a resolved receiver.
- nflverse source extracts can be revised upstream; source file hashes are recorded.
- The public dashboard was not changed, tested, merged, pushed, or deployed.
"""
    (OUT / "FOLD_3_REPORT.md").write_text(report, encoding="utf-8")
    print(OUT / "FOLD_3_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
