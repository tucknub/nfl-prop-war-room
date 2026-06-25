# Streamlit Community Cloud Deployment

1. Push this repo to GitHub.
2. Go to Streamlit Community Cloud.
3. Click Create app.
4. Select the GitHub repo.
5. Set main file path to `dashboard/Home.py`.
6. Deploy.
7. Confirm the app shows `HISTORICAL TEST ONLY` and Final Readiness `NO-GO`.

Preferred Streamlit Cloud main file path: `dashboard/Home.py`.
Legacy-compatible path: `dashboard/app.py`.

This deployment is research-only unless Live Readiness becomes `GO`. Do not commit secrets, do not upload `.env`, and do not add Streamlit secrets unless they are required later and stored outside git.

Receptions V1 and Receiving Yards V1 are the active built historical-test markets. The dashboard includes a multi-market framework and roadmap, but all other markets are planned and do not currently output projections.
