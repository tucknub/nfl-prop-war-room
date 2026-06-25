from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path
from src.models.receptions_probability import build_receptions_market_probability, calibration_error_sd


EDGE_COLUMNS = [
    "player_name",
    "player_id",
    "team",
    "opponent",
    "position",
    "market",
    "sportsbook",
    "line",
    "over_odds",
    "under_odds",
    "implied_over_probability",
    "implied_under_probability",
    "model_over_probability",
    "model_under_probability",
    "over_edge",
    "under_edge",
    "best_side",
    "best_edge",
    "price_grade",
    "validation_status",
    "usage_status",
    "notes",
]


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def american_odds_implied_probability(value) -> float | None:
    odds = pd.to_numeric(value, errors="coerce")
    if pd.isna(odds) or odds == 0:
        return None
    odds = float(odds)
    return abs(odds) / (abs(odds) + 100) if odds < 0 else 100 / (odds + 100)


def _final_readiness() -> str:
    readiness = _read(output_path("google_sheets/live_readiness_export.csv"))
    if readiness.empty:
        return "NO-GO"
    row = readiness[readiness["Gate"] == "Final Betting Use"]
    return "NO-GO" if row.empty else str(row["Status"].iloc[0])


def _gate_status(gate: str) -> str:
    readiness = _read(output_path("google_sheets/live_readiness_export.csv"))
    if readiness.empty:
        return "NEEDS DATA"
    row = readiness[readiness["Gate"] == gate]
    return "NEEDS DATA" if row.empty else str(row["Status"].iloc[0])


def _identity_clean() -> bool:
    report = _read(output_path("identity/gate_identity_match_report.csv"))
    if report.empty:
        return False
    issue_cols = ["unmatched_rows", "duplicate_name_rows", "team_verify_rows"]
    return int(report[issue_cols].fillna(0).astype(int).sum().sum()) == 0


def price_grade(best_edge, odds_valid: bool, identity_clean: bool) -> str:
    if best_edge is None or pd.isna(best_edge):
        return "NEEDS DATA"
    if best_edge >= 0.05 and odds_valid and identity_clean:
        return "PASS"
    if best_edge >= 0.02:
        return "REVIEW"
    return "BAD PRICE"


def build_blockers(final_readiness: str, odds_rows: int, identity_clean: bool) -> pd.DataFrame:
    blockers = []
    if final_readiness != "GO":
        blockers.append(
            {
                "blocker": "Final readiness is not GO",
                "severity": "HIGH",
                "why_it_matters": "Live betting edges cannot be created while the control room is NO-GO.",
                "required_before_projection": "No",
                "required_before_betting": "Yes",
                "next_action": "Resolve Live Readiness blockers.",
            }
        )
    if odds_rows == 0 or _gate_status("Market Odds Gate") == "NEEDS DATA":
        blockers.append(
            {
                "blocker": "Market odds missing",
                "severity": "HIGH",
                "why_it_matters": "No betting edge can be produced without sportsbook lines and odds.",
                "required_before_projection": "No",
                "required_before_betting": "Yes",
                "next_action": "Load real odds into data/gates/odds and rerun pipeline.",
            }
        )
    for gate in ["Schedule Gate", "Roster Gate", "Role Gate", "Injury Gate"]:
        status = _gate_status(gate)
        if status not in {"READY", "PASS"}:
            blockers.append(
                {
                    "blocker": gate,
                    "severity": "HIGH",
                    "why_it_matters": f"{gate} status is {status}.",
                    "required_before_projection": "Yes",
                    "required_before_betting": "Yes",
                    "next_action": f"Complete {gate} validation.",
                }
            )
    if not identity_clean:
        blockers.append(
            {
                "blocker": "Identity validation not clean",
                "severity": "HIGH",
                "why_it_matters": "Wrong-player or stale-team edges are unsafe.",
                "required_before_projection": "Yes",
                "required_before_betting": "Yes",
                "next_action": "Resolve unmatched, duplicate, or TEAM_VERIFY identity rows.",
            }
        )
    return pd.DataFrame(blockers)


