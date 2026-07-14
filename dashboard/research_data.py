from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


CANONICAL_FILES = (
    "outputs/role_validation/fold_1_diagnostics/canonical_role_2018_2021_enriched.csv.gz",
    "outputs/role_validation/fold_2/canonical_role_2022_enriched.csv.gz",
    "outputs/role_validation/fold_3/canonical_role_2023_enriched.csv.gz",
    "outputs/role_validation/fold_4/canonical_role_2024_enriched.csv.gz",
    "outputs/role_research/canonical_role_2025_descriptive.csv.gz",
)
SITUATIONAL_FILE = "outputs/role_research/situational_player_week.csv.gz"
PRODUCTION_FILE = "outputs/role_research/game_player_usage.csv.gz"
EVENTS_FILE = "outputs/role_research/opportunity_events.csv.gz"
ROLE_LABELS = {
    "rb_carry_share": "RB carry share",
    "rb_opportunity_share": "RB opportunity share",
    "wr_target_share": "WR target share",
    "te_target_share": "TE target share",
}
CONTEXT_LABELS = {
    "all_play": "Overall",
    "normal_game": "Normal game",
    "early_down": "Early down",
    "passing_down": "Passing down",
    "two_minute": "Two minute",
    "short_yardage": "Short yardage",
    "red_zone": "Red zone",
    "inside_10": "Inside 10",
    "inside_5": "Inside 5",
    "end_zone": "End-zone targets",
    "leading": "Leading",
    "trailing": "Trailing",
    "close": "Close (within 7)",
    "quarter_1": "First quarter",
    "quarter_2": "Second quarter",
    "quarter_3": "Third quarter",
    "quarter_4": "Fourth quarter",
}
KEY_COLUMNS = ["season", "week", "player_id", "team", "role_family"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.fillna("").astype(str).str.strip().str.lower().isin({"1", "true", "yes"})


@lru_cache(maxsize=1)
def load_role_data() -> pd.DataFrame:
    frames = [pd.read_csv(repo_root() / path, compression="gzip", low_memory=False) for path in CANONICAL_FILES]
    frame = pd.concat(frames, ignore_index=True)
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").astype("Int64")
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce").astype("Int64")
    frame = frame[frame["season"].between(2018, 2025)].copy()
    frame["role_family_label"] = frame["role_family"].map(ROLE_LABELS).fillna(frame["role_family"])
    quality = _as_bool(frame["data_quality_pass"]) & _as_bool(frame["qualifying_game"])
    confirmed = _as_bool(frame.get("confirmed_partial_game", pd.Series(False, index=frame.index)))
    suspected = _as_bool(frame.get("suspected_partial_game", pd.Series(False, index=frame.index)))
    frame["confirmed_partial_game"] = confirmed
    frame["suspected_partial_game"] = suspected
    frame["public_primary_row"] = quality & ~confirmed
    frame["partial_game_note"] = np.select(
        [confirmed, suspected],
        ["Confirmed partial game — excluded", "Suspected partial game — included"],
        default="Included",
    )
    return frame.sort_values(["season", "week", "team", "player_id", "role_family"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def load_situational_data() -> pd.DataFrame:
    path = repo_root() / SITUATIONAL_FILE
    frame = pd.read_csv(path, compression="gzip", low_memory=False)
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").astype("Int64")
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce").astype("Int64")
    frame["role_family_label"] = frame["role_family"].map(ROLE_LABELS)
    eligible = primary_rows()[["season", "week", "player_id", "team", "role_family"]].drop_duplicates()
    return frame.merge(
        eligible.assign(_public_eligible=True),
        on=["season", "week", "player_id", "team", "role_family"],
        how="inner",
    ).drop(columns="_public_eligible")


@lru_cache(maxsize=1)
def load_production_data() -> pd.DataFrame:
    frame = pd.read_csv(repo_root() / PRODUCTION_FILE, compression="gzip", low_memory=False)
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").astype("Int64")
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce").astype("Int64")
    return frame


@lru_cache(maxsize=1)
def load_opportunity_events() -> pd.DataFrame:
    frame = pd.read_csv(repo_root() / EVENTS_FILE, compression="gzip", low_memory=False)
    frame["season"] = pd.to_numeric(frame["season"], errors="coerce").astype("Int64")
    frame["week"] = pd.to_numeric(frame["week"], errors="coerce").astype("Int64")
    for column in CONTEXT_LABELS:
        if column != "all_play" and column in frame:
            frame[column] = _as_bool(frame[column])
    return frame


def primary_rows(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    data = load_role_data() if frame is None else frame
    return data[data["public_primary_row"]].copy()


def available_seasons() -> list[int]:
    return sorted(primary_rows()["season"].dropna().astype(int).unique().tolist(), reverse=True)


def available_weeks(season: int, frame: pd.DataFrame | None = None) -> list[int]:
    data = primary_rows() if frame is None else frame
    return sorted(data.loc[data["season"].eq(season), "week"].dropna().astype(int).unique().tolist())


def _window_weeks(data: pd.DataFrame, end_week: int, window: int | str) -> list[int]:
    weeks = sorted(data.loc[data["week"].le(end_week), "week"].dropna().astype(int).unique().tolist())
    return weeks if window == "Season" else weeks[-int(window):]


def _share_column(context: str) -> tuple[str, str, str]:
    if context == "Normal game":
        return "raw_opportunities_normal", "team_opportunities_normal", "metric_normal"
    return "raw_opportunities_all", "team_opportunities_all", "metric_all"


def observable_changes(season: int, end_week: int, baseline_games: int = 4) -> pd.DataFrame:
    data = primary_rows()
    data = data[data["season"].eq(season) & data["week"].le(end_week)].copy()
    rows: list[dict[str, object]] = []
    for _, group in data.groupby(["player_id", "team", "role_family"], sort=False):
        group = group.sort_values("week")
        current = group.iloc[-1]
        prior = group.iloc[:-1].tail(baseline_games)
        if len(prior) < 2:
            continue
        denominator = float(prior["team_opportunities_normal"].sum())
        if denominator <= 0:
            continue
        baseline_share = float(prior["raw_opportunities_normal"].sum() / denominator)
        recent_share = float(current["metric_normal"])
        change = recent_share - baseline_share
        direction = "higher" if change >= 0 else "lower"
        noun = "Carry share" if current["role_family"] == "rb_carry_share" else (
            "RB opportunity share" if current["role_family"] == "rb_opportunity_share" else "Target share"
        )
        rows.append({
            "season": int(current["season"]),
            "week": int(current["week"]),
            "player_id": current["player_id"],
            "player_name": current["player_name"],
            "team": current["team"],
            "position": current["position"],
            "role_family": current["role_family"],
            "role_family_label": current["role_family_label"],
            "baseline_share": baseline_share,
            "recent_share": recent_share,
            "change": change,
            "raw_opportunities": int(current["raw_opportunities_normal"]),
            "team_denominator": int(current["team_opportunities_normal"]),
            "metric_normal": float(current["metric_normal"]),
            "metric_all": float(current["metric_all"]),
            "baseline_games": int(len(prior)),
            "partial_game_note": current["partial_game_note"],
            "factual_text": f"{noun} was {abs(change) * 100:.1f} percentage points {direction} than the prior {len(prior)}-game baseline.",
        })
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.assign(abs_change=result["change"].abs()).sort_values(
        ["abs_change", "raw_opportunities"], ascending=[False, False]
    ).reset_index(drop=True)


def team_window_summary(
    season: int,
    team: str,
    role_family: str,
    end_week: int,
    window: int | str,
    context: str,
) -> pd.DataFrame:
    data = primary_rows()
    data = data[
        data["season"].eq(season) & data["team"].eq(team) & data["role_family"].eq(role_family)
        & data["week"].le(end_week)
    ].copy()
    weeks = _window_weeks(data, end_week, window)
    current = data[data["week"].isin(weeks)].copy()
    if current.empty:
        return current
    raw_col, denom_col, _ = _share_column(context)
    team_denominator = current.drop_duplicates(["season", "week", "game_id", "team", "role_family"])[denom_col].sum()
    summary = current.groupby(["player_id", "player_name", "team", "position"], as_index=False).agg(
        raw_opportunities=(raw_col, "sum"),
        sample_games=("week", "nunique"),
        suspected_partial_games=("suspected_partial_game", "sum"),
    )
    summary["team_denominator"] = team_denominator
    summary["share"] = summary["raw_opportunities"] / summary["team_denominator"].replace(0, np.nan)
    first_week = min(weeks)
    prior_weeks = sorted(data.loc[data["week"].lt(first_week), "week"].dropna().astype(int).unique().tolist())
    if window != "Season":
        prior_weeks = prior_weeks[-int(window):]
    prior = data[data["week"].isin(prior_weeks)]
    prior_denominator = prior.drop_duplicates(["season", "week", "game_id", "team", "role_family"])[denom_col].sum()
    prior_summary = prior.groupby("player_id", as_index=False).agg(prior_raw=(raw_col, "sum"))
    prior_summary["prior_denom"] = prior_denominator
    prior_summary["prior_share"] = prior_summary["prior_raw"] / prior_summary["prior_denom"].replace(0, np.nan)
    summary = summary.merge(prior_summary[["player_id", "prior_share"]], on="player_id", how="left")
    summary["change"] = summary["share"] - summary["prior_share"]
    return summary.sort_values(["share", "raw_opportunities"], ascending=[False, False]).reset_index(drop=True)


def situational_team_summary(
    season: int,
    team: str,
    role_family: str,
    end_week: int,
    window: int | str,
) -> pd.DataFrame:
    data = load_situational_data()
    data = data[
        data["season"].eq(season) & data["team"].eq(team) & data["role_family"].eq(role_family)
        & data["week"].le(end_week)
    ].copy()
    if data.empty:
        return pd.DataFrame()
    weeks = _window_weeks(data, end_week, window)
    data = data[data["week"].isin(weeks)]
    denominators = data.drop_duplicates(["season", "week", "game_id", "team", "role_family", "context"]).groupby(
        "context", as_index=False
    )["team_opportunities"].sum()
    numerators = data.groupby(
        ["player_id", "player_name", "position", "context"], as_index=False
    )["raw_opportunities"].sum()
    joined = numerators.merge(denominators, on="context", how="left")
    joined["share"] = joined["raw_opportunities"] / joined["team_opportunities"].replace(0, np.nan)
    result = joined[["player_id", "player_name", "position"]].drop_duplicates().reset_index(drop=True)
    for context in sorted(joined["context"].dropna().astype(str).unique().tolist()):
        context_rows = joined[joined["context"].eq(context)][
            ["player_id", "raw_opportunities", "team_opportunities", "share"]
        ].rename(
            columns={
                "raw_opportunities": f"{context}_raw",
                "team_opportunities": f"{context}_denominator",
                "share": context,
            }
        )
        result = result.merge(context_rows, on="player_id", how="left")
    return result


def league_window_summary(
    season: int,
    end_week: int,
    window: int | str,
    context: str = "Normal game",
    role_families: Iterable[str] | None = None,
) -> pd.DataFrame:
    data = primary_rows()
    data = data[data["season"].eq(season) & data["week"].le(end_week)].copy()
    if role_families:
        data = data[data["role_family"].isin(list(role_families))]
    weeks = _window_weeks(data, end_week, window)
    current = data[data["week"].isin(weeks)]
    raw_col, denom_col, _ = _share_column(context)
    denominators = current.drop_duplicates(["season", "week", "game_id", "team", "role_family"]).groupby(
        ["team", "role_family"], as_index=False
    )[denom_col].sum().rename(columns={denom_col: "team_denominator"})
    summary = current.groupby(
        ["player_id", "player_name", "team", "position", "role_family", "role_family_label"], as_index=False
    ).agg(
        raw_opportunities=(raw_col, "sum"),
        sample_games=("week", "nunique"), suspected_partial_games=("suspected_partial_game", "sum"),
    )
    summary = summary.merge(denominators, on=["team", "role_family"], how="left")
    summary["share"] = summary["raw_opportunities"] / summary["team_denominator"].replace(0, np.nan)
    first_week = min(weeks) if weeks else 0
    prior_weeks = sorted(data.loc[data["week"].lt(first_week), "week"].dropna().astype(int).unique().tolist())
    if window != "Season":
        prior_weeks = prior_weeks[-int(window):]
    prior_rows = data[data["week"].isin(prior_weeks)]
    prior_denominators = prior_rows.drop_duplicates(["season", "week", "game_id", "team", "role_family"]).groupby(
        ["team", "role_family"], as_index=False
    )[denom_col].sum().rename(columns={denom_col: "prior_denom"})
    prior = prior_rows.groupby(
        ["player_id", "team", "role_family"], as_index=False
    ).agg(prior_raw=(raw_col, "sum"))
    prior = prior.merge(prior_denominators, on=["team", "role_family"], how="left")
    prior["prior_share"] = prior["prior_raw"] / prior["prior_denom"].replace(0, np.nan)
    summary = summary.merge(prior[["player_id", "team", "role_family", "prior_share"]], on=["player_id", "team", "role_family"], how="left")
    summary["change"] = summary["share"] - summary["prior_share"]
    return summary.sort_values(["share", "raw_opportunities"], ascending=[False, False]).reset_index(drop=True)


def league_situational_summary(
    season: int,
    end_week: int,
    window: int | str,
    context: str,
    role_families: Iterable[str] | None = None,
) -> pd.DataFrame:
    data = load_situational_data()
    data = data[data["season"].eq(season) & data["week"].le(end_week) & data["context"].eq(context)].copy()
    if role_families:
        data = data[data["role_family"].isin(list(role_families))]
    weeks = _window_weeks(data, end_week, window)
    data = data[data["week"].isin(weeks)]
    denominators = data.drop_duplicates(["season", "week", "game_id", "team", "role_family", "context"]).groupby(
        ["team", "role_family"], as_index=False
    )["team_opportunities"].sum()
    summary = data.groupby(
        ["player_id", "player_name", "team", "position", "role_family", "role_family_label"], as_index=False
    ).agg(raw_opportunities=("raw_opportunities", "sum"), sample_games=("week", "nunique"))
    summary = summary.merge(denominators, on=["team", "role_family"], how="left").rename(
        columns={"team_opportunities": "team_denominator"}
    )
    summary["share"] = summary["raw_opportunities"] / summary["team_denominator"].replace(0, np.nan)
    return summary.sort_values(["share", "raw_opportunities"], ascending=[False, False]).reset_index(drop=True)


def explorer_usage(
    season: int,
    start_week: int,
    end_week: int,
    role_family: str,
    *,
    player_id: str | None = None,
    team: str | None = None,
    game_state: str = "All",
    quarter: str = "All",
    down_distance: str = "All",
    field_zone: str = "All",
    two_minute: bool = False,
    normal_game: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    events = load_opportunity_events()
    events = events[
        events["season"].eq(season) & events["week"].between(start_week, end_week)
    ].copy()
    filters = {
        "Leading": "leading", "Trailing": "trailing", "Close": "close",
        "Q1": "quarter_1", "Q2": "quarter_2", "Q3": "quarter_3", "Q4": "quarter_4",
        "Early down": "early_down", "Passing down": "passing_down", "Short yardage": "short_yardage",
        "Red zone": "red_zone", "Inside 10": "inside_10", "Inside 5": "inside_5",
    }
    for selected in [game_state, quarter, down_distance, field_zone]:
        if selected != "All":
            events = events[events[filters[selected]]]
    if two_minute:
        events = events[events["two_minute"]]
    if normal_game:
        events = events[events["normal_game"]]
    if team:
        events = events[events["team"].eq(team)]
    if role_family == "rb_carry_share":
        denominator = events[events["opportunity_type"].eq("carry")]
        numerator = denominator[denominator["position"].eq("RB")]
    elif role_family == "rb_opportunity_share":
        denominator = events[events["position"].eq("RB")]
        numerator = denominator
    elif role_family == "wr_target_share":
        denominator = events[events["opportunity_type"].eq("target")]
        numerator = denominator[denominator["position"].eq("WR")]
    else:
        denominator = events[events["opportunity_type"].eq("target")]
        numerator = denominator[denominator["position"].eq("TE")]
    if player_id:
        numerator = numerator[numerator["player_id"].astype(str).eq(str(player_id))]
    eligible = primary_rows()
    eligible = eligible[eligible["role_family"].eq(role_family)][
        ["season", "week", "player_id", "team"]
    ].drop_duplicates()
    numerator = numerator.merge(eligible.assign(_eligible=True), on=["season", "week", "player_id", "team"], how="inner")
    team_denoms = denominator.groupby(["season", "week", "game_id", "team"], as_index=False).agg(
        team_denominator=("play_id", "nunique")
    )
    player_week = numerator.groupby(
        ["season", "week", "game_id", "team", "player_id", "player_name", "position"], as_index=False
    ).agg(raw_opportunities=("play_id", "nunique"))
    player_week = player_week.merge(team_denoms, on=["season", "week", "game_id", "team"], how="left")
    player_week["share"] = player_week["raw_opportunities"] / player_week["team_denominator"].replace(0, np.nan)
    summary = player_week.groupby(["player_id", "player_name", "team", "position"], as_index=False).agg(
        raw_opportunities=("raw_opportunities", "sum"), team_denominator=("team_denominator", "sum"),
        sample_games=("game_id", "nunique"),
    )
    summary["share"] = summary["raw_opportunities"] / summary["team_denominator"].replace(0, np.nan)
    return summary.sort_values("share", ascending=False), player_week.sort_values(["player_name", "week"])


def player_profile(player_id: str, season: int, role_family: str) -> pd.DataFrame:
    data = primary_rows()
    return data[
        data["player_id"].astype(str).eq(str(player_id)) & data["season"].eq(season)
        & data["role_family"].eq(role_family)
    ].sort_values("week").copy()


def player_window_table(profile: pd.DataFrame, end_week: int) -> pd.DataFrame:
    rows = []
    for label, window in [("Season", "Season"), ("Last 8", 8), ("Last 4", 4), ("Last 2", 2)]:
        weeks = _window_weeks(profile, end_week, window)
        current = profile[profile["week"].isin(weeks)]
        prior_weeks = sorted(profile.loc[profile["week"].lt(min(weeks) if weeks else 0), "week"].astype(int).unique().tolist())
        if window != "Season":
            prior_weeks = prior_weeks[-int(window):]
        prior = profile[profile["week"].isin(prior_weeks)]
        all_raw = float(current["raw_opportunities_all"].sum())
        all_den = float(current["team_opportunities_all"].sum())
        norm_raw = float(current["raw_opportunities_normal"].sum())
        norm_den = float(current["team_opportunities_normal"].sum())
        prior_share = (
            float(prior["raw_opportunities_normal"].sum() / prior["team_opportunities_normal"].sum())
            if len(prior) and prior["team_opportunities_normal"].sum() > 0 else np.nan
        )
        normal_share = norm_raw / norm_den if norm_den else np.nan
        rows.append({
            "Window": label, "All raw": int(all_raw), "All denominator": int(all_den),
            "All share": all_raw / all_den if all_den else np.nan,
            "Normal raw": int(norm_raw), "Normal denominator": int(norm_den),
            "Normal share": normal_share, "Change vs prior": normal_share - prior_share,
            "Games": int(current["week"].nunique()),
        })
    return pd.DataFrame(rows)


def game_usage(season: int, week: int, game_id: str) -> pd.DataFrame:
    roles = primary_rows()
    roles = roles[roles["season"].eq(season) & roles["week"].eq(week) & roles["game_id"].eq(game_id)]
    identity = roles[["player_id", "player_name", "team", "position", "partial_game_note"]].drop_duplicates("player_id")
    shares = roles.pivot_table(index="player_id", columns="role_family", values="metric_all", aggfunc="first").reset_index()
    normal = roles.pivot_table(index="player_id", columns="role_family", values="metric_normal", aggfunc="first").add_suffix("_normal").reset_index()
    raw_all = roles.pivot_table(
        index="player_id", columns="role_family", values="raw_opportunities_all", aggfunc="first"
    ).add_suffix("_raw").reset_index()
    denominator_all = roles.pivot_table(
        index="player_id", columns="role_family", values="team_opportunities_all", aggfunc="first"
    ).add_suffix("_denominator").reset_index()
    raw_normal = roles.pivot_table(
        index="player_id", columns="role_family", values="raw_opportunities_normal", aggfunc="first"
    ).add_suffix("_normal_raw").reset_index()
    denominator_normal = roles.pivot_table(
        index="player_id", columns="role_family", values="team_opportunities_normal", aggfunc="first"
    ).add_suffix("_normal_denominator").reset_index()
    result = identity.merge(shares, on="player_id", how="left").merge(normal, on="player_id", how="left")
    for counts in [raw_all, denominator_all, raw_normal, denominator_normal]:
        result = result.merge(counts, on="player_id", how="left")
    production = load_production_data()
    production = production[
        production["season"].eq(season) & production["week"].eq(week) & production["game_id"].eq(game_id)
    ]
    if not production.empty:
        result = result.merge(
            production.drop(columns=["player_name", "team", "position"], errors="ignore"),
            on=["player_id"], how="left",
        )
    return result.sort_values(["team", "position", "player_name"]).reset_index(drop=True)


def opponent_from_game_id(game_id: str, team: str) -> str:
    parts = str(game_id).split("_")
    if len(parts) < 4:
        return "—"
    away, home = parts[-2], parts[-1]
    return home if team == away else away


def canonical_quality_profile(frame: pd.DataFrame | None = None) -> dict[str, object]:
    data = load_role_data() if frame is None else frame
    required = [
        "season", "week", "player_id", "player_name", "team", "position", "role_family",
        "metric_all", "metric_normal", "raw_opportunities_all", "raw_opportunities_normal",
        "team_opportunities_all", "team_opportunities_normal", "qualifying_game",
        "data_quality_pass", "identity_resolved",
    ]
    return {
        "rows": int(len(data)),
        "seasons": sorted(data["season"].dropna().astype(int).unique().tolist()),
        "duplicate_keys": int(data.duplicated(KEY_COLUMNS).sum()),
        "required_missing_cells": int(data[required].isna().sum().sum()),
        "identity_coverage": float(_as_bool(data["identity_resolved"]).mean()),
        "confirmed_partial_rows": int(data["confirmed_partial_game"].sum()),
        "suspected_partial_rows": int(data["suspected_partial_game"].sum()),
        "public_primary_rows": int(data["public_primary_row"].sum()),
        "latest_completed_season": int(data["season"].max()),
    }


def filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    return sorted(frame[column].dropna().astype(str).unique().tolist())


def percent(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return "—" if pd.isna(number) else f"{float(number):.1%}"


def pp(value: object) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return "—" if pd.isna(number) else f"{float(number) * 100:+.1f} pp"
