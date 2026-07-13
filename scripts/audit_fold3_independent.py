from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
FOLD3 = ROOT / "outputs" / "role_validation" / "fold_3"
OUT = ROOT / "outputs" / "role_validation" / "fold_3_independent_audit"
AUDITED_COMMIT = "a18c5cc3e8c9124be4781bececea0a93f7b4faf8"
START_COMMIT = "c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9"
CONFIG_SHA = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"
PRIMARY = "PRIMARY_CONFIRMED_EXCLUDED"
RB_FAMILIES = ["rb_carry_share", "rb_opportunity_share"]
ROLE_FAMILIES = ["rb_carry_share", "rb_opportunity_share", "wr_target_share", "te_target_share"]
METHODS = ["naive_spike", "two_week_raw", "normal_game_trend", "full_propwar"]
POLICIES = ["ALL_INCLUDED", PRIMARY, "STRICT_SUSPECTED_EXCLUDED"]
BOOTSTRAPS = 2000
SEED = 850

sys.path.insert(0, str(ROOT / "src"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def indicator(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(float)
    mapping = {True: 1.0, False: 0.0, "True": 1.0, "False": 0.0, "true": 1.0, "false": 0.0, 1: 1.0, 0: 0.0}
    return series.map(mapping).astype(float)


def rate_interval(values: pd.Series) -> tuple[float, float]:
    array = indicator(values).dropna().to_numpy()
    if not len(array):
        return np.nan, np.nan
    rng = np.random.default_rng(SEED)
    samples = rng.choice(array, size=(BOOTSTRAPS, len(array)), replace=True).mean(axis=1)
    return float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))


def cluster_difference_interval(frame: pd.DataFrame) -> tuple[float, float]:
    work = frame.loc[
        frame["method"].isin(["full_propwar", "naive_spike"])
    ].copy()
    work["value"] = indicator(work["persistent"])
    work = work.loc[work["value"].notna()]
    work["cluster"] = work["season"].astype(str) + "-" + work["week"].astype(str)
    clusters = sorted(work["cluster"].unique())
    grouped = work.groupby(["cluster", "method"])["value"].agg(["sum", "count"]).reset_index()
    sums = grouped.pivot(index="cluster", columns="method", values="sum").reindex(clusters).fillna(0)
    counts = grouped.pivot(index="cluster", columns="method", values="count").reindex(clusters).fillna(0)
    rng = np.random.default_rng(SEED)
    sampled = rng.integers(0, len(clusters), size=(BOOTSTRAPS, len(clusters)))
    full_den = counts["full_propwar"].to_numpy()[sampled].sum(axis=1)
    naive_den = counts["naive_spike"].to_numpy()[sampled].sum(axis=1)
    valid = (full_den > 0) & (naive_den > 0)
    full_num = sums["full_propwar"].to_numpy()[sampled].sum(axis=1)
    naive_num = sums["naive_spike"].to_numpy()[sampled].sum(axis=1)
    differences = full_num[valid] / full_den[valid] - naive_num[valid] / naive_den[valid]
    return float(np.quantile(differences, 0.025)), float(np.quantile(differences, 0.975))


def metric_summary(frame: pd.DataFrame) -> dict[str, float | int]:
    persistent = indicator(frame["persistent"])
    reversion = indicator(frame["immediate_reversion"])
    evaluable = persistent.notna()
    reversion_evaluable = reversion.notna()
    return {
        "alerts": len(frame),
        "evaluable_alerts": int(evaluable.sum()),
        "persistent_alerts": int(persistent.sum(skipna=True)),
        "precision": float(persistent.mean()) if evaluable.any() else np.nan,
        "reversion_evaluable_alerts": int(reversion_evaluable.sum()),
        "immediate_reversions": int(reversion.sum(skipna=True)),
        "reversion_rate": float(reversion.mean()) if reversion_evaluable.any() else np.nan,
        "median_retention": float(pd.to_numeric(frame.loc[evaluable, "retention"], errors="coerce").median()) if evaluable.any() else np.nan,
    }


def family_method_results(alerts: pd.DataFrame, period: str) -> pd.DataFrame:
    rows = []
    for (family, method), group in alerts.groupby(["role_family", "method"], sort=True):
        if family not in RB_FAMILIES:
            continue
        row = metric_summary(group)
        low, high = rate_interval(group["persistent"])
        rows.append({"period": period, "role_family": family, "method": method, **row, "precision_ci_low": low, "precision_ci_high": high})
    return pd.DataFrame(rows)


def family_comparisons(alerts: pd.DataFrame, period: str) -> pd.DataFrame:
    rows = []
    for family in RB_FAMILIES:
        group = alerts.loc[alerts["role_family"].eq(family)]
        full = metric_summary(group.loc[group["method"].eq("full_propwar")])
        naive = metric_summary(group.loc[group["method"].eq("naive_spike")])
        low, high = cluster_difference_interval(group)
        rows.append({
            "period": period,
            "role_family": family,
            "full_alerts": full["alerts"],
            "full_evaluable_alerts": full["evaluable_alerts"],
            "full_persistent_alerts": full["persistent_alerts"],
            "full_precision": full["precision"],
            "naive_alerts": naive["alerts"],
            "naive_evaluable_alerts": naive["evaluable_alerts"],
            "naive_persistent_alerts": naive["persistent_alerts"],
            "naive_precision": naive["precision"],
            "precision_improvement": full["precision"] - naive["precision"],
            "precision_improvement_ci_low": low,
            "precision_improvement_ci_high": high,
            "full_reversion_evaluable_alerts": full["reversion_evaluable_alerts"],
            "full_immediate_reversions": full["immediate_reversions"],
            "full_reversion_rate": full["reversion_rate"],
            "naive_reversion_evaluable_alerts": naive["reversion_evaluable_alerts"],
            "naive_immediate_reversions": naive["immediate_reversions"],
            "naive_reversion_rate": naive["reversion_rate"],
            "reversion_improvement": naive["reversion_rate"] - full["reversion_rate"],
            "full_median_retention": full["median_retention"],
            "naive_median_retention": naive["median_retention"],
        })
    return pd.DataFrame(rows)


def directional_results(alerts: pd.DataFrame, period: str) -> pd.DataFrame:
    rows = []
    for family in RB_FAMILIES:
        for direction in ["decrease", "increase"]:
            selected = alerts.loc[alerts["role_family"].eq(family) & alerts["direction"].eq(direction)]
            full = metric_summary(selected.loc[selected["method"].eq("full_propwar")])
            naive = metric_summary(selected.loc[selected["method"].eq("naive_spike")])
            rows.append({
                "period": period, "role_family": family, "direction": direction,
                **{f"full_{key}": value for key, value in full.items()},
                **{f"naive_{key}": value for key, value in naive.items()},
                "precision_improvement": full["precision"] - naive["precision"],
                "reversion_improvement": naive["reversion_rate"] - full["reversion_rate"],
            })
    return pd.DataFrame(rows)


def weekly_results(alerts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    full = alerts.loc[alerts["method"].eq("full_propwar")]
    for family in RB_FAMILIES:
        counts = full.loc[full["role_family"].eq(family)].groupby("week").size()
        family_frame = full.loc[full["role_family"].eq(family)]
        for week in range(1, 19):
            group = family_frame.loc[family_frame["week"].eq(week)]
            rows.append({"role_family": family, "week": week, **metric_summary(group)})
    return pd.DataFrame(rows)


def subgroup_results(primary_2023: pd.DataFrame) -> pd.DataFrame:
    full = primary_2023.loc[
        primary_2023["method"].eq("full_propwar") & primary_2023["role_family"].isin(RB_FAMILIES)
    ].copy()
    full["week_block"] = pd.cut(full["week"], [0, 6, 12, 18], labels=["weeks_1_6", "weeks_7_12", "weeks_13_18"])
    full["partial_status_group"] = np.where(full["suspected_partial_game"].fillna(False), "suspected", "not_suspected")
    denominator = pd.to_numeric(full["confirmation_min_team_denominator"], errors="coerce")
    full["denominator_band"] = pd.cut(denominator, [17, 20, 24, 29, np.inf], labels=["18_20", "21_24", "25_29", "30_plus"])
    raw = pd.to_numeric(full["raw_opportunities_normal"], errors="coerce")
    full["current_raw_band"] = pd.cut(raw, [-np.inf, 5, 9, 14, np.inf], labels=["0_5", "6_9", "10_14", "15_plus"])
    rows = []
    for dimension in ["direction", "week_block", "partial_status_group", "denominator_band", "current_raw_band"]:
        for (family, subgroup), group in full.groupby(["role_family", dimension], observed=True, sort=True):
            rows.append({"role_family": family, "dimension": dimension, "subgroup": str(subgroup), **metric_summary(group)})
    return pd.DataFrame(rows)


def concentration_results(primary_2023: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    full = primary_2023.loc[
        primary_2023["method"].eq("full_propwar") & primary_2023["role_family"].isin(RB_FAMILIES)
    ]
    summaries = []
    details = []
    for family in RB_FAMILIES:
        family_frame = full.loc[full["role_family"].eq(family)]
        for dimension, column in [("team", "team"), ("player", "player_id")]:
            counts = family_frame[column].value_counts()
            shares = counts / len(family_frame)
            leave_one_precision = []
            for entity in counts.index:
                remaining = family_frame.loc[~family_frame[column].eq(entity)]
                leave_one_precision.append(metric_summary(remaining)["precision"])
            summaries.append({
                "role_family": family, "dimension": dimension, "alerts": len(family_frame),
                "unique_groups": int(len(counts)), "top_1_share": float(shares.iloc[:1].sum()),
                "top_3_share": float(shares.iloc[:3].sum()), "top_5_share": float(shares.iloc[:5].sum()),
                "hhi": float((shares ** 2).sum()), "effective_groups": float(1 / (shares ** 2).sum()),
                "leave_one_out_precision_min": float(np.nanmin(leave_one_precision)),
                "leave_one_out_precision_max": float(np.nanmax(leave_one_precision)),
            })
            for entity, count in counts.head(10).items():
                group = family_frame.loc[family_frame[column].eq(entity)]
                details.append({"role_family": family, "dimension": dimension, "entity": entity, "alert_count": int(count), "alert_share": count / len(family_frame), **metric_summary(group)})
    return pd.DataFrame(summaries), pd.DataFrame(details)


def overlap_results(primary_2023: pd.DataFrame, primary_2022: pd.DataFrame) -> pd.DataFrame:
    rows = []
    key = ["season", "week", "player_id", "team"]
    for period, data in [("untouched_2022", primary_2022), ("untouched_2023", primary_2023), ("pooled_2022_2023", pd.concat([primary_2022, primary_2023], ignore_index=True))]:
        full = data.loc[data["method"].eq("full_propwar")]
        opportunity_keys = set(map(tuple, full.loc[full["role_family"].eq("rb_opportunity_share"), key].itertuples(index=False, name=None)))
        carry = full.loc[full["role_family"].eq("rb_carry_share")].copy()
        carry["overlap_group"] = ["also_opportunity" if values in opportunity_keys else "carry_only" for values in map(tuple, carry[key].itertuples(index=False, name=None))]
        for subgroup, group in carry.groupby("overlap_group"):
            rows.append({"period": period, "role_family": "rb_carry_share", "overlap_group": subgroup, **metric_summary(group)})
    return pd.DataFrame(rows)


def retention_outliers(primary_2023: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for family in RB_FAMILIES:
        group = primary_2023.loc[
            primary_2023["method"].eq("full_propwar") & primary_2023["role_family"].eq(family)
        ].copy()
        values = pd.to_numeric(group.loc[indicator(group["persistent"]).notna(), "retention"], errors="coerce").dropna()
        trimmed = values.sort_values().iloc[int(len(values) * .10): len(values) - int(len(values) * .10)]
        rows.append({
            "role_family": family, "evaluable_retention_values": len(values), "minimum": values.min(),
            "p05": values.quantile(.05), "median": values.median(), "mean": values.mean(),
            "p95": values.quantile(.95), "maximum": values.max(),
            "trimmed_10pct_mean": trimmed.mean(), "clipped_0_1_mean": values.clip(0, 1).mean(),
            "below_zero": int(values.lt(0).sum()), "above_one": int(values.gt(1).sum()),
        })
    return pd.DataFrame(rows)


def equal_volume_audit(alerts_2023: pd.DataFrame) -> pd.DataFrame:
    observed = alerts_2023.groupby(["partial_policy", "role_family", "week", "method"]).size().to_dict()
    rows = []
    for policy in POLICIES:
        for family in ROLE_FAMILIES:
            for week in range(1, 19):
                counts = {method: int(observed.get((policy, family, week, method), 0)) for method in METHODS}
                rows.append({"partial_policy": policy, "role_family": family, "week": week, **{f"{method}_count": counts[method] for method in METHODS}, "equal_volume": len(set(counts.values())) == 1})
    return pd.DataFrame(rows)


def repeat_results(primary_2023: pd.DataFrame) -> pd.DataFrame:
    rows = []
    full = primary_2023.loc[
        primary_2023["method"].eq("full_propwar")
        & primary_2023["role_family"].isin(RB_FAMILIES)
    ].copy()
    for family in RB_FAMILIES:
        group = full.loc[full["role_family"].eq(family)].sort_values(["player_id", "week"])
        prior = group.groupby("player_id")["week"].shift()
        consecutive = group["week"].eq(prior + 1)
        counts = group["player_id"].value_counts()
        rows.append({
            "role_family": family,
            "alerts": len(group),
            "unique_players": group["player_id"].nunique(),
            "players_with_multiple_alerts": int(counts.gt(1).sum()),
            "alerts_from_multiple_alert_players": int(counts.loc[counts.gt(1)].sum()),
            "maximum_alerts_one_player": int(counts.max()),
            "consecutive_repeat_alerts": int(consecutive.sum()),
            "consecutive_repeat_rate": float(consecutive.mean()),
        })
    return pd.DataFrame(rows)


def gate_margin_diagnostics(comparisons_2023: pd.DataFrame) -> pd.DataFrame:
    carry = comparisons_2023.loc[comparisons_2023["role_family"].eq("rb_carry_share")].iloc[0]
    precision_fail_flips = 0
    while (carry.full_persistent_alerts - precision_fail_flips) / carry.full_evaluable_alerts >= 0.60:
        precision_fail_flips += 1
    improvement_fail_flips = 0
    while ((carry.full_persistent_alerts - improvement_fail_flips) / carry.full_evaluable_alerts - carry.naive_precision) >= 0.10:
        improvement_fail_flips += 1
    reversion_fail_additions = 0
    while ((carry.full_immediate_reversions + reversion_fail_additions) / carry.full_reversion_evaluable_alerts) <= 0.25:
        reversion_fail_additions += 1
    return pd.DataFrame([
        {"role_family": "rb_carry_share", "stress": "persistent_outcomes_flipped_to_fail_precision", "minimum_changes_to_fail": precision_fail_flips},
        {"role_family": "rb_carry_share", "stress": "persistent_outcomes_flipped_to_fail_naive_lift", "minimum_changes_to_fail": improvement_fail_flips},
        {"role_family": "rb_carry_share", "stress": "additional_immediate_reversions_to_fail", "minimum_changes_to_fail": reversion_fail_additions},
        {"role_family": "rb_carry_share", "stress": "alerts_removed_to_fail_volume", "minimum_changes_to_fail": int(carry.full_alerts - 49)},
    ])


def fairness_results(primary_2023: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (family, method), group in primary_2023.loc[primary_2023["role_family"].isin(RB_FAMILIES)].groupby(["role_family", "method"]):
        rows.append({
            "role_family": family, "method": method, "alerts": len(group),
            "unique_players": group["player_id"].nunique(),
            "data_quality_pass_rate": indicator(group["data_quality_pass"]).mean(),
            "qualifying_game_rate": indicator(group["qualifying_game"]).mean(),
            "identity_resolved_rate": indicator(group["identity_resolved"]).mean(),
            "feature_eligible_rate": indicator(group["feature_eligible"]).mean(),
            "minimum_baseline_n": pd.to_numeric(group["baseline_n"], errors="coerce").min(),
            "confirmation_window_match_rate": (pd.to_numeric(group["confirmation_n"], errors="coerce") == pd.to_numeric(group["confirmation_games"], errors="coerce")).mean(),
            "outcome_evaluable_rate": indicator(group["persistent"]).notna().mean(),
        })
    return pd.DataFrame(rows)


def full_alert_rule_compliance(alerts_2023: pd.DataFrame, candidate: dict) -> pd.DataFrame:
    rows = []
    full = alerts_2023.loc[alerts_2023["method"].eq("full_propwar")].copy()
    for (policy, family), group in full.groupby(["partial_policy", "role_family"], sort=True):
        violations = {
            "quality": ~indicator(group["data_quality_pass"]).fillna(0).astype(bool),
            "qualifying": ~indicator(group["qualifying_game"]).fillna(0).astype(bool),
            "identity": ~indicator(group["identity_resolved"]).fillna(0).astype(bool),
            "baseline_minimum": pd.to_numeric(group["baseline_n"], errors="coerce").lt(int(candidate["baseline"]["min_games"])),
            "confirmation_complete": pd.to_numeric(group["confirmation_n"], errors="coerce").ne(pd.to_numeric(group["confirmation_games"], errors="coerce")),
            "strict_confirmation": ~indicator(group["strict_confirmation_pass"]).fillna(0).astype(bool),
        }
        threshold_violation = pd.Series(False, index=group.index)
        opportunity_violation = pd.Series(False, index=group.index)
        denominator_violation = pd.Series(False, index=group.index)
        for direction in ["increase", "decrease"]:
            selected = group["direction"].eq(direction)
            rule = candidate["thresholds"][family][direction]
            threshold_violation |= selected & pd.to_numeric(group["detected_delta"], errors="coerce").abs().lt(float(rule["min_abs_delta"]))
            reference = rule["player_opportunity_reference"]
            reference_column = {
                "confirmation_min": "confirmation_min_player_opportunities",
                "confirmation_mean": "confirmation_mean_player_opportunities",
                "baseline_mean": "baseline_mean_player_opportunities",
            }[reference]
            opportunity_violation |= selected & pd.to_numeric(group[reference_column], errors="coerce").lt(float(rule["min_player_opportunities"]))
            denominator_violation |= selected & pd.to_numeric(group["confirmation_min_team_denominator"], errors="coerce").lt(float(rule["min_team_denominator"]))
        violations.update({"absolute_delta": threshold_violation, "player_opportunity": opportunity_violation, "team_denominator": denominator_violation})
        rows.append({
            "partial_policy": policy, "role_family": family, "alerts": len(group),
            **{f"{name}_violations": int(mask.sum()) for name, mask in violations.items()},
            "all_rules_satisfied": not any(bool(mask.any()) for mask in violations.values()),
        })
    return pd.DataFrame(rows)


def comparator_selection_replay(alerts_2023: pd.DataFrame, canonical: pd.DataFrame, candidate: dict) -> pd.DataFrame:
    # Secondary implementation-path check: rebuild comparator eligibility and ranking,
    # but do not run the full detector or attach outcomes.
    from role_validation.redevelopment import _comparator_features

    rows = []
    feature_cache: dict = {}
    key = ["season", "week", "player_id", "team", "role_family"]
    for policy in POLICIES:
        policy_alerts = alerts_2023.loc[alerts_2023["partial_policy"].eq(policy)]
        full_counts = policy_alerts.loc[policy_alerts["method"].eq("full_propwar")].groupby(["role_family", "week"]).size().to_dict()
        for family in ROLE_FAMILIES:
            family_data = canonical.loc[canonical["role_family"].eq(family)].copy()
            for method in ["naive_spike", "two_week_raw", "normal_game_trend"]:
                featured = _comparator_features(family_data, candidate, method, policy, feature_cache=feature_cache)
                candidates = featured.loc[indicator(featured["method_eligible"]).fillna(0).astype(bool)].copy()
                candidates["_abs_score"] = pd.to_numeric(candidates["method_score"], errors="coerce").abs()
                candidates = candidates.sort_values(["season", "week", "_abs_score", "player_id", "team"], ascending=[True, True, False, True, True])
                selected_archive = policy_alerts.loc[policy_alerts["role_family"].eq(family) & policy_alerts["method"].eq(method)]
                for week in range(1, 19):
                    target = int(full_counts.get((family, week), 0))
                    pool = candidates.loc[candidates["week"].eq(week)]
                    expected = set(map(tuple, pool.head(target)[key].itertuples(index=False, name=None)))
                    observed = set(map(tuple, selected_archive.loc[selected_archive["week"].eq(week), key].itertuples(index=False, name=None)))
                    rows.append({
                        "partial_policy": policy, "role_family": family, "method": method, "week": week,
                        "target_alerts": target, "eligible_pool_rows": len(pool),
                        "pool_sufficient": len(pool) >= target,
                        "selected_rows": len(observed), "selection_matches_deterministic_top_n": expected == observed,
                    })
    return pd.DataFrame(rows)


def temporal_audit(alerts_2023: pd.DataFrame, canonical: pd.DataFrame) -> pd.DataFrame:
    checks = {
        "alert_archive_2023_only": set(alerts_2023["season"].astype(int).unique()) == {2023},
        "canonical_archive_2023_only": set(canonical["season"].astype(int).unique()) == {2023},
        "baseline_precedes_confirmation": bool((pd.to_numeric(alerts_2023["baseline_max_week"], errors="coerce") < pd.to_numeric(alerts_2023["confirmation_start_week"], errors="coerce")).all()),
        "confirmation_ends_on_alert_week": bool((pd.to_numeric(alerts_2023["confirmation_end_week"], errors="coerce") == pd.to_numeric(alerts_2023["week"], errors="coerce")).all()),
        "first_outcome_after_alert": bool((pd.to_numeric(alerts_2023.loc[alerts_2023["future_week_1"].notna(), "future_week_1"]) > pd.to_numeric(alerts_2023.loc[alerts_2023["future_week_1"].notna(), "week"])).all()),
        "second_outcome_after_first": bool((pd.to_numeric(alerts_2023.loc[alerts_2023["future_week_2"].notna(), "future_week_2"]) > pd.to_numeric(alerts_2023.loc[alerts_2023["future_week_2"].notna(), "future_week_1"])).all()),
        "primary_contains_no_confirmed_partial": not indicator(alerts_2023.loc[alerts_2023["partial_policy"].eq(PRIMARY), "confirmed_partial_game"]).fillna(0).astype(bool).any(),
        "primary_retains_suspected_rows": bool(indicator(alerts_2023.loc[alerts_2023["partial_policy"].eq(PRIMARY), "suspected_partial_game"]).fillna(0).astype(bool).any()),
    }
    confirmed = canonical.loc[indicator(canonical["confirmed_partial_game"]).fillna(0).astype(bool)].copy()
    evidence = pd.to_datetime(confirmed["evidence_available_at_utc"], errors="coerce", utc=True)
    trigger = pd.to_datetime(confirmed["trigger_kickoff_utc"], errors="coerce", utc=True)
    next_game = pd.to_datetime(confirmed["next_game_kickoff_utc"], errors="coerce", utc=True)
    checks["confirmed_evidence_after_trigger"] = bool((evidence > trigger).all())
    checks["confirmed_evidence_before_next_game"] = bool((evidence < next_game).all())
    return pd.DataFrame([{"check": name, "passed": bool(passed)} for name, passed in checks.items()])


def reconstruct_primary_outcomes(primary_2023: pd.DataFrame, canonical: pd.DataFrame) -> pd.DataFrame:
    weekly = canonical.sort_values(["player_id", "role_family", "season", "week"]).copy()
    metric = pd.to_numeric(weekly["metric_normal"], errors="coerce")
    eligible = (
        indicator(weekly["qualifying_game"]).fillna(0).astype(bool)
        & ~indicator(weekly["confirmed_partial_game"]).fillna(0).astype(bool)
        & indicator(weekly["data_quality_pass"]).fillna(0).astype(bool)
        & metric.notna()
    )
    eligible_weekly = weekly.loc[eligible].copy()
    eligible_weekly["_metric"] = pd.to_numeric(eligible_weekly["metric_normal"], errors="coerce")
    keys = ["player_id", "role_family", "season"]
    grouped_metric = eligible_weekly.groupby(keys, sort=False)["_metric"]
    grouped_week = eligible_weekly.groupby(keys, sort=False)["week"]
    eligible_weekly["audit_future_1"] = grouped_metric.shift(-1)
    eligible_weekly["audit_future_2"] = grouped_metric.shift(-2)
    eligible_weekly["audit_future_week_1"] = grouped_week.shift(-1)
    eligible_weekly["audit_future_week_2"] = grouped_week.shift(-2)
    eligible_weekly["audit_future_n"] = eligible_weekly[["audit_future_1", "audit_future_2"]].notna().sum(axis=1)
    eligible_weekly["audit_future_mean"] = eligible_weekly[["audit_future_1", "audit_future_2"]].mean(axis=1)
    lookup_keys = ["season", "week", "player_id", "team", "role_family"]
    lookup = eligible_weekly[
        lookup_keys + ["audit_future_1", "audit_future_2", "audit_future_week_1", "audit_future_week_2", "audit_future_n", "audit_future_mean"]
    ].drop_duplicates(lookup_keys)
    work = primary_2023.merge(lookup, on=lookup_keys, how="left", validate="many_to_one")
    work["audit_future_n"] = work["audit_future_n"].fillna(0).astype(int)
    baseline = pd.to_numeric(work["baseline_value"], errors="coerce")
    detected = pd.to_numeric(work["detected_value"], errors="coerce")
    delta = detected - baseline
    direction = np.sign(delta)
    denominator = delta.abs().replace(0, np.nan)
    work["audit_next_game_retention"] = (work["audit_future_1"] - baseline) * direction / denominator
    work["audit_retention"] = (work["audit_future_mean"] - baseline) * direction / denominator
    persistence_evaluable = work["audit_retention"].notna() & work["audit_future_n"].ge(2)
    work["audit_persistent"] = np.nan
    work.loc[persistence_evaluable, "audit_persistent"] = work.loc[persistence_evaluable, "audit_retention"].ge(.50).astype(float)
    reversion_evaluable = work["audit_next_game_retention"].notna()
    work["audit_immediate_reversion"] = np.nan
    work.loc[reversion_evaluable, "audit_immediate_reversion"] = work.loc[reversion_evaluable, "audit_next_game_retention"].lt(.25).astype(float)

    comparisons = [
        ("future_n", pd.to_numeric(work["future_n"], errors="coerce"), work["audit_future_n"]),
        ("next_game_value", pd.to_numeric(work["next_game_value"], errors="coerce"), work["audit_future_1"]),
        ("future_week_1", pd.to_numeric(work["future_week_1"], errors="coerce"), work["audit_future_week_1"]),
        ("future_week_2", pd.to_numeric(work["future_week_2"], errors="coerce"), work["audit_future_week_2"]),
        ("future_mean", pd.to_numeric(work["future_mean"], errors="coerce"), work["audit_future_mean"]),
        ("next_game_retention", pd.to_numeric(work["next_game_retention"], errors="coerce"), work["audit_next_game_retention"]),
        ("retention", pd.to_numeric(work["retention"], errors="coerce"), work["audit_retention"]),
        ("persistent", indicator(work["persistent"]), work["audit_persistent"]),
        ("immediate_reversion", indicator(work["immediate_reversion"]), work["audit_immediate_reversion"]),
    ]
    rows = []
    for field, committed, audit in comparisons:
        both_missing = committed.isna() & audit.isna()
        numeric_match = np.isclose(committed.fillna(0), audit.fillna(0), equal_nan=True, rtol=1e-10, atol=1e-12)
        match = both_missing | (~committed.isna() & ~audit.isna() & numeric_match)
        differences = (committed - audit).abs()
        rows.append({
            "field": field,
            "rows_compared": len(work),
            "mismatch_rows": int((~match).sum()),
            "maximum_absolute_difference": float(differences.max()) if differences.notna().any() else 0.0,
            "matched": bool(match.all()),
        })
    return pd.DataFrame(rows)


def gate_results(comparisons_2023: pd.DataFrame, cross_direction: pd.DataFrame, validation_config: dict, frozen: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    gates = validation_config["release_gates"]["full_release"]
    rows = []
    decisions = []
    for family in RB_FAMILIES:
        result = comparisons_2023.loc[comparisons_2023["role_family"].eq(family)].iloc[0]
        direction_cells = cross_direction.loc[cross_direction["role_family"].eq(family)]
        direction_consistent = bool(direction_cells["precision_improvement"].ge(0).all())
        values = [
            ("min_holdout_alerts", result.full_alerts, f">= {gates['min_holdout_alerts']}", result.full_alerts >= gates["min_holdout_alerts"]),
            ("min_persistence_precision", result.full_precision, f">= {gates['min_persistence_precision']}", result.full_precision >= gates["min_persistence_precision"]),
            ("min_absolute_improvement_vs_naive", result.precision_improvement, f">= {gates['min_absolute_improvement_vs_naive']}", result.precision_improvement >= gates["min_absolute_improvement_vs_naive"]),
            ("max_immediate_reversion_rate", result.full_reversion_rate, f"<= {gates['max_immediate_reversion_rate']}", result.full_reversion_rate <= gates["max_immediate_reversion_rate"]),
            ("min_reversion_improvement_vs_naive", result.reversion_improvement, f">= {gates['min_reversion_improvement_vs_naive']}", result.reversion_improvement >= gates["min_reversion_improvement_vs_naive"]),
            ("min_median_retention", result.full_median_retention, f">= {gates['min_median_retention']}", result.full_median_retention >= gates["min_median_retention"]),
            ("min_alerts_per_week", result.full_alerts / 18, f">= {gates['min_alerts_per_week']}", result.full_alerts / 18 >= gates["min_alerts_per_week"]),
            ("direction_consistent_across_periods", direction_consistent, "all available period-direction lifts >= 0", direction_consistent),
            ("frozen_before_holdout", frozen, "required", frozen),
        ]
        for name, observed, threshold, passed in values:
            rows.append({"role_family": family, "gate": name, "observed": observed, "threshold": threshold, "passed": bool(passed)})
        decisions.append({"role_family": family, "all_gates_pass": all(bool(value[3]) for value in values), "failed_gates": " | ".join(value[0] for value in values if not value[3])})
    return pd.DataFrame(rows), pd.DataFrame(decisions)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", AUDITED_COMMIT, "HEAD"], cwd=ROOT, check=True)

    fold3_alerts = pd.read_csv(FOLD3 / "fold3_alerts_2023.csv.gz", low_memory=False)
    fold2_alerts = pd.read_csv(ROOT / "outputs" / "role_validation" / "fold_2" / "fold2_alerts_2022.csv.gz", low_memory=False)
    fold1_alerts = pd.read_csv(ROOT / "outputs" / "role_validation" / "fold_1_diagnostics" / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz", low_memory=False)
    canonical = pd.read_csv(FOLD3 / "canonical_role_2023_enriched.csv.gz", low_memory=False)
    primary_2023 = fold3_alerts.loc[fold3_alerts["partial_policy"].eq(PRIMARY)].copy()
    primary_2022 = fold2_alerts.loc[fold2_alerts["partial_policy"].eq(PRIMARY)].copy()
    primary_2021 = fold1_alerts.loc[fold1_alerts["partial_policy"].eq(PRIMARY) & fold1_alerts["season"].eq(2021)].copy()
    pooled = pd.concat([primary_2022, primary_2023], ignore_index=True)

    headline = family_method_results(primary_2023, "untouched_2023")
    comparisons = family_comparisons(primary_2023, "untouched_2023")
    cross_comparisons = pd.concat([
        family_comparisons(primary_2021, "redeveloped_2021"),
        family_comparisons(primary_2022, "untouched_2022"),
        comparisons,
    ], ignore_index=True)
    directions = directional_results(primary_2023, "untouched_2023")
    cross_directions = pd.concat([
        directional_results(primary_2021, "redeveloped_2021"),
        directional_results(primary_2022, "untouched_2022"),
        directions,
    ], ignore_index=True)
    pooled_comparisons = family_comparisons(pooled, "pooled_untouched_2022_2023")
    pooled_directions = directional_results(pooled, "pooled_untouched_2022_2023")
    weekly = weekly_results(primary_2023)
    subgroups = subgroup_results(primary_2023)
    concentration, concentration_details = concentration_results(primary_2023)
    overlap = overlap_results(primary_2023, primary_2022)
    retention = retention_outliers(primary_2023)
    repeats = repeat_results(primary_2023)
    partial_sensitivity = pd.concat(
        [family_comparisons(fold3_alerts.loc[fold3_alerts["partial_policy"].eq(policy)], policy) for policy in POLICIES],
        ignore_index=True,
    )
    gate_margins = gate_margin_diagnostics(comparisons)
    equal_volume = equal_volume_audit(fold3_alerts)
    fairness = fairness_results(primary_2023)
    temporal = temporal_audit(fold3_alerts, canonical)
    outcome_reconstruction = reconstruct_primary_outcomes(primary_2023, canonical)

    config_path = ROOT / "config" / "role_change_fold2_candidate.yaml"
    frozen_path = FOLD3 / "frozen_role_change_fold3_candidate.yaml"
    validation_path = ROOT / "config" / "role_change_validation.yaml"
    config_hashes_match = sha256(config_path) == sha256(frozen_path) == CONFIG_SHA
    tag_commit = subprocess.check_output(["git", "rev-list", "-n", "1", "role-change-validation-v1-pre-fold3-checkpoint"], cwd=ROOT, text=True).strip()
    frozen = bool(config_hashes_match and tag_commit == START_COMMIT)
    validation_config = yaml.safe_load(validation_path.read_text(encoding="utf-8"))
    candidate_document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    candidate = candidate_document["candidate"]
    rule_compliance = full_alert_rule_compliance(fold3_alerts, candidate)
    comparator_replay = comparator_selection_replay(fold3_alerts, canonical, candidate)
    gates, decisions = gate_results(comparisons, cross_directions, validation_config, frozen)

    duplicate_key = ["partial_policy", "role_family", "method", "season", "week", "player_id", "team"]
    source_manifest = pd.read_csv(FOLD3 / "input_source_manifest.csv")
    source_hash_results = []
    for row in source_manifest.itertuples(index=False):
        path = Path(row.path)
        source_hash_results.append({"source": row.source, "path": row.path, "expected_sha256": row.sha256, "observed_sha256": sha256(path), "matched": sha256(path) == row.sha256})
    source_hashes = pd.DataFrame(source_hash_results)

    committed_headline = pd.read_csv(FOLD3 / "rb_family_method_results_2023.csv")
    committed_primary = committed_headline.loc[committed_headline["partial_policy"].eq(PRIMARY)]
    reconcile = headline.merge(committed_primary, on=["role_family", "method"], suffixes=("_audit", "_committed"))
    reconciliation_rows = []
    for metric in ["alerts", "evaluable_alerts", "precision", "precision_ci_low", "precision_ci_high", "reversion_rate", "median_retention"]:
        left = pd.to_numeric(reconcile[f"{metric}_audit"], errors="coerce")
        right = pd.to_numeric(reconcile[f"{metric}_committed"], errors="coerce")
        reconciliation_rows.append({"metric": metric, "rows_compared": len(reconcile), "maximum_absolute_difference": float((left - right).abs().max()), "matched": bool(np.allclose(left, right, equal_nan=True, rtol=1e-10, atol=1e-12))})
    reconciliation = pd.DataFrame(reconciliation_rows)

    outputs = {
        "headline_recomputed_2023.csv": headline,
        "family_comparisons_recomputed_2023.csv": comparisons,
        "cross_season_recomputed_2021_2023.csv": cross_comparisons,
        "direction_recomputed_2023.csv": directions,
        "cross_season_direction_recomputed_2021_2023.csv": cross_directions,
        "pooled_recomputed_2022_2023.csv": pooled_comparisons,
        "pooled_direction_recomputed_2022_2023.csv": pooled_directions,
        "weekly_recomputed_2023.csv": weekly,
        "subgroup_metrics_2023.csv": subgroups,
        "concentration_summary_2023.csv": concentration,
        "concentration_top_entities_2023.csv": concentration_details,
        "carry_opportunity_overlap_dependence.csv": overlap,
        "retention_outlier_diagnostics_2023.csv": retention,
        "repeat_dependence_2023.csv": repeats,
        "partial_policy_sensitivity_recomputed_2023.csv": partial_sensitivity,
        "gate_margin_diagnostics_2023.csv": gate_margins,
        "equal_volume_independent_check.csv": equal_volume,
        "comparator_fairness_selected_rows.csv": fairness,
        "full_alert_rule_compliance.csv": rule_compliance,
        "comparator_selection_replay.csv": comparator_replay,
        "temporal_integrity_independent_check.csv": temporal,
        "outcome_label_reconstruction.csv": outcome_reconstruction,
        "gate_by_gate_independent_check.csv": gates,
        "family_decisions_independent_check.csv": decisions,
        "input_hash_reconciliation.csv": source_hashes,
        "committed_summary_reconciliation.csv": reconciliation,
    }
    for name, frame in outputs.items():
        frame.to_csv(OUT / name, index=False)

    manifest = {
        "audited_commit": AUDITED_COMMIT,
        "audit_passed": bool(
            equal_volume["equal_volume"].all()
            and temporal["passed"].all()
            and outcome_reconstruction["matched"].all()
            and source_hashes["matched"].all()
            and reconciliation["matched"].all()
            and rule_compliance["all_rules_satisfied"].all()
            and comparator_replay["pool_sufficient"].all()
            and comparator_replay["selection_matches_deterministic_top_n"].all()
            and decisions.set_index("role_family").at["rb_carry_share", "all_gates_pass"]
            and not decisions.set_index("role_family").at["rb_opportunity_share", "all_gates_pass"]
        ),
        "alert_archive_sha256": sha256(FOLD3 / "fold3_alerts_2023.csv.gz"),
        "config_sha256": sha256(config_path),
        "equal_volume_cells": len(equal_volume),
        "unequal_volume_cells": int((~equal_volume["equal_volume"]).sum()),
        "duplicate_alert_keys": int(fold3_alerts.duplicated(duplicate_key, keep=False).sum()),
        "temporal_checks_passed": int(temporal["passed"].sum()),
        "temporal_checks_total": len(temporal),
        "outcome_fields_reconstructed": len(outcome_reconstruction),
        "outcome_reconstruction_passed": bool(outcome_reconstruction["matched"].all()),
        "source_hashes_matched": bool(source_hashes["matched"].all()),
        "full_alert_rule_compliance_passed": bool(rule_compliance["all_rules_satisfied"].all()),
        "comparator_replay_cells": len(comparator_replay),
        "comparator_replay_passed": bool(comparator_replay["selection_matches_deterministic_top_n"].all()),
        "post_2023_values_used_in_scoring": False,
        "multi_season_cache_files_scanned_before_row_filtering": True,
        "manifest_post_2023_read_flag_literally_accurate": False,
        "fold4_executed": False,
        "recommendations": {
            "rb_carry_share": "ADVANCE_UNCHANGED_TO_FOLD_4",
            "rb_opportunity_share": "CONTINUE_UNCHANGED_SHADOW_FOLD_4",
            "wr_target_share": "REMAIN_RETIRED",
            "te_target_share": "REMAIN_RETIRED",
        },
    }
    (OUT / "audit_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
