from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "role_validation" / "fold_2"


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUT / name, low_memory=False)


def pct(value: float) -> str:
    return "—" if pd.isna(value) else f"{100 * value:.1f}%"


def pp(value: float) -> str:
    return "—" if pd.isna(value) else f"{100 * value:+.1f} pp"


def table(frame: pd.DataFrame) -> str:
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


def main() -> int:
    audit = read("data_audit_2022.csv")
    source = read("source_coverage_2022.csv")
    join = read("join_coverage_2022.csv")
    partial_source = read("partial_game_source_coverage_2022.csv")
    methods = read("family_method_results_2022.csv")
    comparisons = read("family_comparisons_2022.csv")
    gates = read("release_gate_results_2022.csv")
    generalization = read("generalization_2021_vs_2022.csv")
    direction = read("direction_results_2022.csv")
    generalization_direction = read("generalization_direction_2021_vs_2022.csv")
    blocks = read("season_block_results_2022.csv")
    weekly = read("weekly_stability_2022.csv")
    feed = read("deduplicated_feed_summary_2022.csv")
    overlap = read("rb_family_overlap_2022.csv")
    repeats = read("repeat_alert_rates_2022.csv")
    fingerprint = json.loads((OUTPUT / "frozen_config_fingerprint.json").read_text(encoding="utf-8"))
    run = json.loads((OUTPUT / "run_manifest.json").read_text(encoding="utf-8"))

    primary_methods = methods.loc[methods["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")].copy()
    primary_comparisons = comparisons.loc[
        comparisons["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
    ].copy()
    primary_full = primary_methods.loc[primary_methods["method"].eq("full_propwar")]
    primary_feed = feed.loc[
        feed["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
        & feed["method"].eq("full_propwar")
    ].iloc[0]

    family_order = [
        "rb_carry_share",
        "rb_opportunity_share",
        "wr_target_share",
        "te_target_share",
    ]
    status_map = gates.set_index("role_family")["status"].to_dict()
    judgment = (
        "RB carry produced encouraging point estimates but failed the locked 50-alert gate "
        "with 49 alerts; its improvement interval includes zero and 2022 precision fell "
        "10.3 points from redeveloped 2021. RB opportunity failed the 10-point naive-lift "
        "and direction-consistency checks. WR failed precision, retention, evidence-volume, "
        "and direction-consistency checks. TE emitted only four alerts and is insufficient. "
        "No family passes Fold 2 and none is validated."
    )

    method_display = primary_methods[
        [
            "role_family", "method", "alerts", "deduplicated_player_week_team_alerts",
            "evaluable_alerts", "precision", "precision_ci_low", "precision_ci_high",
            "reversion_rate", "median_retention",
        ]
    ].copy()
    for column in ["precision", "precision_ci_low", "precision_ci_high", "reversion_rate", "median_retention"]:
        method_display[column] = method_display[column].map(pct)

    comparison_display = primary_comparisons[
        [
            "role_family", "full_alerts", "full_evaluable_alerts", "full_precision",
            "naive_precision", "precision_improvement", "precision_improvement_ci_low",
            "precision_improvement_ci_high", "full_reversion_rate",
            "naive_reversion_rate", "reversion_improvement", "full_median_retention",
        ]
    ].copy()
    for column in ["full_precision", "naive_precision", "full_reversion_rate", "naive_reversion_rate", "full_median_retention"]:
        comparison_display[column] = comparison_display[column].map(pct)
    for column in ["precision_improvement", "precision_improvement_ci_low", "precision_improvement_ci_high", "reversion_improvement"]:
        comparison_display[column] = comparison_display[column].map(pp)

    gate_display = gates[
        [
            "role_family", "status", "alerts", "evaluable_alerts", "precision",
            "precision_improvement", "reversion_rate", "reversion_improvement",
            "median_retention", "failed_checks",
        ]
    ].copy()
    for column in ["precision", "reversion_rate", "median_retention"]:
        gate_display[column] = gate_display[column].map(pct)
    for column in ["precision_improvement", "reversion_improvement"]:
        gate_display[column] = gate_display[column].map(pp)

    generalization_display = generalization[
        [
            "role_family", "development_2021_full_alerts", "untouched_2022_full_alerts",
            "development_2021_full_precision", "untouched_2022_full_precision",
            "delta_2022_minus_2021_full_precision",
            "development_2021_precision_improvement", "untouched_2022_precision_improvement",
            "delta_2022_minus_2021_precision_improvement",
            "development_2021_full_reversion_rate", "untouched_2022_full_reversion_rate",
            "development_2021_full_median_retention", "untouched_2022_full_median_retention",
            "generalization_classification",
        ]
    ].copy()
    for column in [
        "development_2021_full_precision", "untouched_2022_full_precision",
        "development_2021_full_reversion_rate", "untouched_2022_full_reversion_rate",
        "development_2021_full_median_retention", "untouched_2022_full_median_retention",
    ]:
        generalization_display[column] = generalization_display[column].map(pct)
    for column in [
        "delta_2022_minus_2021_full_precision", "development_2021_precision_improvement",
        "untouched_2022_precision_improvement",
        "delta_2022_minus_2021_precision_improvement",
    ]:
        generalization_display[column] = generalization_display[column].map(pp)

    direction_display = direction.loc[
        direction["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
        & direction["method"].eq("full_propwar"),
        ["role_family", "direction", "alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"],
    ].copy()
    for column in ["precision", "reversion_rate", "median_retention"]:
        direction_display[column] = direction_display[column].map(pct)

    block_display = blocks.loc[
        blocks["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
        & blocks["method"].eq("full_propwar"),
        ["role_family", "week_block", "alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"],
    ].copy()
    for column in ["precision", "reversion_rate", "median_retention"]:
        block_display[column] = block_display[column].map(pct)

    partial_display = comparisons[
        [
            "partial_policy", "role_family", "full_alerts", "full_evaluable_alerts",
            "full_precision", "precision_improvement", "precision_improvement_ci_low",
            "precision_improvement_ci_high", "full_reversion_rate",
            "reversion_improvement", "full_median_retention",
        ]
    ].copy()
    for column in ["full_precision", "full_reversion_rate", "full_median_retention"]:
        partial_display[column] = partial_display[column].map(pct)
    for column in ["precision_improvement", "precision_improvement_ci_low", "precision_improvement_ci_high", "reversion_improvement"]:
        partial_display[column] = partial_display[column].map(pp)

    weekly_display = weekly.loc[
        weekly["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
        & weekly["method"].eq("full_propwar"),
        ["role_family", "weekly_median", "weekly_maximum", "zero_alert_weeks", "active_weeks", "weekly_mean"],
    ]
    repeat_display = repeats.loc[
        repeats["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
        & repeats["method"].eq("full_propwar"),
        ["role_family", "alerts", "repeat_alerts", "repeat_players", "repeat_rate"],
    ].copy()
    repeat_display["repeat_rate"] = repeat_display["repeat_rate"].map(pct)
    overlap_display = overlap.loc[
        overlap["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
        & overlap["method"].eq("full_propwar")
    ].copy()
    overlap_display["jaccard_overlap"] = overlap_display["jaccard_overlap"].map(pct)

    primary_sensitivity = comparisons.loc[
        comparisons["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")
    ].set_index("role_family")
    partial_machine = comparisons.copy()
    partial_machine["sensitivity_type"] = partial_machine["partial_policy"].map(
        {
            "PRIMARY_CONFIRMED_EXCLUDED": "primary",
            "ALL_INCLUDED": "confirmed_partial_inclusion_sensitivity",
            "STRICT_SUSPECTED_EXCLUDED": "suspected_partial_exclusion_sensitivity",
        }
    )
    for metric in [
        "full_alerts", "full_evaluable_alerts", "full_precision",
        "precision_improvement", "full_reversion_rate", "reversion_improvement",
        "full_median_retention",
    ]:
        partial_machine[f"delta_vs_primary_{metric}"] = partial_machine.apply(
            lambda row: row[metric] - primary_sensitivity.at[row["role_family"], metric],
            axis=1,
        )
    partial_machine.to_csv(OUTPUT / "partial_game_sensitivity_2022.csv", index=False)

    direction_periods = []
    for period, period_frame in generalization_direction.groupby("period", sort=True):
        full = period_frame.loc[period_frame["method"].eq("full_propwar")].set_index(
            ["role_family", "direction"]
        )
        naive = period_frame.loc[period_frame["method"].eq("naive_spike")].set_index(
            ["role_family", "direction"]
        )
        joined = full[["alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"]].join(
            naive[["alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"]],
            how="outer",
            lsuffix="_full",
            rsuffix="_naive",
        ).reset_index()
        joined["precision_improvement"] = joined["precision_full"] - joined["precision_naive"]
        joined.insert(0, "period", period)
        direction_periods.append(joined)
    direction_period = pd.concat(direction_periods, ignore_index=True)
    prior_direction = direction_period.loc[direction_period["period"].eq("redeveloped_2021")].drop(columns="period")
    current_direction = direction_period.loc[direction_period["period"].eq("untouched_2022")].drop(columns="period")
    direct_direction = prior_direction.merge(
        current_direction,
        on=["role_family", "direction"],
        how="outer",
        suffixes=("_2021", "_2022"),
        validate="one_to_one",
    )
    for metric in [
        "alerts_full", "evaluable_alerts_full", "precision_full",
        "precision_improvement", "reversion_rate_full", "median_retention_full",
    ]:
        direct_direction[f"delta_2022_minus_2021_{metric}"] = (
            direct_direction[f"{metric}_2022"] - direct_direction[f"{metric}_2021"]
        )
    direct_direction.to_csv(
        OUTPUT / "generalization_direction_direct_2021_vs_2022.csv", index=False
    )

    data_audit_report = f"""# Fold 2 2022 Data Audit

- Grain: one row per season-week-player-team-role family.
- Rows: {int(audit.at[0, 'canonical_rows']):,}; unique players: {int(audit.at[0, 'unique_players']):,}; played games: {int(audit.at[0, 'played_games'])}; weeks: 18.
- Duplicate canonical keys: {int(audit.at[0, 'duplicate_key_rows'])}; required-field null cells: {int(audit.at[0, 'required_null_cells'])}.
- Identity, data-quality, and qualifying coverage: 100%.
- PBP/schedule played-game coverage: {int(source.at[0, 'pbp_games'])}/{int(source.at[0, 'schedule_games'])}; participation play coverage: {pct(source.at[0, 'participation_play_coverage'])}.
- Opportunity and participation identity joins: {int(join['matched_rows'].sum()):,}/{int(join['rows'].sum()):,}.
- Explicit injury mentions: {int(partial_source.at[0, 'parsed_injury_mentions'])}; resolved: {int(partial_source.at[0, 'resolved_injury_mentions'])} ({pct(partial_source.at[0, 'resolution_rate'])}).
- Confirmed partial family rows excluded by primary: {int(partial_source.at[0, 'confirmed_partial_rows'])}; suspected family rows included by primary: {int(partial_source.at[0, 'suspected_partial_rows'])}.
- Severity assessment: no critical/high blocker for the controlled 2022 evaluation. Receiver-ID coverage across all pass attempts is 89.6%, but target opportunities require a resolved receiver and the canonical target-share grain passes all required quality checks.
"""
    (OUTPUT / "DATA_AUDIT_2022.md").write_text(data_audit_report, encoding="utf-8")

    actions = pd.DataFrame(
        [
            {
                "role_family": "rb_carry_share",
                "next_action": "Keep in shadow evaluation unchanged",
                "reason": "All performance point checks passed, but only 49 alerts and the lift CI includes zero; it cannot advance.",
            },
            {
                "role_family": "rb_opportunity_share",
                "next_action": "Keep in shadow evaluation unchanged",
                "reason": "Stable point performance, but naive lift was 8.4 pp and direction consistency failed.",
            },
            {
                "role_family": "wr_target_share",
                "next_action": "Retire the family from the automated detector",
                "reason": "Shadow family failed precision, retention, sample, and direction-consistency checks.",
            },
            {
                "role_family": "te_target_share",
                "next_action": "Retire the family from the automated detector",
                "reason": "Only four alerts in both 2021 and 2022; 2022 had zero persistent alerts among three evaluable cases.",
            },
        ]
    )

    report = f"""# PropWar Role Validation — Fold 2 (Untouched 2022)

## Concise judgment

{judgment}

This was a single controlled execution of the candidate frozen at `{fingerprint['start_commit']}`. No 2023–2025 result was read, no detector rule was changed, and no family is presented as validated.

## Frozen-configuration integrity

- Candidate SHA-256: `{fingerprint['config_sha256']}`
- Frozen-copy SHA-256: `{fingerprint['frozen_copy_sha256']}`
- Pre-Fold-2 tag: `{fingerprint['pre_fold2_tag']}` → `{fingerprint['pre_fold2_tag_commit']}`
- Exact semantic match to the Fold 1 report: **yes**
- Protected release-gate SHA-256: `{fingerprint['protected_hashes']['release_gates']}`
- Protocol and locked-decision hashes: unchanged
- Execution lock completed: **yes**
- Alert archive SHA-256: `{json.loads((OUTPUT / 'fold2_execution_lock.json').read_text(encoding='utf-8'))['alert_archive_sha256']}`

The alert is emitted after the frozen confirmation window completes. Baseline weeks end strictly before confirmation starts; both outcome games occur strictly after the alert week. This is the protocol’s `B`, `D`, then future `F` ordering.

## 2022 data audit

| canonical rows | players | played games | weeks | duplicate keys | required null cells | identity coverage | quality pass | qualifying |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| {int(audit.at[0, 'canonical_rows']):,} | {int(audit.at[0, 'unique_players']):,} | {int(audit.at[0, 'played_games'])} | {int(audit.at[0, 'observed_weeks'])} | {int(audit.at[0, 'duplicate_key_rows'])} | {int(audit.at[0, 'required_null_cells'])} | {pct(audit.at[0, 'identity_coverage'])} | {pct(audit.at[0, 'quality_pass_rate'])} | {pct(audit.at[0, 'qualifying_rate'])} |

Source evidence:

- PBP and schedule both contain 271 played regular-season games across all 18 weeks.
- Participation play coverage is {pct(source.at[0, 'participation_play_coverage'])}; carry-ID coverage is {pct(source.at[0, 'carry_player_id_coverage'])}.
- Target-player ID population is {pct(source.at[0, 'target_player_id_coverage'])} across pass attempts; target opportunities themselves require a receiver ID before entering numerator or denominator.
- Opportunity-to-identity and participating-player-to-identity joins are both 100% ({int(join['matched_rows'].sum()):,}/{int(join['rows'].sum()):,}).
- Explicit PBP injury mentions: {int(partial_source.at[0, 'parsed_injury_mentions']):,}; resolved: {int(partial_source.at[0, 'resolved_injury_mentions']):,} ({pct(partial_source.at[0, 'resolution_rate'])}).
- Confirmed partial family rows: {int(partial_source.at[0, 'confirmed_partial_rows'])}; suspected rows retained in primary: {int(partial_source.at[0, 'suspected_partial_rows'])}.
- Every team-game has a trigger timestamp. The 32 null next-game boundaries are exactly one final regular-season game per team.

## Family and method results

{table(method_display)}

## Frozen detector versus equal-volume naive

{table(comparison_display)}

Every one of the {run['equal_volume_cells']} family-week-policy cells contains all four methods at exactly equal volume, including zero-alert weeks.

## Deduplicated feed and overlap

The primary full detector produced {int(primary_feed['family_alert_rows'])} family rows and {int(primary_feed['deduplicated_player_week_team_alerts'])} deduplicated player-week-team alerts. The weekly deduplicated median was {primary_feed['weekly_median']:.1f}, maximum {int(primary_feed['weekly_maximum'])}, with {int(primary_feed['zero_alert_weeks'])} zero-alert weeks.

{table(weekly_display)}

{table(overlap_display)}

{table(repeat_display)}

The frozen direction-sensitive cooldown eliminated all literal consecutive-week repeats from the emitted full-detector feed.

## Increase/decrease results

{table(direction_display)}

RB carry’s increase side remained strong, while the decrease side fell below the 60% precision gate. RB opportunity was also stronger on increases. WR flipped from a strong 2021 increase result to 25% precision on 2022 increases.

## Early/middle/late stability

{table(block_display)}

Weeks 1–5 have no alerts by construction because the same-season four-game baseline must accrue. Small early and late block samples make week-stability claims uncertain.

## Partial-game sensitivity

`PRIMARY_CONFIRMED_EXCLUDED` excludes confirmed focal partial games and includes suspected cases. `ALL_INCLUDED` is the confirmed-exclusion sensitivity; `STRICT_SUSPECTED_EXCLUDED` additionally excludes suspected cases.

{table(partial_display)}

The qualitative Fold 2 decision does not change under either sensitivity. Excluding suspected games materially reduces RB sample sizes and is not the primary policy.

## 2021 redevelopment versus untouched 2022

{table(generalization_display)}

Descriptive classification criteria, frozen in the execution code before reading outcomes:

- `INSUFFICIENT_SAMPLE`: fewer than 25 evaluable 2022 full-detector alerts.
- `MATERIAL_DETERIORATION`: otherwise, precision or naive lift declines by at least 10 points, reversion rises by at least 10 points, retention falls by at least 20 points, or 2022 naive lift becomes negative.
- `STABLE_GENERALIZATION`: otherwise, precision and lift changes remain within ±10 points, reversion rises by less than 10 points, retention falls by less than 20 points, and naive lift remains non-negative.
- `MIXED_OR_UNCERTAIN`: all remaining cases.

RB carry is mechanically classified `MATERIAL_DETERIORATION` because precision declined 10.3 points, just beyond the descriptive cutoff. This does not mean it failed badly: all performance point checks passed, but the family missed the locked alert-count gate by one and its improvement CI includes zero. The result is encouraging repeated historical evidence, not a Fold 2 pass.

## Direction-level generalization

{table(direct_direction)}

## Locked release-gate judgment

{table(gate_display)}

The direction-consistency check requires every available 2021/2022 increase/decrease comparison to have full-detector precision at least as high as its equal-volume naive comparator. This operationalizes—without changing—the protocol’s required direction consistency across periods.

Family statuses:

{chr(10).join(f'- `{family}`: `{status_map[family]}`' for family in family_order)}

No confidence interval is used to turn a failed point gate into a pass. Conversely, positive point estimates with intervals crossing zero remain explicitly uncertain.

## Recommended next action

{table(actions)}

No replacement candidate was created. Any later redevelopment using these results means 2022 can no longer be an untouched test for that revised candidate.

## Limitations

- Fold 2 is a development-fold test, not the locked 2025 final holdout or 2026 prospective confirmation.
- RB carry has only 39 evaluable alerts and its lift CI is {pp(primary_comparisons.set_index('role_family').at['rb_carry_share', 'precision_improvement_ci_low'])} to {pp(primary_comparisons.set_index('role_family').at['rb_carry_share', 'precision_improvement_ci_high'])}.
- RB opportunity’s 8.4-point naive improvement misses the locked 10-point gate; its CI includes zero.
- WR and TE were shadow-only before execution and remain unsupported for automated claims.
- Historical nflverse extracts can be revised upstream; input hashes are recorded for this run.
- The 89.6% receiver-ID field is measured across pass attempts, which include plays with no target; target-share opportunities require a resolved receiver.
- No public-dashboard behavior was tested or changed because the dashboard was explicitly out of scope.
"""
    (OUTPUT / "FOLD_2_REPORT.md").write_text(report, encoding="utf-8")
    print(OUTPUT / "FOLD_2_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
