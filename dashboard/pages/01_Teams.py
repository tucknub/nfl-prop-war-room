from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PAGE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PAGE_DIR.parent
REPO_ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_data import (
    ROLE_LABELS, available_seasons, available_weeks, primary_rows,
    situational_team_summary, team_window_summary,
)
from research_ui import (
    enable_browser_history_sync, initialize_query_control, methodology_expander,
    note, numeric_percent_sort, page_intro, parse_int, query_value, ratio_text,
    responsive_table, role_noun, searchable_selectbox, section, selection_summary,
    source_footer, update_query_from_widget,
)
from supporting_evidence import home_evidence_message, role_leader, situational_leader
from role_change import build_team_role_change_table


enable_browser_history_sync()
page_intro("Team Role Breakdown", "Who currently controls each offensive role on this team?")
summary_slot = st.empty()

seasons = available_seasons()
season_state = initialize_query_control("teams", "season", "teams_season", seasons, parser=parse_int)
season = int(season_state.value)
season_rows = primary_rows()
season_rows = season_rows[season_rows["season"].eq(season)]
teams = sorted(season_rows["team"].dropna().astype(str).unique().tolist())
team_state = initialize_query_control("teams", "team", "teams_team", teams)
family_state = initialize_query_control("teams", "family", "teams_family", list(ROLE_LABELS), default="rb_carry_share")

with st.expander("Change filters"):
    controls = st.columns(5)
    with controls[0]:
        season = st.selectbox("Season", seasons, key="teams_season", on_change=update_query_from_widget, args=("season", "teams_season"), kwargs={"clear_query": ("week",)})
    with controls[1]:
        team = searchable_selectbox("Search or select team", teams, key="teams_team", on_change=update_query_from_widget, args=("team", "teams_team"))
    with controls[2]:
        window_label = st.selectbox("Window", ["Season", "Last 8", "Last 4", "Last 2"], index=2, key="teams_window")
    with controls[3]:
        context = st.selectbox("Context", ["All plays", "Normal game"], index=1, key="teams_context")
    with controls[4]:
        role_family = st.selectbox("Role family", list(ROLE_LABELS), format_func=ROLE_LABELS.get, key="teams_family", on_change=update_query_from_widget, args=("family", "teams_family"))

if season_state.invalid_query or team_state.invalid_query or family_state.invalid_query:
    # query_params initialize deep links; invalid values remain explicit and recoverable.
    if season_state.invalid_query: st.warning("The requested season was not found.")
    if team_state.invalid_query: st.warning("Team not found. Search for and select a valid team.")
    if family_state.invalid_query: st.warning("The requested role family was not found.")
    st.stop()

window = "Season" if window_label == "Season" else int(window_label.split()[-1])
week_text = query_value("week")
requested_week = int(week_text) if week_text.isdigit() else None
weeks = available_weeks(season)
if requested_week is not None and requested_week not in weeks:
    st.warning(f"Week not found for {season}: {week_text}")
    st.stop()
end_week = requested_week if requested_week is not None else max(weeks)

family_summaries = {
    family: team_window_summary(
        season,
        team,
        family,
        end_week,
        window,
        context,
    )
    for family in ROLE_LABELS
}
summary = family_summaries[role_family]
selection_summary(
    f"{team} · {season} · {window_label}",
    f"{context} · {ROLE_LABELS[role_family]}",
    f"Through Week {end_week} · {len(summary)} players",
    target=summary_slot,
)
if query_value("origin") == "home" and query_value("focus_family") == role_family:
    origin_message = home_evidence_message(
        season, end_week, query_value("focus"), role_family, team=team
    )
    if origin_message:
        note(origin_message)

