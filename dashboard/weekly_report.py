from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote

import numpy as np
import pandas as pd

from research_data import (
    ROLE_LABELS,
    load_production_data,
    load_situational_data,
    primary_rows,
)


CATEGORY_GAINED = "Opportunity Gained"
CATEGORY_LOST = "Opportunity Lost"
CATEGORY_OVERSTATED = "Box Score Overstated the Role"
CATEGORY_WEAK_PRODUCTION = "Strong Opportunity, Weak Production"

CATEGORY_PRIORITY = [
    CATEGORY_OVERSTATED,
    CATEGORY_LOST,
    CATEGORY_GAINED,
    CATEGORY_WEAK_PRODUCTION,
]
DISPLAY_CATEGORIES = [
    CATEGORY_GAINED,
    CATEGORY_LOST,
    CATEGORY_OVERSTATED,
    CATEGORY_WEAK_PRODUCTION,
]


@dataclass(frozen=True)
class WeeklyReportConfig:
    baseline_games: int = 4
    minimum_baseline_games: int = 2
    early_season_week: int = 2
    early_season_minimum_baseline_games: int = 1
    maximum_default_cards: int = 12
    maximum_cards_per_category: int = 3
    minimum_share_change: float = 0.15
    minimum_team_denominator: int = 10
    minimum_baseline_share_for_loss: float = 0.25
    minimum_baseline_raw_for_loss: int = 5
    minimum_all_play_normal_gap: float = 0.10
    minimum_outside_normal_opportunities: int = 2
    minimum_strong_share: float = 0.25
    minimum_useful_contexts: int = 2
    maximum_yards_per_opportunity: float = 3.0
    minimum_raw_opportunities: tuple[tuple[str, int], ...] = (
        ("rb_carry_share", 6),
        ("rb_opportunity_share", 8),
        ("wr_target_share", 5),
        ("te_target_share", 4),
    )

    @property
    def raw_minimums(self) -> dict[str, int]:
        return dict(self.minimum_raw_opportunities)


WEEKLY_REPORT_CONFIG = WeeklyReportConfig()


def player_href(player_id: object, season: int, role_family: str, week: int) -> str:
    return (
        f"/players?player={quote(str(player_id))}&season={season}"
        f"&family={quote(role_family)}&week={week}"
    )


def team_href(team: object, season: int, role_family: str, week: int) -> str:
    return (
        f"/teams?team={quote(str(team))}&season={season}"
        f"&family={quote(role_family)}&week={week}"
    )


def game_href(game_id: object, season: int, week: int) -> str:
    return f"/games?season={season}&week={week}&game={quote(str(game_id))}"


def _role_noun(role_family: str) -> str:
    return {
        "rb_carry_share": "team carries",
        "rb_opportunity_share": "team RB opportunities",
        "wr_target_share": "team targets",
        "te_target_share": "team targets",
    }.get(role_family, "team opportunities")


def _share_noun(role_family: str) -> str:
    return {
        "rb_carry_share": "Carry share",
        "rb_opportunity_share": "RB opportunity share",
        "wr_target_share": "Target share",
        "te_target_share": "Target share",
    }.get(role_family, "Opportunity share")


