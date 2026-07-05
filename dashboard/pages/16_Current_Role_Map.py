from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd,streamlit as st
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles,load_csv_safe,metric_card,page_header,presentation_table,section_header,show_table_or_missing,sidebar_status,warning_banner
MAP="outputs/roles/current_role_map.csv";STATUS="outputs/roles/current_role_map_status.csv";REVIEW="outputs/roles/current_role_needs_review.csv"
st.set_page_config(page_title="Role / Depth Chart Mapping",layout="wide");inject_global_styles();sidebar_status();page_header("Role / Depth Chart Mapping","Verified workload context required for every forward projection.","NO-GO");warning_banner("Forward projection blocked until player roles are verified","Template rows do not count as role data. Low-confidence, unknown, mismatched, and unapproved role rows remain blockers.")
mapped=load_csv_safe(MAP);status=load_csv_safe(STATUS);review=load_csv_safe(REVIEW)
def value(c):
 if status.empty or c not in status.columns:return 0
 x=pd.to_numeric(status[c],errors="coerce").iloc[0];return 0 if pd.isna(x) else int(x)
overall=str(status.status.iloc[0]) if not status.empty and "status" in status.columns else "NEEDS DATA";items=[("Role Rows Loaded",value("role_rows_loaded"),overall),("READY",value("ready_rows"),"READY"),("NEEDS REVIEW",value("needs_review_rows"),"NEEDS REVIEW"),("NEEDS DATA",value("needs_data_rows"),"NEEDS DATA"),("BLOCKED",value("blocked_rows"),"BLOCKED"),("Manual Overrides",value("manual_overrides"),"REVIEW"),("Low-Confidence Roles",value("low_confidence_roles"),"REVIEW")];cols=st.columns(4)
for i,(label,v,state) in enumerate(items):
 with cols[i%4]:metric_card(label,v,state)
st.markdown('<div class="info-card">Current team tells us where a player is. Role mapping tells us whether his workload is usable for props. A player can be on the right team and still be blocked if his role is unclear.</div>',unsafe_allow_html=True)
section_header("Current Role Map",f"Overall mapping status: {overall}");show_table_or_missing(presentation_table(mapped),MAP);section_header("Needs Review");show_table_or_missing(presentation_table(review),REVIEW)
with st.expander("Role map status details"):show_table_or_missing(presentation_table(status),STATUS)
