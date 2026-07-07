from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.common import output_path, project_path


PROFILE_PATH = project_path("config", "signal_weight_profiles.yaml")
COMPONENTS = [
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
]
FAMILIES = ["receiving", "rushing", "passing"]
BUCKETS = [0, 40, 55, 70, 85, 101]
BUCKET_LABELS = ["0-39", "40-54", "55-69", "70-84", "85-100"]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def load_profiles() -> dict:
    with PROFILE_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_weights(weights: dict[str, float], available: list[str]) -> dict[str, float]:
    filtered = {key: float(weights.get(key, 0.0)) for key in available}
    total = sum(value for value in filtered.values() if value > 0)
    if total <= 0:
        return {key: 0.0 for key in available}
    return {key: value / total for key, value in filtered.items()}


def tier_from_score(score: object) -> str:
    value = pd.to_numeric(score, errors="coerce")
    if pd.isna(value):
        return "INSUFFICIENT_DATA"
    if value >= 85:
        return "ELITE_SIGNAL"
    if value >= 72:
        return "STRONG_SIGNAL"
    if value >= 58:
        return "GOOD_SIGNAL"
    if value >= 40:
        return "WATCH"
    return "REVIEW"


def score_rows(rows: pd.DataFrame, profile_name: str, family: str, weights: dict[str, float]) -> pd.DataFrame:
    data = rows[rows["market_family"].astype(str).eq(family)].copy()
    if data.empty:
        return data
    available = [component for component in COMPONENTS if component in data.columns]
    normalized = normalize_weights(weights, available)
    numerator = pd.Series(0.0, index=data.index)
    denominator = pd.Series(0.0, index=data.index)
    for component, weight in normalized.items():
        values = pd.to_numeric(data[component], errors="coerce")
        mask = values.notna()
        numerator += values.fillna(0) * weight
        denominator += mask.astype(float) * weight
    data["profile_name"] = profile_name
    data["challenger_signal_score"] = (numerator / denominator.replace(0, pd.NA)).round(2)
    data["challenger_signal_tier"] = data["challenger_signal_score"].map(tier_from_score)
    data["dominant_component"] = max(normalized, key=normalized.get) if normalized else ""
    data["dominant_component_weight"] = max(normalized.values()) if normalized else 0.0
    return data


def monotonicity_status(group: pd.DataFrame) -> str:
    bucketed = group.copy()
    bucketed["score_bucket"] = pd.cut(pd.to_numeric(bucketed["challenger_signal_score"], errors="coerce"), BUCKETS, labels=BUCKET_LABELS, right=False)
    averages = []
    for bucket in BUCKET_LABELS:
        rows = bucketed[bucketed["score_bucket"].astype(str).eq(bucket)]
        averages.append(pd.to_numeric(rows["actual_primary_value"], errors="coerce").mean() if len(rows) else pd.NA)
    clean = [value for value in averages if pd.notna(value)]
    if len(clean) < 3:
        return "LOW_SAMPLE"
    return "PASS" if all(right >= left for left, right in zip(clean, clean[1:])) else "CHECK"


