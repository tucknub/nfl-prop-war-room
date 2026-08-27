from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd


SURGE = "ROLE SURGE"
GAIN = "ROLE GAIN"
STABLE = "ROLE STABLE"
FADE = "ROLE FADE"
DROP = "ROLE DROP"
INSUFFICIENT = "INSUFFICIENT SAMPLE"

STRONGLY_RISING = "Strongly rising"
RISING = "Rising"
STEADY = "Stable"
FALLING = "Falling"
STRONGLY_FALLING = "Strongly falling"
UNKNOWN = "Unclear"

_WINDOW_ORDER = ("Season", "Last 8", "Last 4", "Last 2")


@dataclass(frozen=True)
class RoleChangeSignal:
    classification: str
    trend: str
    confidence: str
    season_share: float | None
    last8_share: float | None
    last4_share: float | None
    last2_share: float | None
    last8_games: int
    last4_games: int
    last2_games: int
    shift_pp: float | None
    recent_step_pp: float | None
    mid_step_pp: float | None
    rank_last8: int | None
    rank_last2: int | None
    rank_label_last8: str | None
    rank_label_last2: str | None
    rank_comparable: bool
    evidence: tuple[str, ...]

    @property
    def rising(self) -> bool:
        return self.trend in {STRONGLY_RISING, RISING}

    @property
    def falling(self) -> bool:
        return self.trend in {STRONGLY_FALLING, FALLING}


def _numeric(value: object) -> float | None:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(number) else float(number)


def _window_row(windows: pd.DataFrame, label: str) -> pd.Series | None:
    if windows.empty or "Window" not in windows:
        return None
    matches = windows[windows["Window"].eq(label)]
    return None if matches.empty else matches.iloc[0]


def _share(windows: pd.DataFrame, label: str) -> float | None:
    row = _window_row(windows, label)
    return None if row is None else _numeric(row.get("Normal share"))


def _games(windows: pd.DataFrame, label: str) -> int:
    row = _window_row(windows, label)
    if row is None:
        return 0
    number = _numeric(row.get("Games"))
    return 0 if number is None else int(number)


