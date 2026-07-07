from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from src.common import output_path, project_path
from src.export.export_player_week_signal_master import signal_tier
from src.export.signal_explainability import recommended_action


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
FAMILY_AVAILABLE_COLUMNS = {
    "receiving": "receiving_market_available",
    "rushing": "rushing_market_available",
    "passing": "passing_market_available",
}
TIER_RANK = {
    "BLOCKED": 0,
    "INSUFFICIENT_DATA": 1,
    "REVIEW": 2,
    "WATCH": 3,
    "GOOD_SIGNAL": 4,
    "STRONG_SIGNAL": 5,
    "ELITE_SIGNAL": 6,
}


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


def selected_profiles(recommendations: pd.DataFrame) -> dict[str, str]:
    selections = {family: "current_v1" for family in FAMILIES}
    if recommendations.empty:
        return selections
    profile_rows = recommendations[
        recommendations.get("recommendation_scope", pd.Series(dtype=str)).fillna("").astype(str).eq("profile")
        & recommendations.get("recommendation", pd.Series(dtype=str)).fillna("").astype(str).eq("TEST_CHALLENGER")
    ].copy()
    for family in FAMILIES:
        candidates = profile_rows[profile_rows["market_family"].astype(str).eq(family)]
        if candidates.empty:
            continue
        candidates = candidates.sort_values(["delta_tier_lift", "delta_score_correlation"], ascending=[False, False])
        selections[family] = str(candidates.iloc[0]["profile_name"])
    return selections


def row_families(row: pd.Series) -> list[str]:
    families = []
    for family, column in FAMILY_AVAILABLE_COLUMNS.items():
        if str(row.get(column, "")).lower() == "true":
            families.append(family)
    if families:
        return families
    raw = str(row.get("market_family", "") or "")
    return [family for family in FAMILIES if family in raw]


def score_with_profile(row: pd.Series, weights: dict[str, float]) -> float | pd.NA:
    available = [component for component in COMPONENTS if component in row.index]
    normalized = normalize_weights(weights, available)
    numerator = 0.0
    denominator = 0.0
    for component, weight in normalized.items():
        value = pd.to_numeric(row.get(component), errors="coerce")
        if pd.isna(value) or weight <= 0:
            continue
        numerator += float(value) * weight
        denominator += weight
    if denominator <= 0:
        return pd.NA
    return round(numerator / denominator, 2)


def tier_change(current: object, challenger: object) -> str:
    current_rank = TIER_RANK.get(str(current).upper(), -1)
    challenger_rank = TIER_RANK.get(str(challenger).upper(), -1)
    if challenger_rank > current_rank:
        return "TIER_UPGRADE"
    if challenger_rank < current_rank:
        return "TIER_DOWNGRADE"
    return "NO_TIER_CHANGE"


def preview_flag(delta: object, tier_status: str, action_changed: bool) -> str:
    value = pd.to_numeric(delta, errors="coerce")
    flags = []
    if pd.notna(value) and value >= 5:
        flags.append("BIG_UPGRADE")
    elif pd.notna(value) and value <= -5:
        flags.append("BIG_DOWNGRADE")
    if tier_status == "TIER_UPGRADE":
        flags.append("TIER_UPGRADE")
    elif tier_status == "TIER_DOWNGRADE":
        flags.append("TIER_DOWNGRADE")
    if action_changed:
        flags.append("ACTION_CHANGED")
    return "|".join(flags) if flags else "NO_MEANINGFUL_CHANGE"


