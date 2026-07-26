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
    maximum_cards_per_team: int = 2
    minimum_share_change: float = 0.15
    minimum_team_denominator: int = 10
    minimum_baseline_share_for_loss: float = 0.25
    minimum_baseline_raw_for_loss: int = 5
    minimum_all_play_normal_gap: float = 0.10
    material_all_play_difference: float = 0.05
    minimum_outside_normal_opportunities: int = 2
    minimum_strong_share: float = 0.25
    minimum_useful_contexts: int = 2
    maximum_role_specific_production_rate: float = 3.0
    maximum_context_facts: int = 2
    context_minimums: tuple[tuple[str, int, int], ...] = (
        ("inside_5", 1, 1),
        ("red_zone", 2, 2),
        ("passing_down", 2, 5),
        ("early_down", 3, 8),
    )
    minimum_raw_opportunities: tuple[tuple[str, int], ...] = (
        ("rb_carry_share", 6),
        ("rb_opportunity_share", 8),
        ("wr_target_share", 5),
        ("te_target_share", 4),
    )

    @property
    def raw_minimums(self) -> dict[str, int]:
        return dict(self.minimum_raw_opportunities)

    @property
    def context_minimum_map(self) -> dict[str, tuple[int, int]]:
        return {context: (raw, denominator) for context, raw, denominator in self.context_minimums}


WEEKLY_REPORT_CONFIG = WeeklyReportConfig()


def role_group(role_family: str) -> str:
    return "backfield" if role_family in {"rb_carry_share", "rb_opportunity_share"} else "target"


def default_home_week(season: int, weeks: Iterable[int]) -> int | None:
    available = sorted(int(week) for week in weeks)
    if not available:
        return None
    if season == 2025 and 18 in available and 17 in available:
        return 17
    return available[-1]


def report_period_notice(week: int) -> tuple[str, str] | None:
    if week == 2:
        return (
            "info",
            "Early-season sample: Week 2 comparisons use Week 1 only, so the baseline is one previous game.",
        )
    if week == 3:
        return (
            "info",
            "Early-season sample: only two prior games can be available for a Week 3 comparison.",
        )
    if week == 18:
        return (
            "warning",
            "Week 18 caution: rest decisions, playoff position, and end-of-season rotations can affect usage.",
        )
    return None


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
                "suspected_partial_corroborated": bool(
                    current.get("suspected_partial_corroborated", False)
                ),
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


def _selected_week_contexts(
    season: int,
    week: int,
    config: WeeklyReportConfig,
) -> pd.DataFrame:
    situational = load_situational_data()
    situational = situational[
        situational["season"].eq(season)
        & situational["week"].eq(week)
        & situational["context"].isin(["early_down", "passing_down", "red_zone", "inside_5"])
    ].copy()
    output_columns = [
        "player_id", "team", "role_family", "useful_contexts", "context_summary",
        "context_detail", "context_facts",
    ]
    if situational.empty:
        return pd.DataFrame(columns=output_columns)
    labels = {
        "early_down": "Early downs",
        "passing_down": "Passing downs",
        "red_zone": "Red zone",
        "inside_5": "Inside five",
    }
    priority = {context: index for index, (context, _, _) in enumerate(config.context_minimums)}
    rows: list[dict[str, object]] = []
    for keys, group in situational.groupby(["player_id", "team", "role_family"], sort=False):
        details: list[dict[str, object]] = []
        qualified: list[dict[str, object]] = []
        for _, item in group.iterrows():
            context = str(item["context"])
            raw = int(item["raw_opportunities"])
            denominator = int(item["team_opportunities"])
            fact = {"context": context, "label": labels[context], "raw": raw, "denominator": denominator}
            if denominator > 0:
                details.append(fact)
            minimum_raw, minimum_denominator = config.context_minimum_map[context]
            if raw >= minimum_raw and denominator >= minimum_denominator:
                qualified.append(fact)
        qualified.sort(
            key=lambda fact: (
                priority[str(fact["context"])],
                -int(fact["raw"]),
                -int(fact["denominator"]),
            )
        )
        selected = tuple(qualified[: config.maximum_context_facts])
        details.sort(key=lambda fact: priority[str(fact["context"])])
        rows.append(
            {
                "player_id": keys[0], "team": keys[1], "role_family": keys[2],
                "useful_contexts": len(qualified), "context_facts": selected,
                "context_summary": "; ".join(
                    f"{fact['label']}: {fact['raw']} of {fact['denominator']}" for fact in selected
                ),
                "context_detail": "; ".join(
                    f"{fact['label']}: {fact['raw']} of {fact['denominator']}" for fact in details
                ),
            }
        )
    return pd.DataFrame(rows, columns=output_columns)


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


