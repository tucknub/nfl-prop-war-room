from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, sidebar_status, warning_banner


MARKET_STATUS_PATH = "outputs/markets/market_status.csv"


st.set_page_config(page_title="Market Hub", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "NFL Prop War Room",
    "Multi-market NFL prop projection framework. Receptions V1 is active; additional markets are planned.",
    "HISTORICAL TEST ONLY",
)
warning_banner(
    "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
    "Only Receptions V1 is built. Planned markets are metadata only and must not be treated as projections or betting edges.",
)

markets = load_csv_safe(MARKET_STATUS_PATH)
if markets.empty:
    st.warning(f"Missing file: `{MARKET_STATUS_PATH}`. Run `python -m src.run_receptions_pipeline`.")
    st.stop()

section_header("Market Status", "Built and planned prop markets grouped by category.")
for category in ["Receiving", "Rushing", "Passing", "Touchdowns", "Long Plays"]:
    group = markets[markets["category"].astype(str).eq(category)]
    if group.empty:
        continue
    section_header(category)
    cols = st.columns(min(3, len(group)))
    for idx, (_, row) in enumerate(group.iterrows()):
        with cols[idx % len(cols)]:
            status = "ACTIVE" if bool(row.get("active")) else "Planned / Not Built Yet"
            metric_card(
                str(row.get("display_name", "")),
                str(row.get("projection_unit", "")),
                row.get("status", ""),
                f"{status}. {row.get('notes', '')}",
            )

section_header("Current Active Market", "Receptions V1")
c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Active Model", "Receptions V1", "built")
with c2:
    metric_card("Mode", "Historical Test", "HISTORICAL TEST ONLY")
with c3:
    metric_card("Line Ladder", "Available", "PASS")
with c4:
    metric_card("Edge Engine", "Blocked", "NO-GO", "Missing odds and live gates.")

st.markdown(
    """
    <div class="info-card">
    Dashboard pages available now: Receptions Projection Board, Reception Line Ladder, Market Edge Engine,
    Forward Readiness Gates, Identity & Team Matching, Run Reports, and Best Overall Board placeholder.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Future Markets Roadmap")
roadmap = [
    "1. Receiving Yards - closest to receptions because it extends target/catch opportunity with yardage efficiency.",
    "2. Rushing Yards - similar volume-efficiency structure using carries and yards per carry.",
    "3. Passing Yards - uses team/QB pass-volume and passing efficiency logic.",
    "4. Completions - tied to QB attempts and completion rate.",
    "5. Pass Attempts - starts from team pass-volume and game environment.",
    "6. Carries - rushing opportunity foundation for backs and mobile QBs.",
    "7. Targets - receiving opportunity market adjacent to Receptions V1.",
    "8. Anytime TD - needs different event probability modeling.",
    "9. Longest Reception / Rush - needs long-play distribution modeling.",
]
st.markdown("<div class='info-card'>" + "<br>".join(roadmap) + "</div>", unsafe_allow_html=True)

with st.expander("Raw market registry export"):
    st.dataframe(presentation_table(markets), use_container_width=True, hide_index=True)