def _rank(summary: pd.DataFrame, player_id: str) -> int | None:
    if summary.empty or "player_id" not in summary or "share" not in summary:
        return None
    ranked = summary.dropna(subset=["share"]).copy()
    if ranked.empty:
        return None
    ranked["player_id"] = ranked["player_id"].astype(str)
    ranked = ranked.sort_values(
        ["share", "raw_opportunities", "player_name"],
        ascending=[False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    matches = ranked.index[ranked["player_id"].eq(str(player_id))]
    return None if len(matches) == 0 else int(matches[0]) + 1


def _rank_label(position: str, rank: int | None) -> str | None:
    if rank is None:
        return None
    prefix = str(position or "").strip().upper() or "ROLE"
    return f"{prefix}{rank}"


def _first_text(*values: object) -> str:
    for value in values:
        if value is None or pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _confidence(last8_games: int, last4_games: int, last2_games: int) -> str:
    if last8_games >= 6 and last4_games >= 4 and last2_games >= 2:
        return "HIGH"
    if last4_games >= 3 and last2_games >= 2:
        return "MEDIUM"
    return "LOW"


def _classify(
    last8_share: float | None,
    last4_share: float | None,
    last2_share: float | None,
    *,
    last8_games: int,
    last4_games: int,
    last2_games: int,
    rank_last8: int | None,
    rank_last2: int | None,
    rank_comparable: bool,
) -> tuple[str, str]:
    if (
        last8_share is None
        or last4_share is None
        or last2_share is None
        or last2_games < 2
    ):
        return INSUFFICIENT, UNKNOWN

    shift = last2_share - last8_share
    recent = last2_share - last4_share
    mid = last4_share - last8_share
    rank_gain = (
        rank_comparable
        and rank_last8 is not None
        and rank_last2 is not None
        and rank_last2 < rank_last8
    )
    rank_loss = (
        rank_comparable
        and rank_last8 is not None
        and rank_last2 is not None
        and rank_last2 > rank_last8
    )

    # Strong labels require both magnitude, directional agreement, and a mature sample.
    mature_sample = last8_games >= 6 and last4_games >= 4 and last2_games >= 2
    if mature_sample and shift >= 0.08 and recent >= 0.03 and mid >= 0:
        return SURGE, STRONGLY_RISING
    if mature_sample and shift <= -0.08 and recent <= -0.03 and mid <= 0:
        return DROP, STRONGLY_FALLING

    if (shift >= 0.04 and recent >= -0.005) or (rank_gain and shift >= 0.025):
        return GAIN, RISING
    if (shift <= -0.04 and recent <= 0.005) or (rank_loss and shift <= -0.025):
        return FADE, FALLING

    return STABLE, STEADY


def build_role_change_signal(
    *,
    player_id: str,
    position: str,
    windows: pd.DataFrame,
    team_last8: pd.DataFrame,
    team_last2: pd.DataFrame,
    profile: pd.DataFrame | None = None,
) -> RoleChangeSignal:
    season_share = _share(windows, "Season")
    last8_share = _share(windows, "Last 8")
    last4_share = _share(windows, "Last 4")
    last2_share = _share(windows, "Last 2")

    last8_games = _games(windows, "Last 8")
    last4_games = _games(windows, "Last 4")
    last2_games = _games(windows, "Last 2")

    rank_last8 = _rank(team_last8, player_id)
    rank_last2 = _rank(team_last2, player_id)

    rank_comparable = True
    if profile is not None and not profile.empty and "team" in profile and "week" in profile:
        recent = profile.sort_values("week").tail(8)
        rank_comparable = recent["team"].astype(str).nunique() <= 1

    classification, trend = _classify(
        last8_share,
        last4_share,
        last2_share,
        last8_games=last8_games,
        last4_games=last4_games,
        last2_games=last2_games,
        rank_last8=rank_last8,
        rank_last2=rank_last2,
        rank_comparable=rank_comparable,
    )

    shift_pp = None if last8_share is None or last2_share is None else (last2_share - last8_share) * 100
    recent_step_pp = None if last4_share is None or last2_share is None else (last2_share - last4_share) * 100
    mid_step_pp = None if last8_share is None or last4_share is None else (last4_share - last8_share) * 100

    evidence: list[str] = []
    if shift_pp is not None:
        direction = "up" if shift_pp >= 0 else "down"
        evidence.append(f"Last-2 normal-game share is {abs(shift_pp):.1f} pp {direction} from Last 8.")
    if recent_step_pp is not None:
        direction = "up" if recent_step_pp >= 0 else "down"
        evidence.append(f"Last-2 share is {abs(recent_step_pp):.1f} pp {direction} from Last 4.")
    if rank_comparable and rank_last8 is not None and rank_last2 is not None:
        if rank_last8 != rank_last2:
            evidence.append(
                f"Team role rank moved from {_rank_label(position, rank_last8)} "
                f"to {_rank_label(position, rank_last2)}."
            )
        else:
            evidence.append(f"Team role rank held at {_rank_label(position, rank_last2)}.")
    elif not rank_comparable:
        evidence.append("Team-rank movement is suppressed because the recent window crosses a team change.")

    confidence = _confidence(last8_games, last4_games, last2_games)
    if confidence == "LOW":
        evidence.append("Confidence is LOW because the recent comparison sample is thin.")

    return RoleChangeSignal(
        classification=classification,
        trend=trend,
        confidence=confidence,
        season_share=season_share,
        last8_share=last8_share,
        last4_share=last4_share,
        last2_share=last2_share,
        last8_games=last8_games,
        last4_games=last4_games,
        last2_games=last2_games,
        shift_pp=shift_pp,
        recent_step_pp=recent_step_pp,
        mid_step_pp=mid_step_pp,
        rank_last8=rank_last8,
        rank_last2=rank_last2,
        rank_label_last8=_rank_label(position, rank_last8),
        rank_label_last2=_rank_label(position, rank_last2),
        rank_comparable=rank_comparable,
        evidence=tuple(evidence),
    )


def build_team_role_change_table(
    *,
    role_family: str,
    last8: pd.DataFrame,
    last4: pd.DataFrame,
    last2: pd.DataFrame,
) -> pd.DataFrame:
    if last2.empty:
        return pd.DataFrame()

    def prepared(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["player_id"])
        keep = [
            column
            for column in (
                "player_id",
                "player_name",
                "position",
                "share",
                "sample_games",
                "raw_opportunities",
            )
            if column in frame
        ]
        result = frame[keep].copy()
        return result.rename(
            columns={
                "player_name": f"{prefix}_player_name",
                "position": f"{prefix}_position",
                "share": f"{prefix}_share",
                "sample_games": f"{prefix}_games",
                "raw_opportunities": f"{prefix}_raw",
            }
        )

    merged = prepared(last2, "last2")
    merged = merged.merge(prepared(last4, "last4"), on="player_id", how="outer")
    merged = merged.merge(prepared(last8, "last8"), on="player_id", how="outer")

    rows: list[dict[str, object]] = []
    for _, row in merged.iterrows():
        player_id = str(row.get("player_id") or "").strip()
        if not player_id:
            continue
        player_name = _first_text(
            row.get("last2_player_name"),
            row.get("last4_player_name"),
            row.get("last8_player_name"),
            player_id,
        )
        position = _first_text(
            row.get("last2_position"),
            row.get("last4_position"),
            row.get("last8_position"),
        )
        l8 = _numeric(row.get("last8_share"))
        l4 = _numeric(row.get("last4_share"))
        l2 = _numeric(row.get("last2_share"))
        g8 = int(_numeric(row.get("last8_games")) or 0)
        g4 = int(_numeric(row.get("last4_games")) or 0)
        g2 = int(_numeric(row.get("last2_games")) or 0)

        rank8 = _rank(last8, player_id)
        rank2 = _rank(last2, player_id)
        classification, trend = _classify(
            l8,
            l4,
            l2,
            last8_games=g8,
            last4_games=g4,
            last2_games=g2,
            rank_last8=rank8,
            rank_last2=rank2,
            rank_comparable=True,
        )
        shift_pp = None if l8 is None or l2 is None else (l2 - l8) * 100

        rows.append(
            {
                "player_id": player_id,
                "player_name": str(player_name),
                "position": str(position),
                "role_family": role_family,
                "classification": classification,
                "trend": trend,
                "confidence": _confidence(g8, g4, g2),
                "last8_share": l8,
                "last4_share": l4,
                "last2_share": l2,
                "shift_pp": shift_pp,
                "rank_last8": rank8,
                "rank_last2": rank2,
                "last2_raw": int(_numeric(row.get("last2_raw")) or 0),
            }
        )

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["abs_shift"] = pd.to_numeric(result["shift_pp"], errors="coerce").abs()
    class_order: Mapping[str, int] = {
        SURGE: 0,
        DROP: 1,
        GAIN: 2,
        FADE: 3,
        STABLE: 4,
        INSUFFICIENT: 5,
    }
    result["_class_order"] = result["classification"].map(class_order).fillna(9)
    return result.sort_values(
        ["_class_order", "abs_shift", "last2_raw", "player_name"],
        ascending=[True, False, False, True],
        kind="stable",
    ).drop(columns="_class_order").reset_index(drop=True)
