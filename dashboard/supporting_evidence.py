from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


ROLE_NOUNS = {
    "rb_carry_share": "carries",
    "rb_opportunity_share": "backfield work",
    "wr_target_share": "targets",
    "te_target_share": "tight-end targets",
}

REPORT_DEFINITIONS: dict[str, str] = {
    "Backfield Control": "Who controls carries, total RB opportunities, passing downs, and scoring-area work?",
    "Target Hierarchy": "Who controls normal-game and all-play targets?",
    "Scoring-Area Usage": "Who receives red-zone, inside-10, inside-five, and end-zone opportunities?",
    "Role Movement": "Whose recent team opportunity share differs most from the prior period?",
    "Opportunity Versus Production": "Whose production was unusually low or high relative to documented workload?",
    "Game-Script Usage": "How did opportunity change while leading, trailing, or in close games?",
}

EXPLORER_PRESETS: dict[str, dict[str, object]] = {
    "Targets while trailing": {
        "explorer_family": "wr_target_share", "explorer_game_state": "Trailing",
        "explorer_quarter": "All", "explorer_down": "All", "explorer_zone": "All",
        "explorer_two_minute": False, "explorer_normal": False,
    },
    "Normal-game red-zone usage": {
        "explorer_family": "rb_opportunity_share", "explorer_game_state": "All",
        "explorer_quarter": "All", "explorer_down": "All", "explorer_zone": "Red zone",
        "explorer_two_minute": False, "explorer_normal": True,
    },
    "Two-minute targets": {
        "explorer_family": "wr_target_share", "explorer_game_state": "All",
        "explorer_quarter": "All", "explorer_down": "All", "explorer_zone": "All",
        "explorer_two_minute": True, "explorer_normal": False,
    },
    "Inside-five RB opportunities": {
        "explorer_family": "rb_opportunity_share", "explorer_game_state": "All",
        "explorer_quarter": "All", "explorer_down": "All", "explorer_zone": "Inside 5",
        "explorer_two_minute": False, "explorer_normal": False,
    },
    "Early-down carry ownership": {
        "explorer_family": "rb_carry_share", "explorer_game_state": "All",
        "explorer_quarter": "All", "explorer_down": "Early down", "explorer_zone": "All",
        "explorer_two_minute": False, "explorer_normal": False,
    },
    "Passing-down RB opportunities": {
        "explorer_family": "rb_opportunity_share", "explorer_game_state": "All",
        "explorer_quarter": "All", "explorer_down": "Passing down", "explorer_zone": "All",
        "explorer_two_minute": False, "explorer_normal": False,
    },
}


def _names_text(names: list[str]) -> str:
    if not names:
        return "teammates"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def apply_home_wording(frame: pd.DataFrame) -> pd.DataFrame:
    """Change presentation copy only; row identity, order, and category stay untouched."""
    result = frame.copy()
    if result.empty:
        return result
    for index, row in result.iterrows():
        if str(row.get("situation_type", "")) != "reciprocal_transfer":
            continue
        members = list(row.get("situation_member_details", ()) or ())
        gained = [str(item["player_name"]) for item in members if item.get("category") == "Opportunity Gained"]
        lost = [str(item["player_name"]) for item in members if item.get("category") == "Opportunity Lost"]
        primary = gained[0] if gained else str(row["player_name"])
        family = str(row["role_family"])
        if family in {"wr_target_share", "te_target_share"} and lost:
            result.at[index, "headline"] = (
                f"{primary} gained target ownership as {_names_text(lost)} handled a smaller share."
            )
        elif lost:
            result.at[index, "headline"] = (
                f"{row['team']} shifted more {ROLE_NOUNS.get(family, 'opportunity')} toward {primary}."
            )
        result.at[index, "explanation"] = (
            f"{primary}'s share increased while {_names_text(lost)} handled less of the same team opportunity."
            if lost else str(row.get("explanation", ""))
        )
    return result


def home_selection_signature(frame: pd.DataFrame) -> list[tuple[object, ...]]:
    columns = ["season", "week", "player_id", "team", "role_family", "category"]
    if frame.empty:
        return []
    return list(frame[columns].itertuples(index=False, name=None))