def export_receptions_market_edges() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prob = build_receptions_market_probability()
    odds = _read(output_path("gate_inputs_normalized/market_odds_gate_normalized.csv"))
    final = _final_readiness()
    identity_clean = _identity_clean()
    blockers = build_blockers(final, len(odds), identity_clean)

    if prob.empty or odds.empty:
        edges = pd.DataFrame(columns=EDGE_COLUMNS)
    else:
        merged = prob.merge(
            odds,
            left_on=["player_id", "team", "line"],
            right_on=["Player ID", "Team", "Line"],
            how="left",
        )
        rows = []
        for _, row in merged.iterrows():
            implied_over = american_odds_implied_probability(row.get("Over Odds"))
            implied_under = american_odds_implied_probability(row.get("Under Odds"))
            model_over = pd.to_numeric(row.get("model_over_probability"), errors="coerce")
            model_under = pd.to_numeric(row.get("model_under_probability"), errors="coerce")
            over_edge = pd.NA if implied_over is None or pd.isna(model_over) else float(model_over) - implied_over
            under_edge = pd.NA if implied_under is None or pd.isna(model_under) else float(model_under) - implied_under
            best_side = ""
            best_edge = pd.NA
            if not pd.isna(over_edge) and (pd.isna(under_edge) or over_edge >= under_edge):
                best_side, best_edge = "Over", over_edge
            elif not pd.isna(under_edge):
                best_side, best_edge = "Under", under_edge
            odds_valid = implied_over is not None and implied_under is not None
            usage = "HISTORICAL TEST ONLY" if row.get("usage_status") == "HISTORICAL TEST ONLY" else ("DO NOT USE" if final != "GO" else "MODEL REVIEW")
            rows.append(
                {
                    "player_name": row.get("player_name"),
                    "player_id": row.get("player_id"),
                    "team": row.get("team"),
                    "opponent": row.get("opponent"),
                    "position": row.get("position"),
                    "market": row.get("Market", "Receptions"),
                    "sportsbook": row.get("Sportsbook", ""),
                    "line": row.get("line"),
                    "over_odds": row.get("Over Odds"),
                    "under_odds": row.get("Under Odds"),
                    "implied_over_probability": implied_over,
                    "implied_under_probability": implied_under,
                    "model_over_probability": model_over,
                    "model_under_probability": model_under,
                    "over_edge": over_edge,
                    "under_edge": under_edge,
                    "best_side": best_side,
                    "best_edge": best_edge,
                    "price_grade": price_grade(best_edge, odds_valid, identity_clean),
                    "validation_status": row.get("Validation Status", "NEEDS DATA"),
                    "usage_status": usage,
                    "notes": "Research only; not betting-ready unless Live Readiness is GO.",
                }
            )
        edges = pd.DataFrame(rows, columns=EDGE_COLUMNS)

    prob.to_csv(output_path("market_edges/receptions_market_probability.csv"), index=False)
    edges.to_csv(output_path("market_edges/receptions_market_edges.csv"), index=False)
    blockers.to_csv(output_path("market_edges/receptions_market_edge_blockers.csv"), index=False)
    write_report(prob, edges, blockers, final)
    return prob, edges, blockers


def write_report(prob: pd.DataFrame, edges: pd.DataFrame, blockers: pd.DataFrame, final: str) -> None:
    best = "None"
    if not edges.empty and "best_edge" in edges.columns:
        clean = edges[pd.to_numeric(edges["best_edge"], errors="coerce").notna()].copy()
        if not clean.empty:
            row = clean.sort_values("best_edge", ascending=False).iloc[0]
            best = f"{row['player_name']} {row['best_side']} {row['line']} edge={row['best_edge']:.4f}"
    odds = _read(output_path("gate_inputs_normalized/market_odds_gate_normalized.csv"))
    text = f"""# Receptions Market Edge Report

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Projection mode: `{_projection_mode()}`

Final readiness: `{final}`

Odds rows loaded: `{len(odds)}`

Matched odds rows: `{len(prob)}`

Probability method: `Normal approximation using calibrated projection mean and calibrated RMSE standard deviation`

Calibration error used: `{calibration_error_sd():.6f}`

Edge rows created: `{len(edges)}`

Best edge if any: `{best}`

Blocked gates: `{', '.join(blockers['blocker'].astype(str)) if not blockers.empty else 'None'}`

Live betting output status: `{'CREATED' if final == 'GO' and not edges.empty else 'NOT CREATED'}`

Warnings: `{'None' if not blockers.empty else 'No blockers'}`

Next required action: `Load real odds and resolve all live readiness blockers before betting use.`
"""
    output_path("run_reports/latest_market_edge_report.md").write_text(text, encoding="utf-8")


def _projection_mode() -> str:
    dashboard = _read(output_path("google_sheets_receptions_historical_test.csv"))
    if dashboard.empty or "projection_mode" not in dashboard.columns:
        return "UNKNOWN"
    return str(dashboard["projection_mode"].iloc[0])


def main() -> None:
    prob, edges, blockers = export_receptions_market_edges()
    print(f"receptions_market_probability: {len(prob):,} rows")
    print(f"receptions_market_edges: {len(edges):,} rows")
    print(f"receptions_market_edge_blockers: {len(blockers):,} rows")


if __name__ == "__main__":
    main()
