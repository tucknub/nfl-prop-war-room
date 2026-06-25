from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.common import ROOT, load_config, output_path


GATE_SPECS = {
    "schedule": {
        "folder": ROOT / "data" / "gates" / "schedule",
        "output": "gate_inputs_normalized/schedule_gate_normalized.csv",
        "columns": [
            "Season",
            "Week",
            "Game Date",
            "Away Team",
            "Home Team",
            "Neutral Site",
            "Venue",
            "Game ID",
            "Game Status",
            "Source",
            "Updated At",
            "Validation Status",
            "Notes",
        ],
    },
    "roster": {
        "folder": ROOT / "data" / "gates" / "rosters",
        "output": "gate_inputs_normalized/roster_gate_normalized.csv",
        "columns": [
            "Player Name",
            "Player ID",
            "Position",
            "Current Team",
            "Roster Status",
            "Depth Chart Role",
            "Source",
            "Updated At",
            "Current Team Verified",
            "Team Verify Flag",
            "Validation Status",
            "Notes",
        ],
    },
    "role": {
        "folder": ROOT / "data" / "gates" / "roles",
        "output": "gate_inputs_normalized/role_gate_normalized.csv",
        "columns": [
            "Player Name",
            "Player ID",
            "Team",
            "Position",
            "Expected Role",
            "Starter Status",
            "Projected Snap Share",
            "Projected Route Share",
            "Target Share Override",
            "Role Confidence",
            "Manual Override",
            "Source",
            "Updated At",
            "Validation Status",
            "Notes",
        ],
    },
    "injury": {
        "folder": ROOT / "data" / "gates" / "injuries",
        "output": "gate_inputs_normalized/injury_gate_normalized.csv",
        "columns": [
            "Player Name",
            "Player ID",
            "Team",
            "Position",
            "Injury Status",
            "Practice Status",
            "Game Status",
            "Availability Risk",
            "Confidence Penalty",
            "Projection Action",
            "Manual Override",
            "Source",
            "Updated At",
            "Validation Status",
            "Notes",
        ],
    },
    "market_odds": {
        "folder": ROOT / "data" / "gates" / "odds",
        "output": "gate_inputs_normalized/market_odds_gate_normalized.csv",
        "columns": [
            "Player Name",
            "Player ID",
            "Team",
            "Opponent",
            "Position",
            "Market",
            "Sportsbook",
            "Line",
            "Over Odds",
            "Under Odds",
            "Implied Over Prob",
            "Model Over Prob",
            "Edge %",
            "Price Grade",
            "Updated At",
            "Validation Status",
            "Notes",
        ],
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def american_odds_implied_probability(value: Any) -> float | None:
    odds = pd.to_numeric(value, errors="coerce")
    if pd.isna(odds) or odds == 0:
        return None
    odds = float(odds)
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)


def price_grade(edge: float | None) -> str:
    if edge is None or pd.isna(edge):
        return ""
    if edge >= 0.03:
        return "PASS"
    if edge >= 0:
        return "REVIEW"
    return "BAD PRICE"


def real_input_file(folder: Path) -> Path | None:
    folder.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in folder.glob("*.csv") if "_template" not in path.name.lower())
    return files[0] if files else None


def blank_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = ""
    return out[columns].copy()


def bool_true(value: Any) -> bool:
    return str(value).strip().upper() in {"TRUE", "YES", "Y", "1"}


def row_status(notes: list[str], review: bool = False, blocked: bool = False) -> str:
    if blocked:
        return "BLOCKED"
    if review:
        return "REVIEW"
    if notes:
        return "BLOCKED"
    return "READY"