target_parts = [family_summaries[name] for name in ("wr_target_share", "te_target_share") if not family_summaries[name].empty]
all_targets = pd.concat(target_parts, ignore_index=True) if target_parts else pd.DataFrame()
leader_specs = [
    ("Backfield", role_leader(family_summaries["rb_carry_share"], label="Carry leader")),
    ("Backfield", role_leader(family_summaries["rb_opportunity_share"], label="RB opportunity leader")),
    ("Receiving", role_leader(family_summaries["wr_target_share"], label="WR target-share leader")),
    ("Receiving", role_leader(family_summaries["te_target_share"], label="TE target-share leader")),
    ("Receiving", role_leader(all_targets, label="Overall target leader") if not all_targets.empty else None),
]
leader_rows, leader_cards = [], []
for group, leader in leader_specs:
    if leader is None:
        continue
    comparison = f"{leader['change'] * 100:+.1f} pp vs prior window" if pd.notna(leader["change"]) else "No prior comparison"
    leader_rows.append({"Group": group, "Role": leader["label"], "Player": leader["player_name"], "Count": leader["raw"], "Denominator": leader["denominator"], "Share": leader["share"] * 100, "Comparison": comparison})
    leader_cards.append({
        "title": leader["label"], "subtitle": f"{leader['player_name']} · {leader['position']} · {group}",
        "metrics": [("Ownership", ratio_text(leader["raw"], leader["denominator"]), context), ("Recent comparison", comparison, window_label)],
        "href": f"/players?player={leader['player_id']}&season={season}&week={end_week}",
    })

section("Role hierarchy at a glance", "Core backfield and receiving ownership leaders for the selected window.")
if leader_rows:
    responsive_table(pd.DataFrame(leader_rows), leader_cards, key="teams_leaders", height=410, percent_columns=["Share"], label="View complete leader table")
else:
    st.info("No valid team denominators are available for this selection.")

role_change_table = build_team_role_change_table(
    role_family=role_family,
    last8=team_window_summary(season, team, role_family, end_week, 8, "Normal game"),
    last4=team_window_summary(season, team, role_family, end_week, 4, "Normal game"),
    last2=team_window_summary(season, team, role_family, end_week, 2, "Normal game"),
)
section(
    "Role Change Radar",
    "What changed in this role family? Normal-game Last 8 → Last 4 → Last 2, ranked by signal strength and shift size.",
)
if role_change_table.empty:
    st.info("No comparable role-change sample is available for this team and role family.")
else:
    radar_rows, radar_cards = [], []
    for _, row in role_change_table.head(8).iterrows():
        shift = row["shift_pp"]
        shift_text = "—" if pd.isna(shift) else f"{float(shift):+.1f} pp"
        rank8 = row["rank_last8"]
        rank2 = row["rank_last2"]
        rank_text = "—"
        if pd.notna(rank2):
            prefix = str(row["position"])
            rank_text = f"{prefix}{int(rank2)}"
            if pd.notna(rank8) and int(rank8) != int(rank2):
                rank_text = f"{prefix}{int(rank8)} → {prefix}{int(rank2)}"
        radar_rows.append(
            {
                "Player": row["player_name"],
                "Position": row["position"],
                "Signal": row["classification"],
                "Trend": row["trend"],
                "Confidence": row["confidence"],
                "Last 8": None if pd.isna(row["last8_share"]) else float(row["last8_share"]) * 100,
                "Last 4": None if pd.isna(row["last4_share"]) else float(row["last4_share"]) * 100,
                "Last 2": None if pd.isna(row["last2_share"]) else float(row["last2_share"]) * 100,
                "Shift (pp)": shift,
                "Team rank": rank_text,
            }
        )
        radar_cards.append(
            {
                "title": f"{row['player_name']} — {row['classification']}",
                "subtitle": f"{row['position']} · {row['trend']} · {row['confidence']} confidence",
                "metrics": [
                    ("Role shift", shift_text, "Last 2 vs Last 8 normal-game share"),
                    ("Team rank", rank_text, "Last 8 → Last 2"),
                    (
                        "Recent ownership",
                        "—" if pd.isna(row["last2_share"]) else f"{float(row['last2_share']):.1%}",
                        "Last 2 normal game",
                    ),
                ],
                "href": f"/players?player={row['player_id']}&season={season}&family={role_family}&week={end_week}",
            }
        )
    responsive_table(
        pd.DataFrame(radar_rows),
        radar_cards,
        key="teams_role_change_radar",
        height=430,
        percent_columns=["Last 8", "Last 4", "Last 2"],
        label="View complete role-change table",
    )
    st.caption(
        "SURGE/DROP require large, directionally consistent movement across multiple windows. "
        "Thin samples are labeled LOW confidence or INSUFFICIENT SAMPLE."
    )

