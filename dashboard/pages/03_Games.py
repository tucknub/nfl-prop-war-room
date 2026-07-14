from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS,
    available_seasons,
    available_weeks,
    game_usage,
    load_situational_data,
    player_profile,
    primary_rows,
)
from research_ui import methodology_expander, note, page_intro, ratio_text, responsive_table, role_noun, section, selection_summary, source_footer


def _whole(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


page_intro(
    "Game Usage Box Score",
    "One-game player workload, team shares, recent comparison, and situational opportunity counts.",
)

summary_slot = st.empty()
with st.expander("Change game"):
    controls = st.columns([1, 1, 2.5])
    with controls[0]:
        season = st.selectbox("Season", available_seasons(), key="games_season")
    weeks = available_weeks(season)
    with controls[1]:
        week = st.selectbox("Week", weeks, index=len(weeks) - 1, key="games_week")
    rows = primary_rows()
    week_rows = rows[rows["season"].eq(season) & rows["week"].eq(week)]
    games = sorted(week_rows["game_id"].dropna().astype(str).unique().tolist())
    with controls[2]:
        game_id = st.selectbox("Game", games, key="games_game")

usage = game_usage(season, week, game_id)
teams = sorted(usage["team"].dropna().astype(str).unique().tolist()) if not usage.empty else []
matchup = " vs ".join(teams) if len(teams) == 2 else game_id
selection_summary(
    f"{matchup} · Week {week}",
    f"{season} regular season",
    f"{len(usage)} player rows",
    target=summary_slot,
)

if season < 2023:
    note("Production and situational counts are available for completed 2023–2025 seasons.", amber=True)

situational = load_situational_data()
situational = situational[
    situational["season"].eq(season) & situational["week"].eq(week) & situational["game_id"].eq(game_id)
]

family_by_position = {"RB": "rb_opportunity_share", "WR": "wr_target_share", "TE": "te_target_share"}
for team in teams:
    section(team, f"{matchup} · grouped player usage")
    team_view = usage[usage["team"].eq(team)].copy()
    cards: list[dict[str, object]] = []
    desktop_rows: list[dict[str, object]] = []
    for _, row in team_view.iterrows():
        family = family_by_position.get(str(row["position"]))
        if not family:
            continue
        raw = row.get(f"{family}_raw")
        denominator = row.get(f"{family}_denominator")
        normal_raw = row.get(f"{family}_normal_raw")
        normal_denominator = row.get(f"{family}_normal_denominator")
        outside_normal = max(0, _whole(raw) - _whole(normal_raw))
        player_situational = situational[
            situational["player_id"].astype(str).eq(str(row["player_id"]))
            & situational["role_family"].eq(family)
        ].set_index("context")

        def context_ratio(context: str) -> str:
            if context not in player_situational.index:
                return "—"
            item = player_situational.loc[context]
            if isinstance(item, pd.DataFrame):
                item = item.iloc[0]
            return ratio_text(item["raw_opportunities"], item["team_opportunities"], role_noun(family))

        history = player_profile(str(row["player_id"]), season, family)
        prior = history[history["week"].lt(week)].tail(4)
        prior_denominator = prior["team_opportunities_normal"].sum()
        prior_share = prior["raw_opportunities_normal"].sum() / prior_denominator if prior_denominator else math.nan
        prior_text = f"{prior_share * 100:.1f}% across {len(prior)} games" if pd.notna(prior_share) else "No prior sample"
        production_text = f"{_whole(row.get('carries'))} carries · {_whole(row.get('targets'))} targets · {_whole(row.get('receptions'))} receptions"
        cards.append(
            {
                "title": row["player_name"],
                "subtitle": f"{team} · {row['position']} · {ROLE_LABELS[family]}",
                "metrics": [
                    ("Production", production_text, f"{_whole(row.get('rushing_yards'))} rush yds · {_whole(row.get('receiving_yards'))} rec yds"),
                    ("Team share", ratio_text(raw, denominator, role_noun(family)), "All play"),
                    ("Normal game", ratio_text(normal_raw, normal_denominator, role_noun(family)), f"{outside_normal} opportunities outside normal-game context"),
                    ("Two minute", context_ratio("two_minute"), "Final two minutes of either half"),
                    ("Red zone", context_ratio("red_zone"), "Opponent 20 or closer"),
                    ("Prior comparison", prior_text, "Prior qualifying normal-game sample"),
                ],
                "note": str(row["partial_game_note"]) if "Suspected" in str(row["partial_game_note"]) else "",
                "href": f"/players?player={row['player_id']}&season={season}&family={family}",
            }
        )
        desktop_rows.append(
            {
                "Player": row["player_name"],
                "Pos": row["position"],
                "Role family": ROLE_LABELS[family],
                "Carries": _whole(row.get("carries")),
                "Targets": _whole(row.get("targets")),
                "Receptions": _whole(row.get("receptions")),
                "All count": f"{_whole(raw)} / {_whole(denominator)}",
                "All share": float(raw) / float(denominator) * 100.0 if pd.notna(raw) and pd.notna(denominator) and denominator else pd.NA,
                "Normal count": f"{_whole(normal_raw)} / {_whole(normal_denominator)}",
                "Normal share": float(normal_raw) / float(normal_denominator) * 100.0 if pd.notna(normal_raw) and pd.notna(normal_denominator) and normal_denominator else pd.NA,
                "Outside normal": outside_normal,
                "Prior baseline": prior_share * 100.0 if pd.notna(prior_share) else pd.NA,
                "Participation": "No flag" if str(row["partial_game_note"]) == "Included" else row["partial_game_note"],
            }
        )
    display = pd.DataFrame(desktop_rows)
    responsive_table(
        display,
        cards,
        key=f"games_{team.lower()}",
        height=max(260, min(520, 42 * (len(display) + 1))),
        percent_columns=["All share", "Normal share", "Prior baseline"],
    )

methodology_expander(
    [
        "All-play and normal-game shares use the player count divided by the matching team count.",
        "Outside-normal-game opportunities equal all-play opportunities minus normal-game opportunities.",
        "The prior comparison uses up to four earlier qualifying games in the same season.",
        "Final scores are not present in the committed public usage extract, so this view does not infer them.",
    ]
)
source_footer("A large percentage can reflect a small denominator; counts remain visible beside every share.")
