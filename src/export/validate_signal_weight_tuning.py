from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yaml

from src.common import output_path, project_path


CONFIG = project_path("config", "signal_weight_profiles.yaml")
REQUIRED = [
    "signal_boards/signal_weight_tuning_results.csv",
    "signal_boards/signal_weight_tuning_by_family.csv",
    "signal_boards/signal_weight_tuning_tier_lift.csv",
    "signal_boards/signal_weight_tuning_recommendations.csv",
    "signal_boards/recommended_signal_weight_profile.yaml",
    "run_reports/latest_signal_weight_tuning_report.md",
]
FORBIDDEN = ["CLV", "ODDS", "BET"]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, str]], check_name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append({"check_name": check_name, "expected": str(expected), "actual": str(actual), "status": "PASS" if passed else "FAIL", "severity": "INFO" if passed else "HIGH", "notes": notes})


def status_value(name: str, default: str = "UNKNOWN") -> str:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or not {"check_name", "value"}.issubset(status.columns):
        return default
    row = status[status["check_name"].astype(str).eq(name)]
    return default if row.empty else str(row["value"].iloc[0])


def text_from_frame(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    return " ".join(frame.fillna("").astype(str).apply(lambda row: " ".join(row.tolist()), axis=1).tolist())


def validate_signal_weight_tuning() -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, str]] = []
    add(checks, "signal_weight_config_exists", True, CONFIG.exists(), CONFIG.exists())
    profiles = {}
    if CONFIG.exists():
        with CONFIG.open("r", encoding="utf-8") as handle:
            profiles = yaml.safe_load(handle)
    profile_names = sorted((profiles.get("profiles") or {}).keys()) if profiles else []
    add(checks, "current_v1_profile_exists", "current_v1", profile_names, "current_v1" in profile_names)
    for relative in REQUIRED:
        path = output_path(relative)
        add(checks, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())

    results = read_csv("signal_boards/signal_weight_tuning_results.csv")
    comparisons = read_csv("signal_boards/signal_weight_tuning_by_family.csv")
    recommendations = read_csv("signal_boards/signal_weight_tuning_recommendations.csv")
    master = read_csv("signal_boards/player_week_signal_master.csv")
    add(checks, "tuning_results_have_rows", ">0", len(results), len(results) > 0)
    add(checks, "recommendations_have_rows", ">0", len(recommendations), len(recommendations) > 0)
    expected_profiles = len(profile_names) * 3
    add(checks, "all_profiles_families_scored", expected_profiles, len(results), len(results) >= expected_profiles)

    champion_present = not results.empty and results["profile_name"].astype(str).eq("current_v1").any()
    add(checks, "current_v1_used_as_champion", True, champion_present, champion_present)
    production_unchanged = "challenger_signal_score" not in master.columns and "recommended_challenger_v1" not in master.columns
    add(checks, "challenger_not_applied_to_production_master", True, production_unchanged, production_unchanged)

    rec_path = output_path("signal_boards/recommended_signal_weight_profile.yaml")
    rec_text = rec_path.read_text(encoding="utf-8", errors="replace") if rec_path.exists() else ""
    research_label = "Research-only recommendation" in rec_text and "Not applied to production" in rec_text
    add(checks, "recommended_profile_labeled_research_only", True, research_label, research_label)

    combined = (text_from_frame(results) + " " + text_from_frame(comparisons) + " " + text_from_frame(recommendations) + " " + rec_text).upper()
    hits = [word for word in FORBIDDEN if word in combined]
    add(checks, "no_forbidden_language_in_tuning_outputs", "no forbidden words", hits, not hits)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(checks, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(checks, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(checks, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    result = pd.DataFrame(checks)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_signal_weight_tuning_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_signal_weight_tuning_validation.md").write_text(
        f"""# Signal Weight Tuning Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Profiles found: `{', '.join(profile_names)}`

Result rows: `{len(results)}`

Recommendation rows: `{len(recommendations)}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_signal_weight_tuning()
    print(f"Signal weight tuning validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
