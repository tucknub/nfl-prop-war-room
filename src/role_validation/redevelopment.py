from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd

from role_validation.evaluation import attach_future_outcomes, build_future_outcome_lookup


ALLOWED_REDEVELOPMENT_SEASONS = (2018, 2019, 2020, 2021)
APPROVED_ROLE_VALIDATION_SEASONS = (2018, 2019, 2020, 2021, 2022, 2023, 2024)
ROLE_FAMILIES = (
    "rb_carry_share",
    "rb_opportunity_share",
    "wr_target_share",
    "te_target_share",
)
EXPECTED_METHODS = (
    "naive_spike",
    "two_week_raw",
    "normal_game_trend",
    "full_propwar",
)
CANONICAL_KEY = ["season", "week", "player_id", "team", "role_family"]
FEED_KEY = ["season", "week", "player_id", "team"]
SORT_COLUMNS = ["player_id", "role_family", "season", "week", "team"]


def load_canonical_seasons(
    path: str,
    seasons: Iterable[int] = ALLOWED_REDEVELOPMENT_SEASONS,
) -> pd.DataFrame:
    """Read only explicitly requested, protocol-approved seasons.

    The default remains the 2018-2021 redevelopment boundary. Fold 2 must pass
    ``seasons=[2022]`` explicitly so 2022 cannot enter a redevelopment run by
    accident.
    """
    allowed = {int(season) for season in seasons}
    if not allowed or not allowed.issubset(set(APPROVED_ROLE_VALIDATION_SEASONS)):
        raise ValueError(
            f"Role-validation seasons must be a non-empty subset of "
            f"{APPROVED_ROLE_VALIDATION_SEASONS}; received {sorted(allowed)}."
        )
    selected: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, chunksize=10_000, low_memory=False):
        season = pd.to_numeric(chunk["season"], errors="coerce")
        selected.append(chunk.loc[season.isin(allowed)].copy())
    result = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
    observed = set(pd.to_numeric(result["season"], errors="raise").astype(int).unique())
    if not observed.issubset(allowed):
        raise AssertionError(f"Disallowed seasons entered the analysis: {sorted(observed - allowed)}")
    return result


def _as_bool(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values.dtype):
        return values.fillna(default).astype(bool)
    normalized = values.fillna(default).astype(str).str.strip().str.lower()
    return normalized.isin({"true", "1", "yes", "y"})


def partial_exclusion_mask(frame: pd.DataFrame, policy: str) -> pd.Series:
    """Return focal-player rows excluded by one of the predeclared sensitivity policies."""
    confirmed = _as_bool(frame, "confirmed_partial_game")
    suspected = _as_bool(frame, "suspected_partial_game")
    if policy == "PRIMARY_CONFIRMED_EXCLUDED":
        return confirmed
    if policy == "ALL_INCLUDED":
        return pd.Series(False, index=frame.index, dtype=bool)
    if policy == "STRICT_SUSPECTED_EXCLUDED":
        return confirmed | suspected
    raise ValueError(f"Unknown partial-game policy: {policy}")


def _base_eligibility(
    frame: pd.DataFrame,
    metric_column: str,
    partial_policy: str,
    require_quality: bool = True,
    require_qualifying: bool = True,
) -> pd.Series:
    eligible = pd.to_numeric(frame[metric_column], errors="coerce").notna()
    if require_quality:
        eligible &= _as_bool(frame, "data_quality_pass")
    if require_qualifying:
        eligible &= _as_bool(frame, "qualifying_game")
    eligible &= ~partial_exclusion_mask(frame, partial_policy)
    return eligible


