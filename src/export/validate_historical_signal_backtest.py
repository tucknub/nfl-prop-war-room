from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path


REQUIRED = [
    "signal_boards/historical_signal_backtest_rows.csv",
    "signal_boards/historical_signal_backtest_summary.csv",
    "signal_boards/historical_signal_tier_lift.csv",
    "signal_boards/historical_signal_component_audit.csv",
    "signal_boards/historical_signal_market_family_audit.csv",
    "run_reports/latest_historical_signal_backtest_report.md",
]
FORBIDDEN = ["BET", "EDGE", "CLV", "ODDS"]


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, str]], check_name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append(
        {
            "check_name": check_name,
            "expected": str(expected),
            "actual": str(actual),
            "status": "PASS" if passed else "FAIL",
            "severity": "INFO" if passed else "HIGH",
            "notes": notes,
        }
    )


def status_value(name: str, default: str = "UNKNOWN") -> str:
    status = read_csv("run_reports/latest_receptions_pipeline_status.csv")
    if status.empty or not {"check_name", "value"}.issubset(status.columns):
        return default
    row = status[status["check_name"].astype(str).eq(name)]
    return default if row.empty else str(row["value"].iloc[0])


def forbidden_hits(*frames: pd.DataFrame) -> list[str]:
    text = ""
    for frame in frames:
        if not frame.empty:
            text += " " + " ".join(frame.fillna("").astype(str).apply(lambda row: " ".join(row.tolist()), axis=1).tolist())
    upper = text.upper()
    return [word for word in FORBIDDEN if word in upper]


def validate_historical_signal_backtest() -> tuple[pd.DataFrame, str]:
    checks: list[dict[str, str]] = []
    for relative in REQUIRED:
        path = output_path(relative)
        add(checks, f"{relative.replace('/', '_')}_exists", True, path.exists(), path.exists())

    rows = read_csv("signal_boards/historical_signal_backtest_rows.csv")
    summary = read_csv("signal_boards/historical_signal_backtest_summary.csv")
    tiers = read_csv("signal_boards/historical_signal_tier_lift.csv")
    components = read_csv("signal_boards/historical_signal_component_audit.csv")
    family = read_csv("signal_boards/historical_signal_market_family_audit.csv")
    outcome = read_csv("signal_boards/signal_score_outcome_audit.csv")

    add(checks, "backtest_rows_exist", ">0", len(rows), len(rows) > 0)
    add(checks, "tier_lift_has_rows", ">0", len(tiers), len(tiers) > 0)
    add(checks, "component_audit_has_rows", ">0", len(components), len(components) > 0)
    add(checks, "market_family_audit_has_rows", ">0", len(family), len(family) > 0)
    add(checks, "summary_has_rows", ">0", len(summary), len(summary) > 0)

    if not rows.empty and {"feature_source_max_game_order", "target_game_order"}.issubset(rows.columns):
        feature_order = pd.to_numeric(rows["feature_source_max_game_order"], errors="coerce")
        target_order = pd.to_numeric(rows["target_game_order"], errors="coerce")
        no_leakage = (feature_order < target_order).all()
        add(checks, "no_future_data_leakage_detected", "feature order < target order", no_leakage, no_leakage)
    else:
        add(checks, "no_future_data_leakage_detected", "feature order columns", "missing", False)

    actual_cols = [
        "actual_receptions",
        "actual_receiving_yards",
        "actual_carries",
        "actual_rushing_yards",
        "actual_pass_attempts",
        "actual_completions",
        "actual_passing_yards",
    ]
    actual_ok = not rows.empty and all(col in rows.columns for col in actual_cols) and pd.to_numeric(rows["actual_primary_value"], errors="coerce").notna().all()
    add(checks, "market_family_actual_metrics_valid", actual_cols, [col for col in actual_cols if col in rows.columns], actual_ok)

    labels_ok = not rows.empty and rows["backtest_usage_status"].astype(str).str.contains("HISTORICAL SIGNAL BACKTEST ONLY", na=False).all()
    add(checks, "outputs_labeled_research_historical", "HISTORICAL SIGNAL BACKTEST ONLY", labels_ok, labels_ok)

    outcome_ok = not outcome.empty and outcome.apply(lambda row: " ".join(str(value) for value in row.tolist()), axis=1).str.contains("PARTIAL_HISTORICAL_SIGNAL_BACKTEST|NEEDS HISTORICAL SIGNAL BACKTEST DATA", regex=True, na=False).any()
    add(checks, "outcome_audit_status_labeled", "PARTIAL or NEEDS", outcome_ok, outcome_ok)

    hits = forbidden_hits(rows.head(500), summary, tiers, components, family, outcome)
    add(checks, "no_forbidden_language_in_backtest_outputs", "no forbidden words", hits, not hits)

    final = status_value("final_live_readiness", "NO-GO")
    live = status_value("live_betting_output_created", "False")
    leakage = status_value("leakage_status", "UNKNOWN")
    add(checks, "final_readiness_remains_no_go", "NO-GO", final, final == "NO-GO")
    add(checks, "live_betting_output_remains_false", "False", live, str(live).lower() == "false")
    add(checks, "leakage_status_pass", "PASS", leakage, leakage == "PASS")

    result = pd.DataFrame(checks)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_historical_signal_backtest_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    seasons = sorted(pd.to_numeric(rows.get("season", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).unique().tolist()) if not rows.empty else []
    families = sorted(rows.get("market_family", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()) if not rows.empty else []
    output_path("run_reports/latest_historical_signal_backtest_validation.md").write_text(
        f"""# Historical Signal Backtest Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{overall}`

Rows: `{len(rows)}`

Seasons: `{', '.join(map(str, seasons))}`

Market families: `{', '.join(families)}`

Final readiness: `{final}`

Leakage status: `{leakage}`

Live betting output created: `{live}`

Failed checks: `{', '.join(failed) if failed else 'None'}`
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_historical_signal_backtest()
    print(f"Historical signal backtest validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