def normalize_schedule(df: pd.DataFrame, source: Path, config: dict) -> pd.DataFrame:
    cols = GATE_SPECS["schedule"]["columns"]
    out = ensure_columns(df, cols)
    target_season = int(config["data"]["target_season"])
    target_week = int(config["data"]["target_week"])
    statuses, notes = [], []
    for _, row in out.iterrows():
        row_notes: list[str] = []
        season = pd.to_numeric(row["Season"], errors="coerce")
        week = pd.to_numeric(row["Week"], errors="coerce")
        if season != target_season or week != target_week:
            row_notes.append("Season/week does not match config target.")
        if not str(row["Away Team"]).strip() or not str(row["Home Team"]).strip():
            row_notes.append("Away Team and Home Team are required.")
        if not str(row["Game Date"]).strip():
            row_notes.append("Game Date is required.")
        statuses.append(row_status(row_notes))
        notes.append("; ".join(row_notes) if row_notes else "Validated local schedule gate input.")
    out["Source"] = str(source)
    out["Updated At"] = out["Updated At"].where(out["Updated At"].astype(str).str.strip() != "", now_utc())
    out["Validation Status"] = statuses
    out["Notes"] = notes
    return out


def normalize_roster(df: pd.DataFrame, source: Path, _: dict) -> pd.DataFrame:
    cols = GATE_SPECS["roster"]["columns"]
    out = ensure_columns(df, cols)
    statuses, notes, flags = [], [], []
    for _, row in out.iterrows():
        row_notes: list[str] = []
        if not str(row["Player Name"]).strip():
            row_notes.append("Player Name is required.")
        if not str(row["Current Team"]).strip():
            row_notes.append("Current Team is required.")
        verified = bool_true(row["Current Team Verified"])
        flag = "" if verified else "TEAM_VERIFY"
        if not verified:
            row_notes.append("Current Team Verified must be TRUE before live use.")
        flags.append(flag)
        statuses.append(row_status(row_notes))
        notes.append("; ".join(row_notes) if row_notes else "Validated local roster gate input.")
    out["Source"] = str(source)
    out["Updated At"] = out["Updated At"].where(out["Updated At"].astype(str).str.strip() != "", now_utc())
    out["Team Verify Flag"] = flags
    out["Validation Status"] = statuses
    out["Notes"] = notes
    return out


def normalize_role(df: pd.DataFrame, source: Path, _: dict) -> pd.DataFrame:
    cols = GATE_SPECS["role"]["columns"]
    out = ensure_columns(df, cols)
    statuses, notes = [], []
    for _, row in out.iterrows():
        row_notes: list[str] = []
        review = False
        for col in ["Player Name", "Team", "Position", "Expected Role"]:
            if not str(row[col]).strip():
                row_notes.append(f"{col} is required.")
        confidence = pd.to_numeric(row["Role Confidence"], errors="coerce")
        if pd.isna(confidence):
            row_notes.append("Role Confidence must be numeric.")
        elif confidence < 60:
            review = True
            row_notes.append("Role Confidence below 60 requires review.")
        if str(row["Expected Role"]).strip().lower() == "unknown":
            review = True
            row_notes.append("Unknown role prevents high-confidence live use.")
        statuses.append(row_status(row_notes, review=review))
        notes.append("; ".join(row_notes) if row_notes else "Validated local role gate input.")
    out["Source"] = str(source)
    out["Updated At"] = out["Updated At"].where(out["Updated At"].astype(str).str.strip() != "", now_utc())
    out["Validation Status"] = statuses
    out["Notes"] = notes
    return out


def normalize_injury(df: pd.DataFrame, source: Path, _: dict) -> pd.DataFrame:
    cols = GATE_SPECS["injury"]["columns"]
    out = ensure_columns(df, cols)
    statuses, notes, actions = [], [], []
    for _, row in out.iterrows():
        row_notes: list[str] = []
        review = False
        blocked = False
        for col in ["Player Name", "Team", "Position"]:
            if not str(row[col]).strip():
                row_notes.append(f"{col} is required.")
        injury = str(row["Injury Status"]).strip()
        game = str(row["Game Status"]).strip()
        if injury in {"Out", "IR", "Doubtful"} or game == "Inactive":
            blocked = True
            row_notes.append("Unavailable injury/game status requires DO NOT USE.")
        elif injury in {"Unknown", ""} or game in {"Unknown", ""}:
            review = True
            row_notes.append("Unknown injury or game status requires review.")
        elif injury == "Questionable" or game == "Game-time decision":
            review = True
            row_notes.append("Questionable or game-time decision requires review.")
        action = "DO NOT USE" if blocked else ("Monitor" if review else str(row["Projection Action"]).strip() or "Use")
        actions.append(action)
        statuses.append(row_status(row_notes, review=review, blocked=blocked))
        notes.append("; ".join(row_notes) if row_notes else "Validated local injury gate input.")
    out["Source"] = str(source)
    out["Updated At"] = out["Updated At"].where(out["Updated At"].astype(str).str.strip() != "", now_utc())
    out["Projection Action"] = actions
    out["Validation Status"] = statuses
    out["Notes"] = notes
    return out


