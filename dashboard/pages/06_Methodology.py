from __future__ import annotations

import streamlit as st

from launch_contract import (
    ALL_PLAY_AUTHORITY_NOTICE,
    REPORT_DEFINITIONS,
    REPORT_METHODS,
    REPORT_ORDER,
)
from research_data import operational_status_text
from research_ui import overview, page_intro, section, source_footer
from supporting_evidence import validated_data_status


page_intro(
    "Methodology",
    "A plain-language guide to what each report measures, how to read it, and where the limits are.",
)

status = validated_data_status()
overview(
    (
        ("Validated data", str(status.get("label") or "Unavailable")),
        ("Completed games", str(int(status.get("completed_games") or 0))),
        ("Status", str(status.get("status") or "UNAVAILABLE")),
    )
)

section("How to read a report", "Start with the answer, confirm the counts, then open the evidence.")
steps = st.columns(3)
step_copy = (
    ("1. Read the finding", "The first sentence states who controls or changed a documented role."),
    ("2. Check the counts", "Every share shows the player's opportunities and the matching team total."),
    ("3. Open the evidence", "Player and team pages let you inspect the same underlying rows in more detail."),
)
for column, (title, description) in zip(steps, step_copy):
    with column:
        with st.container(border=True):
            st.markdown(f"### {title}")
            st.write(description)

st.info(ALL_PLAY_AUTHORITY_NOTICE)

section("Launch report contract", "The public product contains exactly three reports.")
for report in REPORT_ORDER:
    with st.container(border=True):
        st.markdown(f"### {report}")
        st.write(REPORT_DEFINITIONS[report])
        st.markdown("**How it is calculated**")
        for method in REPORT_METHODS[report]:
            st.markdown(f"- {method}")

section("Plain-language terms", "The report labels are simple; the technical definitions remain available here.")
term_columns = st.columns(2)
terms = (
    ("Team share", "The player's documented opportunities divided by the matching team opportunities."),
    ("Team total", "The same-team denominator used for the selected role and time period."),
    ("Typical-game share", "Supporting context that removes defined abnormal late-game situations."),
    ("Role movement", "The current time period compared with the immediately previous matching period."),
)
for index, (term, meaning) in enumerate(terms):
    with term_columns[index % 2]:
        with st.container(border=True):
            st.markdown(f"**{term}**")
            st.write(meaning)

section("Report boundaries", "What each report does—and does not—claim.")
st.markdown(
    """
- **Backfield Control** describes carry and total RB opportunity ownership.
- **Target Hierarchy** describes WR and TE target ownership.
- **Role Movement** describes the difference between a current period and the immediately preceding matching period.
- Typical-game values are supporting context; they do not replace the full-period player count and team total.
- Report ordering is descriptive. It is not a projection, sportsbook edge, fantasy recommendation, or guarantee that a role will persist.
"""
)

with st.expander("Calculation details"):
    st.markdown(
        """
1. Identify the documented player opportunity on each eligible offensive play.
2. Identify the matching same-team opportunity denominator for the same role and context.
3. Sum player and team counts across the selected period.
4. Divide the summed player count by the summed team total.
5. Preserve the raw player count and team total beside every displayed share.

Averages of weekly percentages are not used as the authority value. Missing denominators do not become zero, and unavailable fields are not fabricated.
"""
    )

with st.expander("Missing and unavailable data"):
    st.markdown(
        """
PropWar displays only fields supported by committed data and validated definitions. Route participation, first-read share, exact coverage assignments, final-score concentration, and other unavailable fields remain unavailable until a trusted source and validation contract exist.

Confirmed partial games are excluded under the existing rules. Suspected partial games remain labeled for review rather than being silently removed.
"""
    )

with st.expander("Current-season operations"):
    st.markdown(
        """
- Only consecutive, fully completed regular-season weeks are eligible to publish.
- Play-by-play, schedules, weekly rosters, player statistics, and offensive snap counts are required.
- Current-season participation data is not estimated when it is unavailable during the season.
- Current injury information is not inferred from an unavailable source. A confirmed partial-game exclusion requires a reviewed manual record.
- New files are built and validated in staging. A failed source, join, or validation gate leaves the prior published partition active.
- Each published season has a manifest, file hashes, join coverage, source coverage, and a public freshness status.
"""
    )

with st.expander("Reproducibility"):
    st.markdown(
        """
The Team, Player, Game, Reports, and Advanced Research pages reconcile to the same canonical player-week and all-play data. Presentation wording may change, but locked role definitions, denominators, classification rules, and historical validation fingerprints must not change without an explicit methodology release.
"""
    )

source_footer(operational_status_text())