def _production_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    carries = pd.to_numeric(result["carries"], errors="coerce").fillna(0)
    targets = pd.to_numeric(result["targets"], errors="coerce").fillna(0)
    receptions = pd.to_numeric(result["receptions"], errors="coerce").fillna(0)
    result["production_yards"] = _production_yards(result).astype(float)
    result["production_metric_denominator"] = np.select(
        [
            result["role_family"].eq("rb_carry_share"),
            result["role_family"].eq("rb_opportunity_share"),
            result["role_family"].isin(["wr_target_share", "te_target_share"]),
        ],
        [carries, carries + receptions, targets],
        default=result["current_raw"],
    ).astype(float)
    result["production_metric_label"] = result["role_family"].map(
        {
            "rb_carry_share": "Yards per carry",
            "rb_opportunity_share": "Yards per touch",
            "wr_target_share": "Receiving yards per target",
            "te_target_share": "Receiving yards per target",
        }
    ).fillna("Production rate")
    result["production_rate"] = result["production_yards"] / result["production_metric_denominator"].replace(0, np.nan)
    result.loc[~result["production_available"], "production_rate"] = np.nan
    return result


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
        & frame["all_play_denominator"].ge(config.minimum_team_denominator)
    ].copy()
    overstated["category"] = CATEGORY_OVERSTATED
    overstated["category_reason"] = "All-play usage materially exceeded normal-game usage because opportunities occurred outside normal context."

    weak = frame[
        frame["current_raw"].ge(raw_minimum)
        & valid_denominator
        & frame["current_share"].ge(config.minimum_strong_share)
        & frame["useful_contexts"].fillna(0).ge(config.minimum_useful_contexts)
        & frame["production_rate"].le(config.maximum_role_specific_production_rate)
    ].copy()
    weak["category"] = CATEGORY_WEAK_PRODUCTION
    weak["category_reason"] = "The player owned a meaningful share across multiple contexts while the role-specific production rate remained low."

    result = pd.concat([gained, lost, overstated, weak], ignore_index=True)
    if result.empty:
        return result
    priority = {category: index for index, category in enumerate(CATEGORY_PRIORITY)}
    result["category_priority"] = result["category"].map(priority).astype(int)
    result["role_group"] = result["role_family"].map(role_group)
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
    result["individual_primary_category"] = result.groupby(
        ["player_id", "role_family"], sort=False
    )["category"].transform("first")
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
        f"{int(row['current_raw'])} of {int(row['current_denominator'])} {_role_noun(str(row['role_family']))}; "
        f"{str(row['production_metric_label']).lower()} was {row['production_rate']:.1f}."
    )


def _explanation(row: pd.Series) -> str:
    category = str(row["category"])
    week = int(row["week"])
    if category == CATEGORY_GAINED:
        if week == 2:
            return f"Week 2 share was {abs(row['share_change']) * 100:.1f} points above Week 1."
        return f"Selected-week share was {abs(row['share_change']) * 100:.1f} points above the prior {int(row['baseline_games'])}-game baseline."
    if category == CATEGORY_LOST:
        teammate = str(row.get("displaced_to_name", "")).strip()
        extra = f" {teammate} had the largest same-family increase for {row['team']}." if teammate else ""
        if week == 2:
            return f"Week 2 share was {abs(row['share_change']) * 100:.1f} points below Week 1.{extra}"
        return f"Selected-week share was {abs(row['share_change']) * 100:.1f} points below the prior {int(row['baseline_games'])}-game baseline.{extra}"
    if category == CATEGORY_OVERSTATED:
        return f"All-play share was {row['all_play_normal_gap'] * 100:.1f} points above normal-game share."
    return f"{row['production_metric_label']} was {row['production_rate']:.1f} in the selected week."


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


