from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
REPORT = OUT / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md"
PRIMARY = "PRIMARY_CONFIRMED_EXCLUDED"
RECOMMENDED = "fold2_candidate_v1_symmetric_deltas"


def read_csv(name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(OUT / name, low_memory=False, **kwargs)


def assert_allowed(frame: pd.DataFrame) -> None:
    if "season" not in frame:
        return
    observed = set(pd.to_numeric(frame["season"], errors="coerce").dropna().astype(int))
    if not observed.issubset({2018, 2019, 2020, 2021}):
        raise AssertionError(f"Report input contains disallowed seasons: {sorted(observed)}")


def fnum(value, digits: int = 3) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):.{digits}f}"


def fpct(value, digits: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{100 * float(value):.{digits}f}%"


def fpp(value, digits: int = 1) -> str:
    if pd.isna(value):
        return "—"
    return f"{100 * float(value):+.{digits}f} pp"


def table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    values = [[str(value) for value in row] for row in frame.fillna("—").to_numpy()]
    columns = [str(column) for column in frame.columns]
    widths = [len(column) for column in columns]
    for row in values:
        widths = [max(width, len(value)) for width, value in zip(widths, row)]
    header = "| " + " | ".join(column.ljust(width) for column, width in zip(columns, widths)) + " |"
    divider = "| " + " | ".join("-" * width for width in widths) + " |"
    body = [
        "| " + " | ".join(value.ljust(width) for value, width in zip(row, widths)) + " |"
        for row in values
    ]
    return "\n".join([header, divider, *body])


def metric_view(frame: pd.DataFrame, *, segment: str | None = None) -> pd.DataFrame:
    work = frame.copy()
    if segment is not None:
        work = work.loc[work["dimension"].eq(segment)]
    columns = [
        column
        for column in [
            "segment",
            "alerts",
            "evaluable_alerts",
            "precision",
            "reversion_evaluable_alerts",
            "reversion_rate",
            "median_retention",
        ]
        if column in work
    ]
    work = work[columns].copy()
    for column in ["precision", "reversion_rate", "median_retention"]:
        if column in work:
            work[column] = work[column].map(fpct)
    return work


def family_comparison_view(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame[
        [
            "role_family",
            "full_alerts",
            "full_evaluable_alerts",
            "full_precision",
            "full_precision_ci_low",
            "full_precision_ci_high",
            "precision_improvement",
            "precision_improvement_ci_low",
            "precision_improvement_ci_high",
            "full_reversion_rate",
            "reversion_improvement",
            "full_median_retention",
        ]
    ].copy()
    work["precision (95% CI)"] = [
        f"{fpct(precision)} ({fpct(low)} to {fpct(high)})"
        for precision, low, high in zip(
            work.pop("full_precision"),
            work.pop("full_precision_ci_low"),
            work.pop("full_precision_ci_high"),
        )
    ]
    work["improvement (95% CI)"] = [
        f"{fpp(improvement)} ({fpp(low)} to {fpp(high)})"
        for improvement, low, high in zip(
            work.pop("precision_improvement"),
            work.pop("precision_improvement_ci_low"),
            work.pop("precision_improvement_ci_high"),
        )
    ]
    for column in ["reversion_improvement"]:
        work[column] = work[column].map(fpp)
    work["full_reversion_rate"] = work["full_reversion_rate"].map(fpct)
    work["full_median_retention"] = work["full_median_retention"].map(fpct)
    return work


def main() -> int:
    manifest = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    audit = read_csv("canonical_redevelopment_audit_2018_2021.csv")
    missing = read_csv("canonical_redevelopment_missingness_2018_2021.csv")
    source = read_csv("partial_game_source_coverage.csv")
    partial_counts = read_csv("partial_game_status_counts.csv")
    original_weekly = read_csv("original_weekly_family_vs_deduplicated_volume_2021.csv")
    original_overlap = read_csv("original_rb_family_overlap_2021.csv").iloc[0]
    original_repeat = read_csv("original_repeat_alerts_2021.csv")
    original_methods = read_csv("original_four_method_comparison_2021.csv")
    original_breakdowns = read_csv("original_requested_breakdowns_2021.csv")
    original_vs = read_csv("original_vs_recommended_fold1_2021.csv")
    ablation = read_csv("legacy_safeguard_ablation_value.csv")
    screens = read_csv("candidate_axis_screen_equal_volume.csv")
    serious_comparisons = read_csv("serious_candidate_comparisons.csv")
    serious_feed = read_csv("serious_candidate_feed_volume_summary_2021.csv")
    recommended_family = read_csv("recommended_candidate_partial_sensitivity_comparisons.csv")
    recommended_method_family = read_csv(
        "recommended_candidate_partial_sensitivity_family.csv"
    )
    recommended_full_ci = recommended_method_family.loc[
        recommended_method_family["method"].eq("full_propwar"),
        [
            "candidate_name",
            "partial_policy",
            "period",
            "role_family",
            "precision_ci_low",
            "precision_ci_high",
        ],
    ].rename(
        columns={
            "precision_ci_low": "full_precision_ci_low",
            "precision_ci_high": "full_precision_ci_high",
        }
    )
    recommended_family = recommended_family.merge(
        recommended_full_ci,
        on=["candidate_name", "partial_policy", "period", "role_family"],
        how="left",
        validate="one_to_one",
    )
    recommended_direction = read_csv("recommended_candidate_partial_sensitivity_direction.csv")
    recommended_blocks = read_csv("recommended_candidate_partial_sensitivity_block_comparisons.csv")
    recommended_feed = read_csv("recommended_candidate_partial_sensitivity_feed_summary_2021.csv")
    recommended_weekly = read_csv("recommended_candidate_partial_sensitivity_weekly_2021.csv")
    gate = read_csv("recommended_candidate_locked_gate_diagnostic_2021.csv")
    threshold_sensitivity = read_csv("recommended_candidate_persistence_threshold_sensitivity.csv")
    for frame in [
        audit,
        missing,
        partial_counts,
        original_weekly,
        original_breakdowns,
        serious_comparisons,
        recommended_family,
        recommended_direction,
        recommended_blocks,
        recommended_weekly,
    ]:
        assert_allowed(frame)

    canonical = read_csv("canonical_role_2018_2021_enriched.csv.gz")
    assert_allowed(canonical)
    identity = (
        canonical.groupby("season", as_index=False)
        .agg(identity_resolved_rate=("identity_resolved", "mean"))
    )
    audit = audit.merge(identity, on="season", how="left", validate="one_to_one")
    audit_view = audit[
        [
            "season",
            "canonical_rows",
            "unique_players",
            "duplicate_key_rows",
            "required_field_null_cells",
            "quality_pass_rate",
            "identity_resolved_rate",
            "confirmed_partial_family_rows",
            "suspected_partial_family_rows",
        ]
    ].copy()
    for column in ["quality_pass_rate", "identity_resolved_rate"]:
        audit_view[column] = audit_view[column].map(fpct)

    original_overall = original_methods.loc[
        original_methods["grain"].eq("all_family_rows")
    ][
        ["method", "alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"]
    ].copy()
    for column in ["precision", "reversion_rate", "median_retention"]:
        original_overall[column] = original_overall[column].map(fpct)

    original_family = original_methods.loc[
        original_methods["grain"].eq("role_family")
        & original_methods["method"].eq("full_propwar")
    ][
        [
            "role_family",
            "alerts",
            "evaluable_alerts",
            "precision",
            "precision_ci_low",
            "precision_ci_high",
            "reversion_rate",
            "median_retention",
        ]
    ].copy()
    original_family["precision (95% CI)"] = [
        f"{fpct(p)} ({fpct(lo)}–{fpct(hi)})"
        for p, lo, hi in zip(
            original_family.pop("precision"),
            original_family.pop("precision_ci_low"),
            original_family.pop("precision_ci_high"),
        )
    ]
    original_family["reversion_rate"] = original_family["reversion_rate"].map(fpct)
    original_family["median_retention"] = original_family["median_retention"].map(fpct)

    ablation_operational = ablation.loc[
        ablation["ablation_mode"].eq("operational")
        & ~ablation["ablation"].eq("original_full_detector")
    ]
    ablation_view = (
        ablation_operational.groupby(["ablation", "ablated_safeguard"], as_index=False)
        .agg(
            alert_delta=("alert_delta", "sum"),
            mean_precision_delta=("precision_delta", "mean"),
            mean_reversion_delta=("reversion_rate_delta", "mean"),
            mean_retention_delta=("median_retention_delta", "mean"),
            identical_membership=("identical_membership", "all"),
            no_measurable_value=("no_measurable_value", "all"),
        )
    )
    for column in ["mean_precision_delta", "mean_reversion_delta", "mean_retention_delta"]:
        ablation_view[column] = ablation_view[column].map(fpp)

    valid_screens = int(screens["integrity_pass"].fillna(False).sum())
    failed_screens = int((~screens["integrity_pass"].fillna(False)).sum())
    failures = screens.loc[~screens["integrity_pass"].fillna(False)]

    decision_rows = []
    for candidate in sorted(serious_feed["candidate_name"].unique()):
        feed_row = serious_feed.loc[serious_feed["candidate_name"].eq(candidate)].iloc[0]
        fold = serious_comparisons.loc[
            serious_comparisons["candidate_name"].eq(candidate)
            & serious_comparisons["period"].eq("fold_1_2021")
        ].set_index("role_family")
        decision_rows.append(
            {
                "candidate": candidate,
                "median feed": fnum(feed_row["median_all_18_weeks"], 1),
                "max": int(feed_row["max_week"]),
                "zero weeks": int(feed_row["zero_alert_weeks"]),
                "RB carry precision/lift": (
                    f"{fpct(fold.loc['rb_carry_share', 'full_precision'])} / "
                    f"{fpp(fold.loc['rb_carry_share', 'precision_improvement'])}"
                ),
                "RB opp precision/lift": (
                    f"{fpct(fold.loc['rb_opportunity_share', 'full_precision'])} / "
                    f"{fpp(fold.loc['rb_opportunity_share', 'precision_improvement'])}"
                ),
                "decision": "recommended" if candidate == "S2_symmetric_deltas" else "not selected",
            }
        )
    decision = pd.DataFrame(decision_rows)

    rec = recommended_family.loc[
        recommended_family["partial_policy"].eq(PRIMARY)
    ].copy()
    rec_dev = rec.loc[rec["period"].eq("development_2018_2020")]
    rec_fold = rec.loc[rec["period"].eq("fold_1_2021")]

    direction = recommended_direction.loc[
        recommended_direction["partial_policy"].eq(PRIMARY)
    ][
        ["period", "role_family", "direction", "alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"]
    ].copy()
    for column in ["precision", "reversion_rate", "median_retention"]:
        direction[column] = direction[column].map(fpct)

    blocks = recommended_blocks.loc[
        recommended_blocks["partial_policy"].eq(PRIMARY)
    ][
        [
            "week_block",
            "role_family",
            "full_alerts",
            "full_evaluable_alerts",
            "full_precision",
            "precision_improvement",
            "full_reversion_rate",
            "reversion_improvement",
            "full_median_retention",
        ]
    ].copy()
    for column in ["full_precision", "full_reversion_rate", "full_median_retention"]:
        blocks[column] = blocks[column].map(fpct)
    for column in ["precision_improvement", "reversion_improvement"]:
        blocks[column] = blocks[column].map(fpp)

    weekly = recommended_weekly.loc[
        recommended_weekly["partial_policy"].eq(PRIMARY)
    ][["week", "family_alert_rows", "deduplicated_feed_alerts", "duplicate_family_rows_removed"]]

    partial_feed = recommended_feed[
        [
            "partial_policy",
            "family_alert_rows",
            "deduplicated_feed_alerts",
            "median_all_18_weeks",
            "max_week",
            "zero_alert_weeks",
        ]
    ].copy()
    partial_family = recommended_family.loc[
        recommended_family["period"].eq("fold_1_2021")
    ][
        [
            "partial_policy",
            "role_family",
            "full_alerts",
            "full_evaluable_alerts",
            "full_precision",
            "precision_improvement",
            "full_reversion_rate",
            "full_median_retention",
        ]
    ].copy()
    for column in ["full_precision", "full_reversion_rate", "full_median_retention"]:
        partial_family[column] = partial_family[column].map(fpct)
    partial_family["precision_improvement"] = partial_family["precision_improvement"].map(fpp)

    gate_view = gate[
        [
            "role_family",
            "point_gate_result",
            "alerts",
            "precision",
            "precision_improvement",
            "reversion_rate",
            "reversion_improvement",
            "median_retention",
            "failed_checks",
        ]
    ].copy()
    for column in ["precision", "reversion_rate", "median_retention"]:
        gate_view[column] = gate_view[column].map(fpct)
    for column in ["precision_improvement", "reversion_improvement"]:
        gate_view[column] = gate_view[column].map(fpp)

    threshold_view = threshold_sensitivity[
        [
            "persistence_threshold",
            "period",
            "role_family",
            "full_evaluable_alerts",
            "full_precision",
            "precision_improvement",
            "precision_improvement_ci_low",
            "precision_improvement_ci_high",
        ]
    ].copy()
    for column in ["persistence_threshold", "full_precision"]:
        threshold_view[column] = threshold_view[column].map(fpct)
    threshold_view["precision_improvement"] = threshold_view["precision_improvement"].map(fpp)
    threshold_view["improvement 95% CI"] = [
        f"{fpp(low)} to {fpp(high)}"
        for low, high in zip(
            threshold_view.pop("precision_improvement_ci_low"),
            threshold_view.pop("precision_improvement_ci_high"),
        )
    ]

    manual_path = OUT / "original_false_positive_manual_adjudication_2021.csv"
    if manual_path.exists():
        manual = pd.read_csv(manual_path, low_memory=False)
        reason = (
            manual.groupby("manual_primary_reason_code", as_index=False)
            .agg(cases=("manual_primary_reason_code", "size"))
            .sort_values("cases", ascending=False)
        )
        reason["share"] = reason["cases"].div(reason["cases"].sum()).map(fpct)
        review_note = (
            f"All {len(manual)} evaluable false positives were manually adjudicated; "
            f"the source ledger hash and any overrides are recorded in the review manifest."
        )
    else:
        reason = read_csv("original_false_positive_reason_summary_2021.csv")[
            ["primary_reason_code", "alerts"]
        ].rename(columns={"primary_reason_code": "reason", "alerts": "cases"})
        review_note = "Rule-assigned evidence codes are present; manual adjudication remains pending."

    recommended_config = yaml.safe_load(
        (ROOT / "config" / "role_change_fold2_candidate.yaml").read_text(encoding="utf-8")
    )
    checkpoint_tag = "role-change-validation-v1-fold1-checkpoint"
    lines = [
        "# Fold 1 Detector Diagnostic and Redevelopment Report",
        "",
        "## TL;DR",
        "",
        "The original detector failed Fold 1 and remains failed. Duplicate RB family alerts inflated the public-facing count, but deduplication still leaves genuinely excessive candidate generation. The recommended symmetric-delta rules materially reduce volume and improve the 2018–2021 diagnostic point estimates, especially for RB carry share. They are recommended only as a candidate for the untouched 2022 test; this report does not claim that the detector works, is validated, or is release-ready.",
        "",
        f"Checkpoint `{manifest['checkpoint_commit']}` is preserved by tag `{checkpoint_tag}`. Fold 2 was not executed, no post-2021 result entered this analysis, and the locked release gates were not changed.",
        "",
        "## Integrity contract",
        "",
        table(pd.DataFrame([
            {"constraint": "Seasons used", "result": "2018–2021 only"},
            {"constraint": "Development / diagnostic test", "result": "2018–2020 / 2021"},
            {"constraint": "Fold 2", "result": "not executed"},
            {"constraint": "Post-2021 results", "result": "not used"},
            {"constraint": "Release gates", "result": "unchanged; diagnostic application only"},
            {"constraint": "Public dashboard", "result": "outside this work and not staged"},
        ])),
        "",
        "## Canonical data audit",
        "",
        table(audit_view),
        "",
        f"The scoped canonical table contains {int(audit['canonical_rows'].sum()):,} family rows. Required detector fields have {int(missing['null_rows'].sum()):,} null rows, and the canonical key has {int(audit['duplicate_key_rows'].sum()):,} duplicate rows. Carry share, RB opportunity share, WR target share, and TE target share are calculated from game-level player opportunities divided by same-team, same-game denominators. Normal-game usage is computed before weekly aggregation; baselines end before confirmation windows and reset each season, preventing future or cross-season leakage.",
        "",
        "Player identity is GSIS-native for opportunity rows. The audit distinguishes unresolved participation from confirmed identity; no unresolved identity is allowed to pass the canonical quality gate. Confirmed partial-game evidence requires an explicit PBP injury mention, resolved identity, no later offensive appearance, at least five focal-team offensive plays after the injury, and a conservative game-end timestamp before the current team’s next scheduled game.",
        "",
        "### Partial-game evidence coverage",
        "",
        table(source),
        "",
        table(partial_counts),
        "",
        "Statistical usage collapse alone is labeled suspected and remains included in the primary analysis. Postgame injury-report evidence may corroborate suspicion but cannot independently create a confirmed exclusion.",
        "",
        "## Original Fold 1 diagnosis",
        "",
        f"The checkpoint emitted {manifest['original_full_family_alerts_2021']:,} family-alert rows but only {manifest['original_deduplicated_feed_alerts_2021']:,} unique player-week-team feed items. Deduplication removed {manifest['original_full_family_alerts_2021'] - manifest['original_deduplicated_feed_alerts_2021']:,} rows ({fpct((manifest['original_full_family_alerts_2021'] - manifest['original_deduplicated_feed_alerts_2021']) / manifest['original_full_family_alerts_2021'])}).",
        "",
        table(pd.DataFrame([{
            "RB carry alerts": int(original_overlap['carry_alerts']),
            "RB opportunity alerts": int(original_overlap['opportunity_alerts']),
            "overlap": int(original_overlap['overlap_alerts']),
            "Jaccard": fpct(original_overlap['jaccard_overlap']),
            "direction conflicts": int(original_overlap['direction_conflicts']),
        }])),
        "",
        table(original_repeat[["grain", "alerts", "repeat_alerts", "repeat_rate", "players_with_repeat"]].assign(repeat_rate=lambda x: x["repeat_rate"].map(fpct))),
        "",
        f"The original family-row median was {fnum(original_weekly['family_alert_rows'].median(), 1)} per week; deduplication reduced it to {fnum(original_weekly['deduplicated_feed_alerts'].median(), 1)}, still above the 15-alert target ceiling in {int(original_weekly['deduplicated_feed_alerts'].gt(15).sum())}/18 weeks. The 38-alert median was inflated by duplicate RB families, but the 26-alert deduplicated median proves excessive candidate generation remained.",
        "",
        "### Raw spike, trend, and full-detector comparison",
        "",
        table(original_overall),
        "",
        table(original_family),
        "",
        "The full detector selected 705 of the same 717 family alerts as the normal-game trend (96.7% Jaccard). Its aggregate point-estimate gain over normal-game trend was only about 0.7 percentage points of precision and 0.9 points of reversion reduction.",
        "",
        "### Requested original breakdowns",
        "",
    ]
    for dimension in [
        "role_family",
        "direction",
        "week_of_season",
        "baseline_sample_size",
        "baseline_sample_bin",
        "raw_player_opportunities",
        "team_opportunity_denominator",
        "absolute_detected_change",
        "partial_game_status",
    ]:
        lines.extend([f"#### {dimension.replace('_', ' ').title()}", "", table(metric_view(original_breakdowns, segment=dimension)), ""])

    lines.extend([
        "## Full-detector safeguard ablations",
        "",
        "Every full-detector safeguard was ablated in operational and fixed-volume modes. Comparator counts remained equal within family-week; fixed-volume backfill is explicitly tagged where an ablation could not naturally supply the checkpoint count.",
        "",
        table(ablation_view),
        "",
        "Sample weighting and the concentration penalty add no measurable selection value in the checkpoint implementation: they alter `full_score`, but alert membership is gated by the unweighted normal two-week score. Several quality safeguards are empirically no-op because they are perfectly satisfied or collinear in this dataset; they remain integrity protections and were not removed. Two-game persistence adds clear value. Direction consistency adds modest value. Removing the minimum delta explodes volume and is not treated as an improvement even when denominator-sensitive point estimates move.",
        "",
        "## False-positive review",
        "",
        review_note,
        "",
        table(reason),
        "",
        "Reason codes describe observed evidence, not inferred injuries. `ROLE_REVERSION_NO_OBSERVED_DATA_ISSUE` means the role outcome failed without a confirmed data defect; it does not manufacture a causal explanation.",
        "",
        "## Candidate redevelopment",
        "",
        f"The one-factor screen attempted {len(screens)} candidates: {valid_screens} passed all comparator-integrity checks and {failed_screens} failed fast. The failed one-game screen could not provide the required two-week-raw comparator count for one early family-week; it was retained as an integrity failure, not silently discarded.",
        "",
        table(failures[[column for column in ["candidate_name", "screening_axis", "screening_level", "integrity_error"] if column in failures]]),
        "",
        "Six serious candidates were rerun on 2018–2020 and revised 2021. The 2021 results are redevelopment evidence because the failed 2021 Fold 1 outcome was already observed.",
        "",
        table(decision),
        "",
        "The recommendation is not based on a single best metric. The symmetric candidate uses the simplest common absolute-change threshold by family, materially improves the governing RB point estimates, preserves equal-volume comparisons, is insensitive to the partial-game policy, and reaches the operating median without weakening qualification. It does not dominate every candidate or every metric.",
        "",
        "## Original versus recommended Fold 1",
        "",
        table(original_vs),
        "",
        "## Recommended candidate results",
        "",
        "### Development, 2018–2020",
        "",
        table(family_comparison_view(rec_dev)),
        "",
        "### Revised Fold 1, 2021",
        "",
        table(family_comparison_view(rec_fold)),
        "",
        "The precision interval is a seeded 2,000-draw bootstrap over evaluable alerts, matching the locked workflow. Improvement intervals use a seeded season-week cluster bootstrap. Uncertainty does not move the locked point gates.",
        "",
        "RB carry is the strongest candidate. RB opportunity advances with development precision-improvement and reversion-improvement caveats: its 2018–2020 point lifts miss the locked 10- and 8-point diagnostics, and its improvement intervals include zero. WR and TE remain shadow-only because evidence and/or absolute performance are insufficient. No family is declared validated.",
        "",
        "### Direction",
        "",
        table(direction),
        "",
        "WR direction results are unstable in 2021 (strong increases, weak decreases on small samples); TE is too sparse for inference.",
        "",
        "### 2021 week blocks",
        "",
        table(blocks),
        "",
        "Weeks 1–5 have no alerts by construction after season reset and a four-game disjoint baseline. Weeks 1–6 therefore represent only tiny Week 6 samples. RB precision lift is positive in both post-accrual blocks, but RB-carry reversion improvement becomes negative late in the season; full multi-metric weekly stability is not established.",
        "",
        "### Deduplicated weekly feed",
        "",
        table(weekly),
        "",
        table(recommended_feed.loc[recommended_feed['partial_policy'].eq(PRIMARY)]),
        "",
        "The primary feed has a 7.5 all-week median, 10 active-week median, 17 maximum, five zero-alert weeks, one week above 15, and no week above 20. It meets the seasonal median target but does not produce 5–15 alerts every week.",
        "",
        "### Locked-gate diagnostic",
        "",
        table(gate_view),
        "",
        "`point_gate_result` is descriptive only. The revised rules were developed after observing 2021, so they were not frozen before this test and cannot authorize release. Fold 2 is the next untouched test.",
        "",
        "### Persistence-threshold sensitivity",
        "",
        table(threshold_view),
        "",
        "### Partial-game sensitivity",
        "",
        table(partial_feed),
        "",
        table(partial_family),
        "",
        "The recommendation is not driven by suspected partial games. Suspected cases remain included in the primary policy; excluding them is sensitivity only.",
        "",
        "## Exact candidate recommended for Fold 2",
        "",
        "```yaml",
        yaml.safe_dump(recommended_config, sort_keys=False).rstrip(),
        "```",
        "",
        "## Limitations and blockers",
        "",
        "- Revised 2021 is not an untouched holdout; it is redevelopment evidence.",
        "- RB carry is the strongest candidate, but its revised-2021 50% improvement interval is only narrowly above zero (+0.7 pp lower bound), and its 40%/60% persistence-threshold sensitivity intervals include zero.",
        "- RB opportunity misses both the locked development precision-improvement and reversion-improvement point gates; its improvement intervals include zero, and one development season is negative.",
        "- WR and TE evidence is insufficient; TE has only four family alerts in each aggregate period.",
        "- Week-level stability is incomplete, and early-season coverage is intentionally zero until the baseline accrues.",
        "- Historical PBP has no immutable publication timestamp. Confirmed evidence uses a conservative kickoff-plus-six-hours availability proxy and a strict next-team-game boundary.",
        "- The explicit nflverse PBP, roster, and schedule pulls are not independently snapshotted in this commit; future rebuilds can differ if upstream historical files are revised. The executed evidence ledger and derived artifacts are committed.",
        "- Equal-volume comparison is exact within family-week, but small family samples still produce wide intervals.",
        "- Fold 2 was not executed. No claim that the detector works is supported yet.",
        "",
        "## Machine-readable evidence",
        "",
        "The report tables are backed by CSV/GZIP artifacts in this directory, including the full original diagnostics, requested breakdowns, every safeguard ablation, 53 valid/1 failed candidate screen, six serious-candidate archives, equal-volume verification, partial-game evidence, sensitivity analyses, and the original-versus-recommended comparison.",
        "",
        "Exact material commands are recorded in `COMMANDS_RUN.md`. Unit-test, notebook, and independent-validation results are recorded in `TEST_AND_VALIDATION_RESULTS.md` and `final_validation.json`.",
        "",
    ])
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
