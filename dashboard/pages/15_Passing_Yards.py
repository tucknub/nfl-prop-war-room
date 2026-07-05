from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd,streamlit as st
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import filter_by_multiselect,filter_by_search,format_percent,inject_global_styles,load_csv_safe,metric_card,numeric_series,page_header,player_card,presentation_table,section_header,show_missing,sidebar_status,warning_banner
BOARD="outputs/google_sheets_passing_yards_historical_test.csv";LADDER="outputs/market_edges/passing_yards_line_ladder.csv";ATTEMPTS="outputs/google_sheets_pass_attempts_historical_test.csv";COMPLETIONS="outputs/google_sheets_completions_historical_test.csv"
st.set_page_config(page_title="Passing Yards V1",layout="wide");inject_global_styles();sidebar_status();page_header("Passing Yards V1","Historical-test QB passing-yard projections and no-odds line ladder.","HISTORICAL TEST ONLY");warning_banner("Historical Test Only - Not Betting Ready","Passing Yards V1 is Research Only - No Odds. Final Readiness remains NO-GO.")
st.markdown('<div class="info-card"><strong>Formula:</strong> projected pass attempts x projected yards per attempt. Raw and calibrated projections remain visible.</div>',unsafe_allow_html=True)
df=load_csv_safe(BOARD)
if df.empty:show_missing(BOARD);st.stop()
view=df.copy();f=st.columns(3)
with f[0]:view=filter_by_multiselect(view,"team","Team")
with f[1]:view=filter_by_multiselect(view,"confidence_bucket","Confidence")
with f[2]:view=filter_by_search(view,"player_name","QB search")
vals=numeric_series(view,"projected_passing_yards_calibrated");cards=st.columns(5)
with cards[0]:metric_card("Rows",len(view))
with cards[1]:metric_card("QBs",view["player_name"].nunique())
with cards[2]:metric_card("Teams",view["team"].nunique())
with cards[3]:metric_card("Avg Projection",f"{vals.mean():.1f}" if not vals.empty else "n/a")
with cards[4]:metric_card("Historical-Test Rows",int(view["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").sum()),"HISTORICAL TEST ONLY")
section_header("Top QB Passing Yard Projections");top=view.sort_values("projected_passing_yards_calibrated",ascending=False).head(5);cols=st.columns(5)
for col,(_,r) in zip(cols,top.iterrows()):
 with col:player_card(str(r.get("player_name","")),str(r.get("team","")),"QB",f"{pd.to_numeric(r.get('projected_passing_yards_calibrated'),errors='coerce'):.1f}",r.get("confidence_bucket",""))
section_header("Projection Table");show=["overall_rank","player_name","team","opponent_team","projected_passing_yards_calibrated","projected_passing_yards_raw","projected_pass_attempts_calibrated","projected_yards_per_attempt","confidence_bucket","quality_flags","usage_status"];st.dataframe(presentation_table(view[[c for c in show if c in view.columns]]),use_container_width=True,hide_index=True)
section_header("Passing Volume vs Efficiency","Context only - not a betting classification.");attempts=load_csv_safe(ATTEMPTS);completions=load_csv_safe(COMPLETIONS)
if attempts.empty or completions.empty:st.info("Volume/efficiency comparison requires the Pass Attempts and Completions boards.")
else:
 keys=[c for c in ["player_id","player_name","team"] if c in view.columns and c in attempts.columns and c in completions.columns];a=attempts[keys+["projected_pass_attempts_calibrated"]].drop_duplicates(keys);c=completions[keys+["projected_completions_calibrated"]].drop_duplicates(keys);j=view.merge(a,on=keys,how="left",suffixes=("","_attempts")).merge(c,on=keys,how="left");av=pd.to_numeric(j["projected_pass_attempts_calibrated"],errors="coerce");yv=pd.to_numeric(j["projected_passing_yards_calibrated"],errors="coerce");ev=pd.to_numeric(j["projected_yards_per_attempt"],errors="coerce");cv=pd.to_numeric(j["projected_completions_calibrated"],errors="coerce");j["volume_efficiency_profile"]="Lower attempts / lower yardage efficiency";j.loc[(av>=av.median())&(yv>=yv.median()),"volume_efficiency_profile"]="High attempts / high passing yards";j.loc[(cv>=cv.median())&(yv>=yv.median()),"volume_efficiency_profile"]="High completions / high passing yards";j.loc[(av>=av.median())&(ev<ev.median()),"volume_efficiency_profile"]="High attempts / lower yardage efficiency";j.loc[(av<av.median())&(ev>=ev.median()),"volume_efficiency_profile"]="Lower attempts / high yardage efficiency";cc=["player_name","team","projected_pass_attempts_calibrated","projected_completions_calibrated","projected_yards_per_attempt","projected_passing_yards_calibrated","volume_efficiency_profile","usage_status"];st.dataframe(presentation_table(j[[x for x in cc if x in j.columns]].sort_values("projected_passing_yards_calibrated",ascending=False)),use_container_width=True,hide_index=True)
section_header("Passing Yards Line Ladder","Research Only - No Odds");ladder=load_csv_safe(LADDER)
if ladder.empty:show_missing(LADDER)
else:
 lines=sorted(pd.to_numeric(ladder["line"],errors="coerce").dropna().unique());default=lines.index(249.5) if 249.5 in lines else 0;line=st.selectbox("Passing yards line",lines,index=default);selected=ladder[pd.to_numeric(ladder["line"],errors="coerce").eq(float(line))].sort_values("model_over_probability",ascending=False).head(15);st.caption(f"Max over probability at {line}: {format_percent(selected['model_over_probability'].max())}");st.bar_chart(selected.set_index("player_name")["model_over_probability"]);st.dataframe(presentation_table(selected),use_container_width=True,hide_index=True)
