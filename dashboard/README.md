# NFL Prop War Room

This is a local Streamlit dashboard for inspecting the NFL Prop War Room historical-test/control-room outputs.

Run the safe pipeline first:

```powershell
python -m src.run_receptions_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
```

Start the dashboard:

```powershell
streamlit run dashboard/Home.py
```

Preferred Streamlit Cloud main file path: `dashboard/Home.py`.
Legacy-compatible path: `dashboard/app.py`.

The dashboard reads files from `outputs/` and does not upload anything. It is research/model review only until `Live Readiness = GO`.

This is the full NFL Prop War Room dashboard shell. Receptions, Receiving Yards, Rushing Yards, Carries, Pass Attempts, Completions, and Passing Yards V1 are active historical-test markets; the other markets remain planned. The Passing Yards page includes QB projections, a passing-volume versus efficiency view, and a no-odds research ladder. Current roster mapping is built but remains `NEEDS DATA` until real source-backed roster files are loaded.

Current expected state for the stable snapshot:

- Final readiness: `NO-GO`
- Leakage status: `PASS`
- Usage status: `HISTORICAL TEST ONLY`
- Live betting output created: `False`

Pages:

- Live Readiness
- Current Roster / Team Mapping
- Receptions Dashboard
- Line Ladder
- Market Edges

## Current Roster / Team Mapping

The roster-map page separates historical stat-team context from verified current/projection-team context. Team changes are resolved through source-backed roster inputs or approved override files, never hardcoded inside market models. Template-only inputs keep the roster map at `NEEDS DATA`, so forward live use remains blocked.
- Gate Status
- Identity Warnings
- Run Reports
