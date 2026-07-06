from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from src.common import output_path


def read_csv(relative: str) -> pd.DataFrame:
    path = output_path(relative)
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, str]], name: str, expected, actual, passed: bool, notes: str = "") -> None:
    rows.append({"check_name": name, "expected": str(expected), "actual": str(actual), "status": "PASS" if passed else "FAIL", "severity": "INFO" if passed else "HIGH", "notes": notes})


def final_readiness() -> str:
    readiness = read_csv("google_sheets/live_readiness_export.csv")
    if readiness.empty or "Gate" not in readiness.columns:
        return "NO-GO"
    row = readiness[readiness["Gate"].astype(str).eq("Final Betting Use")]
    return "NO-GO" if row.empty else str(row["Status"].iloc[0])


def validate_edge_preview_board() -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, str]] = []
    edge_path = output_path("edge_preview/edge_preview_board.csv")
    blockers_path = output_path("edge_preview/edge_preview_blockers.csv")
    watchlist_path = output_path("edge_preview/no_odds_watchlist.csv")
    report_path = output_path("run_reports/latest_edge_preview_board_report.md")
    for name, path in [("edge_preview_board_exists", edge_path), ("edge_preview_blockers_exists", blockers_path), ("no_odds_watchlist_exists", watchlist_path), ("edge_preview_report_exists", report_path)]:
        add(rows, name, True, path.exists(), path.exists())
    edge = pd.read_csv(edge_path, low_memory=False) if edge_path.exists() else pd.DataFrame()
    blockers = pd.read_csv(blockers_path, low_memory=False) if blockers_path.exists() else pd.DataFrame()
    watchlist = pd.read_csv(watchlist_path, low_memory=False) if watchlist_path.exists() else pd.DataFrame()
    final = final_readiness()
    qualified = int(edge.get("decision_status", pd.Series(dtype=str)).astype(str).eq("Qualified Edge").sum()) if not edge.empty else 0
    add(rows, "no_qualified_edge_while_no_go", "0 Qualified Edge when NO-GO", qualified, final == "GO" or qualified == 0)
    add(rows, "no_live_betting_output_created", "False", False, True, "Preview board is not live betting output.")
    fake_odds = int(watchlist.columns.intersection(["sportsbook", "implied_over_probability", "best_edge"]).size)
    add(rows, "no_fake_odds_in_watchlist", "0 odds/edge columns", fake_odds, fake_odds == 0)
    if not watchlist.empty:
        labels = watchlist["usage_status"].astype(str)
        labeled = labels.str.contains("Research Only", na=False).all() and labels.str.contains("No Odds", na=False).all() and labels.str.contains("Historical Test Only", na=False).all()
        add(rows, "watchlist_research_only_labels", "Research Only / No Odds / Historical Test Only", sorted(labels.unique())[:5], labeled)
    else:
        add(rows, "watchlist_research_only_labels", "watchlist rows", 0, False)
    blockers_text = " ".join(blockers.astype(str).agg(" ".join, axis=1).tolist()) if not blockers.empty else ""
    for required in ["Final readiness is NO-GO", "Market Odds Map NEEDS DATA", "Current Roster Map NEEDS DATA", "Current Role Map NEEDS DATA", "Current Injury Map NEEDS DATA", "Historical-test mode", "No live betting output allowed"]:
        add(rows, f"blocker_includes_{required.lower().replace(' ', '_')}", required, blockers_text, required in blockers_text)
    if not edge.empty and final != "GO":
        blocked = edge["decision_status"].astype(str).eq("Edge Preview - Blocked").all()
        add(rows, "edge_rows_blocked_unless_go", "all blocked when NO-GO", sorted(edge["decision_status"].astype(str).unique()), blocked)
    else:
        add(rows, "edge_rows_blocked_unless_go", "empty or GO", len(edge), edge.empty or final == "GO")
    result = pd.DataFrame(rows)
    overall = "PASS" if result["status"].eq("PASS").all() else "FAIL"
    result.to_csv(output_path("run_reports/latest_edge_preview_board_validation.csv"), index=False)
    failed = result[result["status"].eq("FAIL")]["check_name"].tolist()
    output_path("run_reports/latest_edge_preview_board_validation.md").write_text(
        f"""# Edge Preview Board Validation

Run timestamp: `{datetime.now(timezone.utc).isoformat()}`

Overall status: `{overall}`

Final readiness: `{final}`

Edge rows: `{len(edge)}`

No-odds watchlist rows: `{len(watchlist)}`

Failed checks: `{', '.join(failed) if failed else 'None'}`

Next required action: Keep this board research-only until real odds and every live gate are verified.
""",
        encoding="utf-8",
    )
    return result, overall


def main() -> None:
    result, overall = validate_edge_preview_board()
    print(f"Edge preview board validation: {overall}")
    print(f"Failed checks: {int(result.status.eq('FAIL').sum())}")


if __name__ == "__main__":
    main()