movement = summary.dropna(subset=["change"]).copy() if not summary.empty else pd.DataFrame()
if not movement.empty:
    movement["absolute_change"] = movement["change"].abs()
    movement = movement.sort_values(["absolute_change", "raw_opportunities", "player_name"], ascending=[False, False, True])
    section("Recent movement", "Largest count-weighted changes versus the prior matching window.")
    move_rows, move_cards = [], []
    for _, row in movement.head(6).iterrows():
        move_rows.append({"Player": row["player_name"], "Position": row["position"], "Change": row["change"] * 100, "Count": row["raw_opportunities"], "Denominator": row["team_denominator"], "Share": row["share"] * 100})
        move_cards.append({"title": row["player_name"], "subtitle": f"{row['position']} · {ROLE_LABELS[role_family]}", "metrics": [("Share change", f"{row['change'] * 100:+.1f} pp", "Versus prior matching window", True), ("Current ownership", ratio_text(row["raw_opportunities"], row["team_denominator"], role_noun(role_family)), context)], "href": f"/players?player={row['player_id']}&season={season}&family={role_family}&week={end_week}"})
    responsive_table(pd.DataFrame(move_rows), move_cards, key="teams_movement", height=300, percent_columns=["Change", "Share"], label="View movement table")

view_mode = st.segmented_control("Usage view", ["Role ownership", "Game script", "Scoring area"], default="Role ownership", label_visibility="collapsed", key="teams_view")
if season < 2023 and view_mode != "Role ownership":
    note("Situational views are available from 2023 onward for published seasons.", amber=True)
    view_mode = "Role ownership"

view_summary = summary
if view_mode != "Role ownership":
    situation = situational_team_summary(
        season,
        team,
        role_family,
        end_week,
        window,
        context,
    )
    if situation.empty:
        view_summary = summary.iloc[0:0].copy()
    else:
        view_summary = summary.merge(
            situation,
            on=["player_id", "player_name", "position"],
            how="left",
        )

section(view_mode, f"Complete {ROLE_LABELS[role_family].lower()} hierarchy.")
if view_summary.empty:
    st.info("No team rows match the selected filters.")
else:
    contexts = {
        "Game script": [("early_down", "Early down"), ("passing_down", "Passing down"), ("two_minute", "Two minute"), ("short_yardage", "Short yardage")],
        "Scoring area": [("red_zone", "Red zone"), ("inside_10", "Inside 10"), ("inside_5", "Inside five"), ("end_zone", "End-zone targets")],
    }
    cards, rows_out = [], []
    for rank, (_, row) in enumerate(view_summary.iterrows(), start=1):
        if view_mode == "Role ownership":
            metrics = [("Ownership", ratio_text(row["raw_opportunities"], row["team_denominator"], role_noun(role_family)), context), ("Prior comparison", f"{row['change'] * 100:+.1f} pp" if pd.notna(row["change"]) else "—", f"{window_label} versus prior window"), ("Sample", f"{int(row['sample_games'])} games", "Qualifying games")]
            rows_out.append({"Rank": rank, "Player": row["player_name"], "Position": row["position"], "Raw": row["raw_opportunities"], "Denominator": row["team_denominator"], "Share": row["share"] * 100, "Change": row["change"] * 100 if pd.notna(row["change"]) else pd.NA})
        else:
            metrics, output = [], {"Rank": rank, "Player": row["player_name"], "Position": row["position"]}
            for source, label in contexts[view_mode]:
                raw, denominator = row.get(f"{source}_raw"), row.get(f"{source}_denominator")
                if pd.notna(denominator) and float(denominator) > 0:
                    metrics.append((label, ratio_text(raw, denominator, role_noun(role_family)), "Same-team context"))
                    output[f"{label} count"] = f"{int(raw)} / {int(denominator)}"
                    output[f"{label} share"] = float(raw) / float(denominator) * 100
            rows_out.append(output)
        cards.append({"rank": f"#{rank}", "title": row["player_name"], "subtitle": f"{team} · {row['position']}", "metrics": metrics, "href": f"/players?player={row['player_id']}&season={season}&family={role_family}&week={end_week}"})
    display = pd.DataFrame(rows_out)
    pct = [column for column in display if column in {"Share", "Change"} or column.endswith(" share")]
    if pct:
        display = numeric_percent_sort(display, pct[0])
    responsive_table(display, cards, key=f"teams_{view_mode.lower().replace(' ', '_')}", height=520, percent_columns=pct)

methodology_expander([
    "Every percentage uses the player count divided by the matching same-team denominator.",
    "Window comparisons sum raw counts before division.",
    "Zero denominators are suppressed rather than displayed as leaders.",
])
source_footer("Historical role ownership only; no future depth-chart claim is made.")
