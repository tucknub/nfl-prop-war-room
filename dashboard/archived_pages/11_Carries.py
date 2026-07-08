from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import filter_by_multiselect, filter_by_search, format_percent, inject_global_styles, load_csv_safe, metric_card, numeric_series, page_header, player_card, presentation_table, section_header, show_missing, sidebar_status, warning_banner

BOARD_PATH="outputs/google_sheets_carries_historical_test.csv"
LADDER_PATH="outputs/market_edges/carries_line_ladder.csv"

st.set_page_config(page_title="Carries V1",layout="wide"); inject_global_styles(); sidebar_status()
page_header("Carries V1","Historical-test rushing volume projections and no-odds line ladder.","HISTORICAL TEST ONLY")
warning_banner("Historical Test Only - Not Betting Ready","Carries V1 is Research Only - No Odds. Final Readiness remains NO-GO.")
df=load_csv_safe(BOARD_PATH)
if df.empty: show_missing(BOARD_PATH); st.stop()
view=df.copy(); filters=st.columns(4)
with filters[0]: view=filter_by_multiselect(view,"team","Team")
with filters[1]: view=filter_by_multiselect(view,"position","Position")
with filters[2]: view=filter_by_multiselect(view,"confidence_bucket","Confidence")
with filters[3]: view=filter_by_search(view,"player_name")
vals=numeric_series(view,"projected_carries_calibrated"); cards=st.columns(5)
with cards[0]: metric_card("Rows",f"{len(view):,}")
with cards[1]: metric_card("Players",view["player_name"].nunique())
with cards[2]: metric_card("Teams",view["team"].nunique())
with cards[3]: metric_card("Avg Projection",f"{vals.mean():.2f}" if not vals.empty else "n/a")
with cards[4]: metric_card("Historical-Test Rows",int(view["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").sum()),"HISTORICAL TEST ONLY")
section_header("Top Carry Projections"); top=view.sort_values("projected_carries_calibrated",ascending=False).head(5); cols=st.columns(5)
for col,(_,row) in zip(cols,top.iterrows()):
    with col: player_card(str(row.get("player_name","")),str(row.get("team","")),str(row.get("position","")),f"{pd.to_numeric(row.get('projected_carries_calibrated'),errors='coerce'):.1f}",row.get("confidence_bucket",""))
section_header("Projection Table")
show=["overall_rank","player_name","team","opponent_team","position","projected_carries_calibrated","projected_carries_raw","projected_team_rush_attempts","projected_player_rush_attempt_share","confidence_bucket","quality_flags","usage_status"]
st.dataframe(presentation_table(view[[c for c in show if c in view.columns]]),use_container_width=True,hide_index=True)

section_header("Rushing Volume vs Efficiency","Carries volume compared with the separate Rushing Yards projection.")
rush=load_csv_safe("outputs/google_sheets_rushing_yards_historical_test.csv")
if not rush.empty:
    joined=view.merge(rush[["player_name","team","projected_rushing_yards_calibrated"]],on=["player_name","team"],how="inner")
    if not joined.empty:
        carry_mid=joined["projected_carries_calibrated"].median(); yard_mid=joined["projected_rushing_yards_calibrated"].median()
        joined["volume_efficiency_profile"]=pd.NA
        joined.loc[(joined["projected_carries_calibrated"]>=carry_mid)&(joined["projected_rushing_yards_calibrated"]>=yard_mid),"volume_efficiency_profile"]="High carries + high yards"
        joined.loc[(joined["projected_carries_calibrated"]>=carry_mid)&(joined["projected_rushing_yards_calibrated"]<yard_mid),"volume_efficiency_profile"]="High carries + lower yards"
        joined.loc[(joined["projected_carries_calibrated"]<carry_mid)&(joined["projected_rushing_yards_calibrated"]>=yard_mid),"volume_efficiency_profile"]="Low carries + high yards"
        compare=["player_name","team","position","projected_carries_calibrated","projected_rushing_yards_calibrated","volume_efficiency_profile","usage_status"]
        st.dataframe(presentation_table(joined[[c for c in compare if c in joined.columns]].head(50)),use_container_width=True,hide_index=True)

section_header("Carries Line Ladder","Research Only - No Odds")
ladder=load_csv_safe(LADDER_PATH)
if ladder.empty: show_missing(LADDER_PATH)
else:
    lines=sorted(pd.to_numeric(ladder["line"],errors="coerce").dropna().unique()); default=lines.index(12.5) if 12.5 in lines else 0
    selected_line=st.selectbox("Carries line",lines,index=default)
    selected=ladder[pd.to_numeric(ladder["line"],errors="coerce").eq(float(selected_line))].sort_values("model_over_probability",ascending=False).head(15)
    st.caption(f"Max over probability at {selected_line}: {format_percent(selected['model_over_probability'].max())}")
    st.bar_chart(selected.set_index("player_name")["model_over_probability"]); st.dataframe(presentation_table(selected),use_container_width=True,hide_index=True)
