# Searchability Design

High-cardinality controls use one pattern: **Search or select player/team/game**, followed by the visible instruction **Open the list and start typing to filter options.** Opening the Streamlit selector focuses its type-to-filter field; the user does not need to delete the current selection first. Results remain constrained to canonical valid options.

Player labels contain name, selected-week team, and position. Game labels contain the human-readable away/home pairing plus the canonical game ID. Duplicate names therefore retain canonical identity, and the six audited multi-team players keep their Week 18 team labels.