def _disjoint_features(
    frame: pd.DataFrame,
    *,
    metric_column: str,
    raw_opportunity_column: str,
    team_denominator_column: str,
    baseline_window: int,
    confirmation_games: int,
    baseline_type: str,
    recent_weight: float,
    season_weight: float,
    reset_each_season: bool,
    partial_policy: str,
    require_quality: bool = True,
    require_qualifying: bool = True,
    history_uses_exclusion_policy: bool = True,
) -> pd.DataFrame:
    """Compute causal features with a baseline ending before the detection window.

    For a two-game confirmation at game t, the confirmation values are t-1 and t,
    while the recent and season baselines end at t-2. No value appears in both the
    baseline and confirmation windows.
    """
    if baseline_window < 1:
        raise ValueError("baseline_window must be positive")
    if confirmation_games < 1:
        raise ValueError("confirmation_games must be positive")
    if baseline_type not in {"recent", "season_plus_recent"}:
        raise ValueError(f"Unsupported baseline_type: {baseline_type}")
    if baseline_type == "season_plus_recent" and not np.isclose(
        recent_weight + season_weight, 1.0
    ):
        raise ValueError("season_plus_recent weights must sum to one")

    df = frame.sort_values(SORT_COLUMNS).copy().reset_index(drop=True)
    metric = pd.to_numeric(df[metric_column], errors="coerce")
    raw = pd.to_numeric(df[raw_opportunity_column], errors="coerce")
    denominator = pd.to_numeric(df[team_denominator_column], errors="coerce")
    current_eligible = _base_eligibility(
        df,
        metric_column,
        partial_policy,
        require_quality=require_quality,
        require_qualifying=require_qualifying,
    )
    if history_uses_exclusion_policy:
        history_eligible = current_eligible.copy()
    else:
        history_eligible = _base_eligibility(
            df,
            metric_column,
            "ALL_INCLUDED",
            require_quality=False,
            require_qualifying=False,
        )

    size = len(df)
    values: dict[str, np.ndarray] = {
        "baseline_n": np.zeros(size, dtype=np.int64),
        "season_baseline_n": np.zeros(size, dtype=np.int64),
        "confirmation_n": np.zeros(size, dtype=np.int64),
        "baseline_value": np.full(size, np.nan),
        "recent_baseline_value": np.full(size, np.nan),
        "season_baseline_value": np.full(size, np.nan),
        "detected_value": np.full(size, np.nan),
        "detected_delta": np.full(size, np.nan),
        "current_metric": metric.to_numpy(dtype=float, na_value=np.nan),
        "previous_metric": np.full(size, np.nan),
        "confirmation_min_player_opportunities": np.full(size, np.nan),
        "confirmation_mean_player_opportunities": np.full(size, np.nan),
        "confirmation_min_team_denominator": np.full(size, np.nan),
        "confirmation_mean_team_denominator": np.full(size, np.nan),
        "baseline_mean_player_opportunities": np.full(size, np.nan),
        "baseline_mean_team_denominator": np.full(size, np.nan),
        "baseline_max_week": np.full(size, np.nan),
        "confirmation_start_week": np.full(size, np.nan),
        "confirmation_end_week": np.full(size, np.nan),
        "strict_confirmation_pass": np.zeros(size, dtype=bool),
        "legacy_confirmation_pass": np.zeros(size, dtype=bool),
        "feature_eligible": np.zeros(size, dtype=bool),
    }

    group_columns = ["player_id", "role_family"]
    if reset_each_season:
        group_columns.append("season")
    for _, indices in df.groupby(group_columns, sort=False, dropna=False).groups.items():
        history: list[dict[str, float | int]] = []
        for index_value in indices:
            index = int(index_value)
            if bool(current_eligible.iat[index]):
                prior_confirmation = history[-(confirmation_games - 1) :] if confirmation_games > 1 else []
                confirmation = [*prior_confirmation]
                confirmation.append(
                    {
                        "metric": float(metric.iat[index]),
                        "raw": float(raw.iat[index]) if pd.notna(raw.iat[index]) else np.nan,
                        "denominator": (
                            float(denominator.iat[index])
                            if pd.notna(denominator.iat[index])
                            else np.nan
                        ),
                        "season": int(df.at[index, "season"]),
                        "week": int(df.at[index, "week"]),
                    }
                )
                baseline_pool = (
                    history[: -(confirmation_games - 1)]
                    if confirmation_games > 1
                    else history
                )
                current_season = int(df.at[index, "season"])
                season_pool = [
                    item for item in baseline_pool if int(item["season"]) == current_season
                ]
                recent_pool = baseline_pool[-baseline_window:]
                if reset_each_season:
                    recent_pool = [
                        item for item in recent_pool if int(item["season"]) == current_season
                    ]

                values["confirmation_n"][index] = len(confirmation)
                values["baseline_n"][index] = len(recent_pool)
                values["season_baseline_n"][index] = len(season_pool)
                if prior_confirmation:
                    values["previous_metric"][index] = float(prior_confirmation[-1]["metric"])
                if recent_pool:
                    recent_value = float(np.mean([item["metric"] for item in recent_pool]))
                    values["recent_baseline_value"][index] = recent_value
                    values["baseline_mean_player_opportunities"][index] = float(
                        np.nanmean([item["raw"] for item in recent_pool])
                    )
                    values["baseline_mean_team_denominator"][index] = float(
                        np.nanmean([item["denominator"] for item in recent_pool])
                    )
                    values["baseline_max_week"][index] = float(
                        max(int(item["week"]) for item in recent_pool)
                    )
                    season_value = (
                        float(np.mean([item["metric"] for item in season_pool]))
                        if season_pool
                        else np.nan
                    )
                    values["season_baseline_value"][index] = season_value
                    if baseline_type == "recent":
                        baseline_value = recent_value
                    elif pd.notna(season_value):
                        baseline_value = recent_weight * recent_value + season_weight * season_value
                    else:
                        baseline_value = np.nan
                    values["baseline_value"][index] = baseline_value

                    if len(confirmation) == confirmation_games and pd.notna(baseline_value):
                        confirmation_metrics = np.array(
                            [item["metric"] for item in confirmation], dtype=float
                        )
                        confirmation_raw = np.array(
                            [item["raw"] for item in confirmation], dtype=float
                        )
                        confirmation_denominator = np.array(
                            [item["denominator"] for item in confirmation], dtype=float
                        )
                        detected_value = float(np.mean(confirmation_metrics))
                        detected_delta = detected_value - baseline_value
                        values["detected_value"][index] = detected_value
                        values["detected_delta"][index] = detected_delta
                        values["confirmation_min_player_opportunities"][index] = float(
                            np.nanmin(confirmation_raw)
                        )
                        values["confirmation_mean_player_opportunities"][index] = float(
                            np.nanmean(confirmation_raw)
                        )
                        values["confirmation_min_team_denominator"][index] = float(
                            np.nanmin(confirmation_denominator)
                        )
                        values["confirmation_mean_team_denominator"][index] = float(
                            np.nanmean(confirmation_denominator)
                        )
                        values["confirmation_start_week"][index] = float(
                            min(int(item["week"]) for item in confirmation)
                        )
                        values["confirmation_end_week"][index] = float(
                            max(int(item["week"]) for item in confirmation)
                        )
                        direction = np.sign(detected_delta)
                        component_directions = np.sign(confirmation_metrics - baseline_value)
                        values["strict_confirmation_pass"][index] = bool(
                            direction != 0 and np.all(component_directions == direction)
                        )
                        current_direction = np.sign(confirmation_metrics[-1] - baseline_value)
                        values["legacy_confirmation_pass"][index] = bool(
                            direction != 0 and current_direction == direction
                        )
                        values["feature_eligible"][index] = True

            if bool(history_eligible.iat[index]) and pd.notna(metric.iat[index]):
                history.append(
                    {
                        "metric": float(metric.iat[index]),
                        "raw": float(raw.iat[index]) if pd.notna(raw.iat[index]) else np.nan,
                        "denominator": (
                            float(denominator.iat[index])
                            if pd.notna(denominator.iat[index])
                            else np.nan
                        ),
                        "season": int(df.at[index, "season"]),
                        "week": int(df.at[index, "week"]),
                    }
                )

    for column, array in values.items():
        df[column] = array
    df["direction"] = np.select(
        [df["detected_delta"].gt(0), df["detected_delta"].lt(0)],
        ["increase", "decrease"],
        default="flat",
    )
    df["metric_column"] = metric_column
    return df