def build_preview_rows(master: pd.DataFrame, profiles: dict, selections: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, source in master.iterrows():
        for family in row_families(source):
            profile_name = selections.get(family, "current_v1")
            weights = profiles["profiles"][profile_name][family]
            challenger_score = score_with_profile(source, weights)
            challenger_row = source.copy()
            challenger_row["overall_signal_score"] = challenger_score
            for text_col in ["blocked_reason", "review_reason"]:
                if text_col in challenger_row.index and pd.isna(challenger_row.get(text_col)):
                    challenger_row[text_col] = ""
            challenger_tier = signal_tier(challenger_row)
            challenger_row["signal_tier"] = challenger_tier
            challenger_action = recommended_action(challenger_row)
            current_score = pd.to_numeric(source.get("overall_signal_score"), errors="coerce")
            delta = round(float(challenger_score) - float(current_score), 2) if pd.notna(challenger_score) and pd.notna(current_score) else pd.NA
            tier_status = tier_change(source.get("signal_tier"), challenger_tier)
            current_action = str(source.get("recommended_user_action", "") or "")
            action_changed = current_action != challenger_action
            record = {key: value for key, value in source.to_dict().items() if key != "live_betting_output_created"}
            record.update(
                {
                    "market_family": family,
                    "preview_usage_status": "RESEARCH_ONLY",
                    "production_champion_profile": "current_v1",
                    "challenger_profile_name": profile_name,
                    "current_overall_signal_score": source.get("overall_signal_score"),
                    "current_signal_tier": source.get("signal_tier"),
                    "current_recommended_user_action": current_action,
                    "challenger_overall_signal_score": challenger_score,
                    "challenger_signal_tier": challenger_tier,
                    "challenger_recommended_user_action": challenger_action,
                    "signal_score_delta": delta,
                    "tier_change": tier_status,
                    "action_change": "ACTION_CHANGED" if action_changed else "NO_ACTION_CHANGE",
                    "preview_flag": preview_flag(delta, tier_status, action_changed),
                    "preview_notes": "RESEARCH_ONLY challenger preview; production signal boards remain current_v1.",
                }
            )
            rows.append(record)
    return pd.DataFrame(rows)


def family_summary(preview: pd.DataFrame, tuning: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for family, group in preview.groupby("market_family"):
        current_score = pd.to_numeric(group["current_overall_signal_score"], errors="coerce")
        challenger_score = pd.to_numeric(group["challenger_overall_signal_score"], errors="coerce")
        tier_up = int(group["tier_change"].eq("TIER_UPGRADE").sum())
        tier_down = int(group["tier_change"].eq("TIER_DOWNGRADE").sum())
        action_changes = int(group["action_change"].eq("ACTION_CHANGED").sum())
        challenger_profile = str(group["challenger_profile_name"].iloc[0])
        tuning_row = tuning[(tuning["market_family"].astype(str).eq(family)) & (tuning["profile_name"].astype(str).eq(challenger_profile))]
        tuning_rec = str(tuning_row["recommendation"].iloc[0]) if not tuning_row.empty else "KEEP_CURRENT"
        if challenger_profile == "current_v1":
            recommendation = "KEEP_CHAMPION"
        elif tier_down > tier_up or action_changes > len(group) * 0.35:
            recommendation = "DO_NOT_PROMOTE"
        elif tuning_rec == "TEST_CHALLENGER" and tier_up >= tier_down:
            recommendation = "CONTINUE_TESTING_CHALLENGER"
        else:
            recommendation = "KEEP_CHAMPION"
        rows.append(
            {
                "market_family": family,
                "champion_profile": "current_v1",
                "challenger_profile": challenger_profile,
                "row_count": len(group),
                "avg_current_score": round(float(current_score.mean()), 4) if current_score.notna().any() else pd.NA,
                "avg_challenger_score": round(float(challenger_score.mean()), 4) if challenger_score.notna().any() else pd.NA,
                "avg_score_delta": round(float((challenger_score - current_score).mean()), 4) if current_score.notna().any() else pd.NA,
                "current_elite_strong_count": int(group["current_signal_tier"].isin(["ELITE_SIGNAL", "STRONG_SIGNAL"]).sum()),
                "challenger_elite_strong_count": int(group["challenger_signal_tier"].isin(["ELITE_SIGNAL", "STRONG_SIGNAL"]).sum()),
                "tier_upgrade_count": tier_up,
                "tier_downgrade_count": tier_down,
                "action_change_count": action_changes,
                "preview_recommendation": recommendation,
                "notes": "Preview only; no automatic production promotion.",
            }
        )
    return pd.DataFrame(rows)


def compact_summary(preview: pd.DataFrame, family: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"metric": "preview_usage_status", "value": "RESEARCH_ONLY"},
            {"metric": "production_champion_profile", "value": "current_v1"},
            {"metric": "rows_previewed", "value": len(preview)},
            {"metric": "families_with_challenger_test", "value": int(family["challenger_profile"].ne("current_v1").sum()) if not family.empty else 0},
            {"metric": "tier_upgrades", "value": int(preview["tier_change"].eq("TIER_UPGRADE").sum()) if not preview.empty else 0},
            {"metric": "tier_downgrades", "value": int(preview["tier_change"].eq("TIER_DOWNGRADE").sum()) if not preview.empty else 0},
            {"metric": "action_changes", "value": int(preview["action_change"].eq("ACTION_CHANGED").sum()) if not preview.empty else 0},
            {"metric": "production_promotion_applied", "value": "False"},
        ]
    )


def top_movers(preview: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "player_id",
        "player_name",
        "team",
        "opponent",
        "position",
        "market_family",
        "current_overall_signal_score",
        "challenger_overall_signal_score",
        "signal_score_delta",
        "current_signal_tier",
        "challenger_signal_tier",
        "tier_change",
        "current_recommended_user_action",
        "challenger_recommended_user_action",
        "top_positive_driver_1",
        "top_negative_driver_1",
        "preview_flag",
        "preview_notes",
    ]
    if preview.empty:
        return pd.DataFrame(columns=columns)
    out = preview.copy()
    out["_abs_delta"] = pd.to_numeric(out["signal_score_delta"], errors="coerce").abs()
    return out.sort_values("_abs_delta", ascending=False)[[col for col in columns if col in out.columns]]


