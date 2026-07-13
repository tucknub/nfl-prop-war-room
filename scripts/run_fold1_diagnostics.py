from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.diagnostics import (  # noqa: E402
    add_diagnostic_dimensions,
    build_requested_breakdowns,
    comparison_improvements,
    deduplicated_feed,
    false_positive_case_review,
    feed_volume_table,
    method_comparison_table,
    rb_family_overlap,
    repeat_alert_summary,
    summarize_metrics,
)
from role_validation.legacy_ablation import run_legacy_ablation  # noqa: E402
from role_validation.evaluation import (  # noqa: E402
    release_decision,
    summarize_alerts,
    summarize_method_comparisons,
)
from role_validation.partial_game import (  # noqa: E402
    build_partial_game_status,
    load_explicit_injury_sources,
)
from role_validation.redevelopment import (  # noqa: E402
    ALLOWED_REDEVELOPMENT_SEASONS,
    CANONICAL_KEY,
    EXPECTED_METHODS,
    ROLE_FAMILIES,
    clone_candidate,
    load_canonical_seasons,
    run_candidate,
)


PRIMARY_POLICY = "PRIMARY_CONFIRMED_EXCLUDED"
PARTIAL_POLICIES = (
    PRIMARY_POLICY,
    "ALL_INCLUDED",
    "STRICT_SUSPECTED_EXCLUDED",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 2018-2021 Fold 1 diagnostics and redevelopment.")
    parser.add_argument(
        "--canonical",
        default="outputs/role_validation/canonical_player_week_role.csv.gz",
    )
    parser.add_argument(
        "--original-alerts",
        default="outputs/role_validation/fold_1/alerts_2021.csv.gz",
    )
    parser.add_argument(
        "--selected-parameters",
        default="outputs/role_validation/fold_1/fold_1_selected_parameters.csv",
    )
    parser.add_argument(
        "--source-cache-dir",
        default="data/raw/role_validation",
    )
    parser.add_argument(
        "--experiments-config",
        default="config/role_change_fold1_experiments.yaml",
    )
    parser.add_argument(
        "--recommended-config",
        default=None,
        help="Optional finalized candidate YAML. Required for --stage final.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/role_validation/fold_1_diagnostics",
    )
    parser.add_argument("--stage", choices=["explore", "final"], default="explore")
    return parser.parse_args()


def _absolute(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_csv(frame: pd.DataFrame, path: Path, *, compressed: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compressed:
        frame.to_csv(
            path,
            index=False,
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
        )
    else:
        frame.to_csv(path, index=False)


def _load_cached_allowed(cache_dir: Path, name: str, seasons: list[int]) -> pd.DataFrame:
    matches = sorted(cache_dir.glob(f"{name}_*.csv.gz"))
    if not matches:
        raise FileNotFoundError(f"No cached {name} source in {cache_dir}")
    # The original integration cache is the only expected match. When reruns create
    # a narrower cache, prefer the widest source and still retain only allowed rows.
    path = max(matches, key=lambda item: item.stat().st_size)
    selected: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, chunksize=100_000, low_memory=False):
        if "season" in chunk:
            source_season = pd.to_numeric(chunk["season"], errors="coerce")
        elif "nflverse_game_id" in chunk:
            source_season = pd.to_numeric(
                chunk["nflverse_game_id"].astype(str).str.slice(0, 4), errors="coerce"
            )
        else:
            raise ValueError(f"Cannot identify season in {path.name}")
        selected.append(chunk.loc[source_season.isin(seasons)].copy())
    result = pd.concat(selected, ignore_index=True)
    if "season" in result:
        observed = set(pd.to_numeric(result["season"], errors="raise").astype(int).unique())
    else:
        observed = set(
            pd.to_numeric(
                result["nflverse_game_id"].astype(str).str.slice(0, 4), errors="raise"
            ).astype(int).unique()
        )
    if not observed.issubset(set(seasons)):
        raise AssertionError(f"Disallowed seasons read from {path}: {sorted(observed)}")
    return result


def _merge_partial_context(alerts: pd.DataFrame, enriched: pd.DataFrame) -> pd.DataFrame:
    context_columns = [
        *CANONICAL_KEY,
        "confirmed_partial_game",
        "suspected_partial_game",
        "suspected_partial_corroborated",
        "partial_game_status",
        "partial_game_reason",
        "confirmed_teammate_exit",
        "suspected_teammate_exit",
        "explicit_pbp_injury",
        "pbp_return_status",
        "postgame_injury_report",
        "injury_report_status",
        "prior_snap_n",
        "prior_three_median_snap_share",
        "snap_share_drop",
        "last_appearance_fraction",
        "trailing_team_plays",
    ]
    context = enriched[context_columns].drop_duplicates(CANONICAL_KEY)
    merged = alerts.merge(context, on=CANONICAL_KEY, how="left", validate="many_to_one")
    if len(merged) != len(alerts):
        raise AssertionError("Partial-game context join changed alert row count")
    return merged


def _method_membership_overlap(alerts: pd.DataFrame) -> pd.DataFrame:
    key = ["season", "week", "player_id", "team", "role_family"]
    full = alerts.loc[alerts["method"].eq("full_propwar")]
    rows = []
    for family, family_full in full.groupby("role_family"):
        full_keys = set(map(tuple, family_full[key].itertuples(index=False, name=None)))
        for method in EXPECTED_METHODS:
            method_frame = alerts.loc[
                alerts["role_family"].eq(family) & alerts["method"].eq(method)
            ]
            method_keys = set(map(tuple, method_frame[key].itertuples(index=False, name=None)))
            union = full_keys | method_keys
            rows.append(
                {
                    "role_family": family,
                    "method": method,
                    "full_alerts": len(full_keys),
                    "method_alerts": len(method_keys),
                    "overlap": len(full_keys & method_keys),
                    "jaccard": len(full_keys & method_keys) / len(union) if union else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _candidate_period(season: pd.Series) -> pd.Series:
    return np.where(season.eq(2021), "fold_1_2021", "development_2018_2020")


def _uncertainty_tables(
    work: pd.DataFrame,
    grouping_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the locked 2,000-draw uncertainty implementation deterministically."""
    method_parts: list[pd.DataFrame] = []
    comparison_parts: list[pd.DataFrame] = []
    grouper: Any = (
        grouping_columns[0] if len(grouping_columns) == 1 else grouping_columns
    )
    for key, group in work.groupby(grouper, dropna=False, sort=True):
        key_values = (key,) if len(grouping_columns) == 1 else tuple(key)
        labels = dict(zip(grouping_columns, key_values))
        method = summarize_alerts(group, bootstrap_iterations=2000)
        comparison = summarize_method_comparisons(
            group,
            bootstrap_iterations=2000,
            confidence_level=0.95,
            seed=850,
        )
        for column, value in reversed(list(labels.items())):
            method.insert(0, column, value)
            comparison.insert(0, column, value)
        method_parts.append(method)
        comparison_parts.append(comparison)
    return (
        pd.concat(method_parts, ignore_index=True) if method_parts else pd.DataFrame(),
        pd.concat(comparison_parts, ignore_index=True)
        if comparison_parts
        else pd.DataFrame(),
    )


def _candidate_summaries(alerts: pd.DataFrame) -> dict[str, pd.DataFrame]:
    work = add_diagnostic_dimensions(alerts)
    work["period"] = _candidate_period(work["season"])
    family_group = ["candidate_name", "partial_policy", "period"]
    family = summarize_metrics(
        work, [*family_group, "role_family", "method"]
    )
    family_ci, comparison_ci = _uncertainty_tables(work, family_group)
    family = family.merge(
        family_ci[
            [
                *family_group,
                "role_family",
                "method",
                "precision_ci_low",
                "precision_ci_high",
            ]
        ],
        on=[*family_group, "role_family", "method"],
        how="left",
        validate="one_to_one",
    )
    comparisons = comparison_improvements(family)
    comparisons = comparisons.merge(
        comparison_ci[
            [
                *family_group,
                "role_family",
                "relative_precision_improvement",
                "precision_improvement_ci_low",
                "precision_improvement_ci_high",
            ]
        ],
        on=[*family_group, "role_family"],
        how="left",
        validate="one_to_one",
    )
    season_group = ["candidate_name", "partial_policy", "season"]
    by_season = summarize_metrics(
        work,
        [*season_group, "role_family", "method"],
    )
    by_season_ci, by_season_comparison_ci = _uncertainty_tables(work, season_group)
    by_season = by_season.merge(
        by_season_ci[
            [
                *season_group,
                "role_family",
                "method",
                "precision_ci_low",
                "precision_ci_high",
            ]
        ],
        on=[*season_group, "role_family", "method"],
        how="left",
        validate="one_to_one",
    )
    by_season_comparisons = comparison_improvements(by_season)
    by_season_comparisons = by_season_comparisons.merge(
        by_season_comparison_ci[
            [
                *season_group,
                "role_family",
                "relative_precision_improvement",
                "precision_improvement_ci_low",
                "precision_improvement_ci_high",
            ]
        ],
        on=[*season_group, "role_family"],
        how="left",
        validate="one_to_one",
    )
    direction = summarize_metrics(
        work.loc[work["method"].eq("full_propwar")],
        ["candidate_name", "partial_policy", "period", "role_family", "direction"],
    )
    blocks = summarize_metrics(
        work.loc[work["season"].eq(2021)],
        ["candidate_name", "partial_policy", "week_block", "role_family", "method"],
    )
    block_comparisons = comparison_improvements(blocks)
    return {
        "family": family,
        "comparisons": comparisons,
        "by_season": by_season,
        "by_season_comparisons": by_season_comparisons,
        "direction": direction,
        "blocks": blocks,
        "block_comparisons": block_comparisons,
    }


def _persistence_threshold_sensitivity(alerts: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for threshold in (0.40, 0.50, 0.60):
        work = alerts.copy()
        work["period"] = _candidate_period(work["season"])
        evaluable = work["retention"].notna() & work["future_n"].ge(2)
        work["persistent"] = pd.Series(pd.NA, index=work.index, dtype="boolean")
        work.loc[evaluable, "persistent"] = work.loc[evaluable, "retention"].ge(
            threshold
        )
        for period, period_group in work.groupby("period", sort=True):
            summary = summarize_metrics(period_group, ["role_family", "method"])
            comparison = comparison_improvements(summary)
            _, uncertainty = _uncertainty_tables(
                period_group, ["candidate_name", "partial_policy", "period"]
            )
            comparison = comparison.merge(
                uncertainty[
                    [
                        "role_family",
                        "relative_precision_improvement",
                        "precision_improvement_ci_low",
                        "precision_improvement_ci_high",
                    ]
                ],
                on="role_family",
                how="left",
                validate="one_to_one",
            )
            comparison.insert(0, "period", period)
            comparison.insert(0, "persistence_threshold", threshold)
            rows.append(comparison)
    return pd.concat(rows, ignore_index=True)


def _candidate_feed_stats(
    alerts: pd.DataFrame,
    candidate_name: str,
    policy: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    full = alerts.loc[
        alerts["method"].eq("full_propwar") & alerts["season"].eq(2021)
    ]
    season_weeks = pd.DataFrame({"season": 2021, "week": range(1, 19)})
    weekly = feed_volume_table(full, season_weeks)
    weekly.insert(0, "candidate_name", candidate_name)
    weekly.insert(1, "partial_policy", policy)
    active = weekly.loc[weekly["deduplicated_feed_alerts"].gt(0), "deduplicated_feed_alerts"]
    stats = pd.DataFrame(
        [
            {
                "candidate_name": candidate_name,
                "partial_policy": policy,
                "family_alert_rows": int(weekly["family_alert_rows"].sum()),
                "deduplicated_feed_alerts": int(weekly["deduplicated_feed_alerts"].sum()),
                "duplicate_family_rows_removed": int(
                    weekly["duplicate_family_rows_removed"].sum()
                ),
                "median_all_18_weeks": float(weekly["deduplicated_feed_alerts"].median()),
                "median_active_weeks": float(active.median()) if len(active) else np.nan,
                "mean_all_18_weeks": float(weekly["deduplicated_feed_alerts"].mean()),
                "p90_all_18_weeks": float(weekly["deduplicated_feed_alerts"].quantile(0.90)),
                "max_week": int(weekly["deduplicated_feed_alerts"].max()),
                "zero_alert_weeks": int(weekly["deduplicated_feed_alerts"].eq(0).sum()),
                "weeks_above_15": int(weekly["deduplicated_feed_alerts"].gt(15).sum()),
                "weeks_above_20": int(weekly["deduplicated_feed_alerts"].gt(20).sum()),
                "within_5_15_median_target": bool(
                    5 <= weekly["deduplicated_feed_alerts"].median() <= 15
                ),
            }
        ]
    )
    return stats, weekly


def _set_family_value(
    candidate: dict[str, Any],
    families: list[str],
    field: str,
    value: float,
) -> None:
    for family in families:
        for direction in ("increase", "decrease"):
            candidate["thresholds"][family][direction][field] = value


def _screen_candidates(
    serious: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    by_name = {candidate["name"]: deepcopy(candidate) for candidate in serious}
    s1 = by_name["S1_corrected_minimal"]
    s2 = by_name["S2_balanced_directional_no_cooldown"]
    screens: list[tuple[dict[str, Any], str, str]] = []

    def add(candidate: dict[str, Any], axis: str, level: str) -> None:
        candidate = deepcopy(candidate)
        safe_level = (
            str(level)
            .lower()
            .replace(".", "p")
            .replace("/", "_")
            .replace(" ", "_")
        )
        candidate["name"] = f"screen_{axis}_{safe_level}"
        screens.append((candidate, axis, level))

    for window, minimum in [(3, 3), (4, 4), (6, 4)]:
        add(
            clone_candidate(
                s1,
                f"screen_baseline_w{window}_min{minimum}",
                baseline__recent_games=window,
                baseline__min_games=minimum,
            ),
            "baseline_window",
            f"recent_{window}_min_{minimum}",
        )
    add(
        clone_candidate(s1, "screen_baseline_w4_min3", baseline__min_games=3),
        "minimum_baseline_games",
        "3",
    )
    add(deepcopy(s1), "minimum_baseline_games", "4")

    one_game = clone_candidate(
        s1,
        "screen_confirmation_one_game",
        confirmation__default_games=1,
        confirmation__te_target_share_games=1,
        confirmation__mode="none",
    )
    legacy_two = clone_candidate(
        s1, "screen_confirmation_legacy_two", confirmation__mode="legacy"
    )
    add(one_game, "consecutive_confirmation", "one_game_none")
    add(legacy_two, "consecutive_confirmation", "legacy_two_game")
    add(deepcopy(s1), "consecutive_confirmation", "strict_two_game")

    blend = clone_candidate(
        s1,
        "screen_season_plus_recent",
        baseline__type="season_plus_recent",
        baseline__recent_weight=0.5,
        baseline__season_weight=0.5,
    )
    add(deepcopy(s1), "baseline_type", "recent")
    add(blend, "baseline_type", "season_plus_recent_50_50")

    te_two = clone_candidate(
        s2, "screen_te_confirmation_two", confirmation__te_target_share_games=2
    )
    te_three = clone_candidate(
        s2, "screen_te_confirmation_three", confirmation__te_target_share_games=3
    )
    add(te_two, "te_confirmation", "two_games")
    add(te_three, "te_confirmation", "three_games")

    cooldown = deepcopy(by_name["S2_balanced_directional"])
    cooldown["name"] = "screen_repeat_cooldown_one_week"
    add(deepcopy(s2), "repeat_suppression", "none")
    add(cooldown, "repeat_suppression", "one_calendar_week_direction_sensitive")

    families_by_axis = {
        "rb": ["rb_carry_share", "rb_opportunity_share"],
        "wr": ["wr_target_share"],
        "te": ["te_target_share"],
    }
    delta_levels = {
        "rb": [0.15, 0.18, 0.20, 0.22],
        "wr": [0.12, 0.13, 0.15, 0.16],
        "te": [0.11, 0.12, 0.15, 0.16],
    }
    for position, levels in delta_levels.items():
        for value in levels:
            candidate = deepcopy(s1)
            candidate["name"] = f"screen_{position}_delta_{value:.2f}".replace(".", "p")
            _set_family_value(
                candidate, families_by_axis[position], "min_abs_delta", value
            )
            add(candidate, f"{position}_minimum_absolute_change", f"{value:.2f}")

    opportunity_levels = {
        "rb": [0, 4, 6, 8],
        "wr": [0, 3, 4, 5],
        "te": [0, 2, 3, 4],
    }
    for position, levels in opportunity_levels.items():
        for value in levels:
            candidate = deepcopy(s1)
            candidate["name"] = f"screen_{position}_player_floor_{value}"
            _set_family_value(
                candidate,
                families_by_axis[position],
                "min_player_opportunities",
                float(value),
            )
            add(candidate, f"{position}_minimum_player_opportunities", str(value))

    denominator_levels = {
        "rb": [0, 15, 18, 20],
        "wr": [0, 18, 20, 22],
        "te": [0, 18, 20, 22],
    }
    for position, levels in denominator_levels.items():
        for value in levels:
            candidate = deepcopy(s1)
            candidate["name"] = f"screen_{position}_team_floor_{value}"
            _set_family_value(
                candidate,
                families_by_axis[position],
                "min_team_denominator",
                float(value),
            )
            add(candidate, f"{position}_minimum_team_denominator", str(value))

    uniform_direction = deepcopy(s2)
    uniform_direction["name"] = "screen_same_increase_decrease_rules"
    for family in ROLE_FAMILIES:
        increase = deepcopy(uniform_direction["thresholds"][family]["increase"])
        increase["player_opportunity_reference"] = "baseline_mean"
        uniform_direction["thresholds"][family]["decrease"] = increase
    add(uniform_direction, "direction_specific_rules", "same_thresholds")
    add(deepcopy(s2), "direction_specific_rules", "separate_increase_decrease")

    uniform_position = deepcopy(s1)
    uniform_position["name"] = "screen_uniform_position_rules"
    for family in ROLE_FAMILIES:
        uniform_position["thresholds"][family] = {
            "increase": {
                "min_abs_delta": 0.18,
                "min_player_opportunities": 4,
                "player_opportunity_reference": "confirmation_min",
                "min_team_denominator": 18,
            },
            "decrease": {
                "min_abs_delta": 0.18,
                "min_player_opportunities": 4,
                "player_opportunity_reference": "baseline_mean",
                "min_team_denominator": 18,
            },
        }
    add(uniform_position, "position_specific_rules", "uniform")
    add(deepcopy(s2), "position_specific_rules", "position_specific")

    # Preserve one row per named screen. Repeated reference settings are retained
    # because they are the explicit control within different one-factor axes.
    metadata = pd.DataFrame(
        [
            {"candidate_name": candidate["name"], "screening_axis": axis, "screening_level": level}
            for candidate, axis, level in screens
        ]
    )
    return [candidate for candidate, _, _ in screens], metadata


def _screen_run(
    data: pd.DataFrame,
    candidates: list[dict[str, Any]],
    metadata: pd.DataFrame,
    feature_cache: dict[tuple[Any, ...], pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    comparison_parts: list[pd.DataFrame] = []
    feed_parts: list[pd.DataFrame] = []
    equal_parts: list[pd.DataFrame] = []
    for candidate in candidates:
        try:
            result = run_candidate(
                data,
                candidate,
                partial_policy=PRIMARY_POLICY,
                feature_cache=feature_cache,
            )
        except (RuntimeError, ValueError) as error:
            comparison_parts.append(
                pd.DataFrame(
                    [
                        {
                            "candidate_name": candidate["name"],
                            "partial_policy": PRIMARY_POLICY,
                            "period": "integrity_failure",
                            "role_family": "ALL",
                            "integrity_pass": False,
                            "integrity_error": str(error),
                        }
                    ]
                )
            )
            feed_parts.append(
                pd.DataFrame(
                    [
                        {
                            "candidate_name": candidate["name"],
                            "partial_policy": PRIMARY_POLICY,
                            "integrity_pass": False,
                            "integrity_error": str(error),
                        }
                    ]
                )
            )
            equal_parts.append(
                pd.DataFrame(
                    [
                        {
                            "candidate_name": candidate["name"],
                            "partial_policy": PRIMARY_POLICY,
                            "family_weeks": 0,
                            "equal_volume_all": False,
                            "expected_methods_all": False,
                            "integrity_pass": False,
                            "integrity_error": str(error),
                        }
                    ]
                )
            )
            continue
        summaries = _candidate_summaries(result["alerts"])
        comparisons = summaries["comparisons"].copy()
        comparisons["integrity_pass"] = True
        comparisons["integrity_error"] = ""
        comparison_parts.append(comparisons)
        feed, _ = _candidate_feed_stats(
            result["alerts"], candidate["name"], PRIMARY_POLICY
        )
        feed["integrity_pass"] = True
        feed["integrity_error"] = ""
        feed_parts.append(feed)
        equal = result["equal_volume"].copy()
        equal_summary = equal.groupby(["candidate_name", "partial_policy"], as_index=False).agg(
                family_weeks=("equal_volume", "size"),
                equal_volume_all=("equal_volume", "all"),
                expected_methods_all=("observed_method_count", lambda values: bool((values == 4).all())),
            )
        equal_summary["integrity_pass"] = True
        equal_summary["integrity_error"] = ""
        equal_parts.append(equal_summary)
    comparisons = pd.concat(comparison_parts, ignore_index=True).merge(
        metadata, on="candidate_name", how="left"
    )
    feed = pd.concat(feed_parts, ignore_index=True).merge(
        metadata, on="candidate_name", how="left"
    )
    equal = pd.concat(equal_parts, ignore_index=True).merge(
        metadata, on="candidate_name", how="left"
    )
    return comparisons, feed, equal


def _ablation_value_table(
    summary: pd.DataFrame,
    membership: pd.DataFrame,
) -> pd.DataFrame:
    full = summary.loc[summary["method"].eq("full_propwar")].copy()
    original = full.loc[full["ablation"].eq("original_full_detector")].set_index(
        ["ablation_mode", "role_family"]
    )
    rows = []
    for row in full.itertuples(index=False):
        base = original.loc[(row.ablation_mode, row.role_family)]
        rows.append(
            {
                "ablation": row.ablation,
                "ablated_safeguard": row.ablated_safeguard,
                "ablation_mode": row.ablation_mode,
                "role_family": row.role_family,
                "alert_delta": int(row.alerts - base["alerts"]),
                "precision_delta": row.precision - base["precision"],
                "reversion_rate_delta": row.reversion_rate - base["reversion_rate"],
                "median_retention_delta": row.median_retention - base["median_retention"],
            }
        )
    result = pd.DataFrame(rows).merge(
        membership,
        on=["ablation", "ablated_safeguard", "ablation_mode"],
        how="left",
    )
    result["no_measurable_value"] = (
        result["identical_membership"]
        & result["alert_delta"].eq(0)
        & result["precision_delta"].fillna(0).abs().lt(1e-12)
        & result["reversion_rate_delta"].fillna(0).abs().lt(1e-12)
        & result["median_retention_delta"].fillna(0).abs().lt(1e-12)
    )
    return result


def main() -> int:
    args = parse_args()
    seasons = list(ALLOWED_REDEVELOPMENT_SEASONS)
    output = _absolute(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    canonical_path = _absolute(args.canonical)
    original_alert_path = _absolute(args.original_alerts)
    selected_parameter_path = _absolute(args.selected_parameters)
    cache_dir = _absolute(args.source_cache_dir)
    experiment_path = _absolute(args.experiments_config)

    experiments = yaml.safe_load(experiment_path.read_text(encoding="utf-8"))
    contract = experiments["analysis_contract"]
    if contract["allowed_seasons"] != seasons:
        raise AssertionError("Experiment config allowed seasons differ from 2018-2021")
    if contract["release_gates_changed"]:
        raise AssertionError("Release gates may not change in Fold 1 redevelopment")
    if args.stage == "final" and not args.recommended_config:
        raise SystemExit("--recommended-config is required for --stage final")

    canonical = load_canonical_seasons(str(canonical_path), seasons)
    selected_pbp = _load_cached_allowed(cache_dir, "pbp", seasons)
    participation = _load_cached_allowed(cache_dir, "participation", seasons)
    injuries = _load_cached_allowed(cache_dir, "injuries", seasons)
    explicit_pbp, full_rosters, full_schedules = load_explicit_injury_sources(seasons)
    partial = build_partial_game_status(
        canonical,
        selected_pbp=selected_pbp,
        participation=participation,
        injuries=injuries,
        explicit_pbp=explicit_pbp,
        full_rosters=full_rosters,
        schedules=full_schedules,
        seasons=seasons,
    )
    enriched = partial.canonical
    observed = set(pd.to_numeric(enriched["season"], errors="raise").astype(int).unique())
    if observed != set(seasons):
        raise AssertionError(f"Enriched canonical seasons differ: {sorted(observed)}")
    _write_csv(
        enriched,
        output / "canonical_role_2018_2021_enriched.csv.gz",
        compressed=True,
    )
    canonical_key = ["season", "week", "player_id", "team", "role_family"]
    required_audit_columns = [
        *canonical_key,
        "player_name",
        "position",
        "metric_all",
        "metric_normal",
        "raw_opportunities_all",
        "raw_opportunities_normal",
        "team_opportunities_all",
        "team_opportunities_normal",
        "qualifying_game",
        "data_quality_pass",
        "snap_share",
    ]
    audit_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for season, group in enriched.groupby("season", sort=True):
        audit_rows.append(
            {
                "season": int(season),
                "canonical_rows": len(group),
                "unique_players": int(group["player_id"].nunique()),
                "duplicate_key_rows": int(group.duplicated(canonical_key, keep=False).sum()),
                "duplicate_key_rate": float(group.duplicated(canonical_key, keep=False).mean()),
                "required_field_null_cells": int(group[required_audit_columns].isna().sum().sum()),
                "quality_fail_rows": int((~group["data_quality_pass"].fillna(False).astype(bool)).sum()),
                "quality_pass_rate": float(group["data_quality_pass"].fillna(False).astype(bool).mean()),
                "qualifying_rate": float(group["qualifying_game"].fillna(False).astype(bool).mean()),
                "confirmed_partial_family_rows": int(group["confirmed_partial_game"].sum()),
                "suspected_partial_family_rows": int(group["suspected_partial_game"].sum()),
            }
        )
        for column in required_audit_columns:
            missing_rows.append(
                {
                    "season": int(season),
                    "column": column,
                    "null_rows": int(group[column].isna().sum()),
                    "null_rate": float(group[column].isna().mean()),
                }
            )
    _write_csv(
        pd.DataFrame(audit_rows), output / "canonical_redevelopment_audit_2018_2021.csv"
    )
    _write_csv(
        pd.DataFrame(missing_rows),
        output / "canonical_redevelopment_missingness_2018_2021.csv",
    )
    _write_csv(partial.evidence_ledger, output / "partial_game_evidence_2018_2021.csv")
    _write_csv(partial.source_coverage, output / "partial_game_source_coverage.csv")
    partial_counts = (
        enriched.groupby(["season", "partial_game_status"])
        .size()
        .rename("canonical_family_rows")
        .reset_index()
    )
    partial_distinct = (
        enriched.drop_duplicates(["season", "week", "game_id", "player_id", "team"])
        .groupby(["season", "partial_game_status"])
        .size()
        .rename("distinct_player_games")
        .reset_index()
    )
    _write_csv(
        partial_counts.merge(
            partial_distinct, on=["season", "partial_game_status"], how="outer"
        ),
        output / "partial_game_status_counts.csv",
    )

    original_alerts = pd.read_csv(original_alert_path, low_memory=False)
    if set(pd.to_numeric(original_alerts["season"], errors="raise").astype(int).unique()) != {2021}:
        raise AssertionError("Original Fold 1 archive is not restricted to 2021")
    original_enriched = _merge_partial_context(original_alerts, enriched)
    original_enriched["candidate_name"] = "original_checkpoint_00d6085"
    original_enriched["partial_policy"] = "CHECKPOINT_NO_RELIABLE_PARTIAL_EXCLUSION"
    original_enriched["period"] = "fold_1_2021"
    _write_csv(
        original_enriched,
        output / "original_checkpoint_alerts_enriched_2021.csv.gz",
        compressed=True,
    )
    original_full = original_enriched.loc[
        original_enriched["method"].eq("full_propwar")
    ].copy()
    original_feed = deduplicated_feed(original_full)
    _write_csv(original_feed, output / "original_deduplicated_feed_2021.csv")
    original_weeks = pd.DataFrame({"season": 2021, "week": range(1, 19)})
    _write_csv(
        feed_volume_table(original_full, original_weeks),
        output / "original_weekly_family_vs_deduplicated_volume_2021.csv",
    )
    _write_csv(rb_family_overlap(original_full), output / "original_rb_family_overlap_2021.csv")
    _write_csv(
        repeat_alert_summary(original_full), output / "original_repeat_alerts_2021.csv"
    )
    _write_csv(
        build_requested_breakdowns(original_full),
        output / "original_requested_breakdowns_2021.csv",
    )
    original_method_family = method_comparison_table(original_enriched)
    original_method_ci = summarize_alerts(original_enriched, bootstrap_iterations=2000)
    original_method_family = original_method_family.merge(
        original_method_ci[
            [
                "role_family",
                "method",
                "precision_ci_low",
                "precision_ci_high",
            ]
        ],
        on=["role_family", "method"],
        how="left",
        validate="one_to_one",
    )
    original_method_overall = summarize_metrics(original_enriched, ["method"])
    original_method_family.insert(0, "grain", "role_family")
    original_method_overall.insert(0, "grain", "all_family_rows")
    original_method_overall.insert(1, "role_family", "ALL")
    _write_csv(
        pd.concat([original_method_family, original_method_overall], ignore_index=True),
        output / "original_four_method_comparison_2021.csv",
    )
    _write_csv(
        summarize_method_comparisons(
            original_enriched,
            bootstrap_iterations=2000,
            confidence_level=0.95,
            seed=850,
        ),
        output / "original_full_vs_naive_comparisons_2021.csv",
    )
    _write_csv(
        _method_membership_overlap(original_enriched),
        output / "original_method_membership_overlap_2021.csv",
    )
    legacy_thresholds = (
        pd.read_csv(selected_parameter_path)
        .set_index("role_family")["min_abs_delta"]
        .astype(float)
        .to_dict()
    )
    false_positives, reason_definitions = false_positive_case_review(
        original_full, legacy_thresholds
    )
    _write_csv(false_positives, output / "original_false_positive_case_review_2021.csv")
    _write_csv(reason_definitions, output / "false_positive_reason_definitions.csv")
    reason_summary = summarize_metrics(false_positives, ["primary_reason_code"])
    _write_csv(reason_summary, output / "original_false_positive_reason_summary_2021.csv")

    feature_cache: dict[tuple[Any, ...], pd.DataFrame] = {}
    serious_candidates = experiments["serious_candidates"]
    screen_candidates, screen_metadata = _screen_candidates(serious_candidates)
    screen_comparisons, screen_feed, screen_equal = _screen_run(
        enriched, screen_candidates, screen_metadata, feature_cache
    )
    _write_csv(screen_comparisons, output / "candidate_axis_screen_comparisons.csv")
    _write_csv(screen_feed, output / "candidate_axis_screen_feed_volume.csv")
    _write_csv(screen_equal, output / "candidate_axis_screen_equal_volume.csv")

    serious_alert_parts: list[pd.DataFrame] = []
    serious_equal_parts: list[pd.DataFrame] = []
    serious_suppressed_parts: list[pd.DataFrame] = []
    serious_feed_stats: list[pd.DataFrame] = []
    serious_weekly: list[pd.DataFrame] = []
    for candidate in serious_candidates:
        result = run_candidate(
            enriched,
            candidate,
            partial_policy=PRIMARY_POLICY,
            feature_cache=feature_cache,
        )
        serious_alert_parts.append(result["alerts"])
        serious_equal_parts.append(result["equal_volume"])
        if not result["suppressed"].empty:
            serious_suppressed_parts.append(result["suppressed"])
        stats, weekly = _candidate_feed_stats(
            result["alerts"], candidate["name"], PRIMARY_POLICY
        )
        serious_feed_stats.append(stats)
        serious_weekly.append(weekly)
    serious_alerts = pd.concat(serious_alert_parts, ignore_index=True)
    serious_equal = pd.concat(serious_equal_parts, ignore_index=True)
    serious_suppressed = (
        pd.concat(serious_suppressed_parts, ignore_index=True)
        if serious_suppressed_parts
        else pd.DataFrame()
    )
    _write_csv(
        serious_alerts,
        output / "serious_candidate_alerts_2018_2021.csv.gz",
        compressed=True,
    )
    _write_csv(serious_equal, output / "serious_candidate_equal_volume.csv")
    _write_csv(serious_suppressed, output / "serious_candidate_suppressed_alerts.csv")
    _write_csv(
        pd.concat(serious_feed_stats, ignore_index=True),
        output / "serious_candidate_feed_volume_summary_2021.csv",
    )
    _write_csv(
        pd.concat(serious_weekly, ignore_index=True),
        output / "serious_candidate_weekly_feed_volume_2021.csv",
    )
    serious_summaries = _candidate_summaries(serious_alerts)
    for name, frame in serious_summaries.items():
        _write_csv(frame, output / f"serious_candidate_{name}.csv")
    serious_full = serious_alerts.loc[serious_alerts["method"].eq("full_propwar")].copy()
    serious_full["period"] = _candidate_period(serious_full["season"])
    _write_csv(
        build_requested_breakdowns(serious_full),
        output / "serious_candidate_requested_breakdowns.csv",
    )

    if args.stage == "final":
        ablation = run_legacy_ablation(
            enriched,
            pd.read_csv(selected_parameter_path),
            original_alerts,
            test_season=2021,
            partial_policy=PRIMARY_POLICY,
        )
        _write_csv(
            ablation["alerts"].loc[ablation["alerts"]["method"].eq("full_propwar")],
            output / "legacy_safeguard_full_alerts_2021.csv.gz",
            compressed=True,
        )
        _write_csv(
            ablation["equal_volume"], output / "legacy_safeguard_ablation_equal_volume.csv"
        )
        _write_csv(
            ablation["membership"], output / "legacy_safeguard_ablation_membership.csv"
        )
        ablation_summary = summarize_metrics(
            ablation["alerts"],
            ["ablation", "ablated_safeguard", "ablation_mode", "role_family", "method"],
        )
        _write_csv(ablation_summary, output / "legacy_safeguard_ablation_summary.csv")
        _write_csv(
            comparison_improvements(ablation_summary),
            output / "legacy_safeguard_ablation_comparisons.csv",
        )
        _write_csv(
            _ablation_value_table(ablation_summary, ablation["membership"]),
            output / "legacy_safeguard_ablation_value.csv",
        )

        recommended_path = _absolute(args.recommended_config)
        recommended_document = yaml.safe_load(recommended_path.read_text(encoding="utf-8"))
        recommended = recommended_document.get("candidate", recommended_document)
        sensitivity_alerts: list[pd.DataFrame] = []
        sensitivity_equal: list[pd.DataFrame] = []
        sensitivity_feed_stats: list[pd.DataFrame] = []
        sensitivity_weekly: list[pd.DataFrame] = []
        sensitivity_cache: dict[tuple[Any, ...], pd.DataFrame] = {}
        for policy in PARTIAL_POLICIES:
            result = run_candidate(
                enriched,
                recommended,
                partial_policy=policy,
                feature_cache=sensitivity_cache,
            )
            sensitivity_alerts.append(result["alerts"])
            sensitivity_equal.append(result["equal_volume"])
            stats, weekly = _candidate_feed_stats(
                result["alerts"], recommended["name"], policy
            )
            sensitivity_feed_stats.append(stats)
            sensitivity_weekly.append(weekly)
        sensitivity_alert_frame = pd.concat(sensitivity_alerts, ignore_index=True)
        sensitivity_equal_frame = pd.concat(sensitivity_equal, ignore_index=True)
        _write_csv(
            sensitivity_alert_frame,
            output / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz",
            compressed=True,
        )
        _write_csv(
            sensitivity_equal_frame,
            output / "recommended_candidate_partial_sensitivity_equal_volume.csv",
        )
        sensitivity_summaries = _candidate_summaries(sensitivity_alert_frame)
        for name, frame in sensitivity_summaries.items():
            _write_csv(frame, output / f"recommended_candidate_partial_sensitivity_{name}.csv")
        _write_csv(
            pd.concat(sensitivity_feed_stats, ignore_index=True),
            output / "recommended_candidate_partial_sensitivity_feed_summary_2021.csv",
        )
        _write_csv(
            pd.concat(sensitivity_weekly, ignore_index=True),
            output / "recommended_candidate_partial_sensitivity_weekly_2021.csv",
        )
        recommended_primary = sensitivity_alert_frame.loc[
            sensitivity_alert_frame["partial_policy"].eq(PRIMARY_POLICY)
        ].copy()
        _write_csv(
            _persistence_threshold_sensitivity(recommended_primary),
            output / "recommended_candidate_persistence_threshold_sensitivity.csv",
        )

        original_comparison = summarize_method_comparisons(
            original_enriched,
            bootstrap_iterations=2000,
            confidence_level=0.95,
            seed=850,
        )
        revised_comparison = sensitivity_summaries["comparisons"].loc[
            sensitivity_summaries["comparisons"]["partial_policy"].eq(PRIMARY_POLICY)
            & sensitivity_summaries["comparisons"]["period"].eq("fold_1_2021")
        ].copy()
        comparison_columns = [
            "full_alerts",
            "full_evaluable_alerts",
            "full_precision",
            "naive_precision",
            "precision_improvement",
            "relative_precision_improvement",
            "precision_improvement_ci_low",
            "precision_improvement_ci_high",
            "full_reversion_rate",
            "naive_reversion_rate",
            "reversion_improvement",
            "full_median_retention",
            "naive_median_retention",
        ]
        original_selected = original_comparison[["role_family", *comparison_columns]].rename(
            columns={column: f"original_{column}" for column in comparison_columns}
        )
        revised_selected = revised_comparison[["role_family", *comparison_columns]].rename(
            columns={column: f"revised_{column}" for column in comparison_columns}
        )
        original_vs_revised = original_selected.merge(
            revised_selected, on="role_family", how="outer", validate="one_to_one"
        )
        for metric in (
            "full_alerts",
            "full_evaluable_alerts",
            "full_precision",
            "precision_improvement",
            "full_reversion_rate",
            "reversion_improvement",
            "full_median_retention",
        ):
            original_vs_revised[f"delta_{metric}"] = (
                original_vs_revised[f"revised_{metric}"]
                - original_vs_revised[f"original_{metric}"]
            )
        _write_csv(
            original_vs_revised,
            output / "original_vs_recommended_fold1_2021.csv",
        )

        validation_config = yaml.safe_load(
            (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
        )
        recommended_fold1_summary = summarize_metrics(
            recommended_primary.loc[recommended_primary["season"].eq(2021)],
            ["role_family", "method"],
        )
        gate_diagnostic = release_decision(
            recommended_fold1_summary,
            validation_config["release_gates"]["full_release"],
            nfl_weeks=18,
        ).rename(columns={"status": "point_gate_result"})
        gate_diagnostic["point_gate_result"] = gate_diagnostic[
            "point_gate_result"
        ].map({"FULL_RELEASE": "POINT_GATES_PASS", "FAIL": "POINT_GATES_FAIL"})
        gate_diagnostic.insert(
            1,
            "release_status",
            "DIAGNOSTIC_ONLY_2021_REUSED_FOR_REDEVELOPMENT",
        )
        gate_diagnostic["frozen_before_2021"] = False
        gate_diagnostic["fold_2_executed"] = False
        gate_diagnostic["release_gates_changed"] = False
        _write_csv(
            gate_diagnostic,
            output / "recommended_candidate_locked_gate_diagnostic_2021.csv",
        )

    source_paths = [
        canonical_path,
        original_alert_path,
        experiment_path,
        ROOT / "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
        ROOT / "LOCKED_DECISIONS.md",
        ROOT / "config" / "role_change_validation.yaml",
    ]
    if args.recommended_config:
        source_paths.append(_absolute(args.recommended_config))
    source_manifest = pd.DataFrame(
        [
            {
                "artifact": str(path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": _hash(path),
                "bytes": path.stat().st_size,
            }
            for path in source_paths
        ]
    )
    _write_csv(source_manifest, output / "input_source_manifest.csv")
    run_manifest = {
        "stage": args.stage,
        "checkpoint_commit": contract["checkpoint_commit"],
        "allowed_seasons": seasons,
        "development_seasons": [2018, 2019, 2020],
        "test_season": 2021,
        "fold_2_executed": False,
        "post_2021_results_used": False,
        "release_gates_changed": False,
        "canonical_rows_2018_2021": len(enriched),
        "original_full_family_alerts_2021": len(original_full),
        "original_deduplicated_feed_alerts_2021": len(original_feed),
        "explicit_partial_family_rows": int(enriched["confirmed_partial_game"].sum()),
        "suspected_partial_family_rows": int(enriched["suspected_partial_game"].sum()),
        "screen_candidates_attempted": len(screen_candidates),
        "screen_candidates_valid": int(screen_equal["integrity_pass"].fillna(False).sum()),
        "screen_candidates_integrity_failures": int(
            (~screen_equal["integrity_pass"].fillna(False)).sum()
        ),
        "serious_candidates": [candidate["name"] for candidate in serious_candidates],
        "recommended_config": args.recommended_config,
        "all_serious_equal_volume": bool(serious_equal["equal_volume"].all()),
        "expected_methods_present": bool(
            serious_equal["observed_method_count"].eq(len(EXPECTED_METHODS)).all()
        ),
    }
    (output / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(run_manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
