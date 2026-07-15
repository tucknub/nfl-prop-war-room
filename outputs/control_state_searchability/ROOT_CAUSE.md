# Root Cause

The public deep-link pages read `st.query_params` on every Streamlit rerun and immediately assigned the URL value to the same session-state key used by the widget. The URL was not updated by a widget callback. In the DAL reproduction, selecting PHI updated the widget briefly, the rerun read `team=DAL`, wrote DAL back into `teams_team`, and rendered DAL again.

The defect was shared by Home season/week, Teams season/team/family, Players season/player/family, and Games season/week/game. Reports and Explorer relied on stable widget keys and did not have the URL overwrite, but dependent option lists and report-specific sort options needed explicit validity guards.

The fix uses one page-scoped query marker. A valid query value initializes on first load or a genuine changed URL; otherwise the current valid widget/session value wins. Widget callbacks immediately replace the corresponding query parameter. Invalid URL values remain explicit and suppress unrelated rendered data until a valid selection replaces them.
