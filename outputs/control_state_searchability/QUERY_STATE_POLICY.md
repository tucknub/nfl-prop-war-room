# Query and Control State Policy

## Initial load or changed browser URL

1. Apply a valid explicit query value.
2. Otherwise keep a valid page session value.
3. Otherwise use the documented default.

## User interaction

1. The widget value is authoritative.
2. Streamlit stores it under one stable page-specific key.
3. A callback updates the supported query parameter.
4. Dependent stale query values are cleared.
5. Later reruns keep the widget value unless a genuinely changed URL supplies another valid value.

## Invalid URL

An invalid explicit query is reported. A valid recovery control remains available, but unrelated fallback data is not rendered. Selecting a valid value replaces the invalid query.