def _baseline_rows(season: int, week: int, config: WeeklyReportConfig) -> pd.DataFrame:
    data = primary_rows()
    data = data[data["season"].eq(season) & data["week"].le(week)].copy()
    rows: list[dict[str, object]] = []
    for _, group in data.groupby(["player_id", "team", "role_family"], sort=False):
        group = group.sort_values("week")
        current = group.iloc[-1]
        if int(current["week"]) != int(week):
            continue
        prior = group.iloc[:-1].tail(config.baseline_games)
        minimum_baseline_games = (
            config.early_season_minimum_baseline_games
            if week == config.early_season_week
            else config.minimum_baseline_games
        )
        if len(prior) < minimum_baseline_games:
            continue
        baseline_denominator = float(prior["team_opportunities_normal"].sum())
        if baseline_denominator <= 0:
            continue
        baseline_raw = float(prior["raw_opportunities_normal"].sum())
        baseline_share = baseline_raw / baseline_denominator
        recent_share = float(current["metric_normal"])
        rows.append(
            {
                "season": int(current["season"]),
                "week": int(current["week"]),
                "game_id": str(current["game_id"]),
                "player_id": str(current["player_id"]),
                "player_name": str(current["player_name"]),
                "team": str(current["team"]),
                "position": str(current["position"]),
                "role_family": str(current["role_family"]),
                "role_family_label": str(current["role_family_label"]),
                "current_raw": int(current["raw_opportunities_normal"]),
                "current_denominator": int(current["team_opportunities_normal"]),
                "current_share": recent_share,
                "all_play_raw": int(current["raw_opportunities_all"]),
                "all_play_denominator": int(current["team_opportunities_all"]),
                "all_play_share": float(current["metric_all"]),
                "baseline_raw": int(baseline_raw),
                "baseline_denominator": int(baseline_denominator),
                "baseline_share": float(baseline_share),
                "baseline_games": int(len(prior)),
                "share_change": float(recent_share - baseline_share),
                "confirmed_partial_game": bool(current["confirmed_partial_game"]),
                "suspected_partial_game": bool(current["suspected_partial_game"]),
                "partial_game_note": str(current["partial_game_note"]),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["absolute_share_change"] = frame["share_change"].abs()
    frame["outside_normal_opportunities"] = (
        frame["all_play_raw"] - frame["current_raw"]
    ).clip(lower=0)
    frame["all_play_normal_gap"] = frame["all_play_share"] - frame["current_share"]
    return frame


def _selected_week_contexts(season: int, week: int) -> pd.DataFrame:
    situational = load_situational_data()
    situational = situational[
        situational["season"].eq(season)
        & situational["week"].eq(week)
        & situational["context"].isin(["early_down", "passing_down", "red_zone", "inside_5"])
    ].copy()
    if situational.empty:
        return pd.DataFrame(columns=["player_id", "team", "role_family", "useful_contexts", "context_summary"])
    positive = situational[situational["raw_opportunities"].gt(0)].copy()
    grouped = positive.groupby(["player_id", "team", "role_family"], as_index=False).agg(
        useful_contexts=("context", "nunique")
    )
    labels = {
        "early_down": "early downs",
        "passing_down": "passing downs",
        "red_zone": "red zone",
        "inside_5": "inside five",
    }
    summaries = (
        positive.sort_values(["raw_opportunities", "context"], ascending=[False, True])
        .groupby(["player_id", "team", "role_family"])["context"]
        .apply(lambda values: ", ".join(labels[value] for value in dict.fromkeys(values)))
        .rename("context_summary")
        .reset_index()
    )
    return grouped.merge(summaries, on=["player_id", "team", "role_family"], how="left")


def _selected_week_production(season: int, week: int) -> pd.DataFrame:
    production = load_production_data()
    production = production[production["season"].eq(season) & production["week"].eq(week)].copy()
    if production.empty:
        return production
    return production[
        [
            "player_id",
            "game_id",
            "carries",
            "targets",
            "receptions",
            "rushing_yards",
            "receiving_yards",
        ]
    ].drop_duplicates(["player_id", "game_id"])


def _production_yards(frame: pd.DataFrame) -> pd.Series:
    rushing = pd.to_numeric(frame["rushing_yards"], errors="coerce").fillna(0)
    receiving = pd.to_numeric(frame["receiving_yards"], errors="coerce").fillna(0)
    return np.select(
        [
            frame["role_family"].eq("rb_carry_share"),
            frame["role_family"].isin(["wr_target_share", "te_target_share"]),
        ],
        [rushing, receiving],
        default=rushing + receiving,
    )


def _qualifying_categories(frame: pd.DataFrame, config: WeeklyReportConfig) -> pd.DataFrame:
    if frame.empty:
        return frame
    raw_minimum = frame["role_family"].map(config.raw_minimums).fillna(1)
    valid_denominator = frame["current_denominator"].ge(config.minimum_team_denominator)

    gained = frame[
        frame["share_change"].ge(config.minimum_share_change)
        & frame["current_raw"].ge(raw_minimum)
        & valid_denominator
    ].copy()
    gained["category"] = CATEGORY_GAINED
    gained["category_reason"] = "Selected-week normal-game share materially exceeded the prior qualifying-game baseline."

    lost = frame[
        frame["share_change"].le(-config.minimum_share_change)
        & frame["baseline_share"].ge(config.minimum_baseline_share_for_loss)
        & frame["baseline_raw"].ge(config.minimum_baseline_raw_for_loss)
        & valid_denominator
    ].copy()
    lost["category"] = CATEGORY_LOST
    lost["category_reason"] = "Selected-week normal-game share was materially below a meaningful prior role."

    overstated = frame[
        frame["all_play_normal_gap"].ge(config.minimum_all_play_normal_gap)
        & frame["outside_normal_opportunities"].ge(config.minimum_outside_normal_opportunities)
        & frame["all_play_raw"].ge(raw_minimum)
        & frame["all_play_denominator"].ge(config.minimum_team_denominator)
    ].copy()
    overstated["category"] = CATEGORY_OVERSTATED
    overstated["category_reason"] = "All-play usage materially exceeded normal-game usage because opportunities occurred outside normal context."

    weak = frame[
        frame["current_raw"].ge(raw_minimum)
        & valid_denominator
        & frame["current_share"].ge(config.minimum_strong_share)
        & frame["useful_contexts"].fillna(0).ge(config.minimum_useful_contexts)
        & frame["yards_per_opportunity"].le(config.maximum_yards_per_opportunity)
    ].copy()
    weak["category"] = CATEGORY_WEAK_PRODUCTION
    weak["category_reason"] = "The player owned a meaningful share across multiple contexts while producing few yards per opportunity."

    result = pd.concat([gained, lost, overstated, weak], ignore_index=True)
    if result.empty:
        return result
    priority = {category: index for index, category in enumerate(CATEGORY_PRIORITY)}
    result["category_priority"] = result["category"].map(priority).astype(int)
    result = result.sort_values(
        [
            "category_priority",
            "absolute_share_change",
            "current_raw",
            "current_denominator",
            "player_name",
        ],
        ascending=[True, False, False, False, True],
        kind="stable",
    ).reset_index(drop=True)
    result["secondary_categories"] = result.groupby("player_id")["category"].transform(
        lambda values: " | ".join(dict.fromkeys(values))
    )
    return result


def _headline(row: pd.Series) -> str:
    category = str(row["category"])
    if category == CATEGORY_GAINED:
        return f"Handled {int(row['current_raw'])} of {int(row['current_denominator'])} {_role_noun(str(row['role_family']))}."
    if category == CATEGORY_LOST:
        return f"{_share_noun(str(row['role_family']))} fell from {row['baseline_share']:.1%} to {row['current_share']:.1%}."
    if category == CATEGORY_OVERSTATED:
        outside = int(row["outside_normal_opportunities"])
        total = int(row["all_play_raw"])
        return f"{outside} of {total} opportunities occurred outside normal-game context."
    return (
        f"Produced {int(row['production_yards'])} yards while handling "
        f"{int(row['current_raw'])} of {int(row['current_denominator'])} {_role_noun(str(row['role_family']))}."
    )


def _explanation(row: pd.Series) -> str:
    category = str(row["category"])
    if category == CATEGORY_GAINED:
        return f"Selected-week share was {abs(row['share_change']) * 100:.1f} points above the prior {int(row['baseline_games'])}-game baseline."
    if category == CATEGORY_LOST:
        teammate = str(row.get("displaced_to_name", "")).strip()
        extra = f" {teammate} had the largest same-family increase for {row['team']}." if teammate else ""
        return f"Selected-week share was {abs(row['share_change']) * 100:.1f} points below the prior {int(row['baseline_games'])}-game baseline.{extra}"
    if category == CATEGORY_OVERSTATED:
        return f"All-play share was {row['all_play_normal_gap'] * 100:.1f} points above normal-game share."
    contexts = str(row.get("context_summary", "")).strip()
    suffix = f" across {contexts}" if contexts else ""
    return f"The player averaged {row['yards_per_opportunity']:.1f} yards per opportunity{suffix}."


def _add_displaced_teammates(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["displaced_to_name"] = ""
    gains = result[result["share_change"].gt(0)].copy()
    if gains.empty:
        return result
    leaders = (
        gains.sort_values(["share_change", "current_raw", "player_name"], ascending=[False, False, True])
        .drop_duplicates(["team", "role_family"])
        .set_index(["team", "role_family"])["player_name"]
    )
    lost_mask = result["category"].eq(CATEGORY_LOST)
    result.loc[lost_mask, "displaced_to_name"] = result.loc[lost_mask].apply(
        lambda row: leaders.get((row["team"], row["role_family"]), ""), axis=1
    )
    return result


def _decorate(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    result["headline"] = result.apply(_headline, axis=1)
    result["explanation"] = result.apply(_explanation, axis=1)
    result["player_href"] = result.apply(
        lambda row: player_href(row["player_id"], int(row["season"]), row["role_family"], int(row["week"])), axis=1
    )
    result["team_href"] = result.apply(
        lambda row: team_href(row["team"], int(row["season"]), row["role_family"], int(row["week"])), axis=1
    )
    result["game_href"] = result.apply(
        lambda row: game_href(row["game_id"], int(row["season"]), int(row["week"])), axis=1
    )
    return result


def build_weekly_role_report(
    season: int,
    week: int,
    config: WeeklyReportConfig = WEEKLY_REPORT_CONFIG,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return default unique-player cards and all technical category matches.

    All comparisons use only earlier qualifying games from the requested season.
    Primary assignment follows ``CATEGORY_PRIORITY``; within a category the
    documented tie-break is absolute share change, current raw count, team
    denominator, then player name.
    """
    base = _baseline_rows(season, week, config)
    if base.empty:
        return base, base
    contexts = _selected_week_contexts(season, week)
    production = _selected_week_production(season, week)
    base = base.merge(contexts, on=["player_id", "team", "role_family"], how="left")
    base = base.merge(production, on=["player_id", "game_id"], how="left")
    base["production_available"] = base["carries"].notna() | base["targets"].notna()
    for column in ["carries", "targets", "receptions", "rushing_yards", "receiving_yards"]:
        base[column] = pd.to_numeric(base[column], errors="coerce").fillna(0)
    base["useful_contexts"] = base["useful_contexts"].fillna(0).astype(int)
    base["context_summary"] = base["context_summary"].fillna("")
    base["production_yards"] = _production_yards(base).astype(float)
    base["yards_per_opportunity"] = base["production_yards"] / base["current_raw"].replace(0, np.nan)
    base.loc[~base["production_available"], "yards_per_opportunity"] = np.nan

    all_matches = _qualifying_categories(base, config)
    if all_matches.empty:
        return all_matches, all_matches
    all_matches = _add_displaced_teammates(all_matches)
    all_matches = _decorate(all_matches)

    primary = all_matches.drop_duplicates("player_id", keep="first").copy()
    primary = (
        primary.groupby("category", group_keys=False, sort=False)
        .head(config.maximum_cards_per_category)
        .head(config.maximum_default_cards)
        .reset_index(drop=True)
    )
    return primary, all_matches.reset_index(drop=True)


def report_category_counts(frame: pd.DataFrame, categories: Iterable[str] = CATEGORY_PRIORITY) -> dict[str, int]:
    return {category: int(frame["category"].eq(category).sum()) if not frame.empty else 0 for category in categories}
