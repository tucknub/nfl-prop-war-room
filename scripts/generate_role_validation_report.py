from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "role_validation"
FOLD = OUTPUT / "fold_1"


EXPECTED_RELEASE_GATES = {
    "min_holdout_alerts": 50,
    "min_persistence_precision": 0.60,
    "min_absolute_improvement_vs_naive": 0.10,
    "max_immediate_reversion_rate": 0.25,
    "min_reversion_improvement_vs_naive": 0.08,
    "min_median_retention": 0.50,
    "min_alerts_per_week": 0.50,
}


def markdown_table(frame: pd.DataFrame, digits: int = 4) -> str:
    if frame.empty:
        return "_No rows._"
    display = frame.copy()
    for column in display.select_dtypes(include="number"):
        display[column] = display[column].map(
            lambda value: "" if pd.isna(value) else f"{value:.{digits}f}" if isinstance(value, float) else str(value)
        )
    headers = [str(column) for column in display.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    return "\n".join(lines)


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def initial_inventory() -> pd.DataFrame:
    rows = []
    for name in ["pbp", "weekly", "rosters", "schedules"]:
        path = ROOT / "data" / "raw" / f"{name}.csv"
        frame = pd.read_csv(path, usecols=["season"], low_memory=False)
        rows.append(
            {
                "file": f"data/raw/{name}.csv",
                "rows": len(frame),
                "seasons": ", ".join(map(str, sorted(frame["season"].dropna().astype(int).unique()))),
                "status_at_start": "present before role-validation integration",
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    config = yaml.safe_load((ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8"))
    actual_gates = config["release_gates"]["full_release"]
    gate_integrity = actual_gates == EXPECTED_RELEASE_GATES
    (OUTPUT / "release_gate_integrity.json").write_text(
        json.dumps(
            {"unchanged": gate_integrity, "expected": EXPECTED_RELEASE_GATES, "actual": actual_gates},
            indent=2,
        ),
        encoding="utf-8",
    )
    if not gate_integrity:
        raise SystemExit("Release gates differ from the supplied package.")

    inventory = initial_inventory()
    inventory.to_csv(OUTPUT / "initial_repository_inventory.csv", index=False)
    coverage = pd.read_csv(OUTPUT / "source_coverage_by_season.csv")
    counts = pd.read_csv(OUTPUT / "canonical_row_counts_2018_2020.csv")
    joins = pd.read_csv(OUTPUT / "join_coverage.csv")
    reconciliation = pd.read_csv(OUTPUT / "opportunity_reconciliation.csv")
    exclusions = pd.read_csv(OUTPUT / "exclusion_ledger.csv")
    sensitivity = pd.read_csv(OUTPUT / "normal_game_sensitivity_2018_2020.csv")
    selected = pd.read_csv(FOLD / "fold_1_selected_parameters.csv")
    summary = pd.read_csv(FOLD / "summary_2021.csv")
    comparisons = pd.read_csv(FOLD / "comparisons_2021.csv")
    equal_volume = pd.read_csv(FOLD / "equal_volume_verification_2021.csv")
    weekly = pd.read_csv(FOLD / "weekly_alert_counts_2021.csv")
    alerts = pd.read_csv(FOLD / "alerts_2021.csv.gz", low_memory=False)
    manifest = json.loads((OUTPUT / "canonical_build_manifest.json").read_text(encoding="utf-8"))

    full_weekly = weekly.loc[weekly["method"].eq("full_propwar")]
    feed_volume = full_weekly.groupby("week")["alerts"].sum()
    family_volume = (
        full_weekly.groupby("role_family")["alerts"]
        .agg(weeks="count", alerts="sum", mean_per_week="mean", median_per_week="median", max_per_week="max")
        .reset_index()
    )
    family_volume.to_csv(FOLD / "full_propwar_alert_volume_2021.csv", index=False)

    gates = EXPECTED_RELEASE_GATES
    diagnostic = comparisons.copy()
    diagnostic["alerts_per_week"] = diagnostic["full_alerts"] / 18
    diagnostic["median_retention"] = diagnostic["full_median_retention"]
    diagnostic["alert_gate"] = diagnostic["full_alerts"].ge(gates["min_holdout_alerts"])
    diagnostic["precision_gate"] = diagnostic["full_precision"].ge(gates["min_persistence_precision"])
    diagnostic["precision_improvement_gate"] = diagnostic["precision_improvement"].ge(gates["min_absolute_improvement_vs_naive"])
    diagnostic["reversion_gate"] = diagnostic["full_reversion_rate"].le(gates["max_immediate_reversion_rate"])
    diagnostic["reversion_improvement_gate"] = diagnostic["reversion_improvement"].ge(gates["min_reversion_improvement_vs_naive"])
    diagnostic["retention_gate"] = diagnostic["median_retention"].ge(gates["min_median_retention"])
    diagnostic["all_point_gates_pass"] = diagnostic[[
        "alert_gate", "precision_gate", "precision_improvement_gate", "reversion_gate",
        "reversion_improvement_gate", "retention_gate",
    ]].all(axis=1)
    diagnostic.to_csv(FOLD / "fold_1_gate_diagnostic.csv", index=False)

    audit_rows = int(counts["rows"].sum())
    excluded_2018_2020 = exclusions.loc[exclusions["season"].between(2018, 2020)]
    primary_sensitivity = sensitivity.loc[
        sensitivity["q3_threshold"].eq(24) & sensitivity["q4_threshold"].eq(17)
    ].iloc[0]
    result_table = diagnostic[[
        "role_family", "full_alerts", "full_evaluable_alerts", "full_precision",
        "naive_precision", "precision_improvement", "precision_improvement_ci_low",
        "precision_improvement_ci_high", "full_reversion_rate", "reversion_improvement",
        "full_median_retention", "all_point_gates_pass",
    ]]
    selected_table = selected[[
        "role_family", "baseline_window", "min_baseline_games", "min_abs_delta",
        "development_evaluable_alerts", "development_precision_improvement",
    ]]

    report = f"""# PropWar Role-Change Validation V1 — Data Audit and Fold 1

**As of:** 2026-07-13
**Branch:** `role-change-validation-v1`
**Overall assessment:** **Needs revision**
**Detector claim:** **Not supported.** No family passes all Fold 1 point-gate diagnostics, and the combined alert volume exceeds the protocol maximum.

Fold 1 is a development test, not the frozen 2025 holdout. The release gates below are used only as diagnostics and were not changed.

## 1. Repository data inventory at start

{markdown_table(inventory, 0)}

The local repository initially contained only 2023–2025 raw history. It also contained derived weekly/player/model outputs, but no canonical `season × week × player_id × team × role_family` table and no 2018–2022 raw partitions.

## 2. Season and schema coverage

{markdown_table(coverage, 6)}

- 2018–2021 and 2023–2025 have every played regular-season game in both PBP and schedules.
- 2022 has 271 played games rather than 272 because Buffalo–Cincinnati was canceled; the played-game partitions are internally complete.
- 2024 `data/raw/weekly.csv` initially had `game_id` missing on 100% of rows. The canonical builder does not mutate that public-pipeline input; it uses PBP/schedule `game_id`, where coverage is complete.
- Receiver ID presence on all pass attempts is not expected to be 100% because sacks and throwaways are pass attempts without a target. Actual target rows require a receiver ID.

### Why 2018 remains the start

The actual schema does **not** create a quality break at 2018. 2017 has 256/256 games, the same 372-column PBP schema, and 99.9938% offensive-play participation coverage versus 99.9938% in 2018. The cutoff therefore remains an operational/precommitted modern-era boundary, not a data-availability boundary. This Fold did not add 2017 because `LOCKED_DECISIONS.md` fixes 2018–2025 and Fold 1 explicitly develops on 2018–2020. A 2017 sensitivity can be considered only with an explicit documented protocol amendment before rules are frozen.

## 3. Canonical metric definitions and leakage controls

- `rb_carry_share`: player RB non-kneel, non-two-point carries / all team non-kneel, non-two-point carries.
- `rb_opportunity_share`: player RB carries + targets / all team RB carries + targets.
- `wr_target_share` and `te_target_share`: player targets / all team targets.
- `metric_all` retains competitive, garbage-time, and overtime usage; kneels, spikes, aborted/deleted plays, and two-point attempts are not role opportunities.
- `metric_normal` excludes overtime, Q3 absolute score differential ≥24, Q4 differential ≥17, kneels/spikes, and trustworthy late-backup flags when available. Competitive two-minute usage remains included.
- Baselines use only prior qualifying games. Fold tuning reads 2018–2020 only. Future outcomes are restricted to later qualifying games in the same 2021 season; no 2022 outcome can enter Fold 1.
- Player identity uses season-week-team GSIS joins from player stats and weekly rosters. Participation creates the player universe, retaining zero-opportunity players and preventing survivorship bias.

## 4. 2018–2020 data audit

- Canonical rows: **{audit_rows:,}**.
- Duplicate canonical keys: **0 (0.0000%)**.
- Required key/metric missingness: **0** for player ID, name, team, position, `metric_all`, and `metric_normal`.
- Quality/qualifying pass: **{(audit_rows-len(excluded_2018_2020))/audit_rows:.4%}** ({audit_rows-len(excluded_2018_2020):,}/{audit_rows:,}).
- Excluded canonical rows: **{len(excluded_2018_2020):,}**; all are conservative `INCOMPLETE_GAME_PARTITION` exclusions caused by sub-99% participation coverage in affected team-games (225 rows in 2018, 191 in 2019, none in 2020).
- Opportunity-to-identity joins: **100%** in each audited season. Participating-player identity coverage: 99.0464% (2018), 99.0077% (2019), and 100% (2020); unmatched participants were non-role/metadata rows and never became canonical role rows.
- PBP versus weekly stat reconciliation is 99.58%–99.97% exact by player row after the confirmed two-point-conversion fix. Remaining count differences are 1–11 season-total opportunities and reflect upstream stat correction/lateral attribution differences, not join multiplication.
- Primary normal-game definition retains **{int(primary_sensitivity['normal_game_plays']):,}/{int(primary_sensitivity['valid_scrimmage_plays']):,}** scrimmage plays; the threshold sensitivity table is preserved in `normal_game_sensitivity_2018_2020.csv`.

### Required-field limitations

- **High blocker — partial-game exits:** no trustworthy in-game exit field exists in PBP, participation, snaps, weekly rosters, or injury reports. `partial_game_flag` is present and conservatively false but is explicitly marked unreliable. Using next-week injury reports creates look-ahead; using outcome-correlated snap drops risks excluding genuine role decreases.
- **Medium caveat — late backups:** no trustworthy late-backup-only flag exists. The protocol allows this exclusion only when reliably identified, so it remains false and marked unreliable.
- Optional `active_status` is missing on 2.94% of 2018 canonical rows and 2.80% of 2019 rows; identity, position, opportunity, and share fields are complete.

## 5. Fold 1 setup

Development-selected parameters (selected only on 2018–2020):

{markdown_table(selected_table, 4)}

The development selector required at least 25 evaluable alerts and ranked candidates by equal-volume precision improvement, precision, lower reversion, retention, and evidence count. This is a development-selection rule only; it does not alter any release gate.

## 6. Fold 1 results — 2021

{markdown_table(result_table, 4)}

- Equal-volume verification: **{bool(equal_volume['equal_volume'].all())}** across **{len(equal_volume)}** family-weeks; every full-detector count exactly matches each baseline count.
- Full-detector alerts: **{int((alerts['method']=='full_propwar').sum()):,}** total; **{int(alerts.loc[alerts['method'].eq('full_propwar'), 'persistent'].notna().sum()):,}** evaluable for the two-game outcome.
- Combined alert volume: mean **{feed_volume.mean():.2f}**, median **{feed_volume.median():.0f}**, range **{feed_volume.min()}–{feed_volume.max()}** per week. This fails the protocol target of 5–15 and hard normal-week maximum of 20.

Interpretation by family:

- RB carry share: precision 57.21%, +7.89 pp versus naive, 28.15% immediate reversion. It misses the 60%, +10 pp, ≤25%, and +8 pp gates.
- RB opportunity share: precision 58.59%, +6.84 pp, 30.14% reversion. It misses the same four gates.
- WR target share: +14.56 pp improvement, but only 44.07% precision, 47.30% reversion, and 40.02% median retention.
- TE target share: 35 alerts, 20.00% precision, negative improvement, 50.00% reversion, and 16.60% median retention.

**Conclusion:** Fold 1 does not support saying that the detector works. Normal-game filtering is directionally useful for some RB/WR comparisons, but the full detector adds little over the normal-game trend and fails multiple precommitted point gates.

## 7. Confirmed fixes only

1. Excluded two-point conversions from carries/targets after reconciliation proved they inflated PBP counts.
2. Separated all-game raw, normal-game trend, and full-detector method inputs; the supplied scaffold mislabeled the same normal metric as raw and normal.
3. Retention now uses the actual detected role value, not the penalized ranking score.
4. Future outcomes cannot cross into the next season/fold.
5. Prior baselines skip nonqualifying rows and use prior qualifying games.
6. Source-cache and gzip artifact writes are atomic/deterministic.

No release gate changed. Integrity check: **{gate_integrity}**.

## 8. Blockers and next decisions

1. Obtain or precommit a defensible contemporaneous partial-game exit source/rule before any public persistence claim.
2. Diagnose excessive alert volume and revise only in later development folds; do not tune on 2025.
3. Investigate why full safeguards barely improve on `normal_game_trend`, especially for RB families.
4. Keep WR and TE persistence claims disabled; TE is both low-evidence and materially poor in Fold 1.
5. Complete Folds 2–4, freeze rules, then run the untouched 2025 holdout. This report makes no 2025 release judgment.

## 9. Artifact integrity

- Canonical rows/hash: `{manifest['canonical_rows']}` / `{manifest['canonical_sha256']}`
- Protocol SHA-256: `{file_hash(ROOT / 'ROLE_CHANGE_VALIDATION_PROTOCOL.md')}`
- Locked decisions SHA-256: `{file_hash(ROOT / 'LOCKED_DECISIONS.md')}`
- Reproducible notebook: `notebooks/role_change_validation.ipynb`
- Alert archive: `outputs/role_validation/fold_1/alerts_2021.csv.gz`
- Exclusion ledger: `outputs/role_validation/exclusion_ledger.csv`
"""
    (OUTPUT / "ROLE_CHANGE_VALIDATION_REPORT.md").write_text(report, encoding="utf-8")
    print(OUTPUT / "ROLE_CHANGE_VALIDATION_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
