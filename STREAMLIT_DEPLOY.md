# Streamlit Community Cloud Deployment

PropWar remains on Streamlit Community Cloud during private-beta proving.

## Production source

- Repository: `tucknub/nfl-prop-war-room`
- Production branch: `streamlit-cloud-deploy`
- Preferred main file: `dashboard/Home.py`
- Equivalent local entrypoint: `dashboard/app.py`

## Deploy or redeploy

1. Run the full PropWar Product Gate before treating a commit as production-safe.
2. Push the intended production state to `streamlit-cloud-deploy`.
3. In Streamlit Community Cloud, select this repository and production branch.
4. Use `dashboard/Home.py` as the main file.
5. Store required secrets only in Streamlit's encrypted Secrets interface. Never commit `.streamlit/secrets.toml`, `.env`, API keys, owner credentials, or private-state tokens.
6. Deploy/reboot the app.
7. Verify the public shell and authenticated owner surfaces.

## Post-deploy verification

Confirm:

- Home opens as the PropWar private-beta product, not the old Role & Usage Research-only shell.
- Owner authentication gates private workspaces correctly.
- Today does not promote the unaged no-key market preview.
- Markets identifies its no-key surface as a ParlayAPI preview/research surface and requires in-book verification.
- Deep Market Research rejects undated player-prop rows and provider quote ages above 120 seconds.
- Player Command Center labels role confidence as **Sample strength** and fresh market data as a sportsbook snapshot.
- Fantasy HQ shows **FAAB Market Context** rather than automated target/aggressive/max bids.
- Fantasy trade analysis is explicitly current-week baseline context and does not present a season-long ACCEPT/DECLINE verdict.
- Margin labels the nflverse spread separately from model mean margin and historical loss/20+ estimates.
- Knockout continues to refuse invented survival probabilities or optimal FAAB bids.
- No page exposes secrets or private Margin state.

## Trust standard

All deployments must follow **[docs/propwar/TRUST_CONTRACT.md](docs/propwar/TRUST_CONTRACT.md)**.

When a required source, quote age, identity match, validation gate, or provider field is missing, the production behavior is to omit the claim or fail closed rather than guess.

The market provider is not the sportsbook of record. Any executable wager line, price, market definition, and settlement rule must be verified inside the sportsbook before use.

## Validation

The Product Gate compiles `dashboard`, `src`, and `tests`, runs the product/regression suite including `tests/test_propwar_trust_contract.py`, and starts every visible Streamlit page from a production-like working directory.

The September 4, 2026 trust-hardening production state passed with **827 tests** and all visible Streamlit pages starting successfully.