def tier_changes(preview: pd.DataFrame) -> pd.DataFrame:
    if preview.empty:
        return preview
    mask = preview["tier_change"].ne("NO_TIER_CHANGE") | preview["action_change"].eq("ACTION_CHANGED")
    columns = [
        "player_id",
        "player_name",
        "team",
        "opponent",
        "position",
        "market_family",
        "production_champion_profile",
        "challenger_profile_name",
        "current_overall_signal_score",
        "challenger_overall_signal_score",
        "signal_score_delta",
        "current_signal_tier",
        "challenger_signal_tier",
        "tier_change",
        "current_recommended_user_action",
        "challenger_recommended_user_action",
        "action_change",
        "preview_usage_status",
        "preview_notes",
    ]
    return preview[mask].copy()[[col for col in columns if col in preview.columns]]


def board_outputs(preview: pd.DataFrame) -> dict[str, pd.DataFrame]:
    def sort_board(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        return frame.sort_values(["challenger_overall_signal_score", "current_overall_signal_score"], ascending=[False, False])

    boards = {
        "challenger_slate_signal_board": sort_board(preview).head(250),
        "challenger_receiving_signal_board": sort_board(preview[preview["market_family"].eq("receiving")].copy()),
        "challenger_rushing_signal_board": sort_board(preview[preview["market_family"].eq("rushing")].copy()),
        "challenger_passing_signal_board": sort_board(preview[preview["market_family"].eq("passing")].copy()),
    }
    for name, frame in boards.items():
        frame.to_csv(output_path(f"signal_boards/{name}.csv"), index=False)
    return boards


def write_report(preview: pd.DataFrame, family: pd.DataFrame, selections: dict[str, str]) -> None:
    best_lines = "\n".join(f"- `{family_name}`: `{profile}`" for family_name, profile in selections.items())
    text = f"""# Champion vs Challenger Signal Preview

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Preview status: `RESEARCH_ONLY`

Production champion: `current_v1`

Selected challenger profiles:

{best_lines}

Rows previewed: `{len(preview)}`

Tier upgrades: `{int(preview["tier_change"].eq("TIER_UPGRADE").sum()) if not preview.empty else 0}`

Tier downgrades: `{int(preview["tier_change"].eq("TIER_DOWNGRADE").sum()) if not preview.empty else 0}`

Action changes: `{int(preview["action_change"].eq("ACTION_CHANGED").sum()) if not preview.empty else 0}`

Family comparison rows: `{len(family)}`

Production status: `No challenger profile promoted; player_week_signal_master remains current_v1.`
"""
    output_path("run_reports/latest_signal_challenger_preview_report.md").write_text(text, encoding="utf-8")


def export_signal_challenger_preview() -> dict[str, pd.DataFrame]:
    master = read_csv("signal_boards/player_week_signal_master.csv")
    recommendations = read_csv("signal_boards/signal_weight_tuning_recommendations.csv")
    tuning_by_family = read_csv("signal_boards/signal_weight_tuning_by_family.csv")
    profiles = load_profiles()
    if master.empty:
        raise RuntimeError("player_week_signal_master.csv is required before challenger preview.")
    selections = selected_profiles(recommendations)
    preview = build_preview_rows(master, profiles, selections)
    family = family_summary(preview, tuning_by_family)
    summary = compact_summary(preview, family)
    movers = top_movers(preview)
    changes = tier_changes(preview)
    preview.to_csv(output_path("signal_boards/signal_challenger_preview_rows.csv"), index=False)
    summary.to_csv(output_path("signal_boards/signal_challenger_preview_summary.csv"), index=False)
    movers.to_csv(output_path("signal_boards/signal_challenger_top_movers.csv"), index=False)
    changes.to_csv(output_path("signal_boards/signal_challenger_tier_changes.csv"), index=False)
    family.to_csv(output_path("signal_boards/signal_challenger_family_comparison.csv"), index=False)
    boards = board_outputs(preview)
    write_report(preview, family, selections)
    return {"preview": preview, "summary": summary, "movers": movers, "changes": changes, "family": family, **boards}


def main() -> None:
    outputs = export_signal_challenger_preview()
    print(f"signal_challenger_preview_rows: {len(outputs['preview']):,} rows")
    print(f"signal_challenger_preview_summary: {len(outputs['summary']):,} rows")
    print(f"signal_challenger_top_movers: {len(outputs['movers']):,} rows")
    print(f"signal_challenger_tier_changes: {len(outputs['changes']):,} rows")
    print(f"signal_challenger_family_comparison: {len(outputs['family']):,} rows")


if __name__ == "__main__":
    main()
