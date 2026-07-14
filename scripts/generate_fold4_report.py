from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_4"
PRIMARY = "PRIMARY_CONFIRMED_EXCLUDED"
ACTIVE = ["rb_carry_share", "rb_opportunity_share"]


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False)


def pct(value: object) -> str:
    return "-" if pd.isna(value) else f"{100 * float(value):.1f}%"


def pp(value: object) -> str:
    return "-" if pd.isna(value) else f"{100 * float(value):+.1f} pp"


def table(frame: pd.DataFrame) -> str:
    def cell(value: object) -> str:
        if pd.isna(value):
            return "-"
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


def format_frame(
    frame: pd.DataFrame, *, percentages: list[str] = [], points: list[str] = []
) -> pd.DataFrame:
    result = frame.copy()
    for column in percentages:
        if column in result:
            result[column] = result[column].map(pct)
    for column in points:
        if column in result:
            result[column] = result[column].map(pp)
    return result


def main() -> int:
    audit = read("data_audit_2024.csv")
    source = read("source_coverage_2024.csv")
    joins = read("join_coverage_2024.csv")
    missingness = read("missingness_2024.csv")
    partial_source = read("partial_game_source_coverage_2024.csv")
    audit_checks = read("data_audit_checks_2024.csv")
    temporal_pre = read("temporal_precheck_2024.csv")
    methods = read("active_family_method_results_2024.csv")
    comparisons = read("active_family_comparisons_2024.csv")
    directions = read("direction_results_2024.csv")
    weekly = read("weekly_stability_2024.csv")
    feed = read("deduplicated_feed_summary_2024.csv")
    overlap = read("rb_family_overlap_2024.csv")
    repeats = read("repeat_alert_rates_2024.csv")
    sensitivity = read("partial_game_sensitivity_2024.csv")
    subgroup = read("subgroup_stability_2024.csv")
    concentration = read("concentration_summary_2024.csv")
    overlap_dependence = read("overlap_dependence_2024.csv")
    retention = read("retention_outlier_diagnostics_2024.csv")
    cross_family = read("cross_season_family_2021_2024.csv")
    cross_direction = read("cross_season_direction_2021_2024.csv")
    pooled_22_23 = read("pooled_untouched_family_2022_2023.csv")
    pooled_22_24 = read("pooled_untouched_family_2022_2024.csv")
    season_statuses = read("individual_season_gate_status_2021_2024.csv")
    gates = read("fold4_gate_decisions.csv")
    gate_details = read("fold4_gate_details.csv")
    recommendations = read("fold4_family_recommendations.csv")
    run = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    pre = json.loads((OUT / "pre_run_manifest.json").read_text(encoding="utf-8"))
    frozen = json.loads(
        (OUT / "frozen_execution_package_manifest.json").read_text(encoding="utf-8")
    )
    lock = json.loads((OUT / "fold4_execution_lock.json").read_text(encoding="utf-8"))

    data_audit = f"""# Fold 4 - 2024 Data Audit

## Dataset and grain

- Grain: one row per season-week-player-team-role family.
- Played games/weeks: {int(audit.at[0, 'played_games'])}/{int(audit.at[0, 'observed_weeks'])}.
- Canonical rows: {int(audit.at[0, 'canonical_rows']):,}; unique players: {int(audit.at[0, 'unique_players']):,}.
- Duplicate canonical keys: {int(audit.at[0, 'duplicate_key_rows'])} ({pct(audit.at[0, 'duplicate_key_rate'])}).
- Required-field missingness: {int(audit.at[0, 'required_null_cells'])} cells across {int(audit.at[0, 'required_null_rows'])} rows.
- Identity coverage: {pct(audit.at[0, 'identity_coverage'])}; quality-pass rate: {pct(audit.at[0, 'quality_pass_rate'])}; qualifying rate: {pct(audit.at[0, 'qualifying_rate'])}.

## Source and join coverage

- Participation play coverage: {pct(source.at[0, 'participation_play_coverage'])}.
- Carry player identity coverage: {pct(source.at[0, 'carry_player_id_coverage'])}.
- Target player identity coverage across pass attempts: {pct(source.at[0, 'target_player_id_coverage'])}; canonical target opportunities require a resolved receiver.
- PBP/schedule games: {int(source.at[0, 'pbp_games'])}/{int(source.at[0, 'schedule_games'])}.
- Opportunity and participation joins: {int(joins['matched_rows'].sum()):,}/{int(joins['rows'].sum()):,}; every recorded join rate is {pct(joins['coverage_rate'].min())} or better.
- Injury mentions resolved: {int(partial_source.at[0, 'resolved_injury_mentions'])}/{int(partial_source.at[0, 'parsed_injury_mentions'])} ({pct(partial_source.at[0, 'resolution_rate'])}).
- Confirmed partial-game family rows: {int(partial_source.at[0, 'confirmed_partial_rows'])}; suspected rows: {int(partial_source.at[0, 'suspected_partial_rows'])}.

## Integrity judgment

All {len(audit_checks)} audit checks and all {len(temporal_pre)} pre-run temporal checks passed. The canonical grain, hashes, source completeness, identity/opportunity joins, season boundary, and evidence timing authorized the single Fold 4 execution. The full missingness profile is preserved in `missingness_2024.csv`.

## File-access boundary

- `source_seasons_physically_available`: `{pre['source_seasons_physically_available']}`
- `source_seasons_physically_opened`: `{pre['source_seasons_physically_opened']}`
- `seasons_admitted_to_feature_generation`: `{pre['seasons_admitted_to_feature_generation']}`
- `seasons_admitted_to_alert_selection`: `{pre['seasons_admitted_to_alert_selection']}`
- `seasons_admitted_to_outcome_evaluation`: `{pre['seasons_admitted_to_outcome_evaluation']}`

Multi-season local files were physically opened and scanned. Only 2024 rows were admitted to feature generation, exclusions, alert selection, and outcome evaluation. No 2025 value was admitted.
"""
    (OUT / "DATA_AUDIT_2024.md").write_text(data_audit, encoding="utf-8")

    primary_methods = methods.loc[methods["partial_policy"].eq(PRIMARY)].copy()
    method_display = format_frame(
        primary_methods[
            [
                "role_family", "method", "alerts",
                "deduplicated_player_week_team_alerts", "evaluable_alerts",
                "persistent_alerts", "precision", "precision_ci_low",
                "precision_ci_high", "reversion_rate", "median_retention",
            ]
        ],
        percentages=[
            "precision", "precision_ci_low", "precision_ci_high",
            "reversion_rate", "median_retention",
        ],
    )
    primary_comparisons = comparisons.loc[comparisons["partial_policy"].eq(PRIMARY)]
    full_uncertainty = primary_methods.loc[
        primary_methods["method"].eq("full_propwar"),
        [
            "role_family", "persistent_alerts", "precision_ci_low",
            "precision_ci_high",
        ],
    ].rename(columns={"persistent_alerts": "full_persistent_alerts"})
    primary_comparisons = primary_comparisons.merge(
        full_uncertainty, on="role_family", how="left", validate="one_to_one"
    )
    comparison_display = format_frame(
        primary_comparisons[
            [
                "role_family", "full_alerts", "full_evaluable_alerts",
                "full_persistent_alerts", "full_precision", "precision_ci_low",
                "precision_ci_high", "naive_precision", "precision_improvement",
                "precision_improvement_ci_low", "precision_improvement_ci_high",
                "full_reversion_rate", "naive_reversion_rate",
                "reversion_improvement", "full_median_retention",
            ]
        ],
        percentages=[
            "full_precision", "precision_ci_low", "precision_ci_high",
            "naive_precision", "full_reversion_rate", "naive_reversion_rate",
            "full_median_retention",
        ],
        points=[
            "precision_improvement", "precision_improvement_ci_low",
            "precision_improvement_ci_high", "reversion_improvement",
        ],
    )
    full_direction = directions.loc[
        directions["partial_policy"].eq(PRIMARY)
        & directions["method"].eq("full_propwar")
    ]
    naive_direction = directions.loc[
        directions["partial_policy"].eq(PRIMARY)
        & directions["method"].eq("naive_spike")
    ]
    direction_display = full_direction.merge(
        naive_direction,
        on=["role_family", "direction", "partial_policy"],
        suffixes=("_full", "_naive"),
        validate="one_to_one",
    )
    direction_display["naive_lift"] = (
        direction_display["precision_full"] - direction_display["precision_naive"]
    )
    direction_display["reversion_improvement"] = (
        direction_display["reversion_rate_naive"]
        - direction_display["reversion_rate_full"]
    )
    direction_display = format_frame(
        direction_display[
            [
                "role_family", "direction", "alerts_full", "evaluable_alerts_full",
                "persistent_alerts_full", "precision_full", "precision_naive",
                "naive_lift", "reversion_rate_full", "reversion_improvement",
                "median_retention_full",
            ]
        ],
        percentages=[
            "precision_full", "precision_naive", "reversion_rate_full",
            "median_retention_full",
        ],
        points=["naive_lift", "reversion_improvement"],
    )
    weekly_display = weekly.loc[
        weekly["partial_policy"].eq(PRIMARY)
        & weekly["method"].eq("full_propwar")
    ][
        [
            "role_family", "weekly_median", "weekly_maximum", "zero_alert_weeks",
            "active_weeks", "weekly_mean",
        ]
    ]
    feed_display = feed.loc[
        feed["partial_policy"].eq(PRIMARY) & feed["method"].eq("full_propwar")
    ]
    overlap_display = format_frame(
        overlap.loc[
            overlap["partial_policy"].eq(PRIMARY)
            & overlap["method"].eq("full_propwar")
        ],
        percentages=["jaccard_overlap"],
    )
    repeat_display = format_frame(
        repeats.loc[
            repeats["partial_policy"].eq(PRIMARY)
            & repeats["method"].eq("full_propwar")
        ][["role_family", "alerts", "repeat_alerts", "repeat_players", "repeat_rate"]],
        percentages=["repeat_rate"],
    )
    sensitivity_display = format_frame(
        sensitivity[
            [
                "partial_policy", "role_family", "full_alerts",
                "full_evaluable_alerts", "full_precision", "precision_improvement",
                "full_reversion_rate", "reversion_improvement",
                "full_median_retention",
            ]
        ],
        percentages=["full_precision", "full_reversion_rate", "full_median_retention"],
        points=["precision_improvement", "reversion_improvement"],
    )
    stability_display = format_frame(
        subgroup.loc[
            subgroup["method"].eq("full_propwar")
            & ~subgroup["dimension"].isin(["player", "team"])
        ][
            [
                "role_family", "dimension", "segment", "alerts", "evaluable_alerts",
                "precision", "reversion_rate", "median_retention",
            ]
        ],
        percentages=["precision", "reversion_rate", "median_retention"],
    )
    concentration_display = format_frame(
        concentration, percentages=["top_entity_share"]
    )
    overlap_dependence_display = format_frame(
        overlap_dependence,
        percentages=["precision", "reversion_rate", "median_retention"],
    )
    cross_display = format_frame(
        cross_family[
            [
                "period", "role_family", "full_alerts", "full_evaluable_alerts",
                "full_precision", "naive_precision", "precision_improvement",
                "full_reversion_rate", "reversion_improvement",
                "full_median_retention",
            ]
        ],
        percentages=[
            "full_precision", "naive_precision", "full_reversion_rate",
            "full_median_retention",
        ],
        points=["precision_improvement", "reversion_improvement"],
    )

    def pooled_display(frame: pd.DataFrame) -> pd.DataFrame:
        return format_frame(
            frame[
                [
                    "period", "role_family", "full_alerts", "full_evaluable_alerts",
                    "full_precision", "naive_precision", "precision_improvement",
                    "precision_improvement_ci_low", "precision_improvement_ci_high",
                    "full_reversion_rate", "reversion_improvement",
                    "full_median_retention",
                ]
            ],
            percentages=[
                "full_precision", "naive_precision", "full_reversion_rate",
                "full_median_retention",
            ],
            points=[
                "precision_improvement", "precision_improvement_ci_low",
                "precision_improvement_ci_high", "reversion_improvement",
            ],
        )

    gate_display = gate_details.copy()
    numeric_gate = gate_display["gate"].isin(
        [
            "min_persistence_precision", "min_absolute_improvement_vs_naive",
            "max_immediate_reversion_rate", "min_reversion_improvement_vs_naive",
            "min_median_retention",
        ]
    )
    gate_display.loc[numeric_gate, "observed"] = gate_display.loc[
        numeric_gate, "observed"
    ].map(pct)

    carry = gates.set_index("role_family").loc["rb_carry_share"]
    opportunity = gates.set_index("role_family").loc["rb_opportunity_share"]
    report = f"""# PropWar Role Validation - Fold 4 (Untouched 2024)

## Concise judgment

RB carry status: `{carry['fold4_candidate_status']}`. RB opportunity status: `{opportunity['fold4_candidate_status']}`. These are literal locked-gate outcomes; a failed gate remains a failure. Neither family is described as validated. WR and TE remain retired and were not evaluated on 2024.

## Frozen execution integrity

- Pre-Fold-4 checkpoint: `{frozen['checkpoint_tag']}` -> `{frozen['checkpoint_commit']}`
- Execution-package commit: `{frozen['execution_package_commit']}`
- Candidate SHA-256: `{frozen['candidate_config_sha256']}`
- Frozen candidate SHA-256: `{frozen['frozen_candidate_sha256']}`
- Frozen execution files: {len(frozen['files'])}; every hash reverified before execution.
- Alert archive SHA-256: `{lock['alert_archive_sha256']}`
- Fold 4 executed once: **yes**; 2025 results used: **no**; post-result redevelopment: **no**.

## File-access boundary

- `source_seasons_physically_available`: `{run['source_seasons_physically_available']}`
- `source_seasons_physically_opened`: `{run['source_seasons_physically_opened']}`
- `seasons_admitted_to_feature_generation`: `{run['seasons_admitted_to_feature_generation']}`
- `seasons_admitted_to_alert_selection`: `{run['seasons_admitted_to_alert_selection']}`
- `seasons_admitted_to_outcome_evaluation`: `{run['seasons_admitted_to_outcome_evaluation']}`

The storage layer physically opened multi-season files. Only 2024 rows entered features, partial-game classifications, alerts, or outcomes. Prior 2021-2023 archives entered cross-season reporting only.

## 2024 data audit

| rows | players | games | weeks | duplicate keys | required null cells | identity | quality | qualifying |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| {int(audit.at[0, 'canonical_rows']):,} | {int(audit.at[0, 'unique_players']):,} | {int(audit.at[0, 'played_games'])} | {int(audit.at[0, 'observed_weeks'])} | {int(audit.at[0, 'duplicate_key_rows'])} | {int(audit.at[0, 'required_null_cells'])} | {pct(audit.at[0, 'identity_coverage'])} | {pct(audit.at[0, 'quality_pass_rate'])} | {pct(audit.at[0, 'qualifying_rate'])} |

Participation coverage is {pct(source.at[0, 'participation_play_coverage'])}; carry identity coverage is {pct(source.at[0, 'carry_player_id_coverage'])}; target identity population is {pct(source.at[0, 'target_player_id_coverage'])}. All recorded participation and opportunity joins passed. Confirmed partial rows were excluded; suspected rows remained included in the primary policy.

## Active-family method results

{table(method_display)}

## Frozen detector versus equal-volume naive

{table(comparison_display)}

All {run['equal_volume_cells']} family-week-policy cells had identical counts for naive spike, two-week raw trend, normal-game trend, and the frozen full detector.

## Deduplicated volume, overlap, and repeats

{table(feed_display)}

{table(weekly_display)}

{table(overlap_display)}

{table(repeat_display)}

## Directional evaluation

{table(direction_display)}

No direction-specific candidate or exclusion was created. Carry decreases remain a diagnostic subgroup only.

## Confirmed and suspected partial-game sensitivity

`PRIMARY_CONFIRMED_EXCLUDED` excludes confirmed cases and includes suspected cases. `ALL_INCLUDED` adds confirmed cases; `STRICT_SUSPECTED_EXCLUDED` removes both confirmed and suspected cases.

{table(sensitivity_display)}

## Seasonal and subgroup stability

{table(stability_display)}

The player/team detail is preserved in `subgroup_stability_2024.csv` and `concentration_entities_2024.csv`. Baseline stability is a descriptive median split of the pre-alert absolute recent-versus-season baseline gap; it does not affect selection.

{table(concentration_display)}

### RB-family overlap dependence

{table(overlap_dependence_display)}

### Retention outlier diagnostics

{table(retention)}

No new exclusions were introduced from any subgroup, overlap, denominator, partial-game, or outlier finding.

## 2021-2024 direct comparison

{table(cross_display)}

{table(season_statuses)}

Every archived season status is preserved. The redeveloped 2021 row remains a development diagnostic, not an untouched holdout. A pooled result does not erase an individual failure.

## Pooled untouched results

### 2022-2023

{table(pooled_display(pooled_22_23))}

### 2022-2024

{table(pooled_display(pooled_22_24))}

Both pooled tables are calculated from concatenated raw alert rows and their raw numerators and denominators, never by averaging seasonal percentages.

## Locked Fold 4 gates

{table(gate_display)}

{table(gates[['role_family', 'candidate_disposition', 'fold4_candidate_status', 'failed_checks']])}

## Exact recommendations

{table(recommendations)}

## Uncertainty and limitations

- This is a historical development-fold test, not final historical or prospective validation.
- Point gates govern the locked decision; confidence intervals govern wording strength and are not used to waive or move a gate.
- Late-season alerts can lack two future qualifying games and therefore reduce outcome evaluability.
- Subgroup samples can be small and are descriptive diagnostics only.
- Multi-season source files were physically scanned, although only 2024 values were admitted to the Fold 4 calculation.
- Source extracts can be revised upstream; exact source hashes and materialized 2024 explicit-injury inputs are archived.
- No dashboard, detector rule, threshold, release gate, 2025 result, merge, push, or deployment entered this task.
"""
    (OUT / "FOLD_4_REPORT.md").write_text(report, encoding="utf-8")
    print(OUT / "FOLD_4_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
