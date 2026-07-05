from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd,streamlit as st
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import filter_by_multiselect,filter_by_search,format_percent,inject_global_styles,load_csv_safe,metric_card,numeric_series,page_header,player_card,presentation_table,section_header,show_missing,sidebar_status,warning_banner
BOARD="outputs/google_sheets_pass_attempts_historical_test.csv"; LADDER="outputs/market_edges/pass_attempts_line_ladder.csv"
st.set_page_config(page_title="Pass Attempts V1",layout="wide");inject_global_styles();sidebar_status();page_header("Pass Attempts V1","Historical-test QB pass-volume projections and no-odds line ladder.","HISTORICAL TEST ONLY");warning_banner("Historical Test Only - Not Betting Ready","Pass Attempts V1 is Research Only - No Odds. Final Readiness remains NO-GO.")
st.markdown('<div class="info-card"><strong>Passing Attempts is a foundation market.</strong><br><br>It helps power future Completions and Passing Yards projections and gives context for receiver target volume.</div>',unsafe_allow_html=True)
df=load_csv_safe(BOARD)
if df.empty:show_missing(BOARD);st.stop()
view=df.copy();f=st.columns(3)
with f[0]:view=filter_by_multiselect(view,"team","Team")
with f[1]:view=filter_by_multiselect(view,"confidence_bucket","Confidence")
with f[2]:view=filter_by_search(view,"player_name","QB search")
vals=numeric_series(view,"projected_pass_attempts_calibrated");cards=st.columns(5)
with cards[0]:metric_card("Rows",len(view))
with cards[1]:metric_card("QBs",view["player_name"].nunique())
with cards[2]:metric_card("Teams",view["team"].nunique())
with cards[3]:metric_card("Avg Projection",f"{vals.mean():.2f}" if not vals.empty else "n/a")
with cards[4]:metric_card("Historical-Test Rows",int(view["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").sum()),"HISTORICAL TEST ONLY")
section_header("Top QB Attempt Projections");top=view.sort_values("projected_pass_attempts_calibrated",ascending=False).head(5);cols=st.columns(5)
for col,(_,r) in zip(cols,top.iterrows()):
    with col:player_card(str(r.get("player_name","")),str(r.get("team","")),"QB",f"{pd.to_numeric(r.get('projected_pass_attempts_calibrated'),errors='coerce'):.1f}",r.get("confidence_bucket",""))
section_header("Projection Table");show=["overall_rank","player_name","team","opponent_team","projected_pass_attempts_calibrated","projected_pass_attempts_raw","projected_team_pass_attempts","projected_qb_attempt_share","confidence_bucket","quality_flags","usage_status"];st.dataframe(presentation_table(view[[c for c in show if c in view.columns]]),use_container_width=True,hide_index=True)
section_header("Pass Attempts Line Ladder","Research Only - No Odds");ladder=load_csv_safe(LADDER)
if ladder.empty:show_missing(LADDER)
else:
    lines=sorted(pd.to_numeric(ladder["line"],errors="coerce").dropna().unique());default=lines.index(31.5) if 31.5 in lines else 0;line=st.selectbox("Pass attempts line",lines,index=default);selected=ladder[pd.to_numeric(ladder["line"],errors="coerce").eq(float(line))].sort_values("model_over_probability",ascending=False).head(15);st.caption(f"Max over probability at {line}: {format_percent(selected['model_over_probability'].max())}");st.bar_chart(selected.set_index("player_name")["model_over_probability"]);st.dataframe(presentation_table(selected),use_container_width=True,hide_index=True)