def _candidate_family_rows(
    data: pd.DataFrame,
    candidate: dict[str, Any],
    family: str,
    partial_policy: str,
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] | None = None,
) -> pd.DataFrame:
    baseline = candidate["baseline"]
    confirmation = candidate["confirmation"]
    safeguards = candidate.get("safeguards", {})
    confirmation_games = int(
        confirmation.get("te_target_share_games", confirmation["default_games"])
        if family == "te_target_share"
        else confirmation["default_games"]
    )
    metric_column = candidate.get("metric", "metric_normal")
    raw_column = (
        "raw_opportunities_normal"
        if metric_column == "metric_normal"
        else "raw_opportunities_all"
    )
    denominator_column = (
        "team_opportunities_normal"
        if metric_column == "metric_normal"
        else "team_opportunities_all"
    )
    cache_key = (
        "full",
        family,
        metric_column,
        raw_column,
        denominator_column,
        int(baseline["recent_games"]),
        confirmation_games,
        baseline["type"],
        float(baseline.get("recent_weight", 1.0)),
        float(baseline.get("season_weight", 0.0)),
        bool(baseline.get("reset_each_season", True)),
        partial_policy,
        bool(safeguards.get("require_data_quality", True)),
        bool(safeguards.get("require_qualifying_game", True)),
        bool(safeguards.get("history_uses_exclusion_policy", True)),
    )
    if feature_cache is not None and cache_key in feature_cache:
        featured = feature_cache[cache_key]
    else:
        featured = _disjoint_features(
            data.loc[data["role_family"].eq(family)].copy(),
            metric_column=metric_column,
            raw_opportunity_column=raw_column,
            team_denominator_column=denominator_column,
            baseline_window=int(baseline["recent_games"]),
            confirmation_games=confirmation_games,
            baseline_type=baseline["type"],
            recent_weight=float(baseline.get("recent_weight", 1.0)),
            season_weight=float(baseline.get("season_weight", 0.0)),
            reset_each_season=bool(baseline.get("reset_each_season", True)),
            partial_policy=partial_policy,
            require_quality=bool(safeguards.get("require_data_quality", True)),
            require_qualifying=bool(safeguards.get("require_qualifying_game", True)),
            history_uses_exclusion_policy=bool(
                safeguards.get("history_uses_exclusion_policy", True)
            ),
        )
        if feature_cache is not None:
            feature_cache[cache_key] = featured
    mask = (
        featured["feature_eligible"]
        & featured["baseline_n"].ge(int(baseline["min_games"]))
        & featured["confirmation_n"].eq(confirmation_games)
    )
    confirmation_mode = confirmation.get("mode", "strict")
    if confirmation_mode == "strict":
        mask &= featured["strict_confirmation_pass"]
    elif confirmation_mode == "legacy":
        mask &= featured["legacy_confirmation_pass"]
    elif confirmation_mode != "none":
        raise ValueError(f"Unknown confirmation mode: {confirmation_mode}")

    thresholds = candidate["thresholds"][family]
    threshold_mask = pd.Series(False, index=featured.index, dtype=bool)
    for direction in ("increase", "decrease"):
        rule = thresholds[direction]
        direction_mask = featured["direction"].eq(direction)
        if safeguards.get("require_min_abs_delta", True):
            direction_mask &= featured["detected_delta"].abs().ge(
                float(rule["min_abs_delta"])
            )
        reference = rule.get(
            "player_opportunity_reference",
            "confirmation_min" if direction == "increase" else "baseline_mean",
        )
        reference_column = {
            "confirmation_min": "confirmation_min_player_opportunities",
            "confirmation_mean": "confirmation_mean_player_opportunities",
            "baseline_mean": "baseline_mean_player_opportunities",
        }.get(reference)
        if reference_column is None:
            raise ValueError(f"Unknown opportunity reference: {reference}")
        if safeguards.get("require_player_opportunity_floor", True):
            direction_mask &= featured[reference_column].ge(
                float(rule.get("min_player_opportunities", 0))
            )
        if safeguards.get("require_team_denominator_floor", True):
            direction_mask &= featured["confirmation_min_team_denominator"].ge(
                float(rule.get("min_team_denominator", 0))
            )
        threshold_mask |= direction_mask
    selected = featured.loc[mask & threshold_mask].copy()
    selected["candidate_name"] = candidate["name"]
    selected["partial_policy"] = partial_policy
    selected["confirmation_games"] = confirmation_games
    selected["method"] = "full_propwar"
    selected["method_score"] = selected["detected_delta"]
    return selected