def valid_rows(frame: pd.DataFrame, raw: str, denominator: str) -> pd.DataFrame:
    result = frame.copy()
    result[raw] = pd.to_numeric(result[raw], errors="coerce")
    result[denominator] = pd.to_numeric(result[denominator], errors="coerce")
    return result[result[denominator].gt(0) & result[raw].notna()].copy()


def role_leader(
    frame: pd.DataFrame,
    *,
    label: str,
    raw: str = "raw_opportunities",
    denominator: str = "team_denominator",
    share: str = "share",
) -> dict[str, object] | None:
    eligible = valid_rows(frame, raw, denominator)
    if eligible.empty:
        return None
    eligible[share] = pd.to_numeric(eligible[share], errors="coerce")
    eligible = eligible.sort_values([share, raw, "player_name"], ascending=[False, False, True])
    row = eligible.iloc[0]
    return {
        "label": label,
        "player_id": str(row["player_id"]),
        "player_name": str(row["player_name"]),
        "position": str(row.get("position", "")),
        "raw": int(row[raw]),
        "denominator": int(row[denominator]),
        "share": float(row[share]),
        "change": float(row["change"]) if "change" in row and pd.notna(row["change"]) else np.nan,
        "sample_games": int(row["sample_games"]) if "sample_games" in row and pd.notna(row["sample_games"]) else 0,
    }


def situational_leader(frame: pd.DataFrame, context: str, label: str) -> dict[str, object] | None:
    raw, denominator = f"{context}_raw", f"{context}_denominator"
    if raw not in frame or denominator not in frame or context not in frame:
        return None
    return role_leader(frame, label=label, raw=raw, denominator=denominator, share=context)


def player_role_sentence(
    player_name: str,
    team: str,
    position: str,
    role_label: str,
    rank: int,
    peer_count: int,
    season_share: float,
    recent_share: float,
    recent_games: int,
) -> str:
    recent_label = "Last 4" if recent_games >= 4 else f"latest {recent_games}-game sample"
    direction = "above" if recent_share >= season_share else "below"
    return (
        f"{player_name} ranks {rank} of {peer_count} among {team} {position}s in {role_label.lower()}. "
        f"The {recent_label} share is {recent_share:.1%}, {direction} the {season_share:.1%} season share."
    )


def matchup_from_game_id(game_id: object) -> tuple[str, str, str]:
    parts = str(game_id).split("_")
    if len(parts) < 4:
        return str(game_id), "", ""
    away, home = parts[-2], parts[-1]
    return f"{away} at {home}", away, home


def game_team_totals(usage: pd.DataFrame, team: str) -> dict[str, int]:
    rows = usage[usage["team"].astype(str).eq(str(team))]
    def maximum(column: str) -> int:
        values = pd.to_numeric(rows.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
        return int(values.max()) if len(values) else 0
    return {
        "carries": maximum("rb_carry_share_denominator"),
        "rb_opportunities": maximum("rb_opportunity_share_denominator"),
        "targets": max(maximum("wr_target_share_denominator"), maximum("te_target_share_denominator")),
        "normal_rb_opportunities": maximum("rb_opportunity_share_normal_denominator"),
        "normal_targets": max(maximum("wr_target_share_normal_denominator"), maximum("te_target_share_normal_denominator")),
    }


def active_filter_summary(state: Mapping[str, object], role_label: str) -> str:
    parts = [str(state.get("team", "All teams")), role_label]
    for key in ("game_state", "quarter", "down_distance", "field_zone"):
        value = str(state.get(key, "All"))
        if value != "All":
            parts.append(value)
    if bool(state.get("two_minute")):
        parts.append("Two minute")
    parts.append("Normal game" if bool(state.get("normal_game")) else "All play")
    return " · ".join(parts)


def apply_explorer_preset(session_state: Mapping[str, object], preset: str) -> None:
    values = EXPLORER_PRESETS[preset]
    for key, value in values.items():
        session_state[key] = value  # type: ignore[index]