def _situation_member(row: pd.Series) -> dict[str, object]:
    return {
        "player_id": str(row["player_id"]),
        "player_name": str(row["player_name"]),
        "category": str(row["individual_primary_category"]),
        "current_raw": int(row["current_raw"]),
        "current_denominator": int(row["current_denominator"]),
        "current_share": float(row["current_share"]),
        "baseline_raw": int(row["baseline_raw"]),
        "baseline_denominator": int(row["baseline_denominator"]),
        "baseline_share": float(row["baseline_share"]),
        "all_play_raw": int(row["all_play_raw"]),
        "all_play_denominator": int(row["all_play_denominator"]),
        "all_play_share": float(row["all_play_share"]),
    }


def _build_situations(matches: pd.DataFrame) -> pd.DataFrame:
    """Collapse reciprocal same-team/family movement into factual situations."""
    if matches.empty:
        return matches
    situations: list[pd.Series] = []
    consumed_players: set[str] = set()
    consumed_team_families: set[tuple[str, str]] = set()
    group_keys = ["season", "week", "team", "role_family"]
    for _, group in matches.groupby(group_keys, sort=False):
        gainers = group[group["category"].eq(CATEGORY_GAINED)].drop_duplicates("player_id")
        losers = group[group["category"].eq(CATEGORY_LOST)].drop_duplicates("player_id")
        if gainers.empty or losers.empty:
            continue
        primary = gainers.sort_values(
            ["share_change", "current_raw", "current_denominator", "player_name"],
            ascending=[False, False, False, True], kind="stable",
        ).iloc[0].copy()
        members = pd.concat([gainers, losers], ignore_index=True).drop_duplicates("player_id")
        member_ids = members["player_id"].astype(str).tolist()
        if any(player_id in consumed_players for player_id in member_ids):
            continue
        consumed_players.update(member_ids)
        consumed_team_families.add((str(primary["team"]), str(primary["role_family"])))
        loser_names = losers.sort_values(
            ["absolute_share_change", "current_raw", "player_name"],
            ascending=[False, False, True], kind="stable",
        )["player_name"].astype(str).tolist()
        primary["category"] = CATEGORY_GAINED
        primary["category_priority"] = CATEGORY_PRIORITY.index(CATEGORY_GAINED)
        primary["situation_type"] = "reciprocal_transfer"
        primary["situation_priority"] = 0
        primary["situation_member_count"] = len(member_ids)
        primary["situation_member_ids"] = " | ".join(member_ids)
        primary["situation_member_names"] = " | ".join(members["player_name"].astype(str))
        primary["situation_member_details"] = tuple(_situation_member(row) for _, row in members.iterrows())
        primary["secondary_categories"] = " | ".join(dict.fromkeys(group["category"].astype(str)))
        primary["headline"] = (
            f"{primary['player_name']} gained {_share_noun(str(primary['role_family']))}; "
            f"{', '.join(loser_names)} lost share."
        )
        counts = ", ".join(
            f"{row['player_name']} {int(row['current_raw'])} of {int(row['current_denominator'])}"
            for _, row in members.iterrows()
        )
        if int(primary["week"]) == 2:
            primary["explanation"] = (
                f"Week 2 share for {primary['player_name']} was {abs(primary['share_change']) * 100:.1f} "
                f"points above Week 1; normal-game counts were {counts}."
            )
        else:
            primary["explanation"] = f"Normal-game counts were {counts}."
        situations.append(primary)

    remaining = matches[~matches["player_id"].astype(str).isin(consumed_players)].copy()
    if consumed_team_families:
        remaining = remaining[
            ~remaining.apply(
                lambda row: (str(row["team"]), str(row["role_family"])) in consumed_team_families,
                axis=1,
            )
        ]
    remaining = remaining.drop_duplicates("player_id", keep="first")
    remaining = remaining.drop_duplicates(["team", "role_family"], keep="first")
    for _, row in remaining.iterrows():
        item = row.copy()
        item["situation_type"] = "individual"
        item["situation_priority"] = 1
        item["situation_member_count"] = 1
        item["situation_member_ids"] = str(row["player_id"])
        item["situation_member_names"] = str(row["player_name"])
        item["situation_member_details"] = (_situation_member(row),)
        situations.append(item)
    if not situations:
        return matches.iloc[0:0].copy()
    result = pd.DataFrame(situations)
    return result.sort_values(
        ["category_priority", "situation_priority", "absolute_share_change", "current_raw", "current_denominator", "player_name"],
        ascending=[True, True, False, False, False, True], kind="stable",
    ).reset_index(drop=True)


