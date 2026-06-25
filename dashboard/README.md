# NFL Prop War Room - Receptions V1

This is a local Streamlit dashboard for inspecting the Receptions V1 historical-test/control-room outputs.

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

Current expected state for the stable snapshot:

- Final readiness: `NO-GO`
- Leakage status: `PASS`
- Usage status: `HISTORICAL TEST ONLY`
- Live betting output created: `False`

Pages:

- Live Readiness
- Receptions Dashboard
- Line Ladder
- Market Edges
- Gate Status
- Identity Warnings
- Run Reports
