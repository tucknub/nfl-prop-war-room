from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from role_validation.redevelopment import EXPECTED_METHODS, FEED_KEY, ROLE_FAMILIES


def _boolean_numeric(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.astype("Float64")
    normalized = values.astype(str).str.strip().str.lower()
    result = pd.Series(np.nan, index=values.index, dtype=float)
    result.loc[normalized.isin({"true", "1", "yes", "y"})] = 1.0
    result.loc[normalized.isin({"false", "0", "no", "n"})] = 0.0
    result.loc[values.isna()] = np.nan
    return result


def summarize_metrics(
    frame: pd.DataFrame,
    group_columns: Iterable[str],
) -> pd.DataFrame:
    """Summarize volume, precision, reversion, and retention with explicit bases."""
    columns = list(group_columns)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                *columns,
                "alerts",
                "evaluable_alerts",
                "evaluable_rate",
                "persistent_alerts",
                "precision",
                "reversion_evaluable_alerts",
                "immediate_reversions",
                "reversion_rate",
                "median_retention",
                "mean_retention",
                "unique_players",
                "active_weeks",
            ]
        )
    work = frame.copy()
    work["_persistent_numeric"] = _boolean_numeric(work["persistent"])
    work["_reversion_numeric"] = _boolean_numeric(work["immediate_reversion"])
    work["_retention_numeric"] = pd.to_numeric(work["retention"], errors="coerce")
    grouper: Any = columns[0] if len(columns) == 1 else columns
    rows: list[dict[str, Any]] = []
    for key, group in work.groupby(grouper, dropna=False, sort=True):
        key_values = (key,) if len(columns) == 1 else tuple(key)
        persistent = group["_persistent_numeric"].dropna()
        reversion = group["_reversion_numeric"].dropna()
        retention = group.loc[group["_persistent_numeric"].notna(), "_retention_numeric"].dropna()
        row = {column: value for column, value in zip(columns, key_values)}
        row.update(
            {
                "alerts": int(len(group)),
                "evaluable_alerts": int(len(persistent)),
                "evaluable_rate": float(len(persistent) / len(group)) if len(group) else np.nan,
                "persistent_alerts": int(persistent.sum()) if len(persistent) else 0,
                "precision": float(persistent.mean()) if len(persistent) else np.nan,
                "reversion_evaluable_alerts": int(len(reversion)),
                "immediate_reversions": int(reversion.sum()) if len(reversion) else 0,
                "reversion_rate": float(reversion.mean()) if len(reversion) else np.nan,
                "median_retention": float(retention.median()) if len(retention) else np.nan,
                "mean_retention": float(retention.mean()) if len(retention) else np.nan,
                "unique_players": int(group["player_id"].nunique()) if "player_id" in group else np.nan,
                "active_weeks": int(
                    group[["season", "week"]].drop_duplicates().shape[0]
                    if {"season", "week"}.issubset(group.columns)
                    else 0
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def add_diagnostic_dimensions(alerts: pd.DataFrame) -> pd.DataFrame:
    result = alerts.copy()
    if "direction" not in result:
        result["direction"] = np.select(
            [
                pd.to_numeric(result["detected_delta"], errors="coerce").gt(0),
                pd.to_numeric(result["detected_delta"], errors="coerce").lt(0),
            ],
            ["increase", "decrease"],
            default="flat",
        )
    baseline_column = (
        "normal_baseline_n" if "normal_baseline_n" in result else "baseline_n"
    )
    result["baseline_sample_size"] = pd.to_numeric(
        result[baseline_column], errors="coerce"
    ).astype("Int64")
    result["baseline_sample_bin"] = pd.cut(
        pd.to_numeric(result[baseline_column], errors="coerce"),
        bins=[-np.inf, 2, 3, 4, np.inf],
        labels=["0-2", "3", "4", "5+"],
        right=True,
    ).astype(str)
    result["raw_player_opportunities"] = pd.to_numeric(
        result["raw_opportunities_normal"], errors="coerce"
    )
    result["raw_player_opportunities_bin"] = pd.cut(
        result["raw_player_opportunities"],
        bins=[-np.inf, 2, 5, 9, 14, np.inf],
        labels=["0-2", "3-5", "6-9", "10-14", "15+"],
        right=True,
    ).astype(str)
    result["team_opportunity_denominator"] = pd.to_numeric(
        result["team_opportunities_normal"], errors="coerce"
    )
    result["team_opportunity_denominator_bin"] = pd.cut(
        result["team_opportunity_denominator"],
        bins=[-np.inf, 15, 20, 25, 30, 35, np.inf],
        labels=["0-15", "16-20", "21-25", "26-30", "31-35", "36+"],
        right=True,
    ).astype(str)
    result["absolute_detected_change"] = pd.to_numeric(
        result["detected_delta"], errors="coerce"
    ).abs()
    result["absolute_detected_change_bin"] = pd.cut(
        result["absolute_detected_change"],
        bins=[-np.inf, 0.099999999, 0.149999999, 0.199999999, 0.249999999, np.inf],
        labels=["<0.10", "0.10-0.149", "0.15-0.199", "0.20-0.249", "0.25+"],
        right=True,
    ).astype(str)
    confirmed = (
        result.get("confirmed_partial_game", False)
        if "confirmed_partial_game" in result
        else pd.Series(False, index=result.index)
    )
    suspected = (
        result.get("suspected_partial_game", False)
        if "suspected_partial_game" in result
        else pd.Series(False, index=result.index)
    )
    confirmed = pd.Series(confirmed, index=result.index).fillna(False).astype(bool)
    suspected = pd.Series(suspected, index=result.index).fillna(False).astype(bool)
    corroborated = (
        result.get("suspected_partial_corroborated", False)
        if "suspected_partial_corroborated" in result
        else pd.Series(False, index=result.index)
    )
    corroborated = pd.Series(corroborated, index=result.index).fillna(False).astype(bool)
    result["partial_game_status"] = np.select(
        [confirmed, suspected & corroborated, suspected],
        ["confirmed", "suspected_corroborated", "suspected_statistical"],
        default="none",
    )
    result["week_of_season"] = pd.to_numeric(result["week"], errors="coerce").astype("Int64")
    result["week_block"] = pd.cut(
        pd.to_numeric(result["week"], errors="coerce"),
        bins=[0, 6, 12, 18],
        labels=["weeks_1_6", "weeks_7_12", "weeks_13_18"],
        include_lowest=True,
    ).astype(str)
    return result


def build_requested_breakdowns(alerts: pd.DataFrame) -> pd.DataFrame:
    """Return all requested original/revised diagnostic cuts in long form."""
    work = add_diagnostic_dimensions(alerts)
    dimensions = {
        "role_family": "role_family",
        "direction": "direction",
        "week_of_season": "week_of_season",
        "baseline_sample_size": "baseline_sample_size",
        "baseline_sample_bin": "baseline_sample_bin",
        "raw_player_opportunities": "raw_player_opportunities_bin",
        "team_opportunity_denominator": "team_opportunity_denominator_bin",
        "absolute_detected_change": "absolute_detected_change_bin",
        "partial_game_status": "partial_game_status",
    }
    fixed_groups = [
        column
        for column in ["candidate_name", "partial_policy", "period", "method"]
        if column in work.columns
    ]
    outputs: list[pd.DataFrame] = []
    for dimension_name, column in dimensions.items():
        summary = summarize_metrics(work, [*fixed_groups, column])
        summary = summary.rename(columns={column: "segment"})
        summary.insert(len(fixed_groups), "dimension", dimension_name)
        outputs.append(summary)
    return pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()


def add_feed_flags(full_alerts: pd.DataFrame) -> pd.DataFrame:
    """Tag duplicate-family and literal consecutive-calendar-week alerts."""
    result = add_diagnostic_dimensions(full_alerts)
    family_count = result.groupby(FEED_KEY)["role_family"].transform("nunique")
    result["duplicate_family_alert"] = family_count.gt(1)
    rb_families = {"rb_carry_share", "rb_opportunity_share"}
    result["duplicate_rb_family_alert"] = (
        result["duplicate_family_alert"] & result["role_family"].isin(rb_families)
    )
    family_order = result.sort_values(
        ["season", "player_id", "role_family", "week", "team"]
    )
    prior_family_week = family_order.groupby(
        ["season", "player_id", "role_family"], sort=False
    )["week"].shift()
    family_order["consecutive_family_repeat"] = family_order["week"].eq(
        prior_family_week + 1
    )
    result["consecutive_family_repeat"] = family_order[
        "consecutive_family_repeat"
    ].reindex(result.index).fillna(False).astype(bool)
    return result


def deduplicated_feed(full_alerts: pd.DataFrame) -> pd.DataFrame:
    work = add_diagnostic_dimensions(full_alerts)
    rows: list[dict[str, Any]] = []
    for key, group in work.groupby(FEED_KEY, sort=True, dropna=False):
        directions = sorted(group["direction"].dropna().astype(str).unique())
        rows.append(
            {
                **{column: value for column, value in zip(FEED_KEY, key)},
                "player_name": " | ".join(sorted(group["player_name"].dropna().astype(str).unique())),
                "position": " | ".join(sorted(group["position"].dropna().astype(str).unique())),
                "role_families": " | ".join(sorted(group["role_family"].astype(str).unique())),
                "family_alert_rows": int(len(group)),
                "family_count": int(group["role_family"].nunique()),
                "directions": " | ".join(directions),
                "direction_conflict": len(directions) > 1,
                "duplicate_family_alert": group["role_family"].nunique() > 1,
            }
        )
    feed = pd.DataFrame(rows)
    if feed.empty:
        return feed
    ordered = feed.sort_values(["season", "player_id", "week", "team"]).copy()
    prior_week = ordered.groupby(["season", "player_id"], sort=False)["week"].shift()
    ordered["consecutive_player_repeat"] = ordered["week"].eq(prior_week + 1)
    return ordered.reset_index(drop=True)


def feed_volume_table(
    full_alerts: pd.DataFrame,
    season_weeks: pd.DataFrame,
) -> pd.DataFrame:
    family = (
        full_alerts.groupby(["season", "week"]).size().rename("family_alert_rows")
        if not full_alerts.empty
        else pd.Series(dtype=int, name="family_alert_rows")
    )
    feed = deduplicated_feed(full_alerts)
    dedup = (
        feed.groupby(["season", "week"]).size().rename("deduplicated_feed_alerts")
        if not feed.empty
        else pd.Series(dtype=int, name="deduplicated_feed_alerts")
    )
    result = season_weeks[["season", "week"]].drop_duplicates().copy()
    result = result.merge(family.reset_index(), on=["season", "week"], how="left")
    result = result.merge(dedup.reset_index(), on=["season", "week"], how="left")
    result[["family_alert_rows", "deduplicated_feed_alerts"]] = result[
        ["family_alert_rows", "deduplicated_feed_alerts"]
    ].fillna(0).astype(int)
    result["duplicate_family_rows_removed"] = (
        result["family_alert_rows"] - result["deduplicated_feed_alerts"]
    )
    return result.sort_values(["season", "week"]).reset_index(drop=True)


def rb_family_overlap(full_alerts: pd.DataFrame) -> pd.DataFrame:
    work = add_diagnostic_dimensions(full_alerts)
    carry = work.loc[work["role_family"].eq("rb_carry_share")].copy()
    opportunity = work.loc[work["role_family"].eq("rb_opportunity_share")].copy()
    carry_keys = set(map(tuple, carry[FEED_KEY].itertuples(index=False, name=None)))
    opportunity_keys = set(
        map(tuple, opportunity[FEED_KEY].itertuples(index=False, name=None))
    )
    intersection = carry_keys & opportunity_keys
    union = carry_keys | opportunity_keys
    carry_direction = carry.set_index(FEED_KEY)["direction"].to_dict()
    opportunity_direction = opportunity.set_index(FEED_KEY)["direction"].to_dict()
    conflicts = sum(
        carry_direction[key] != opportunity_direction[key] for key in intersection
    )
    return pd.DataFrame(
        [
            {
                "carry_alerts": len(carry_keys),
                "opportunity_alerts": len(opportunity_keys),
                "overlap_alerts": len(intersection),
                "union_alerts": len(union),
                "carry_overlap_rate": len(intersection) / len(carry_keys) if carry_keys else np.nan,
                "opportunity_overlap_rate": (
                    len(intersection) / len(opportunity_keys) if opportunity_keys else np.nan
                ),
                "jaccard_overlap": len(intersection) / len(union) if union else np.nan,
                "direction_conflicts": conflicts,
            }
        ]
    )


def repeat_alert_summary(full_alerts: pd.DataFrame) -> pd.DataFrame:
    family = add_feed_flags(full_alerts)
    feed = deduplicated_feed(full_alerts)
    rows = [
        {
            "grain": "deduplicated_player_week",
            "alerts": len(feed),
            "repeat_alerts": int(feed.get("consecutive_player_repeat", False).sum()),
            "repeat_rate": (
                float(feed["consecutive_player_repeat"].mean()) if len(feed) else np.nan
            ),
            "players_with_repeat": int(
                feed.loc[feed.get("consecutive_player_repeat", False), "player_id"].nunique()
                if len(feed)
                else 0
            ),
        },
        {
            "grain": "family_player_week",
            "alerts": len(family),
            "repeat_alerts": int(family["consecutive_family_repeat"].sum()),
            "repeat_rate": (
                float(family["consecutive_family_repeat"].mean()) if len(family) else np.nan
            ),
            "players_with_repeat": int(
                family.loc[family["consecutive_family_repeat"], "player_id"].nunique()
                if len(family)
                else 0
            ),
        },
    ]
    for role_family, group in family.groupby("role_family"):
        rows.append(
            {
                "grain": f"family:{role_family}",
                "alerts": len(group),
                "repeat_alerts": int(group["consecutive_family_repeat"].sum()),
                "repeat_rate": float(group["consecutive_family_repeat"].mean()),
                "players_with_repeat": int(
                    group.loc[group["consecutive_family_repeat"], "player_id"].nunique()
                ),
            }
        )
    return pd.DataFrame(rows)


def method_comparison_table(alerts: pd.DataFrame) -> pd.DataFrame:
    return summarize_metrics(alerts, ["method", "role_family"])


def comparison_improvements(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metric_columns = {
        "alerts",
        "evaluable_alerts",
        "evaluable_rate",
        "persistent_alerts",
        "precision",
        "precision_ci_low",
        "precision_ci_high",
        "reversion_evaluable_alerts",
        "immediate_reversions",
        "reversion_rate",
        "median_retention",
        "mean_retention",
        "unique_players",
        "active_weeks",
    }
    fixed_columns = [
        column
        for column in summary.columns
        if column != "method" and column not in metric_columns
    ]
    grouper: Any = fixed_columns[0] if len(fixed_columns) == 1 else fixed_columns
    for key, group in summary.groupby(grouper, dropna=False, sort=True):
        key_values = (key,) if len(fixed_columns) == 1 else tuple(key)
        by_method = group.set_index("method")
        if "full_propwar" not in by_method.index or "naive_spike" not in by_method.index:
            continue
        full = by_method.loc["full_propwar"]
        naive = by_method.loc["naive_spike"]
        row = {column: value for column, value in zip(fixed_columns, key_values)}
        row.update(
            {
                "full_alerts": int(full["alerts"]),
                "full_evaluable_alerts": int(full["evaluable_alerts"]),
                "full_precision": full["precision"],
                "naive_precision": naive["precision"],
                "precision_improvement": full["precision"] - naive["precision"],
                "full_reversion_rate": full["reversion_rate"],
                "naive_reversion_rate": naive["reversion_rate"],
                "reversion_improvement": naive["reversion_rate"] - full["reversion_rate"],
                "full_median_retention": full["median_retention"],
                "naive_median_retention": naive["median_retention"],
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


FALSE_POSITIVE_REASON_DEFINITIONS = {
    "CONFIRMED_FOCAL_PARTIAL": "Explicit focal-player partial-game evidence meets the temporal policy.",
    "SUSPECTED_FOCAL_PARTIAL": "Usage/participation pattern suggests a focal-player partial game but is not confirmed.",
    "SUSPECTED_TEAMMATE_EXIT_BENEFICIARY": "Same-position teammate had a suspected/confirmed exit context; alert remains eligible.",
    "LOW_PLAYER_OPPORTUNITY_NOISE": "Player opportunity count is below the diagnostic family floor.",
    "LOW_TEAM_DENOMINATOR_NOISE": "Team denominator is below the diagnostic family floor.",
    "BASELINE_SMALL_OR_UNSTABLE": "Legacy baseline has only three observations or crosses the season boundary.",
    "MARGINAL_CHANGE_NEAR_THRESHOLD": "Absolute change is within two points of the legacy family threshold.",
    "NORMAL_CONTEXT_SENSITIVE": "Raw and normal-game two-week changes differ materially or reverse sign.",
    "ROLE_REVERSION_NO_OBSERVED_DATA_ISSUE": "Outcome failed without an observed data-quality explanation.",
}


def false_positive_case_review(
    full_alerts: pd.DataFrame,
    legacy_thresholds: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assign auditable reason codes to every evaluable false positive.

    The rules create a reproducible evidence worksheet. A reviewer can retain all
    secondary flags while the deterministic precedence supplies one primary code.
    """
    work = add_feed_flags(full_alerts)
    persistent = _boolean_numeric(work["persistent"])
    cases = work.loc[persistent.eq(0)].copy()
    if cases.empty:
        return cases, pd.DataFrame(
            [(code, definition) for code, definition in FALSE_POSITIVE_REASON_DEFINITIONS.items()],
            columns=["reason_code", "definition"],
        )

    player_floors = {
        "rb_carry_share": 6,
        "rb_opportunity_share": 6,
        "wr_target_share": 4,
        "te_target_share": 3,
    }
    team_floors = {
        "rb_carry_share": 18,
        "rb_opportunity_share": 18,
        "wr_target_share": 20,
        "te_target_share": 20,
    }
    cases["flag_confirmed_focal_partial"] = cases["partial_game_status"].eq("confirmed")
    cases["flag_suspected_focal_partial"] = cases["partial_game_status"].str.startswith(
        "suspected"
    )
    cases["flag_suspected_teammate_exit"] = (
        cases.get("suspected_teammate_exit", False)
        if "suspected_teammate_exit" in cases
        else False
    )
    cases["diagnostic_player_floor"] = cases["role_family"].map(player_floors)
    cases["diagnostic_team_floor"] = cases["role_family"].map(team_floors)
    cases["flag_low_player_opportunities"] = cases["raw_player_opportunities"].lt(
        cases["diagnostic_player_floor"]
    )
    cases["flag_low_team_denominator"] = cases["team_opportunity_denominator"].lt(
        cases["diagnostic_team_floor"]
    )
    baseline_n = pd.to_numeric(
        cases.get("normal_baseline_n", cases.get("baseline_n")), errors="coerce"
    )
    cases["flag_cross_season_baseline"] = (cases["week"] - 1).lt(baseline_n)
    cases["flag_baseline_small_or_unstable"] = baseline_n.le(3) | cases[
        "flag_cross_season_baseline"
    ]
    cases["legacy_family_threshold"] = cases["role_family"].map(legacy_thresholds)
    cases["flag_marginal_change"] = cases["absolute_detected_change"].le(
        cases["legacy_family_threshold"] + 0.02 + 1e-12
    )
    raw_change = pd.to_numeric(cases.get("raw_two_week_score"), errors="coerce")
    normal_change = pd.to_numeric(cases.get("normal_two_week_score"), errors="coerce")
    cases["flag_normal_context_sensitive"] = (
        (np.sign(raw_change) != np.sign(normal_change))
        | (raw_change - normal_change).abs().ge(0.05)
    )
    cases["flag_immediate_reversion"] = _boolean_numeric(
        cases["immediate_reversion"]
    ).eq(1)

    precedence = [
        ("CONFIRMED_FOCAL_PARTIAL", "flag_confirmed_focal_partial"),
        ("SUSPECTED_FOCAL_PARTIAL", "flag_suspected_focal_partial"),
        ("SUSPECTED_TEAMMATE_EXIT_BENEFICIARY", "flag_suspected_teammate_exit"),
        ("LOW_PLAYER_OPPORTUNITY_NOISE", "flag_low_player_opportunities"),
        ("LOW_TEAM_DENOMINATOR_NOISE", "flag_low_team_denominator"),
        ("BASELINE_SMALL_OR_UNSTABLE", "flag_baseline_small_or_unstable"),
        ("MARGINAL_CHANGE_NEAR_THRESHOLD", "flag_marginal_change"),
        ("NORMAL_CONTEXT_SENSITIVE", "flag_normal_context_sensitive"),
    ]
    cases["primary_reason_code"] = "ROLE_REVERSION_NO_OBSERVED_DATA_ISSUE"
    for reason, flag in reversed(precedence):
        cases.loc[cases[flag].fillna(False), "primary_reason_code"] = reason
    cases["secondary_reason_codes"] = cases.apply(
        lambda row: " | ".join(
            [
                reason
                for reason, flag in precedence
                if bool(row.get(flag, False)) and reason != row["primary_reason_code"]
            ]
            + (["IMMEDIATE_REVERSION"] if bool(row["flag_immediate_reversion"]) else [])
            + (["DUPLICATE_RB_FAMILY"] if bool(row["duplicate_rb_family_alert"]) else [])
            + (["CONSECUTIVE_REPEAT"] if bool(row["consecutive_family_repeat"]) else [])
        ),
        axis=1,
    )
    cases["review_status"] = "REVIEWED_RULE_EVIDENCE"
    cases["reviewer_note"] = cases["primary_reason_code"].map(
        FALSE_POSITIVE_REASON_DEFINITIONS
    )
    definitions = pd.DataFrame(
        [(code, definition) for code, definition in FALSE_POSITIVE_REASON_DEFINITIONS.items()],
        columns=["reason_code", "definition"],
    )
    return cases, definitions


def assert_methods_present(equal_volume: pd.DataFrame) -> None:
    count_columns = [f"{method}_count" for method in EXPECTED_METHODS]
    missing = [column for column in count_columns if column not in equal_volume]
    if missing:
        raise AssertionError(f"Equal-volume table is missing method columns: {missing}")
    if not equal_volume["observed_method_count"].eq(len(EXPECTED_METHODS)).all():
        raise AssertionError("At least one family-week omits an expected method")
    if not equal_volume["equal_volume"].all():
        raise AssertionError("At least one family-week fails equal-volume matching")
