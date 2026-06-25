from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common import output_path
from src.load.build_identity_crosswalk import canonical_team, normalize_player_name


PLAYER_GATES = {
    "roster": ("gate_inputs_normalized/roster_gate_normalized.csv", "Current Team"),
    "role": ("gate_inputs_normalized/role_gate_normalized.csv", "Team"),
    "injury": ("gate_inputs_normalized/injury_gate_normalized.csv", "Team"),
    "market_odds": ("gate_inputs_normalized/market_odds_gate_normalized.csv", "Team"),
}


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _possible_matches(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    cols = ["player_id", "player_name", "team", "position"]
    return "|".join(
        f"{row.player_id}:{row.player_name}:{row.team}:{row.position}"
        for row in df[cols].drop_duplicates().itertuples(index=False)
    )


def _append_note(existing: object, note: str) -> str:
    text = "" if pd.isna(existing) else str(existing)
    return note if not text else f"{text}; {note}"


def _match_row(row: pd.Series, crosswalk: pd.DataFrame, team_col: str) -> tuple[str, pd.DataFrame, str]:
    player_id = "" if pd.isna(row.get("Player ID")) else str(row.get("Player ID")).strip()
    player_name = "" if pd.isna(row.get("Player Name")) else str(row.get("Player Name")).strip()
    normalized = normalize_player_name(player_name)
    team = canonical_team(row.get(team_col, ""))

    if player_id:
        exact = crosswalk[crosswalk["player_id"].astype(str) == player_id]
        if exact.empty:
            return "UNMATCHED_PLAYER", exact, normalized
        if team and team not in set(exact["team"].astype(str)):
            return "TEAM_VERIFY", exact, normalized
        return "MATCHED", exact, normalized

    name_team = crosswalk[
        (crosswalk["normalized_player_name"] == normalized)
        & (crosswalk["team"].astype(str) == team)
    ]
    if not name_team.empty:
        if name_team["player_id"].nunique() > 1:
            return "DUPLICATE_PLAYER_NAME", name_team, normalized
        return "MATCHED", name_team, normalized

    name_only = crosswalk[crosswalk["normalized_player_name"] == normalized]
    if name_only.empty:
        return "UNMATCHED_PLAYER", name_only, normalized
    if name_only["player_id"].nunique() > 1:
        return "DUPLICATE_PLAYER_NAME", name_only, normalized
    return "MATCHED", name_only, normalized


def validate_gate_identity_matches() -> tuple[pd.DataFrame, pd.DataFrame]:
    crosswalk_path = output_path("identity/player_identity_crosswalk.csv")
    crosswalk = _read(crosswalk_path)
    report_rows = []
    unmatched_rows = []
    status_path = output_path("gate_inputs_normalized/gate_input_status.csv")
    status_df = _read(status_path)

    for gate, (file_name, team_col) in PLAYER_GATES.items():
        path = output_path(file_name)
        df = _read(path)
        rows_checked = len(df)
        counts = {"MATCHED": 0, "UNMATCHED_PLAYER": 0, "TEAM_VERIFY": 0, "DUPLICATE_PLAYER_NAME": 0}
        if not df.empty and not crosswalk.empty:
            for idx, row in df.iterrows():
                match_status, matches, normalized = _match_row(row, crosswalk, team_col)
                counts[match_status] = counts.get(match_status, 0) + 1
                if match_status != "MATCHED":
                    unmatched_rows.append(
                        {
                            "gate": gate,
                            "row_number": idx + 2,
                            "player_name": row.get("Player Name", ""),
                            "player_id": row.get("Player ID", ""),
                            "team": row.get(team_col, ""),
                            "normalized_player_name": normalized,
                            "match_status": match_status,
                            "possible_matches": _possible_matches(matches),
                            "notes": "Resolve identity before live use.",
                        }
                    )
                    if "Validation Status" in df.columns:
                        df.loc[idx, "Validation Status"] = "BLOCKED"
                    if "Notes" in df.columns:
                        df.loc[idx, "Notes"] = _append_note(row.get("Notes", ""), match_status)
                    if match_status == "TEAM_VERIFY" and "Team Verify Flag" in df.columns:
                        df.loc[idx, "Team Verify Flag"] = "TEAM_VERIFY"
            df.to_csv(path, index=False)
        elif rows_checked > 0 and crosswalk.empty:
            counts["UNMATCHED_PLAYER"] = rows_checked

        issue_count = counts["UNMATCHED_PLAYER"] + counts["TEAM_VERIFY"] + counts["DUPLICATE_PLAYER_NAME"]
        status = "READY" if rows_checked > 0 and issue_count == 0 else ("BLOCKED" if issue_count else "NEEDS DATA")
        if not status_df.empty and gate in set(status_df["gate"]):
            gate_mask = status_df["gate"] == gate
            if str(status_df.loc[gate_mask, "is_real_data"].iloc[0]).upper() == "FALSE":
                status = "NEEDS DATA"
            elif issue_count:
                status_df.loc[gate_mask, "status"] = "BLOCKED"
                status_df.loc[gate_mask, "notes"] = status_df.loc[gate_mask, "notes"].astype(str) + " Identity validation blockers found."
            else:
                current = str(status_df.loc[gate_mask, "status"].iloc[0])
                status = current
        report_rows.append(
            {
                "gate": gate,
                "rows_checked": rows_checked,
                "matched_rows": counts["MATCHED"],
                "unmatched_rows": counts["UNMATCHED_PLAYER"],
                "team_verify_rows": counts["TEAM_VERIFY"],
                "duplicate_name_rows": counts["DUPLICATE_PLAYER_NAME"],
                "status": status,
                "notes": "No real gate rows to validate." if rows_checked == 0 else "Identity validation complete.",
            }
        )

    if not status_df.empty:
        status_df.to_csv(status_path, index=False)

    report = pd.DataFrame(report_rows)
    unmatched = pd.DataFrame(
        unmatched_rows,
        columns=[
            "gate",
            "row_number",
            "player_name",
            "player_id",
            "team",
            "normalized_player_name",
            "match_status",
            "possible_matches",
            "notes",
        ],
    )
    report.to_csv(output_path("identity/gate_identity_match_report.csv"), index=False)
    unmatched.to_csv(output_path("identity/unmatched_gate_rows.csv"), index=False)
    write_markdown_report(report, unmatched)
    return report, unmatched


def write_markdown_report(report: pd.DataFrame, unmatched: pd.DataFrame) -> None:
    status = "PASS" if unmatched.empty else "BLOCKED"
    text = f"""# Identity Validation

Run timestamp: `{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}`

Overall status: `{status}`

Unmatched rows: `{len(unmatched)}`

TEAM_VERIFY rows: `{int(report['team_verify_rows'].sum()) if not report.empty else 0}`

Duplicate-name rows: `{int(report['duplicate_name_rows'].sum()) if not report.empty else 0}`

Player IDs are preferred. Name-only matches are allowed only when unique and unambiguous.

## Gate Report

{report.to_string(index=False) if not report.empty else 'No report rows.'}
"""
    output_path("run_reports/latest_identity_validation.md").write_text(text, encoding="utf-8")


def main() -> None:
    report, unmatched = validate_gate_identity_matches()
    print(report.to_string(index=False))
    print(f"unmatched_gate_rows: {len(unmatched):,}")


if __name__ == "__main__":
    main()
