from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path
from src.models.odds_utils import calculate_edge


MARKETS = {
    "receptions": {
        "display": "Receptions",
        "ladder": "market_edges/receptions_line_ladder.csv",
        "default_line": 3.5,
    },
    "receiving_yards": {
        "display": "Receiving Yards",
        "ladder": "market_edges/receiving_yards_line_ladder.csv",
        "default_line": 49.5,
    },
    "rushing_yards": {
        "display": "Rushing Yards",
        "ladder": "market_edges/rushing_yards_line_ladder.csv",
        "default_line": 49.5,
    },
    "carries": {
        "display": "Carries",
        "ladder": "market_edges/carries_line_ladder.csv",
        "default_line": 12.5,
    },
    "pass_attempts": {
        "display": "Pass Attempts",
        "ladder": "market_edges/pass_attempts_line_ladder.csv",
        "default_line": 31.5,
    },
    "completions": {
        "display": "Completions",
        "ladder": "market_edges/completions_line_ladder.csv",
        "default_line": 20.5,
    },
    "passing_yards": {
        "display": "Passing Yards",
        "ladder": "market_edges/passing_yards_line_ladder.csv",
        "default_line": 224.5,
    },
}

EDGE_COLUMNS = [
    "market_key",
    "market_display_name",
    "player_id",
    "player_name",
    "team",
    "position",
    "line",
    "sportsbook",
    "model_projection",
    "model_over_probability",
    "model_under_probability",
    "implied_over_probability",
    "implied_under_probability",
    "edge_over",
    "edge_under",
    "best_side",
    "best_edge",
    "decision_status",
    "usage_status",
    "notes",
]