def _apply_repeat_suppression(
    full_alerts: pd.DataFrame,
    candidate: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    repeat = candidate.get("repeat_suppression", {})
    if not repeat.get("enabled", False) or full_alerts.empty:
        return full_alerts.copy(), pd.DataFrame(columns=[*CANONICAL_KEY, "suppression_reason"])
    scope = repeat.get("scope", "player_role_family")
    cooldown = int(repeat.get("cooldown_calendar_weeks", 1))
    direction_sensitive = bool(repeat.get("direction_sensitive", True))
    if scope == "player_role_family":
        group_columns = ["season", "player_id", "role_family"]
    elif scope == "player":
        group_columns = ["season", "player_id"]
    else:
        raise ValueError(f"Unknown repeat suppression scope: {scope}")
    if direction_sensitive:
        group_columns.append("direction")

    ordered = full_alerts.sort_values(
        [*group_columns, "week", "team", "role_family"]
    ).copy()
    keep_indices: list[int] = []
    suppressed_rows: list[dict[str, Any]] = []
    for _, group in ordered.groupby(group_columns, sort=False, dropna=False):
        last_emitted_week: int | None = None
        for index, row in group.iterrows():
            week = int(row["week"])
            if last_emitted_week is not None and week - last_emitted_week <= cooldown:
                suppressed_rows.append(
                    {
                        **{column: row[column] for column in CANONICAL_KEY},
                        "candidate_name": candidate["name"],
                        "direction": row["direction"],
                        "prior_emitted_week": last_emitted_week,
                        "suppression_reason": "REPEAT_ALERT_COOLDOWN",
                    }
                )
            else:
                keep_indices.append(index)
                last_emitted_week = week
    kept = full_alerts.loc[sorted(keep_indices)].copy()
    return kept, pd.DataFrame(suppressed_rows)


def build_full_candidate_alerts(
    data: pd.DataFrame,
    candidate: dict[str, Any],
    partial_policy: str = "PRIMARY_CONFIRMED_EXCLUDED",
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] | None = None,
    allowed_seasons: Iterable[int] = ALLOWED_REDEVELOPMENT_SEASONS,
    role_families: Iterable[str] = ROLE_FAMILIES,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a transparent full-detector alert set before comparator matching."""
    observed = set(pd.to_numeric(data["season"], errors="raise").astype(int).unique())
    allowed = {int(season) for season in allowed_seasons}
    if not allowed or not allowed.issubset(set(APPROVED_ROLE_VALIDATION_SEASONS)):
        raise ValueError(f"Invalid allowed seasons: {sorted(allowed)}")
    if not observed.issubset(allowed):
        raise AssertionError(f"Candidate input contains disallowed seasons: {sorted(observed)}")
    families = tuple(str(family) for family in role_families)
    if not families or not set(families).issubset(set(ROLE_FAMILIES)):
        raise ValueError(f"Invalid role-family scope: {families}")
    missing_families = set(families) - set(data["role_family"].astype(str).unique())
    if missing_families:
        raise AssertionError(f"Candidate input lacks scoped families: {sorted(missing_families)}")
    rows = [
        _candidate_family_rows(
            data, candidate, family, partial_policy, feature_cache=feature_cache
        )
        for family in families
    ]
    full = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return _apply_repeat_suppression(full, candidate)


def _comparator_features(
    family_data: pd.DataFrame,
    candidate: dict[str, Any],
    method: str,
    partial_policy: str,
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] | None = None,
) -> pd.DataFrame:
    baseline = candidate["baseline"]
    safeguards = candidate.get("safeguards", {})
    if method == "naive_spike":
        metric_column = "metric_all"
        confirmation_games = 1
    elif method == "two_week_raw":
        metric_column = "metric_all"
        confirmation_games = 2
    elif method == "normal_game_trend":
        metric_column = "metric_normal"
        confirmation_games = 2
    else:
        raise ValueError(f"Unsupported comparator method: {method}")
    suffix = "normal" if metric_column == "metric_normal" else "all"
    family = str(family_data["role_family"].iloc[0])
    cache_key = (
        "comparator",
        family,
        method,
        metric_column,
        int(baseline["recent_games"]),
        confirmation_games,
        baseline["type"],
        float(baseline.get("recent_weight", 1.0)),
        float(baseline.get("season_weight", 0.0)),
        bool(baseline.get("reset_each_season", True)),
        partial_policy,
        bool(safeguards.get("require_data_quality", True)),
        bool(safeguards.get("require_qualifying_game", True)),
        bool(safeguards.get("history_uses_exclusion_policy", True)),
    )
    if feature_cache is not None and cache_key in feature_cache:
        featured = feature_cache[cache_key].copy(deep=False)
    else:
        featured = _disjoint_features(
            family_data,
            metric_column=metric_column,
            raw_opportunity_column=f"raw_opportunities_{suffix}",
            team_denominator_column=f"team_opportunities_{suffix}",
            baseline_window=int(baseline["recent_games"]),
            confirmation_games=confirmation_games,
            baseline_type=baseline["type"],
            recent_weight=float(baseline.get("recent_weight", 1.0)),
            season_weight=float(baseline.get("season_weight", 0.0)),
            reset_each_season=bool(baseline.get("reset_each_season", True)),
            partial_policy=partial_policy,
            require_quality=bool(safeguards.get("require_data_quality", True)),
            require_qualifying=bool(safeguards.get("require_qualifying_game", True)),
            history_uses_exclusion_policy=bool(
                safeguards.get("history_uses_exclusion_policy", True)
            ),
        )
        if feature_cache is not None:
            feature_cache[cache_key] = featured
        featured = featured.copy(deep=False)
    featured["method_eligible"] = (
        featured["feature_eligible"]
        & featured["baseline_n"].ge(int(baseline["min_games"]))
        & featured["confirmation_n"].eq(confirmation_games)
        & featured["detected_delta"].notna()
    )
    featured["method"] = method
    featured["method_score"] = featured["detected_delta"]
    featured["candidate_name"] = candidate["name"]
    featured["partial_policy"] = partial_policy
    featured["confirmation_games"] = confirmation_games
    return featured


def select_equal_volume_candidate_comparators(
    data: pd.DataFrame,
    candidate: dict[str, Any],
    full_alerts: pd.DataFrame,
    partial_policy: str = "PRIMARY_CONFIRMED_EXCLUDED",
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] | None = None,
    role_families: Iterable[str] = ROLE_FAMILIES,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Match every comparator to the full candidate count within family-week.

    Zero-alert family-weeks are written to the verification table rather than
    silently omitted.
    """
    output = [full_alerts.copy()]
    verification_rows: list[dict[str, Any]] = []
    weeks = (
        data[["season", "week"]]
        .drop_duplicates()
        .sort_values(["season", "week"])
        .itertuples(index=False, name=None)
    )
    week_pairs = [(int(season), int(week)) for season, week in weeks]
    full_counts = (
        full_alerts.groupby(["role_family", "season", "week"]).size().to_dict()
        if not full_alerts.empty
        else {}
    )

    families = tuple(str(family) for family in role_families)
    if not families or not set(families).issubset(set(ROLE_FAMILIES)):
        raise ValueError(f"Invalid role-family scope: {families}")
    for family in families:
        family_data = data.loc[data["role_family"].eq(family)].copy()
        method_frames = {
            method: _comparator_features(
                family_data,
                candidate,
                method,
                partial_policy,
                feature_cache=feature_cache,
            )
            for method in EXPECTED_METHODS
            if method != "full_propwar"
        }
        selected_counts: dict[tuple[int, int, str], int] = {}
        for method, featured in method_frames.items():
            candidates = featured.loc[featured["method_eligible"]].copy()
            candidates["_abs_score"] = candidates["method_score"].abs()
            candidates = candidates.sort_values(
                ["season", "week", "_abs_score", "player_id", "team"],
                ascending=[True, True, False, True, True],
            )
            for season, week in week_pairs:
                n_alerts = int(full_counts.get((family, season, week), 0))
                if n_alerts == 0:
                    selected_counts[(season, week, method)] = 0
                    continue
                pool = candidates.loc[
                    candidates["season"].eq(season) & candidates["week"].eq(week)
                ]
                if len(pool) < n_alerts:
                    raise RuntimeError(
                        f"Equal-volume selection impossible for {candidate['name']} "
                        f"{family} {season} week {week} {method}: "
                        f"need {n_alerts}, have {len(pool)}."
                    )
                chosen = pool.head(n_alerts).drop(columns="_abs_score")
                selected_counts[(season, week, method)] = len(chosen)
                output.append(chosen)

        for season, week in week_pairs:
            target = int(full_counts.get((family, season, week), 0))
            method_counts = {
                "full_propwar": target,
                **{
                    method: int(selected_counts.get((season, week, method), 0))
                    for method in EXPECTED_METHODS
                    if method != "full_propwar"
                },
            }
            verification_rows.append(
                {
                    "candidate_name": candidate["name"],
                    "partial_policy": partial_policy,
                    "role_family": family,
                    "season": season,
                    "week": week,
                    **{f"{method}_count": method_counts[method] for method in EXPECTED_METHODS},
                    "expected_method_count": len(EXPECTED_METHODS),
                    "observed_method_count": len(method_counts),
                    "equal_volume": len(set(method_counts.values())) == 1,
                }
            )
    alerts = pd.concat(output, ignore_index=True) if output else pd.DataFrame()
    verification = pd.DataFrame(verification_rows)
    if not verification["equal_volume"].all():
        raise AssertionError(f"Equal-volume verification failed for {candidate['name']}")
    if not verification["observed_method_count"].eq(len(EXPECTED_METHODS)).all():
        raise AssertionError(f"A comparator method is missing for {candidate['name']}")
    return alerts, verification


def evaluate_candidate_alerts(
    alerts: pd.DataFrame,
    data: pd.DataFrame,
    *,
    partial_policy: str,
    horizon: int = 2,
    retention_threshold: float = 0.50,
    reversion_threshold: float = 0.25,
    allowed_seasons: Iterable[int] = ALLOWED_REDEVELOPMENT_SEASONS,
) -> pd.DataFrame:
    if alerts.empty:
        return alerts.copy()
    evaluation_data = data.copy()
    evaluation_data["partial_game_flag"] = partial_exclusion_mask(
        evaluation_data, partial_policy
    )
    lookup = build_future_outcome_lookup(
        evaluation_data,
        metric_column="metric_normal",
        horizon=horizon,
    )
    evaluated = attach_future_outcomes(
        alerts,
        full_weekly=evaluation_data,
        metric_column="metric_normal",
        horizon=horizon,
        retention_threshold=retention_threshold,
        reversion_threshold=reversion_threshold,
        future_lookup=lookup,
    )
    observed = set(pd.to_numeric(evaluated["season"], errors="raise").astype(int).unique())
    allowed = {int(season) for season in allowed_seasons}
    if not observed.issubset(allowed):
        raise AssertionError(f"Evaluation produced disallowed seasons: {sorted(observed)}")
    return evaluated


def run_candidate(
    data: pd.DataFrame,
    candidate: dict[str, Any],
    *,
    partial_policy: str = "PRIMARY_CONFIRMED_EXCLUDED",
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] | None = None,
    allowed_seasons: Iterable[int] = ALLOWED_REDEVELOPMENT_SEASONS,
    role_families: Iterable[str] = ROLE_FAMILIES,
) -> dict[str, pd.DataFrame]:
    """Build, equal-volume match, and evaluate one candidate deterministically."""
    full, suppressed = build_full_candidate_alerts(
        data,
        candidate,
        partial_policy,
        feature_cache=feature_cache,
        allowed_seasons=allowed_seasons,
        role_families=role_families,
    )
    alerts, equal_volume = select_equal_volume_candidate_comparators(
        data,
        candidate,
        full,
        partial_policy,
        feature_cache=feature_cache,
        role_families=role_families,
    )
    evaluated = evaluate_candidate_alerts(
        alerts,
        data,
        partial_policy=partial_policy,
        allowed_seasons=allowed_seasons,
    )
    return {
        "alerts": evaluated,
        "equal_volume": equal_volume,
        "suppressed": suppressed,
    }


def clone_candidate(candidate: dict[str, Any], name: str, **updates: Any) -> dict[str, Any]:
    """Small helper for deterministic one-factor screening configurations."""
    result = deepcopy(candidate)
    result["name"] = name
    for dotted_path, value in updates.items():
        target = result
        parts = dotted_path.split("__")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    return result