def evaluate_profile(scored: pd.DataFrame) -> dict[str, object]:
    actual = pd.to_numeric(scored["actual_primary_value"], errors="coerce")
    score = pd.to_numeric(scored["challenger_signal_score"], errors="coerce")
    strong_mask = scored["challenger_signal_tier"].isin(["ELITE_SIGNAL", "STRONG_SIGNAL"])
    watch_mask = scored["challenger_signal_tier"].isin(["WATCH", "REVIEW", "INSUFFICIENT_DATA", "BLOCKED"])
    top_cut = score.quantile(0.75)
    bottom_cut = score.quantile(0.25)
    top_actual = actual[score >= top_cut]
    bottom_actual = actual[score <= bottom_cut]
    elite_count = int(strong_mask.sum())
    tier_lift = actual[strong_mask].mean() - actual[watch_mask].mean() if strong_mask.any() and watch_mask.any() else pd.NA
    top_lift = top_actual.mean() - bottom_actual.mean() if len(top_actual) and len(bottom_actual) else pd.NA
    low_sample = elite_count < 50
    overfit_flags = []
    if elite_count < 25:
        overfit_flags.append("TINY_TOP_TIER")
    if scored["dominant_component_weight"].max() > 0.50:
        overfit_flags.append("ONE_COMPONENT_DOMINATES")
    mono = monotonicity_status(scored)
    if mono != "PASS":
        overfit_flags.append("NON_MONOTONIC_OR_LOW_SAMPLE")
    return {
        "profile_name": str(scored["profile_name"].iloc[0]),
        "market_family": str(scored["market_family"].iloc[0]),
        "row_count": len(scored),
        "score_actual_correlation": score.corr(actual),
        "spearman_score_actual_correlation": score.corr(actual, method="spearman") if score.nunique(dropna=True) > 1 and actual.nunique(dropna=True) > 1 else pd.NA,
        "elite_or_strong_count": elite_count,
        "elite_or_strong_average_actual": actual[strong_mask].mean(),
        "watch_or_review_average_actual": actual[watch_mask].mean(),
        "tier_lift": tier_lift,
        "top_quartile_average_actual": top_actual.mean(),
        "bottom_quartile_average_actual": bottom_actual.mean(),
        "top_vs_bottom_lift": top_lift,
        "monotonicity_status": mono,
        "low_sample_warning": "YES" if low_sample else "NO",
        "overfit_risk_flag": "; ".join(overfit_flags) if overfit_flags else "LOW",
        "dominant_component": str(scored["dominant_component"].iloc[0]),
        "dominant_component_weight": float(scored["dominant_component_weight"].iloc[0]),
    }


