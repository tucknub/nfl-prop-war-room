# Streamlit Community Cloud Deployment

1. Push this repo to GitHub.
2. Go to Streamlit Community Cloud.
3. Click Create app.
4. Select the GitHub repo.
5. Set main file path to `dashboard/Home.py` (the deployment entrypoint; `dashboard/app.py` is equivalent locally).
6. Deploy.
7. Confirm the app opens the Role & Usage Research home page, defaults to completed 2025 data, and states that the 2026 season has not started.

Preferred Streamlit Cloud main file path: `dashboard/Home.py`.
Equivalent local path: `dashboard/app.py`.

This deployment is descriptive role-and-usage research only. It does not publish detector conclusions, projections, picks, or betting recommendations. Do not commit secrets, upload `.env`, or add Streamlit secrets unless required later and stored outside Git.