WATCHLIST_COLUMNS = [
    "market_key",
    "market_display_name",
    "player_id",
    "player_name",
    "team",
    "position",
    "line",
    "model_projection",
    "model_over_probability",
    "decision_status",
    "usage_status",
    "notes",
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def final_readiness() -> tuple[str, str]:
    readiness = read_csv(output_path("google_sheets/live_readiness_export.csv"))
    final = "NO-GO"
    mode = "UNKNOWN"
    if not readiness.empty and {"Gate", "Status"}.issubset(readiness.columns):
        row = readiness[readiness["Gate"].astype(str).eq("Final Betting Use")]
        if not row.empty:
            final = str(row["Status"].iloc[0])
    status = read_csv(output_path("run_reports/latest_receptions_pipeline_status.csv"))
    if not status.empty and {"check_name", "value"}.issubset(status.columns):
        row = status[status["check_name"].astype(str).eq("projection_mode")]
        if not row.empty:
            mode = str(row["value"].iloc[0])
    return final, mode


def gate_status(relative: str, column: str = "status") -> str:
    frame = read_csv(output_path(relative))
    if frame.empty or column not in frame.columns:
        return "NEEDS DATA"
    return str(frame[column].iloc[0])


def nearest_line(frame: pd.DataFrame, target: float) -> float | None:
    lines = pd.to_numeric(frame.get("line", pd.Series(dtype=float)), errors="coerce").dropna().unique()
    if len(lines) == 0:
        return None
    return float(min(lines, key=lambda value: abs(float(value) - target)))


def build_watchlist() -> pd.DataFrame:
    rows = []
    for market_key, meta in MARKETS.items():
        ladder = read_csv(output_path(meta["ladder"]))
        if ladder.empty or "line" not in ladder.columns:
            continue
        selected = nearest_line(ladder, float(meta["default_line"]))
        if selected is None:
            continue
        view = ladder[pd.to_numeric(ladder["line"], errors="coerce").eq(selected)].copy()
        if view.empty:
            continue
        view["model_over_probability_sort"] = pd.to_numeric(view.get("model_over_probability"), errors="coerce")
        view = view.sort_values("model_over_probability_sort", ascending=False).head(25)
        for _, row in view.iterrows():
            rows.append(
                {
                    "market_key": market_key,
                    "market_display_name": meta["display"],
                    "player_id": row.get("player_id", ""),
                    "player_name": row.get("player_name", ""),
                    "team": row.get("team", ""),
                    "position": row.get("position", ""),
                    "line": row.get("line", selected),
                    "model_projection": row.get("calibrated_projection", row.get("raw_projection", "")),
                    "model_over_probability": row.get("model_over_probability", ""),
                    "decision_status": "Watchlist Only - No Odds",
                    "usage_status": "Research Only - No Odds | Historical Test Only | Not Betting Ready",
                    "notes": "No sportsbook odds are loaded. This is a model-probability watchlist, not a betting board.",
                }
            )
    return pd.DataFrame(rows, columns=WATCHLIST_COLUMNS)


def build_blockers(final: str, mode: str) -> pd.DataFrame:
    gates = {
        "Current Roster Map": gate_status("roster/current_roster_map_status.csv"),
        "Current Role Map": gate_status("roles/current_role_map_status.csv"),
        "Current Injury Map": gate_status("injuries/current_injury_map_status.csv"),
        "Market Odds Map": gate_status("odds/current_market_odds_status.csv"),
    }
    rows = []
    if final != "GO":
        rows.append({"blocker": "Final readiness is NO-GO", "status": final, "severity": "HIGH", "notes": "No decision can become actionable until Final Readiness is GO."})
    for label, status in gates.items():
        if status != "READY":
            rows.append({"blocker": f"{label} {status}", "status": status, "severity": "HIGH", "notes": f"{label} must be READY before true edge use."})
    if mode == "historical_test":
        rows.append({"blocker": "Historical-test mode", "status": mode, "severity": "HIGH", "notes": "Historical-test output cannot be treated as live betting output."})
    rows.append({"blocker": "No live betting output allowed", "status": "ENFORCED", "severity": "HIGH", "notes": "The preview board is research-only while Final Readiness is NO-GO."})
    return pd.DataFrame(rows)


def build_edge_preview(final: str) -> pd.DataFrame:
    odds = read_csv(output_path("odds/current_market_odds_map.csv"))
    if odds.empty:
        return pd.DataFrame(columns=EDGE_COLUMNS)
    rows = []
    for market_key, meta in MARKETS.items():
        ladder = read_csv(output_path(meta["ladder"]))
        if ladder.empty:
            continue
        market_odds = odds[odds.get("market_key", pd.Series(dtype=str)).astype(str).eq(market_key)].copy()
        if market_odds.empty:
            continue
        merged = market_odds.merge(ladder, on=["player_id", "team", "line"], how="left", suffixes=("_odds", ""))
        for _, row in merged.iterrows():
            model_over = pd.to_numeric(row.get("model_over_probability"), errors="coerce")
            model_under = pd.to_numeric(row.get("model_under_probability"), errors="coerce")
            implied_over = pd.to_numeric(row.get("implied_over_probability"), errors="coerce")
            implied_under = pd.to_numeric(row.get("implied_under_probability"), errors="coerce")
            edge_over = calculate_edge(model_over, implied_over)
            edge_under = calculate_edge(model_under, implied_under)
            best_side = ""
            best_edge = pd.NA
            if edge_over is not None and (edge_under is None or edge_over >= edge_under):
                best_side, best_edge = "Over", edge_over
            elif edge_under is not None:
                best_side, best_edge = "Under", edge_under
            qualified = final == "GO" and row.get("odds_mapping_status") == "READY" and best_edge is not pd.NA
            rows.append(
                {
                    "market_key": market_key,
                    "market_display_name": meta["display"],
                    "player_id": row.get("player_id", ""),
                    "player_name": row.get("player_name", row.get("player_name_odds", "")),
                    "team": row.get("team", ""),
                    "position": row.get("position", ""),
                    "line": row.get("line", ""),
                    "sportsbook": row.get("sportsbook", ""),
                    "model_projection": row.get("calibrated_projection", row.get("model_projection", "")),
                    "model_over_probability": model_over,
                    "model_under_probability": model_under,
                    "implied_over_probability": implied_over,
                    "implied_under_probability": implied_under,
                    "edge_over": edge_over,
                    "edge_under": edge_under,
                    "best_side": best_side,
                    "best_edge": best_edge,
                    "decision_status": "Qualified Edge" if qualified else "Edge Preview - Blocked",
                    "usage_status": "MODEL REVIEW" if qualified else "Research Only - Historical Test Only - Not Betting Ready",
                    "notes": "Blocked until Final Readiness is GO and every live-context gate is READY.",
                }
            )
    return pd.DataFrame(rows, columns=EDGE_COLUMNS)


def write_report(edge: pd.DataFrame, blockers: pd.DataFrame, watchlist: pd.DataFrame, final: str, mode: str) -> None:
    text = f"""# Edge Preview Board Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Projection mode: `{mode}`

Final readiness: `{final}`

True edge rows: `{len(edge)}`

No-odds watchlist rows: `{len(watchlist)}`

Blocked gates: `{', '.join(blockers['blocker'].astype(str)) if not blockers.empty else 'None'}`

Live betting output status: `NOT CREATED`

Usage status: `Research Only - No Odds / Historical Test Only / Not Betting Ready`

Next required action: `Load real odds and resolve roster, role, injury, identity, safety, and readiness gates before any row can become actionable.`
"""
    output_path("run_reports/latest_edge_preview_board_report.md").write_text(text, encoding="utf-8")


def export_edge_preview_board() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    final, mode = final_readiness()
    edge = build_edge_preview(final)
    blockers = build_blockers(final, mode)
    watchlist = build_watchlist()
    edge.to_csv(output_path("edge_preview/edge_preview_board.csv"), index=False)
    blockers.to_csv(output_path("edge_preview/edge_preview_blockers.csv"), index=False)
    watchlist.to_csv(output_path("edge_preview/no_odds_watchlist.csv"), index=False)
    write_report(edge, blockers, watchlist, final, mode)
    return edge, blockers, watchlist


def main() -> None:
    edge, blockers, watchlist = export_edge_preview_board()
    print(f"edge_preview_board: {len(edge):,} rows")
    print(f"edge_preview_blockers: {len(blockers):,} rows")
    print(f"no_odds_watchlist: {len(watchlist):,} rows")


if __name__ == "__main__":
    main()