def normalize_odds(df: pd.DataFrame, source: Path, _: dict) -> pd.DataFrame:
    cols = GATE_SPECS["market_odds"]["columns"]
    out = ensure_columns(df, cols)
    statuses, notes, implied, edges, grades = [], [], [], [], []
    for _, row in out.iterrows():
        row_notes: list[str] = []
        review = False
        for col in ["Player Name", "Team", "Market", "Sportsbook", "Line", "Over Odds", "Under Odds"]:
            if not str(row[col]).strip():
                row_notes.append(f"{col} is required.")
        if str(row["Market"]).strip() != "Receptions":
            row_notes.append("Market must be Receptions for V1.")
        implied_prob = american_odds_implied_probability(row["Over Odds"])
        model_prob = pd.to_numeric(row["Model Over Prob"], errors="coerce")
        edge = None
        if implied_prob is None:
            row_notes.append("American odds are required to calculate implied probability.")
        if pd.isna(model_prob):
            review = True
            row_notes.append("Model Over Prob missing; edge cannot be produced.")
        elif implied_prob is not None:
            edge = float(model_prob) - implied_prob
        implied.append("" if implied_prob is None else implied_prob)
        edges.append("" if edge is None else edge)
        grades.append(price_grade(edge))
        statuses.append(row_status(row_notes, review=review))
        notes.append("; ".join(row_notes) if row_notes else "Validated local market odds gate input.")
    out["Source"] = str(source)
    out["Updated At"] = out["Updated At"].where(out["Updated At"].astype(str).str.strip() != "", now_utc())
    out["Implied Over Prob"] = implied
    out["Edge %"] = edges
    out["Price Grade"] = grades
    out["Validation Status"] = statuses
    out["Notes"] = notes
    return out


NORMALIZERS = {
    "schedule": normalize_schedule,
    "roster": normalize_roster,
    "role": normalize_role,
    "injury": normalize_injury,
    "market_odds": normalize_odds,
}


def aggregate_status(df: pd.DataFrame, is_real_data: bool) -> str:
    if not is_real_data or df.empty:
        return "NEEDS DATA"
    statuses = set(df["Validation Status"].astype(str))
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "REVIEW" in statuses:
        return "REVIEW"
    if statuses == {"READY"}:
        return "READY"
    return "CHECK"


def load_gate_inputs() -> pd.DataFrame:
    config = load_config()
    status_rows = []
    for gate, spec in GATE_SPECS.items():
        folder = spec["folder"]
        source = real_input_file(folder)
        is_real_data = source is not None
        if source is None:
            normalized = blank_frame(spec["columns"])
            source_note = f"No real CSV found in {folder}. Template files do not count as real data."
        else:
            raw = pd.read_csv(source, low_memory=False)
            normalized = NORMALIZERS[gate](raw, source, config)
            source_note = str(source)
        out_path = output_path(spec["output"], config)
        normalized.to_csv(out_path, index=False)
        status = aggregate_status(normalized, is_real_data)
        status_rows.append(
            {
                "gate": gate,
                "status": status,
                "rows": len(normalized),
                "is_real_data": is_real_data,
                "source_file": "" if source is None else str(source),
                "normalized_output": str(out_path),
                "notes": source_note,
            }
        )
    status_df = pd.DataFrame(status_rows)
    status_df.to_csv(output_path("gate_inputs_normalized/gate_input_status.csv", config), index=False)
    return status_df


def main() -> None:
    status = load_gate_inputs()
    print(status.to_string(index=False))


if __name__ == "__main__":
    main()
