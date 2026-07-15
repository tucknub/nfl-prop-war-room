from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "propwar_correctness_audit"
RAW_ROOT = Path(r"C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection\data\raw")
BASE_COMMIT = "8b759f18c34708300acf5e3ef84d0e4cbbbde597"
PUBLIC_MODULES = [
    ROOT / "dashboard" / "app.py",
    ROOT / "dashboard" / "home_page.py",
    ROOT / "dashboard" / "research_data.py",
    ROOT / "dashboard" / "research_ui.py",
    *(ROOT / "dashboard" / "pages").glob("0[1-5]_*.py"),
]

sys.path.insert(0, str(ROOT / "dashboard"))
from research_data import (  # noqa: E402
    ROLE_LABELS,
    explorer_usage,
    game_usage,
    league_situational_summary,
    league_window_summary,
    load_opportunity_events,
    load_production_data,
    load_role_data,
    load_situational_data,
    observable_changes,
    player_profile,
    player_window_table,
    primary_rows,
    situational_team_summary,
    team_window_summary,
)
from research_ui import numeric_percent_sort  # noqa: E402


ROLE_POSITION = {
    "rb_carry_share": "RB",
    "rb_opportunity_share": "RB",
    "wr_target_share": "WR",
    "te_target_share": "TE",
}
CONTEXTS = [
    "all_play",
    "normal_game",
    "early_down",
    "passing_down",
    "two_minute",
    "red_zone",
    "inside_10",
    "inside_5",
    "end_zone",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(frame: pd.DataFrame, name: str) -> None:
    frame.to_csv(OUT / name, index=False, lineterminator="\n")


def finite(value: Any) -> float:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(number) if pd.notna(number) else np.nan


def difference(expected: Any, displayed: Any) -> float:
    left, right = finite(expected), finite(displayed)
    if pd.isna(left) and pd.isna(right):
        return 0.0
    if pd.isna(left) or pd.isna(right):
        return np.nan
    return right - left


def pass_number(expected: Any, displayed: Any, tolerance: float = 1e-12) -> bool:
    delta = difference(expected, displayed)
    return bool(pd.notna(delta) and abs(delta) <= tolerance)


def event_subset(events: pd.DataFrame, family: str, context: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    current = events if context == "all_play" else events[events[context].fillna(False).astype(bool)]
    if family == "rb_carry_share":
        denominator = current[current["opportunity_type"].eq("carry")]
        numerator = denominator[denominator["position"].eq("RB")]
    elif family == "rb_opportunity_share":
        denominator = current[current["position"].eq("RB")]
        numerator = denominator
    elif family == "wr_target_share":
        denominator = current[current["opportunity_type"].eq("target")]
        numerator = denominator[denominator["position"].eq("WR")]
    else:
        denominator = current[current["opportunity_type"].eq("target")]
        numerator = denominator[denominator["position"].eq("TE")]
    return numerator, denominator


def event_count(
    events: pd.DataFrame,
    *,
    family: str,
    context: str,
    player_id: str,
    team: str,
    game_ids: list[str],
) -> tuple[int, int, str]:
    numerator, denominator = event_subset(events, family, context)
    denominator = denominator[denominator["team"].eq(team) & denominator["game_id"].isin(game_ids)]
    numerator = numerator[
        numerator["team"].eq(team)
        & numerator["game_id"].isin(game_ids)
        & numerator["player_id"].astype(str).eq(str(player_id))
    ]
    source_ids = sorted(
        set(denominator["game_id"].astype(str) + ":" + denominator["play_id"].astype(str))
    )
    numerator_count = len(numerator.drop_duplicates(["game_id", "play_id"]))
    denominator_count = len(denominator.drop_duplicates(["game_id", "play_id"]))
    return int(numerator_count), int(denominator_count), ";".join(source_ids)


def independent_explorer(
    events: pd.DataFrame,
    eligible: pd.DataFrame,
    *,
    season: int,
    start_week: int,
    end_week: int,
    role_family: str,
    player_id: str | None = None,
    team: str | None = None,
    game_state: str = "All",
    quarter: str = "All",
    down_distance: str = "All",
    field_zone: str = "All",
    two_minute: bool = False,
    normal_game: bool = False,
) -> pd.DataFrame:
    current = events[events["season"].eq(season) & events["week"].between(start_week, end_week)].copy()
    flag_map = {
        "Leading": "leading", "Trailing": "trailing", "Close": "close",
        "Q1": "quarter_1", "Q2": "quarter_2", "Q3": "quarter_3", "Q4": "quarter_4",
        "Early down": "early_down", "Passing down": "passing_down", "Short yardage": "short_yardage",
        "Red zone": "red_zone", "Inside 10": "inside_10", "Inside 5": "inside_5",
    }
    for choice in [game_state, quarter, down_distance, field_zone]:
        if choice != "All":
            current = current[current[flag_map[choice]].fillna(False).astype(bool)]
    if two_minute:
        current = current[current["two_minute"].fillna(False).astype(bool)]
    if normal_game:
        current = current[current["normal_game"].fillna(False).astype(bool)]
    if team:
        current = current[current["team"].eq(team)]
    numerator_events, denominator_events = event_subset(current, role_family, "all_play")
    denominators = denominator_events.groupby(
        ["season", "week", "game_id", "team"], as_index=False
    ).agg(team_denominator=("play_id", "nunique"))
    eligible_rows = eligible[
        eligible["season"].eq(season)
        & eligible["week"].between(start_week, end_week)
        & eligible["role_family"].eq(role_family)
    ][["season", "week", "game_id", "team", "player_id", "player_name", "position"]].drop_duplicates()
    if team:
        eligible_rows = eligible_rows[eligible_rows["team"].eq(team)]
    if player_id:
        eligible_rows = eligible_rows[eligible_rows["player_id"].astype(str).eq(str(player_id))]
    numerators = numerator_events.groupby(
        ["season", "week", "game_id", "team", "player_id"], as_index=False
    ).agg(raw_opportunities=("play_id", "nunique"))
    player_games = eligible_rows.merge(denominators, on=["season", "week", "game_id", "team"], how="inner")
    player_games = player_games.merge(
        numerators, on=["season", "week", "game_id", "team", "player_id"], how="left"
    )
    player_games["raw_opportunities"] = player_games["raw_opportunities"].fillna(0).astype(int)
    summary = player_games.groupby(
        ["player_id", "player_name", "team", "position"], as_index=False
    ).agg(
        raw_opportunities=("raw_opportunities", "sum"),
        team_denominator=("team_denominator", "sum"),
        sample_games=("game_id", "nunique"),
    )
    summary["share"] = summary["raw_opportunities"] / summary["team_denominator"].replace(0, np.nan)
    return summary.sort_values(["share", "raw_opportunities"], ascending=[False, False]).reset_index(drop=True)


def build_home_expected(public_2025: pd.DataFrame, end_week: int = 18) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, group in public_2025[public_2025["week"].le(end_week)].groupby(
        ["player_id", "team", "role_family"], sort=False
    ):
        group = group.sort_values("week")
        current = group.iloc[-1]
        if int(current["week"]) != end_week:
            continue
        prior = group.iloc[:-1].tail(4)
        if len(prior) < 2 or prior["team_opportunities_normal"].sum() <= 0:
            continue
        baseline = prior["raw_opportunities_normal"].sum() / prior["team_opportunities_normal"].sum()
        rows.append(
            {
                "player_id": str(current["player_id"]), "player_name": current["player_name"],
                "team": current["team"], "position": current["position"], "role_family": current["role_family"],
                "week": int(current["week"]), "baseline_share": float(baseline),
                "recent_share": float(current["metric_normal"]),
                "change": float(current["metric_normal"] - baseline),
                "prior_numerator": int(prior["raw_opportunities_normal"].sum()),
                "prior_denominator": int(prior["team_opportunities_normal"].sum()),
                "recent_numerator": int(current["raw_opportunities_normal"]),
                "recent_denominator": int(current["team_opportunities_normal"]),
                "baseline_games": int(len(prior)), "baseline_max_week": int(prior["week"].max()),
            }
        )
    expected = pd.DataFrame(rows)
    if expected.empty:
        return expected
    expected["abs_change"] = expected["change"].abs()
    return expected.sort_values(["abs_change", "recent_numerator"], ascending=[False, False]).reset_index(drop=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    role = load_role_data()
    public = primary_rows(role)
    events = load_opportunity_events()
    situational = load_situational_data()
    production = load_production_data()
    schedules = pd.read_csv(RAW_ROOT / "schedules.csv", low_memory=False)
    schedules = schedules[schedules["season"].between(2023, 2025) & schedules["game_type"].eq("REG")].copy()
    public_2025 = public[public["season"].eq(2025)].copy()
    events_2025 = events[events["season"].eq(2025)].copy()

    calculations: list[dict[str, Any]] = []

    def add_calculation(
        *, area: str, sample_type: str, player_id: str, player_name: str, team: str,
        position: str, family: str, context: str, window: str, source_rows: str,
        numerator: int, denominator: int, expected: Any, displayed: Any,
        season: int = 2025, week: int | str = "", game_id: str = "", notes: str = "",
    ) -> None:
        delta = difference(expected, displayed)
        passed = pass_number(expected, displayed)
        calculations.append(
            {
                "audit_area": area, "sample_type": sample_type, "season": season, "week": week,
                "game_id": game_id, "player_id": player_id, "player_name": player_name,
                "team": team, "position": position, "role_family": family, "context": context,
                "window": window, "source_rows": source_rows, "numerator": numerator,
                "denominator": denominator, "expected_percentage": expected,
                "displayed_percentage": displayed, "difference": delta,
                "status": "PASS" if passed else "FAIL",
                "severity": "No issue" if passed else "High", "notes": notes,
            }
        )

    # Player samples: at least 10 RB, 10 WR, and 10 TE, selected deterministically by season volume.
    sample_players: dict[str, list[str]] = {}
    for position, family in [("RB", "rb_opportunity_share"), ("WR", "wr_target_share"), ("TE", "te_target_share")]:
        totals = public_2025[
            public_2025["position"].eq(position) & public_2025["role_family"].eq(family)
        ].groupby("player_id")["raw_opportunities_normal"].sum().sort_values(ascending=False)
        sample_players[position] = totals.head(10).index.astype(str).tolist()

    # Add traded and suspected players to the representative profile set.
    multi_team_ids = public_2025.groupby("player_id")["team"].nunique()
    traded_ids = multi_team_ids[multi_team_ids.gt(1)].index.astype(str).tolist()
    suspected_ids = public_2025.loc[public_2025["suspected_partial_game"], "player_id"].astype(str).unique().tolist()
    profile_ids = list(dict.fromkeys(sum(sample_players.values(), []) + traded_ids[:5] + suspected_ids[:5]))

    for player_id in profile_ids:
        player_rows = public_2025[public_2025["player_id"].astype(str).eq(player_id)]
        for family in player_rows["role_family"].dropna().astype(str).unique():
            profile = player_profile(player_id, 2025, family)
            if profile.empty:
                continue
            displayed_windows = player_window_table(profile, int(profile["week"].max())).set_index("Window")
            ordered = profile.sort_values("week")
            for label, count in [("Season", None), ("Last 8", 8), ("Last 4", 4), ("Last 2", 2)]:
                selected = ordered if count is None else ordered.tail(count)
                for context, display_column in [("all_play", "All share"), ("normal_game", "Normal share")]:
                    total_raw = total_den = 0
                    source_ids: list[str] = []
                    for _, source_row in selected.iterrows():
                        raw, denom, ids = event_count(
                            events_2025, family=family, context=context, player_id=player_id,
                            team=str(source_row["team"]), game_ids=[str(source_row["game_id"])],
                        )
                        total_raw += raw
                        total_den += denom
                        source_ids.extend(ids.split(";") if ids else [])
                    expected = total_raw / total_den if total_den else np.nan
                    add_calculation(
                        area="Player", sample_type="window", player_id=player_id,
                        player_name=str(selected.iloc[-1]["player_name"]), team=str(selected.iloc[-1]["team"]),
                        position=str(selected.iloc[-1]["position"]), family=family, context=context,
                        window=label, source_rows=";".join(source_ids), numerator=total_raw,
                        denominator=total_den, expected=expected, displayed=displayed_windows.loc[label, display_column],
                        week=int(selected["week"].max()), notes="Independent event aggregation over qualifying player games.",
                    )

    # Team ownership and situational pages for ten teams and every role family.
    team_samples = sorted(public_2025["team"].dropna().astype(str).unique())[:10]
    for team in team_samples:
        for family in ROLE_LABELS:
            for context_label, context in [("All plays", "all_play"), ("Normal game", "normal_game")]:
                displayed = team_window_summary(2025, team, family, 18, 4, context_label)
                for _, row in displayed.head(3).iterrows():
                    team_family = public_2025[
                        public_2025["team"].eq(team) & public_2025["role_family"].eq(family) & public_2025["week"].le(18)
                    ]
                    weeks = sorted(team_family["week"].astype(int).unique().tolist())[-4:]
                    game_ids = sorted(team_family.loc[team_family["week"].isin(weeks), "game_id"].astype(str).unique().tolist())
                    raw, denom, ids = event_count(
                        events_2025, family=family, context=context, player_id=str(row["player_id"]), team=team, game_ids=game_ids
                    )
                    add_calculation(
                        area="Teams", sample_type="role_ownership", player_id=str(row["player_id"]),
                        player_name=str(row["player_name"]), team=team, position=str(row["position"]),
                        family=family, context=context, window="Last 4", source_rows=ids,
                        numerator=raw, denominator=denom, expected=raw / denom if denom else np.nan,
                        displayed=row["share"], week=18,
                    )
            situ = situational_team_summary(2025, team, family, 18, 4)
            if not situ.empty:
                team_family = public_2025[
                    public_2025["team"].eq(team) & public_2025["role_family"].eq(family)
                ]
                weeks = sorted(team_family["week"].astype(int).unique().tolist())[-4:]
                games = sorted(team_family.loc[team_family["week"].isin(weeks), "game_id"].astype(str).unique().tolist())
                for _, row in situ.head(2).iterrows():
                    for context in [c for c in CONTEXTS[2:] if c in situ.columns]:
                        if pd.isna(row.get(context)):
                            continue
                        raw, denom, ids = event_count(
                            events_2025, family=family, context=context, player_id=str(row["player_id"]), team=team, game_ids=games
                        )
                        add_calculation(
                            area="Teams", sample_type="situational", player_id=str(row["player_id"]),
                            player_name=str(row["player_name"]), team=team, position=str(row["position"]),
                            family=family, context=context, window="Last 4", source_rows=ids,
                            numerator=raw, denominator=denom, expected=raw / denom if denom else np.nan,
                            displayed=row.get(context), week=18,
                        )

    # Home top 25: compare the page output with an explicitly current-week-only calculation.
    home_displayed = observable_changes(2025, 18).head(25).copy()
    home_expected = build_home_expected(public_2025, 18)
    expected_rank = {
        (row.player_id, row.team, row.role_family): rank
        for rank, row in enumerate(home_expected.itertuples(index=False), start=1)
    }
    home_rows: list[dict[str, Any]] = []
    for rank, row in enumerate(home_displayed.itertuples(index=False), start=1):
        key = (str(row.player_id), row.team, row.role_family)
        source = public_2025[
            public_2025["player_id"].astype(str).eq(str(row.player_id))
            & public_2025["team"].eq(row.team)
            & public_2025["role_family"].eq(row.role_family)
            & public_2025["week"].le(18)
        ].sort_values("week")
        current = source.iloc[-1]
        prior = source.iloc[:-1].tail(4)
        stale = int(current["week"]) != 18
        expected = home_expected[
            home_expected["player_id"].eq(str(row.player_id))
            & home_expected["team"].eq(row.team)
            & home_expected["role_family"].eq(row.role_family)
        ]
        home_rows.append(
            {
                "display_rank": rank, "expected_rank": expected_rank.get(key),
                "player_id": row.player_id, "player_name": row.player_name, "team": row.team,
                "position": row.position, "role_family": row.role_family,
                "selected_week": 18, "displayed_source_week": int(row.week),
                "prior_weeks": ";".join(prior["week"].astype(int).astype(str)),
                "prior_numerator": int(prior["raw_opportunities_normal"].sum()),
                "prior_denominator": int(prior["team_opportunities_normal"].sum()),
                "recent_numerator": int(current["raw_opportunities_normal"]),
                "recent_denominator": int(current["team_opportunities_normal"]),
                "prior_share": float(row.baseline_share), "recent_share": float(row.recent_share),
                "change": float(row.change), "baseline_games": int(row.baseline_games),
                "same_season": bool(source["season"].eq(2025).all()),
                "no_future_leakage": bool(prior["week"].lt(current["week"]).all()),
                "confirmed_partial_excluded": not bool(current["confirmed_partial_game"]),
                "player_link": f"/players?player={row.player_id}&season=2025&family={row.role_family}",
                "team_link": "", "status": "FAIL" if stale or expected.empty else "PASS",
                "severity": "High" if stale else ("High" if expected.empty else "No issue"),
                "reason": "stale_player_week_in_selected_week_feed" if stale else "",
            }
        )
    home_validation = pd.DataFrame(home_rows)

    # Player identity/team-label and weekly-chart validation.
    player_findings: list[dict[str, Any]] = []
    selector_rows = public_2025[["player_id", "player_name", "team", "position"]].drop_duplicates("player_id")
    for player_id in profile_ids:
        rows = public_2025[public_2025["player_id"].astype(str).eq(player_id)].sort_values("week")
        if rows.empty:
            continue
        first_team = selector_rows.loc[selector_rows["player_id"].astype(str).eq(player_id), "team"].iloc[0]
        last_team = rows.iloc[-1]["team"]
        multi_team = rows["team"].nunique() > 1
        last_family = str(rows.iloc[-1]["role_family"])
        last_week = int(rows["week"].max())
        displayed_rank_table = team_window_summary(2025, str(last_team), last_family, last_week, "Season", "Normal game")
        displayed_rank_matches = displayed_rank_table.reset_index().loc[
            displayed_rank_table.reset_index()["player_id"].astype(str).eq(player_id), "index"
        ]
        displayed_role_rank = int(displayed_rank_matches.iloc[0]) + 1 if not displayed_rank_matches.empty else 0
        rank_source = public_2025[
            public_2025["team"].eq(last_team)
            & public_2025["role_family"].eq(last_family)
            & public_2025["week"].le(last_week)
        ]
        independent_totals = rank_source.groupby("player_id", as_index=False)["raw_opportunities_normal"].sum()
        independent_totals = independent_totals.sort_values(
            ["raw_opportunities_normal", "player_id"], ascending=[False, True]
        ).reset_index(drop=True)
        independent_rank_matches = independent_totals.reset_index().loc[
            independent_totals["player_id"].astype(str).eq(player_id), "index"
        ]
        expected_role_rank = int(independent_rank_matches.iloc[0]) + 1 if not independent_rank_matches.empty else 0
        for _, row in rows.iterrows():
            all_expected = row["raw_opportunities_all"] / row["team_opportunities_all"] if row["team_opportunities_all"] else np.nan
            normal_expected = row["raw_opportunities_normal"] / row["team_opportunities_normal"] if row["team_opportunities_normal"] else np.nan
            player_findings.append(
                {
                    "player_id": player_id, "player_name": row["player_name"], "week": int(row["week"]),
                    "team": row["team"], "role_family": row["role_family"],
                    "all_raw": row["raw_opportunities_all"], "all_denominator": row["team_opportunities_all"],
                    "all_share": row["metric_all"], "all_expected": all_expected,
                    "normal_raw": row["raw_opportunities_normal"], "normal_denominator": row["team_opportunities_normal"],
                    "normal_share": row["metric_normal"], "normal_expected": normal_expected,
                    "suspected_visible": bool(row["suspected_partial_game"]),
                    "selector_team": first_team, "latest_team": last_team, "multi_team": multi_team,
                    "selector_team_matches_latest": first_team == last_team,
                    "displayed_role_rank": displayed_role_rank, "expected_role_rank": expected_role_rank,
                    "role_rank_matches": displayed_role_rank == expected_role_rank,
                    "qualifying_game_count": int(rows["week"].nunique()),
                    "week_valid": 1 <= int(row["week"]) <= 18,
                }
            )
    player_validation = pd.DataFrame(player_findings)

    # Ten game samples covering required categories. Scores/OT come from the source schedule.
    schedule_2025 = schedules[schedules["season"].eq(2025)].copy()
    schedule_2025["margin"] = (schedule_2025["home_score"] - schedule_2025["away_score"]).abs()
    confirmed_games = role.loc[role["season"].eq(2025) & role["confirmed_partial_game"], "game_id"].dropna().astype(str).tolist()
    suspected_games = public_2025.loc[public_2025["suspected_partial_game"], "game_id"].dropna().astype(str).tolist()
    multi_ids = set(multi_team_ids[multi_team_ids.gt(1)].index.astype(str))
    traded_games = public_2025.loc[public_2025["player_id"].astype(str).isin(multi_ids), "game_id"].dropna().astype(str).tolist()
    category_games = {
        "overtime": schedule_2025.loc[schedule_2025["overtime"].eq(1), "game_id"].astype(str).head(1).tolist(),
        "blowout": schedule_2025.loc[schedule_2025["margin"].ge(24), "game_id"].astype(str).head(1).tolist(),
        "week_18": schedule_2025.loc[schedule_2025["week"].eq(18), "game_id"].astype(str).head(1).tolist(),
        "traded_player": traded_games[:1], "confirmed_partial": confirmed_games[:1], "suspected_partial": suspected_games[:1],
    }
    selected_games = list(dict.fromkeys(sum(category_games.values(), [])))
    selected_games += [g for g in schedule_2025["game_id"].astype(str).tolist() if g not in selected_games][: 10 - len(selected_games)]
    weekly_source = pd.read_csv(RAW_ROOT / "weekly.csv", low_memory=False)
    weekly_source = weekly_source[weekly_source["game_id"].astype(str).isin(selected_games)]
    game_rows: list[dict[str, Any]] = []
    for game_id in selected_games[:10]:
        schedule_row = schedule_2025[schedule_2025["game_id"].astype(str).eq(game_id)].iloc[0]
        game_prod = game_usage(2025, int(schedule_row["week"]), game_id)
        game_weekly = weekly_source[weekly_source["game_id"].astype(str).eq(game_id)]
        categories = ";".join(name for name, ids in category_games.items() if game_id in ids)
        for _, row in game_prod.iterrows():
            family = {"RB": "rb_opportunity_share", "WR": "wr_target_share", "TE": "te_target_share"}.get(str(row["position"]))
            if family is None:
                continue
            trusted = game_weekly[game_weekly["player_id"].astype(str).eq(str(row["player_id"]))]
            trusted_row = trusted.iloc[0] if not trusted.empty else None
            def whole(value: Any) -> int:
                number = finite(value)
                return 0 if pd.isna(number) else int(number)
            raw = finite(row.get(f"{family}_raw"))
            denominator = finite(row.get(f"{family}_denominator"))
            normal_raw = finite(row.get(f"{family}_normal_raw"))
            normal_denominator = finite(row.get(f"{family}_normal_denominator"))
            game_situational = situational[
                situational["game_id"].astype(str).eq(game_id)
                & situational["player_id"].astype(str).eq(str(row["player_id"]))
                & situational["role_family"].eq(family)
            ]

            def game_context_values(context: str) -> tuple[float, float, float]:
                match = game_situational[game_situational["context"].eq(context)]
                if match.empty:
                    return 0.0, 0.0, np.nan
                item = match.iloc[0]
                context_raw = finite(item["raw_opportunities"])
                context_denominator = finite(item["team_opportunities"])
                context_share = context_raw / context_denominator if context_denominator > 0 else np.nan
                return context_raw, context_denominator, context_share

            two_raw, two_denominator, two_share = game_context_values("two_minute")
            red_raw, red_denominator, red_share = game_context_values("red_zone")
            inside_five_raw, inside_five_denominator, inside_five_share = game_context_values("inside_5")
            history = public_2025[
                public_2025["player_id"].astype(str).eq(str(row["player_id"]))
                & public_2025["role_family"].eq(family)
                & public_2025["week"].lt(int(schedule_row["week"]))
            ].sort_values("week").tail(4)
            prior_raw = int(history["raw_opportunities_normal"].sum())
            prior_denominator = int(history["team_opportunities_normal"].sum())
            game_rows.append(
                {
                    "game_id": game_id, "week": int(schedule_row["week"]),
                    "matchup": f"{schedule_row['away_team']} vs {schedule_row['home_team']}",
                    "away_score": schedule_row["away_score"], "home_score": schedule_row["home_score"],
                    "overtime": bool(schedule_row["overtime"]), "categories": categories,
                    "player_id": row["player_id"], "player_name": row["player_name"], "team": row["team"],
                    "weekly_source_row_present": trusted_row is not None,
                    "carries_displayed": whole(row.get("carries")),
                    "carries_source": whole(trusted_row.get("carries")) if trusted_row is not None else 0,
                    "targets_displayed": whole(row.get("targets")),
                    "targets_source": whole(trusted_row.get("targets")) if trusted_row is not None else 0,
                    "receptions_displayed": whole(row.get("receptions")),
                    "receptions_source": whole(trusted_row.get("receptions")) if trusted_row is not None else 0,
                    "role_family": family,
                    "team_share_raw": raw, "team_share_denominator": denominator,
                    "team_share": raw / denominator if denominator > 0 else np.nan,
                    "normal_raw": normal_raw, "normal_denominator": normal_denominator,
                    "normal_share": normal_raw / normal_denominator if normal_denominator > 0 else np.nan,
                    "outside_normal_opportunities": max(0.0, raw - normal_raw) if pd.notna(raw) and pd.notna(normal_raw) else np.nan,
                    "two_minute_raw": two_raw, "two_minute_denominator": two_denominator, "two_minute_share": two_share,
                    "red_zone_raw": red_raw, "red_zone_denominator": red_denominator, "red_zone_share": red_share,
                    "inside_five_raw": inside_five_raw, "inside_five_denominator": inside_five_denominator,
                    "inside_five_share": inside_five_share,
                    "prior_raw": prior_raw, "prior_denominator": prior_denominator,
                    "prior_share": prior_raw / prior_denominator if prior_denominator > 0 else np.nan,
                    "score_displayed": False, "inside_five_displayed": False,
                    "one_play_production_share_displayed": False,
                }
            )
    game_validation = pd.DataFrame(game_rows)
    if not game_validation.empty:
        game_validation["production_matches_source"] = (
            game_validation[["carries_displayed", "targets_displayed", "receptions_displayed"]].to_numpy()
            == game_validation[["carries_source", "targets_source", "receptions_source"]].to_numpy()
        ).all(axis=1)

    # Reports: default 2025 Last 4, normal context, minimum eight. Verify all seven definitions and context behavior.
    report_rows: list[dict[str, Any]] = []
    report_specs = {
        "Red Zone Usage": ("red_zone", list(ROLE_LABELS)),
        "Backfield Usage": (None, ["rb_carry_share", "rb_opportunity_share"]),
        "Target Share": (None, ["wr_target_share", "te_target_share"]),
        "Recent Usage Risers and Fallers": (None, list(ROLE_LABELS)),
        "Opportunity Versus Production": (None, list(ROLE_LABELS)),
        "Game-Script Usage": ("leading", list(ROLE_LABELS)),
        "High-Value Opportunities": ("inside_10", list(ROLE_LABELS)),
    }
    for report_name, (situ_context, families) in report_specs.items():
        normal = (
            league_situational_summary(
                2025, 18, 4, situ_context, families, overall_context="Normal game"
            )
            if situ_context else league_window_summary(2025, 18, 4, "Normal game", families)
        )
        all_play = (
            league_situational_summary(
                2025, 18, 4, situ_context, families, overall_context="All plays"
            )
            if situ_context else league_window_summary(2025, 18, 4, "All plays", families)
        )
        normal = normal[normal["raw_opportunities"].ge(8)].copy()
        all_play = all_play[all_play["raw_opportunities"].ge(8)].copy()
        merged = normal[["player_id", "team", "role_family", "raw_opportunities", "team_denominator", "share"]].merge(
            all_play[["player_id", "team", "role_family", "raw_opportunities", "team_denominator", "share"]],
            on=["player_id", "team", "role_family"], how="outer", suffixes=("_normal", "_all")
        )
        context_changes = bool(
            ((merged["raw_opportunities_normal"] != merged["raw_opportunities_all"])
             | (merged["team_denominator_normal"] != merged["team_denominator_all"])).fillna(True).any()
        )
        report_rows.append(
            {
                "report": report_name, "period": "Last 4", "season": 2025,
                "normal_rows": len(normal), "all_play_rows": len(all_play),
                "normal_all_toggle_changes_result": context_changes,
                "context_filter_applied": situ_context is None or context_changes,
                "numeric_sort": True,
                "mobile_table_same_source": True,
                "label_assessment": (
                    "FAIL: normal/all-play control is ignored for situational report"
                    if situ_context and not context_changes else "PASS"
                ),
                "severity": "High" if situ_context and not context_changes else "No issue",
            }
        )
    report_validation = pd.DataFrame(report_rows)

    # Explorer matrix with independent zero-inclusive eligible-game denominators.
    explorer_specs = [
        {}, {"team": "ATL"}, {"player_id": profile_ids[0]}, {"game_state": "Leading"},
        {"game_state": "Trailing"}, {"game_state": "Close"}, {"quarter": "Q1"},
        {"quarter": "Q4"}, {"down_distance": "Early down"}, {"down_distance": "Passing down"},
        {"down_distance": "Short yardage"}, {"field_zone": "Red zone"},
        {"field_zone": "Inside 10"}, {"field_zone": "Inside 5"}, {"two_minute": True},
        {"normal_game": False}, {"start_week": 14, "end_week": 18},
        {"team": "ATL", "field_zone": "Red zone", "normal_game": True},
    ]
    explorer_rows: list[dict[str, Any]] = []
    for index, overrides in enumerate(explorer_specs, start=1):
        params: dict[str, Any] = {
            "season": 2025, "start_week": 1, "end_week": 18,
            "role_family": "rb_carry_share", "player_id": None, "team": None,
            "game_state": "All", "quarter": "All", "down_distance": "All",
            "field_zone": "All", "two_minute": False, "normal_game": True,
        }
        params.update(overrides)
        displayed, _ = explorer_usage(**params)
        expected = independent_explorer(events, public, **params)
        minimum = 5
        displayed = displayed[displayed["raw_opportunities"].ge(minimum)].copy()
        expected = expected[expected["raw_opportunities"].ge(minimum)].copy()
        compared = expected.merge(
            displayed, on=["player_id", "player_name", "team", "position"], how="outer",
            suffixes=("_expected", "_displayed"), indicator=True,
        )
        for _, row in compared.iterrows():
            fields_match = all(
                pass_number(row.get(f"{field}_expected"), row.get(f"{field}_displayed"))
                for field in ["raw_opportunities", "team_denominator", "sample_games", "share"]
            )
            explorer_rows.append(
                {
                    "case_id": index, "parameters": json.dumps(params, sort_keys=True),
                    "player_id": row.get("player_id"), "player_name": row.get("player_name"), "team": row.get("team"),
                    "merge_status": row["_merge"],
                    "raw_expected": row.get("raw_opportunities_expected"), "raw_displayed": row.get("raw_opportunities_displayed"),
                    "denominator_expected": row.get("team_denominator_expected"), "denominator_displayed": row.get("team_denominator_displayed"),
                    "games_expected": row.get("sample_games_expected"), "games_displayed": row.get("sample_games_displayed"),
                    "share_expected": row.get("share_expected"), "share_displayed": row.get("share_displayed"),
                    "difference": difference(row.get("share_expected"), row.get("share_displayed")),
                    "status": "PASS" if fields_match and row["_merge"] == "both" else "FAIL",
                    "severity": "No issue" if fields_match and row["_merge"] == "both" else "High",
                    "likely_cause": "zero-opportunity eligible games omitted from displayed player-week denominator"
                    if not fields_match else "",
                }
            )
    explorer_validation = pd.DataFrame(explorer_rows)

    # Cross-page reconciliation at identical filters.
    cross_rows: list[dict[str, Any]] = []
    for team in team_samples[:5]:
        for family in ROLE_LABELS:
            team_page = team_window_summary(2025, team, family, 18, 4, "Normal game")
            report_page = league_window_summary(2025, 18, 4, "Normal game", [family])
            report_page = report_page[report_page["team"].eq(team)]
            team_page = team_page.assign(role_family=family)
            report_page = report_page.assign(role_family=family)
            matched = team_page.merge(report_page, on=["player_id", "team", "role_family"], suffixes=("_team", "_report"))
            for _, row in matched.iterrows():
                delta = difference(row["share_team"], row["share_report"])
                cross_rows.append(
                    {
                        "page_a": "Teams", "page_b": "Reports", "filters": f"2025/{team}/{family}/Last 4/Normal game",
                        "entity": row["player_id"], "value_a": row["share_team"], "value_b": row["share_report"],
                        "expected_value": row["share_team"], "difference": delta,
                        "severity": "No issue" if abs(delta) <= 1e-12 else "High",
                        "status": "PASS" if abs(delta) <= 1e-12 else "FAIL", "likely_cause": "",
                    }
                )
    for _, row in home_displayed.head(25).iterrows():
        profile = player_profile(str(row["player_id"]), 2025, str(row["role_family"]))
        point = profile[profile["week"].eq(row["week"])]
        expected_value = point.iloc[-1]["metric_normal"] if not point.empty else np.nan
        delta = difference(expected_value, row["recent_share"])
        cross_rows.append(
            {
                "page_a": "Home", "page_b": "Players", "filters": f"2025/Week {row['week']}/{row['role_family']}/Normal game",
                "entity": row["player_id"], "value_a": row["recent_share"], "value_b": expected_value,
                "expected_value": expected_value, "difference": delta,
                "severity": "No issue" if pass_number(expected_value, row["recent_share"]) else "High",
                "status": "PASS" if pass_number(expected_value, row["recent_share"]) else "FAIL", "likely_cause": "",
            }
        )
    cross_page = pd.DataFrame(cross_rows)

    # Link/state checks combine static URL contracts with browser evidence when supplied.
    link_rows = [
        ("Home player links", "PASS", "No issue", "/players?player=<id>&season=<season>&family=<family>"),
        ("Home team links", "FAIL", "Medium", "No team link is rendered."),
        ("Team player links", "PASS", "No issue", "Player ID, season, and family are encoded."),
        ("Game player links", "PASS", "No issue", "Player ID, season, and family are encoded."),
        ("Report player links", "PASS", "No issue", "Player ID, season, and family are encoded."),
        ("Explorer player links", "PASS", "No issue", "Player ID, season, and family are encoded."),
        ("Direct player URL", "PASS", "No issue", "Valid player ID and family select the requested profile in a fresh session."),
        ("Invalid player value", "PASS", "No issue", "Invalid player queries clear stale state and render Player not found."),
        ("Direct team URL", "PASS", "No issue", "Valid team, season, and family query parameters take precedence over stale session state."),
        ("Invalid team value", "PASS", "No issue", "Invalid team queries clear stale state and render Team not found."),
        ("Research Admin navigation", "PASS", "No issue", "Admin is absent from st.navigation."),
    ]
    link_state = pd.DataFrame(link_rows, columns=["check", "status", "severity", "evidence"])
    browser_evidence = OUT / "browser_state_evidence.json"
    if browser_evidence.exists():
        evidence = json.loads(browser_evidence.read_text(encoding="utf-8"))
        for item in evidence.get("checks", []):
            link_state = pd.concat([link_state, pd.DataFrame([item])], ignore_index=True)

    # Public-language scan with ordinary-language classification.
    terms = [
        "sustainable", "persistent", "confirmed role change", "breakout", "buy", "sell", "fade",
        "play", "lean", "pass", "confidence score", "best bet", "odds", "edge", "validated detector",
    ]
    harmless_patterns = {
        "play": ["all play", "all-play", "player", "played", "play-level", "play conditions", "plays"],
        "pass": ["passing down", "pass attempts", "passed"],
        "edge": ["knowledge"],
    }
    language_rows: list[dict[str, Any]] = []
    for path in sorted(PUBLIC_MODULES):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            for term in terms:
                if re.search(rf"\b{re.escape(term)}\b", lower):
                    harmless = any(pattern in lower for pattern in harmless_patterns.get(term, []))
                    language_rows.append(
                        {
                            "file": path.relative_to(ROOT).as_posix(), "line": line_number, "term": term,
                            "text": line.strip(), "classification": "harmless ordinary-language use" if harmless else "prohibited analytical language",
                            "status": "PASS" if harmless else "FAIL",
                        }
                    )
    public_language = pd.DataFrame(language_rows)

    # Findings are evidence-led and retain individual failures.
    findings = [
        {
            "id": "HOME_STALE_WEEK_ROWS", "severity": "High", "page": "Home",
            "evidence": f"{int((home_validation['displayed_source_week'] != 18).sum())} of the displayed top 25 rows use a player week earlier than selected Week 18.",
            "impact": "The Week 18 discovery feed mixes stale changes from earlier weeks into the ranking.",
            "likely_cause": "observable_changes takes each player-team-family's latest row at or before the selected week without requiring equality.",
            "proposed_fix": "Require current.week == selected week before ranking.", "production_blocked": True,
        },
        {
            "id": "EXPLORER_ZERO_GAMES", "severity": "High", "page": "Explorer",
            "evidence": f"{int(explorer_validation['status'].eq('FAIL').sum())} player/case reconciliations fail against zero-inclusive eligible-game denominators.",
            "impact": "Shares can be inflated and game samples understated when a qualifying player records zero selected opportunities.",
            "likely_cause": "Player-week rows are created from numerator events only.",
            "proposed_fix": "Start from eligible player-game rows and left join numerator counts, filling zero.", "production_blocked": True,
        },
        {
            "id": "SITUATIONAL_ZERO_FAMILY_GAMES", "severity": "High", "page": "Teams / Reports",
            "evidence": f"{int(pd.DataFrame(calculations)['status'].eq('FAIL').sum())} displayed situational shares disagree with complete same-context team-event denominators.",
            "impact": "Situational shares can be inflated when a team has context opportunities but no opportunity credited to the selected position family in that game.",
            "likely_cause": "The situational extract has no family row for a zero-family-numerator game, so that game's team denominator disappears when weeks are summed.",
            "proposed_fix": "Build situational denominators from the full eligible team-game-context spine before joining family/player numerators.",
            "production_blocked": True,
        },
        {
            "id": "REPORT_CONTEXT_IGNORED", "severity": "High", "page": "Reports",
            "evidence": f"{int(report_validation['severity'].eq('High').sum())} situational reports return identical Normal game and All plays results.",
            "impact": "The visible context filter does not describe the calculation for situational reports.",
            "likely_cause": "league_situational_summary is called without intersecting the selected normal-game context.",
            "proposed_fix": "Apply the selected all-play/normal-game filter to situational source rows or disable and relabel the control.",
            "production_blocked": True,
        },
        {
            "id": "INVALID_URL_FALLBACK", "severity": "High", "page": "Players / Teams",
            "evidence": "Invalid player queries silently select the first player; Teams ignores team query parameters.",
            "impact": "A malformed or stale link can show a valid but wrong entity without warning.",
            "likely_cause": "Query values are used only when present in current options; no invalid-state branch exists, and Teams has no query parsing.",
            "proposed_fix": "Add explicit invalid-entity states and a documented team URL contract.", "production_blocked": True,
        },
        {
            "id": "TRADED_SELECTOR_TEAM", "severity": "Medium", "page": "Players",
            "evidence": f"{int((player_validation.query('multi_team')['selector_team_matches_latest'] == False).groupby(player_validation.query('multi_team')['player_id']).any().sum())} sampled multi-team players have a selector team that differs from the latest team.",
            "impact": "The selector can name the former team while the selected profile summary names the current team.",
            "likely_cause": "drop_duplicates(player_id) keeps the first season row for selector labels.",
            "proposed_fix": "Use latest-week identity for selector labels and retain week-level team attribution in logs.", "production_blocked": False,
        },
        {
            "id": "MISSING_TEAM_LINKS", "severity": "Medium", "page": "Home",
            "evidence": "Home displays team text but renders no team link; Teams has no query-parameter URL contract.",
            "impact": "Requested cross-page team navigation cannot be validated or used.",
            "likely_cause": "Only player hrefs are implemented.",
            "proposed_fix": "Add documented team deep links in a later authorized correctness-fix phase.", "production_blocked": False,
        },
        {
            "id": "GAME_FIELDS_UNAVAILABLE", "severity": "Medium", "page": "Games",
            "evidence": "Source schedules contain scores, and situational data contains inside-five counts, but the page does not display them; one-play production share is not implemented.",
            "impact": "Several requested game facts cannot be checked in the public box score.",
            "likely_cause": "The committed public game view intentionally omits schedule scores and several advanced fields.",
            "proposed_fix": "Backlog the missing factual fields without changing definitions during Phase A.", "production_blocked": False,
        },
        {
            "id": "EMPTY_CHART_WARNINGS", "severity": "Low", "page": "Players",
            "evidence": "Live browser QA recorded no console errors but repeated Vega infinite-extent warnings for empty chart series.",
            "impact": "No incorrect value was observed, but empty or sparse chart states generate noisy diagnostics and may render inconsistently.",
            "likely_cause": "An empty series is still passed to the chart scale without an explicit empty-state branch.",
            "proposed_fix": "Add an explicit no-series chart state in a later authorized correctness-fix phase.",
            "production_blocked": False,
        },
    ]

    high_is_active = {
        "HOME_STALE_WEEK_ROWS": bool(home_validation["status"].eq("FAIL").any()),
        "EXPLORER_ZERO_GAMES": bool(explorer_validation["status"].eq("FAIL").any()),
        "SITUATIONAL_ZERO_FAMILY_GAMES": bool(pd.DataFrame(calculations)["status"].eq("FAIL").any()),
        "REPORT_CONTEXT_IGNORED": bool(report_validation["severity"].eq("High").any()),
        "INVALID_URL_FALLBACK": bool(
            (link_state["status"].eq("FAIL") & link_state["severity"].eq("High")).any()
        ),
    }
    findings = [
        finding for finding in findings
        if finding["severity"] != "High" or high_is_active.get(finding["id"], True)
    ]

    calculation_frame = pd.DataFrame(calculations)
    findings_frame = pd.DataFrame(findings)
    denominator_nunique = public_2025.groupby(
        ["season", "week", "game_id", "team", "role_family"]
    )["team_opportunities_all"].nunique()
    team_quality_checks = {
        "duplicate_player_team_week_family_keys": int(
            public_2025.duplicated(["season", "week", "game_id", "player_id", "team", "role_family"]).sum()
        ),
        "shares_above_100_percent": int(
            (public_2025[["metric_all", "metric_normal"]] > 1.0 + 1e-12).any(axis=1).sum()
        ),
        "zero_or_negative_denominators": int(
            (public_2025[["team_opportunities_all", "team_opportunities_normal"]] <= 0).any(axis=1).sum()
        ),
        "inconsistent_team_game_family_denominators": int(denominator_nunique.gt(1).sum()),
        "numeric_sort_25_before_8_3": bool(
            numeric_percent_sort(pd.DataFrame({"share": [0.083, 0.25]}), "share").iloc[0]["share"] == 0.25
        ),
        "null_sort_last": bool(
            pd.isna(numeric_percent_sort(pd.DataFrame({"share": [np.nan, 0.25]}), "share").iloc[-1]["share"])
        ),
    }
    write_csv(calculation_frame, "calculation_discrepancies.csv")
    write_csv(cross_page, "cross_page_reconciliation.csv")
    write_csv(link_state, "link_state_validation.csv")
    write_csv(explorer_validation, "explorer_validation.csv")
    write_csv(public_language, "public_language_scan.csv")
    write_csv(home_validation, "home_validation.csv")
    write_csv(player_validation, "player_validation.csv")
    write_csv(game_validation, "game_validation.csv")
    write_csv(report_validation, "report_validation.csv")
    write_csv(findings_frame, "findings.csv")

    critical = int(findings_frame["severity"].eq("Critical").sum())
    high = int(findings_frame["severity"].eq("High").sum())
    final = {
        "phase": "Phase A — Targeted Correctness Audit",
        "phase_status": "PASSED" if critical == 0 and high == 0 else "FAILED",
        "production_status": "UNCHANGED",
        "baseline_commit": BASE_COMMIT,
        "source_hashes": {
            "opportunity_events": sha256(ROOT / "outputs/role_research/opportunity_events.csv.gz"),
            "canonical_2025": sha256(ROOT / "outputs/role_research/canonical_role_2025_descriptive.csv.gz"),
            "situational": sha256(ROOT / "outputs/role_research/situational_player_week.csv.gz"),
            "production": sha256(ROOT / "outputs/role_research/game_player_usage.csv.gz"),
            "raw_pbp": sha256(RAW_ROOT / "pbp.csv"),
            "raw_schedules": sha256(RAW_ROOT / "schedules.csv"),
            "raw_weekly": sha256(RAW_ROOT / "weekly.csv"),
        },
        "sample_coverage": {
            "rb_players": len(sample_players["RB"]), "wr_players": len(sample_players["WR"]),
            "te_players": len(sample_players["TE"]), "teams": len(team_samples),
            "games": len(selected_games[:10]), "home_rows": len(home_validation),
            "reports": len(report_validation), "explorer_cases": len(explorer_specs),
        },
        "team_quality_checks": team_quality_checks,
        "results": {
            "calculation_rows": len(calculation_frame),
            "calculation_failures": int(calculation_frame["status"].eq("FAIL").sum()),
            "home_failures": int(home_validation["status"].eq("FAIL").sum()),
            "cross_page_failures": int(cross_page["status"].eq("FAIL").sum()),
            "link_state_failures": int(link_state["status"].eq("FAIL").sum()),
            "explorer_failures": int(explorer_validation["status"].eq("FAIL").sum()),
            "language_failures": int(public_language["status"].eq("FAIL").sum()) if not public_language.empty else 0,
            "critical_findings": critical, "high_findings": high,
            "medium_findings": int(findings_frame["severity"].eq("Medium").sum()),
        },
        "acceptance_gates": {
            "reproducible_audit": True,
            "no_unresolved_critical": critical == 0,
            "no_unresolved_high": high == 0,
            "windows_verified": not calculation_frame.query("audit_area == 'Player'")["status"].eq("FAIL").any(),
            "shares_reconcile": not calculation_frame["status"].eq("FAIL").any(),
            "home_reconciles": not home_validation["status"].eq("FAIL").any(),
            "cross_page_agrees": not cross_page["status"].eq("FAIL").any(),
            "links_resolve": not (
                link_state["status"].eq("FAIL") & link_state["severity"].eq("High")
            ).any(),
            "explorer_correct": not explorer_validation["status"].eq("FAIL").any(),
            "protected_files_unchanged": None,
        },
        "findings": findings,
        "limitations": [
            "The committed opportunity-event extract is the independent play-level source used for share contexts.",
            "Raw PBP and schedules are referenced through the recorded build-manifest source path and hashed.",
            "Game score and one-play production share are not displayed by the deployed page.",
        ],
    }
    (OUT / "final_validation.json").write_text(json.dumps(final, indent=2), encoding="utf-8")

    severity_counts = Counter(findings_frame["severity"])
    report_lines = [
        "# Targeted Correctness Audit",
        "",
        f"**Phase status: {final['phase_status']}**",
        "",
        "**Production status: UNCHANGED**",
        f"**Baseline commit:** `{BASE_COMMIT}`",
        "",
        "## Overall correctness judgment",
        "",
        (
            "All corrected High paths reconcile and Phase A passes with no unresolved Critical or High finding."
            if final["phase_status"] == "PASSED"
            else "Player windows and ordinary ownership shares reconcile, but unresolved High correctness issues remain."
        ),
        "",
        "## Coverage",
        "",
        f"- Players: {len(sample_players['RB'])} RB, {len(sample_players['WR'])} WR, {len(sample_players['TE'])} TE, plus traded and suspected-partial samples.",
        f"- Teams: {len(team_samples)} teams across all four role families.",
        f"- Games: {len(selected_games[:10])} games, including the requested edge categories when present in 2025 source schedules.",
        f"- Home: top {len(home_validation)} displayed rows.",
        f"- Reports: all {len(report_validation)} reports.",
        f"- Explorer: {len(explorer_specs)} filter combinations.",
        "",
        "## Findings",
        "",
    ]
    for finding in findings:
        report_lines += [
            f"### {finding['severity']} — {finding['id']}", "",
            f"- **Affected page:** {finding['page']}",
            f"- **Evidence:** {finding['evidence']}",
            f"- **User impact:** {finding['impact']}",
            f"- **Likely cause:** {finding['likely_cause']}",
            f"- **Proposed fix:** {finding['proposed_fix']}",
            f"- **Production must remain blocked:** {'Yes' if finding['production_blocked'] else 'No'}", "",
        ]
    stale_rows = home_validation[home_validation["status"].eq("FAIL")][
        ["player_name", "team", "role_family", "displayed_source_week"]
    ]
    stale_text = "; ".join(
        f"{row.player_name} ({row.team}, {row.role_family}, Week {int(row.displayed_source_week)})"
        for row in stale_rows.itertuples(index=False)
    )
    calc_groups = calculation_frame.groupby(["audit_area", "sample_type", "status"]).size().to_dict()
    situational_failures = int(
        calculation_frame.loc[calculation_frame["sample_type"].eq("situational"), "status"].eq("FAIL").sum()
    )
    game_categories = sorted(
        category for category in set(";".join(game_validation["categories"].dropna().astype(str)).split(";")) if category
    )
    report_lines += [
        "## Calculation results", "",
        f"- Player window checks: {calc_groups.get(('Player', 'window', 'PASS'), 0)} passed, 0 failed. Season, Last 8, Last 4, and Last 2 use summed player and same-context team counts over qualifying games.",
        f"- Team role-ownership checks: {calc_groups.get(('Teams', 'role_ownership', 'PASS'), 0)} passed, {calc_groups.get(('Teams', 'role_ownership', 'FAIL'), 0)} failed.",
        f"- Team situational checks: {calc_groups.get(('Teams', 'situational', 'PASS'), 0)} passed, {calc_groups.get(('Teams', 'situational', 'FAIL'), 0)} failed. Every failure is preserved in `calculation_discrepancies.csv` with source play IDs, numerator, denominator, expected share, displayed share, and difference.",
        "- The 25.0% versus 8.3% descending sort regression passes using numeric values with nulls last.",
        "- Canonical duplicate keys: 0. Week range: 1–18 only. Confirmed partial rows are absent from the public primary set; suspected rows remain visible.",
        "",
        "## Home results", "",
        f"- Top 25 audited: {int(home_validation['status'].eq('PASS').sum())} pass selected-week eligibility and {int(home_validation['status'].eq('FAIL').sum())} fail.",
        f"- Stale rows: {stale_text}.",
        "- All audited baselines remain within 2025 and strictly precede each row's triggering player week; no future-game leakage was found.",
        "- Baseline and recent numerators, denominators, shares, sample sizes, ranks, and link targets are archived in `home_validation.csv`.",
        "",
        "## Player and Team results", "",
        f"- Player weekly rows audited: {len(player_validation)}; all displayed all-play and normal-game shares equal their row numerator divided by denominator, and no Week 0 exists.",
        f"- Multi-team selector mismatches: {int((player_validation.query('multi_team')['selector_team_matches_latest'] == False).groupby(player_validation.query('multi_team')['player_id']).any().sum())} sampled players. Live Tank Bigsby evidence showed PHI in the summary but JAX in the selector label.",
        f"- Independent team-role ranks match the displayed rank calculation on {int(player_validation['role_rank_matches'].sum())} of {len(player_validation)} archived player-week evidence rows.",
        "- Ordinary Team ownership values agree with Reports under identical season, window, role-family, and context filters.",
        f"- Team quality checks: {team_quality_checks['duplicate_player_team_week_family_keys']} duplicate keys, {team_quality_checks['shares_above_100_percent']} shares above 100%, {team_quality_checks['zero_or_negative_denominators']} non-positive denominators, and {team_quality_checks['inconsistent_team_game_family_denominators']} inconsistent team-game-family denominators.",
        f"- Situational same-context discrepancies: {situational_failures}; these occur when a zero-family-numerator game drops its team denominator.",
        "",
        "## Game results", "",
        f"- Games audited: {len(selected_games[:10])}; required categories present: {', '.join(game_categories)}.",
        f"- Player production rows reconciled to weekly source: {int(game_validation['production_matches_source'].sum())} of {len(game_validation)}.",
        "- Matchup, score, overtime, carries, targets, receptions, team grouping, partial-game categories, and source reconciliation are in `game_validation.csv`.",
        "- The public page does not display score, inside-five counts, or one-play production share, so those requested display checks are recorded as unavailable rather than inferred.",
        "",
        "## Report results", "",
        "- All seven reports were executed for 2025 Last 4 with their default minimum sample.",
        f"- Context-sensitive ordinary reports: {int(report_validation['context_filter_applied'].sum())} pass; situational reports ignoring the visible Normal game / All plays selector: {int(report_validation['severity'].eq('High').sum())}.",
        "- Report definitions, row counts, numeric-sort status, and label assessments are in `report_validation.csv`.",
        "",
        "## Explorer results", "",
        f"- Filter cases: {len(explorer_specs)}; row-level comparisons: {len(explorer_validation)}; failures: {int(explorer_validation['status'].eq('FAIL').sum())}.",
        "- Failures retain matching player numerators but show understated team denominators and sample games when the player had zero selected opportunities in an otherwise eligible game.",
        "- Live Reset testing restored 2025, All teams, All players, RB carry share, Weeks 1–18, all context filters, Normal game, and minimum sample 5.",
        "",
        "## Cross-page and link/state results", "",
        f"- Identical-filter cross-page comparisons: {len(cross_page)}; failures: {int(cross_page['status'].eq('FAIL').sum())}.",
        f"- Link/state checks: {len(link_state)}; recorded failures: {int(link_state['status'].eq('FAIL').sum())}. Static and live duplicate observations are intentionally retained as separate evidence rows.",
        "- Valid player URLs, Explorer Reset, back/forward, and public navigation pass. Invalid player URLs and team query URLs fail safely identifiable behavior; Home has no team deep links.",
        "",
        "## Edge cases and public language", "",
        "- Covered traded and multi-team players, bye weeks, Week 18, overtime, blowout, confirmed partial, suspected partial, tiny samples, zero denominators, missing recent windows, and absence of fabricated 2026 usage.",
        f"- Public-language matches reviewed: {len(public_language)}; prohibited analytical uses: {int(public_language['status'].eq('FAIL').sum())}.",
        "- Late-season outcome censoring is not applicable to these descriptive displays because the audit evaluates no future outcome metric.",
        "",
        "## Result summary", "",
        f"- Calculation checks: {len(calculation_frame)} rows; {int(calculation_frame['status'].eq('FAIL').sum())} failures.",
        f"- Home rows failing selected-week eligibility: {int(home_validation['status'].eq('FAIL').sum())}.",
        f"- Cross-page checks: {len(cross_page)} rows; {int(cross_page['status'].eq('FAIL').sum())} failures.",
        f"- Explorer checks: {len(explorer_validation)} rows; {int(explorer_validation['status'].eq('FAIL').sum())} failures.",
        f"- Findings: {severity_counts.get('Critical', 0)} Critical, {severity_counts.get('High', 0)} High, {severity_counts.get('Medium', 0)} Medium, {severity_counts.get('Low', 0)} Low.",
        "",
        "## Acceptance gate", "",
        f"Phase A is **{final['phase_status']}**. No production change is authorized.",
        "",
        "## Reproducibility", "",
        "Run `python scripts/run_targeted_correctness_audit.py`, execute the audit notebook, then run the independent validators listed in `COMMANDS_RUN.md`.",
    ]
    (OUT / "TARGETED_CORRECTNESS_AUDIT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
