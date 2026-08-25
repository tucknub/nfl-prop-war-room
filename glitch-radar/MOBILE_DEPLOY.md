# NFL Glitch Radar — Mobile / Anywhere

Deploy this branch with Streamlit Community Cloud.

Repository: `tucknub/nfl-prop-war-room`
Branch: `glitch-radar`
Entrypoint: `glitch-radar/app.py`

## Deploy
1. Open https://share.streamlit.io
2. Sign in and connect GitHub.
3. Click **Create app**.
4. Choose repository `tucknub/nfl-prop-war-room`.
5. Choose branch `glitch-radar`.
6. Set entrypoint to `glitch-radar/app.py`.
7. Deploy.
8. Bookmark the resulting `streamlit.app` URL on your phone.

## How mobile mode works
- Home PC does not need to be on.
- No API key is required in the default mode.
- The app fetches public no-key NFL data when opened.
- Results are cached for 10 minutes.
- **Force fresh scan** clears the cache and refreshes.
- Community Cloud can hibernate inactive apps; opening the URL wakes the app.

## Local Windows mode
The local package can still run scheduled scans and maintain richer history on your home PC.
