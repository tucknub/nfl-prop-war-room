from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.common import output_path, project_path


@dataclass(frozen=True)
class MetricSpec:
    metric_name: str
    metric_category: str
    desired_board: str
    current_source_file: str
    current_source_column: str
    historical_available: str
    live_available: str
    latency: str
    cost: str
    reliability_tier: str
    implementation_status: str
    notes: str


SPECS = [
    MetricSpec("receptions_projection", "projection", "Receiving Signal Board", "outputs/google_sheets_receptions_historical_test.csv", "projected_receptions_calibrated", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Historical-test projection only."),
    MetricSpec("receiving_yards_projection", "projection", "Receiving Signal Board", "outputs/google_sheets_receiving_yards_historical_test.csv", "projected_receiving_yards_calibrated", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Historical-test projection only."),
    MetricSpec("rushing_yards_projection", "projection", "Rushing Signal Board", "outputs/google_sheets_rushing_yards_historical_test.csv", "projected_rushing_yards_calibrated", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Historical-test projection only."),
    MetricSpec("carries_projection", "projection", "Rushing Signal Board", "outputs/google_sheets_carries_historical_test.csv", "projected_carries_calibrated", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Historical-test projection only."),
    MetricSpec("pass_attempts_projection", "projection", "Passing Signal Board", "outputs/google_sheets_pass_attempts_historical_test.csv", "projected_pass_attempts_calibrated", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Historical-test projection only."),
    MetricSpec("completions_projection", "projection", "Passing Signal Board", "outputs/google_sheets_completions_historical_test.csv", "projected_completions_calibrated", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Historical-test projection only."),
    MetricSpec("passing_yards_projection", "projection", "Passing Signal Board", "outputs/google_sheets_passing_yards_historical_test.csv", "projected_passing_yards_calibrated", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Historical-test projection only."),
    MetricSpec("projected_target_share", "usage", "Receiving Signal Board", "outputs/google_sheets_receptions_historical_test.csv", "projected_target_share", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Receptions model support signal, not Targets V1."),
    MetricSpec("estimated_routes_proxy", "usage", "Receiving Signal Board", "outputs/google_sheets_receptions_historical_test.csv", "estimated_routes", "Yes", "No", "pipeline", "local", "low", "AVAILABLE_PROXY", "Route proxy is not true route participation."),
    MetricSpec("projected_carry_share", "usage", "Rushing Signal Board", "outputs/google_sheets_carries_historical_test.csv", "projected_player_rush_attempt_share", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Carries support signal."),
    MetricSpec("projection_confidence", "data_quality", "All Signal Boards", "market projection outputs", "confidence_bucket", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Available where market exports include confidence_bucket."),
    MetricSpec("quality_flags", "data_quality", "Blocked / Review Board", "market projection outputs", "quality_flags", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Used for review flags."),
    MetricSpec("recent_form_features", "recent_form", "All Signal Boards", "outputs/signal_boards/signal_context_features.csv", "recent_form_reliability", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Pre-target L3/L5/L8 weekly player form from data/raw/weekly.csv."),
    MetricSpec("recent_receiving_form", "recent_form", "Receiving Signal Board", "outputs/signal_boards/signal_context_features.csv", "l3_targets", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Pre-target recent targets/catches/yards; not Targets V1."),
    MetricSpec("recent_rushing_form", "recent_form", "Rushing Signal Board", "outputs/signal_boards/signal_context_features.csv", "l3_carries", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Pre-target recent carries and rushing yards."),
    MetricSpec("recent_passing_form", "recent_form", "Passing Signal Board", "outputs/signal_boards/signal_context_features.csv", "l3_pass_attempts", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Pre-target recent pass volume and yards."),
    MetricSpec("spread_total_game_script", "game_script", "Slate Overview", "outputs/signal_boards/signal_context_features.csv", "game_script_score", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "From schedules.csv spread_line/total_line where present; historical-test context only."),
    MetricSpec("game_environment_buckets", "game_script", "By-Game Matchup Board", "outputs/signal_boards/signal_context_features.csv", "game_total_bucket", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Conservative total/spread buckets from schedules.csv."),
    MetricSpec("opponent_allowed_by_position", "defense_fit", "Position Signal Boards", "outputs/signal_boards/signal_context_features.csv", "defense_fit_reliability", "Yes", "No", "pipeline", "local", "low", "AVAILABLE_WITH_SHRINKAGE", "Historical allowed stats by opponent/position with shrinkage toward league average."),
    MetricSpec("context_data_quality", "data_quality", "All Signal Boards", "outputs/signal_boards/signal_context_features.csv", "context_data_quality", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE", "Reliability-aware context data quality field."),
    MetricSpec("current_roster_gate_status", "role", "Blocked / Review Board", "outputs/roster/current_roster_map_status.csv", "status", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE_NEEDS_DATA", "Gate exists but production status currently needs real data."),
    MetricSpec("current_role_gate_status", "role", "Blocked / Review Board", "outputs/roles/current_role_map_status.csv", "status", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE_NEEDS_DATA", "Gate exists but production status currently needs real data."),
    MetricSpec("current_injury_gate_status", "injury", "Blocked / Review Board", "outputs/injuries/current_injury_map_status.csv", "status", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE_NEEDS_DATA", "Gate exists but production status currently needs real data."),
    MetricSpec("market_odds_gate_status", "data_quality", "Edge Preview Board", "outputs/odds/current_market_odds_status.csv", "status", "Yes", "No", "pipeline", "local", "medium", "AVAILABLE_NEEDS_DATA", "Odds gate exists but no real odds loaded."),
    MetricSpec("route_share", "usage", "Receiving Signal Board", "", "", "No", "No", "planned", "unknown", "unknown", "NEEDS SOURCE", "True route share is not currently sourced."),
    MetricSpec("snap_share", "usage", "All Signal Boards", "", "", "No", "No", "planned", "unknown", "unknown", "NEEDS SOURCE", "True snap share is not currently sourced."),
    MetricSpec("air_yards_share", "usage", "Receiving Signal Board", "", "", "No", "No", "planned", "unknown", "unknown", "NEEDS SOURCE", "No sourced air-yards-share column in current outputs."),
    MetricSpec("red_zone_targets", "usage", "Receiving Signal Board", "", "", "No", "No", "planned", "unknown", "unknown", "PLANNED_SOURCE", "Possible later from play-by-play, not built now."),
    MetricSpec("goal_line_carries", "usage", "Rushing Signal Board", "", "", "No", "No", "planned", "unknown", "unknown", "PLANNED_SOURCE", "Possible later from play-by-play, not built now."),
    MetricSpec("coverage_tendency", "defense_fit", "Receiving Signal Board", "", "", "No", "No", "planned", "unknown", "unknown", "NEEDS SOURCE", "No man/zone source exists in current project."),
    MetricSpec("shadow_cb_matchup", "defense_fit", "Receiving Signal Board", "", "", "No", "No", "planned", "unknown", "unknown", "NEEDS SOURCE", "Do not assume shadow coverage."),
    MetricSpec("weather", "weather", "Slate Overview", "", "", "No", "No", "planned", "unknown", "unknown", "NEEDS SOURCE", "No weather source loaded."),
    MetricSpec("practice_report_progression", "practice_trend", "Blocked / Review Board", "", "", "No", "No", "planned", "unknown", "unknown", "NEEDS SOURCE", "Injury status exists, but practice progression trend is not sourced."),
    MetricSpec("projection_volatility_proxy", "volatility", "Slate Overview", "market projection outputs", "confidence_bucket", "Yes", "No", "pipeline", "local", "low", "PARTIAL", "Proxy only from confidence/quality flags."),
]


def _source_available(relative: str, column: str) -> bool:
    if not relative or not column:
        return False
    if relative == "market projection outputs":
        paths = [
            "outputs/google_sheets_receptions_historical_test.csv",
            "outputs/google_sheets_receiving_yards_historical_test.csv",
            "outputs/google_sheets_rushing_yards_historical_test.csv",
            "outputs/google_sheets_carries_historical_test.csv",
            "outputs/google_sheets_pass_attempts_historical_test.csv",
            "outputs/google_sheets_completions_historical_test.csv",
            "outputs/google_sheets_passing_yards_historical_test.csv",
        ]
        return any(_source_available(path, column) for path in paths)
    path = project_path(relative)
    if not path.exists():
        return False
    try:
        frame = pd.read_csv(path, nrows=1, low_memory=False)
    except pd.errors.EmptyDataError:
        return False
    return column in frame.columns


def export_signal_data_inventory() -> pd.DataFrame:
    rows = []
    for spec in SPECS:
        available = _source_available(spec.current_source_file, spec.current_source_column)
        status = spec.implementation_status
        if not available and status in {"AVAILABLE", "AVAILABLE_PROXY", "AVAILABLE_NEEDS_DATA", "PARTIAL"}:
            status = "NOT_AVAILABLE"
        rows.append(
            {
                "metric_name": spec.metric_name,
                "metric_category": spec.metric_category,
                "desired_board": spec.desired_board,
                "current_source_file": spec.current_source_file or "NOT_AVAILABLE",
                "current_source_column": spec.current_source_column or "NOT_AVAILABLE",
                "available_now": "Yes" if available else "No",
                "historical_available": spec.historical_available if available or spec.historical_available == "No" else "No",
                "live_available": spec.live_available,
                "latency": spec.latency,
                "cost": spec.cost,
                "reliability_tier": spec.reliability_tier,
                "implementation_status": status,
                "notes": spec.notes,
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(output_path("signal_boards/signal_data_inventory.csv"), index=False)
    return out


def main() -> None:
    out = export_signal_data_inventory()
    available = int(out["available_now"].eq("Yes").sum())
    print(f"signal_data_inventory: {len(out):,} rows")
    print(f"available_now: {available:,}")


if __name__ == "__main__":
    main()
