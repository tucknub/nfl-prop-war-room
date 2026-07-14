# PropWar Rollback Plan

## Current checkpoint

- Production branch: `streamlit-cloud-deploy`
- Current production commit: `8b759f18c34708300acf5e3ef84d0e4cbbbde597`
- Pre-mobile rollback tag: `production-streamlit-cloud-pre-mobile-ux-v2`
- Tagged commit: `3bc43a8ffbea06f06e048665bda77e879666bdf7`

## Phase A rule

Phase A cannot deploy, merge, or move production. Therefore no rollback action should be required from this audit branch.

## Authorized rollback procedure for a future incident

1. Confirm the incident and current production SHA.
2. Preserve evidence and tag the failing production SHA.
3. Obtain explicit production authorization.
4. Fast-forward or revert `streamlit-cloud-deploy` to the approved known-good commit; do not rewrite shared history without explicit authorization.
5. Push the production branch and wait for Streamlit deployment.
6. Hard reload the public app and repeat the affected live workflows.
7. Record the rollback commit, reason, validation, and timestamp in `RELEASE_HISTORY.md`.

The rollback tag is a recovery reference, not permission to change production during Phase A.
