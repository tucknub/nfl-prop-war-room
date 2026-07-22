from __future__ import annotations

import pandas as pd
import streamlit as st

from launch_contract import (
    ALL_PLAY_AUTHORITY_NOTICE,
    REPORT_DEFINITIONS,
    REPORT_METHODS,
    REPORT_ORDER,
)
from research_ui import page_intro, section, source_footer
from supporting_evidence import validated_data_status


page_intro(
    "Methodology",
    "How PropWar turns documented offensive plays into the three launch reports.",
)

status = validated_data_status()
status_columns = st.columns(3)
status_columns[0].metric("Validated data", status.get("label") or "Unavailable")
status_columns[1].metric("Completed games", int(status.get("completed_games") or 0))
status_columns[2].metric("Status", str(status.get("status") or "UNAVAILABLE"))

st.info(ALL_PLAY_AUTHORITY_NOTICE)

section("Launch report contract", "The launch product contains exactly three reports.")
contract_rows = []
for report in REPORT_ORDER:
    contract_rows.append(
        {
            "Report": report,
            "Question": REPORT_DEFINITIONS[report],
            "Method": " ".join(REPORT_METHODS[report]),
        }
    )
st.dataframe(pd.DataFrame(contract_rows), width="stretch", hide_index=True)

section("Calculation authority", "Percentages are derived after raw counts are summed.")
st.markdown(
    """
1. Identify the documented player opportunity on each eligible offensive play.
2. Identify the matching same-team opportunity denominator for the same role family and context.
3. Sum player and team counts across the selected window.
4. Divide the summed player count by the summed team denominator.
5. Preserve the raw numerator and denominator beside every displayed share.

Averages of weekly percentages are not used as the authority value. Missing denominators do not become zero, and unavailable fields are not fabricated.
"""
)

section("Report boundaries", "What each report does—and does not—claim.")
st.markdown(
    """
- **Backfield Control** describes carry and total RB opportunity ownership.
- **Target Hierarchy** describes WR and TE target ownership.
- **Role Movement** describes the difference between a current window and the immediately preceding matching window.
- Normal-game values are context for reviewing abnormal late-game or extreme situations; they do not replace all-play authority.
- Report ordering is descriptive. It is not a projection, sportsbook edge, fantasy recommendation, or guarantee that a role will persist.
"""
)

section("Missing and unavailable data", "Trust requires refusing to invent precision.")
st.markdown(
    """
PropWar displays only fields supported by the committed data and validated definitions. Route participation, first-read share, exact coverage assignments, final-score concentration, and other unavailable fields remain unavailable until a trusted source and validation contract exist. Confirmed partial games are excluded under the existing rules; suspected partial games remain labeled for review.
"""
)

section("Reproducibility", "Every conclusion must be traceable to the same underlying rows.")
st.markdown(
    """
The Team, Player, Game, Reports, and Advanced Research surfaces are expected to reconcile to the same canonical player-week and all-play data. Presentation wording may change, but locked role definitions, denominators, classification rules, and historical validation fingerprints must not change without an explicit methodology release.
"""
)

source_footer("Methodology applies to completed historical data currently available in the application.")