def tier_lift_rows(scored_all: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (profile, family, tier), group in scored_all.groupby(["profile_name", "market_family", "challenger_signal_tier"]):
        actual = pd.to_numeric(group["actual_primary_value"], errors="coerce")
        family_base = pd.to_numeric(scored_all[scored_all["market_family"].eq(family)]["actual_primary_value"], errors="coerce").mean()
        rows.append(
            {
                "profile_name": profile,
                "market_family": family,
                "challenger_signal_tier": tier,
                "row_count": len(group),
                "average_challenger_score": pd.to_numeric(group["challenger_signal_score"], errors="coerce").mean(),
                "average_actual_primary_value": actual.mean(),
                "baseline_average_actual": family_base,
                "lift_vs_baseline": actual.mean() - family_base,
            }
        )
    return pd.DataFrame(rows)


def compare_to_champion(results: pd.DataFrame) -> pd.DataFrame:
    champion = results[results["profile_name"].eq("current_v1")].set_index("market_family")
    rows = []
    for _, row in results.iterrows():
        family = row["market_family"]
        if family not in champion.index:
            continue
        champ = champion.loc[family]
        delta_tier = row["tier_lift"] - champ["tier_lift"]
        delta_corr = row["spearman_score_actual_correlation"] - champ["spearman_score_actual_correlation"]
        delta_top = row["top_vs_bottom_lift"] - champ["top_vs_bottom_lift"]
        delta_mono = "SAME"
        if row["monotonicity_status"] == "PASS" and champ["monotonicity_status"] != "PASS":
            delta_mono = "IMPROVED"
        elif row["monotonicity_status"] != "PASS" and champ["monotonicity_status"] == "PASS":
            delta_mono = "WORSE"
        if row["profile_name"] == "current_v1":
            recommendation = "KEEP_CURRENT"
        elif row["low_sample_warning"] == "YES":
            recommendation = "NEEDS_MORE_DATA"
        elif row["monotonicity_status"] != "PASS" or "ONE_COMPONENT_DOMINATES" in str(row["overfit_risk_flag"]):
            recommendation = "DO_NOT_USE"
        elif pd.to_numeric(delta_tier, errors="coerce") > 0 and pd.to_numeric(delta_corr, errors="coerce") >= -0.01 and pd.to_numeric(delta_top, errors="coerce") >= 0:
            recommendation = "TEST_CHALLENGER"
        else:
            recommendation = "KEEP_CURRENT"
        rows.append(
            {
                "profile_name": row["profile_name"],
                "market_family": family,
                "delta_tier_lift": delta_tier,
                "delta_score_correlation": delta_corr,
                "delta_top_vs_bottom_lift": delta_top,
                "delta_monotonicity": delta_mono,
                "recommendation": recommendation,
                "notes": "Champion remains current_v1 unless a challenger is explicitly promoted later.",
            }
        )
    out = pd.DataFrame(rows)
    for profile, group in out.groupby("profile_name"):
        if profile == "current_v1":
            continue
        improved = int(group["recommendation"].eq("TEST_CHALLENGER").sum())
        worse = int(group["recommendation"].eq("DO_NOT_USE").sum() + group["delta_score_correlation"].lt(-0.02).sum())
        if improved == 1 and worse >= 2:
            out.loc[out["profile_name"].eq(profile), "recommendation"] = out.loc[out["profile_name"].eq(profile), "recommendation"].replace("TEST_CHALLENGER", "DO_NOT_USE")
            out.loc[out["profile_name"].eq(profile), "notes"] = "Profile worsens multiple families while improving one; do not promote."
    return out


def component_recommendations(component_audit: pd.DataFrame, profiles: dict, correlations: pd.DataFrame) -> pd.DataFrame:
    current = profiles["profiles"]["current_v1"]
    risk_components = set()
    if not correlations.empty and "double_count_risk" in correlations.columns:
        risky = correlations[correlations["double_count_risk"].astype(str).str.lower().eq("true")]
        risk_components.update(risky.get("component_a", pd.Series(dtype=str)).astype(str).tolist())
        risk_components.update(risky.get("component_b", pd.Series(dtype=str)).astype(str).tolist())
    rows = []
    for _, row in component_audit.iterrows():
        family = str(row["market_family"])
        component = str(row["component_name"])
        flag = str(row.get("usefulness_flag", ""))
        current_weight = float(current.get(family, {}).get(component, 0.0))
        risk = component in risk_components
        if flag == "USEFUL" and current_weight < 0.25:
            recommendation = "increase_weight"
        elif flag in {"NOISY", "INVERTED"} and component == "opponent_fit_score":
            recommendation = "reduce_weight"
        elif flag in {"NOISY", "INVERTED"}:
            recommendation = "reduce_weight"
        elif flag == "LOW_SAMPLE":
            recommendation = "needs_more_data"
        elif risk and flag != "USEFUL":
            recommendation = "family_specific_only"
        else:
            recommendation = "keep"
        rows.append(
            {
                "recommendation_scope": "component",
                "component_name": component,
                "market_family": family,
                "current_weight": current_weight,
                "historical_usefulness_flag": flag,
                "correlation_with_actual": row.get("correlation_with_actual"),
                "double_count_risk": risk,
                "recommendation": recommendation,
                "notes": "Opponent fit should be reliability-gated or reduced when noisy; no production change applied.",
            }
        )
    return pd.DataFrame(rows)


def recommendation_file(results: pd.DataFrame, comparisons: pd.DataFrame, profiles: dict) -> tuple[str, dict]:
    recommended = {"profiles": {"recommended_challenger_v1": {"notes": "Research-only challenger; not applied to production."}}}
    best_by_family = {}
    for family in FAMILIES:
        candidates = comparisons[(comparisons["market_family"].eq(family)) & (comparisons["recommendation"].eq("TEST_CHALLENGER"))]
        if candidates.empty:
            best_profile = "current_v1"
        else:
            candidates = candidates.sort_values(["delta_tier_lift", "delta_score_correlation"], ascending=[False, False])
            best_profile = str(candidates.iloc[0]["profile_name"])
        best_by_family[family] = best_profile
        recommended["profiles"]["recommended_challenger_v1"][family] = profiles["profiles"][best_profile][family]
    header = (
        "# Research-only recommendation.\n"
        "# Not applied to production signal master unless explicitly promoted later.\n"
        "# Generated from 2023-2024 historical signal backtest.\n"
    )
    text = header + yaml.safe_dump(recommended, sort_keys=False)
    output_path("signal_boards/recommended_signal_weight_profile.yaml").write_text(text, encoding="utf-8")
    return text, best_by_family


def export_signal_weight_tuning() -> dict[str, pd.DataFrame]:
    profiles = load_profiles()
    rows = read_csv("signal_boards/historical_signal_backtest_rows.csv")
    component = read_csv("signal_boards/historical_signal_component_audit.csv")
    family_audit = read_csv("signal_boards/historical_signal_market_family_audit.csv")
    correlations = read_csv("signal_boards/signal_score_component_correlations.csv")
    if rows.empty:
        raise RuntimeError("Historical signal backtest rows are required before weight tuning.")
    scored_frames = []
    result_rows = []
    for profile_name, profile in profiles["profiles"].items():
        for family in FAMILIES:
            weights = profile.get(family, {})
            scored = score_rows(rows, profile_name, family, weights)
            if scored.empty:
                continue
            scored_frames.append(scored)
            result_rows.append(evaluate_profile(scored))
    scored_all = pd.concat(scored_frames, ignore_index=True, sort=False)
    results = pd.DataFrame(result_rows)
    comparisons = compare_to_champion(results)
    tier_lift = tier_lift_rows(scored_all)
    comp_recs = component_recommendations(component, profiles, correlations)
    profile_recs = comparisons.copy()
    profile_recs["recommendation_scope"] = "profile"
    profile_recs["component_name"] = ""
    profile_recs["current_weight"] = pd.NA
    profile_recs["historical_usefulness_flag"] = ""
    profile_recs["correlation_with_actual"] = profile_recs["delta_score_correlation"]
    profile_recs["double_count_risk"] = False
    recommendations = pd.concat([profile_recs, comp_recs], ignore_index=True, sort=False)
    yaml_text, best_by_family = recommendation_file(results, comparisons, profiles)
    results.to_csv(output_path("signal_boards/signal_weight_tuning_results.csv"), index=False)
    comparisons.to_csv(output_path("signal_boards/signal_weight_tuning_by_family.csv"), index=False)
    tier_lift.to_csv(output_path("signal_boards/signal_weight_tuning_tier_lift.csv"), index=False)
    recommendations.to_csv(output_path("signal_boards/signal_weight_tuning_recommendations.csv"), index=False)
    write_report(results, comparisons, recommendations, best_by_family, family_audit)
    return {"results": results, "comparisons": comparisons, "tier_lift": tier_lift, "recommendations": recommendations}


def write_report(results: pd.DataFrame, comparisons: pd.DataFrame, recommendations: pd.DataFrame, best_by_family: dict[str, str], family_audit: pd.DataFrame) -> None:
    tested = ", ".join(sorted(results["profile_name"].dropna().unique()))
    text = f"""# Signal Weight Tuning Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Audit type: `RESEARCH ONLY / CHALLENGER PROFILES`

Profiles tested: `{tested}`

Families tested: `{', '.join(FAMILIES)}`

Best challenger by family:

{chr(10).join(f"- `{family}`: `{profile}`" for family, profile in best_by_family.items())}

Recommendations rows: `{len(recommendations)}`

Production status: `current_v1 remains champion; no production weights changed`

Notes:

- Actual outcomes are used only for evaluation.
- Pregame component scores are reused from historical signal backtest rows.
- Challenger profiles are saved for review only.
"""
    output_path("run_reports/latest_signal_weight_tuning_report.md").write_text(text, encoding="utf-8")


def main() -> None:
    outputs = export_signal_weight_tuning()
    print(f"signal_weight_tuning_results: {len(outputs['results']):,} rows")
    print(f"signal_weight_tuning_by_family: {len(outputs['comparisons']):,} rows")
    print(f"signal_weight_tuning_tier_lift: {len(outputs['tier_lift']):,} rows")
    print(f"signal_weight_tuning_recommendations: {len(outputs['recommendations']):,} rows")


if __name__ == "__main__":
    main()