def _allocate_default_situations(situations: pd.DataFrame, config: WeeklyReportConfig) -> pd.DataFrame:
    """Apply category capacity, role-group reservation, and same-team caps."""
    if situations.empty:
        return situations
    selected_indices: list[int] = []
    team_counts: dict[str, int] = {}
    for category in CATEGORY_PRIORITY:
        candidates = situations[situations["category"].eq(category)]
        if candidates.empty:
            continue
        groups = candidates["role_group"].dropna().astype(str).unique().tolist()
        required_groups = [group for group in ["backfield", "target"] if group in groups] if len(groups) > 1 else []
        category_indices: list[int] = []

        def add_first(pool: pd.DataFrame) -> bool:
            for index, row in pool.iterrows():
                team = str(row["team"])
                if index in selected_indices or index in category_indices:
                    continue
                if team_counts.get(team, 0) >= config.maximum_cards_per_team:
                    continue
                category_indices.append(index)
                team_counts[team] = team_counts.get(team, 0) + 1
                return True
            return False

        for group in required_groups:
            add_first(candidates[candidates["role_group"].eq(group)])
        while len(category_indices) < config.maximum_cards_per_category:
            if not add_first(candidates):
                break
        selected_indices.extend(category_indices)
        if len(selected_indices) >= config.maximum_default_cards:
            break
    return situations.loc[selected_indices[: config.maximum_default_cards]].reset_index(drop=True)


def _decorate(frame: pd.DataFrame, config: WeeklyReportConfig) -> pd.DataFrame:
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
    result["show_all_play_prominently"] = (
        result["category"].eq(CATEGORY_OVERSTATED)
        | result["all_play_normal_gap"].abs().ge(config.material_all_play_difference)
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
    contexts = _selected_week_contexts(season, week, config)
    production = _selected_week_production(season, week)
    base = base.merge(contexts, on=["player_id", "team", "role_family"], how="left")
    base = base.merge(production, on=["player_id", "game_id"], how="left")
    base["production_available"] = base["carries"].notna() | base["targets"].notna()
    for column in ["carries", "targets", "receptions", "rushing_yards", "receiving_yards"]:
        base[column] = pd.to_numeric(base[column], errors="coerce").fillna(0)
    base["useful_contexts"] = base["useful_contexts"].fillna(0).astype(int)
    base["context_summary"] = base["context_summary"].fillna("")
    base["context_detail"] = base["context_detail"].fillna("")
    base["context_facts"] = base["context_facts"].apply(lambda value: value if isinstance(value, tuple) else tuple())
    base = _production_metrics(base)

    all_matches = _qualifying_categories(base, config)
    if all_matches.empty:
        return all_matches, all_matches
    all_matches = _add_displaced_teammates(all_matches)
    all_matches = _decorate(all_matches, config)
    situations = _build_situations(all_matches)
    primary = _allocate_default_situations(situations, config)
    qualified_counts = {
        (str(category), str(group)): int(count)
        for (category, group), count in situations.groupby(["category", "role_group"]).size().items()
    }
    primary.attrs["qualified_situation_counts"] = qualified_counts
    primary.attrs["qualified_situation_total"] = int(len(situations))
    all_matches = all_matches.reset_index(drop=True)
    all_matches.attrs["qualified_situation_counts"] = qualified_counts
    all_matches.attrs["qualified_situation_total"] = int(len(situations))
    return primary, all_matches


def report_category_counts(frame: pd.DataFrame, categories: Iterable[str] = CATEGORY_PRIORITY) -> dict[str, int]:
    return {category: int(frame["category"].eq(category).sum()) if not frame.empty else 0 for category in categories}
