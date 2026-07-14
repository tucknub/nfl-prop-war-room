# PropWar completed-2025 descriptive-data release

Release date: 2026-07-14

## Judgment

Completed 2025 descriptive role-and-usage data is integrated and live. The public app defaults to 2025 and explicitly states that the 2026 NFL season has not started. The release adds no 2025 detector result, prediction, confidence label, betting recommendation, odds, or release-gate claim.

## Repository and deployment integrity

- Feature branch: `propwar-role-research-ui-v1`
- Clean integration branch: `propwar-role-research-production`
- Streamlit deployment branch: `streamlit-cloud-deploy`
- Application/data commit before the release-documentation commit: `5cc08bd2cf7b5a4c7e9fd0625b5bfd7802321185`
- Pre-release production commit: `9dd335fa1743deaf2a1c08d139c28c7cdbbe6c1e`
- Rollback tag: `production-streamlit-cloud-pre-role-research-2025`
- Integration method: fast-forward only from the former production commit through the complete validation and UI history
- Original validation worktree after deployment: unchanged on `role-change-validation-v1` at `f3e4a9d5349215af1ee1b1204511dcc377dc7e2e`, with the same 57 pre-existing dirty entries

The production main-file path `dashboard/Home.py` and local path `dashboard/app.py` were both executed and verified. Both now launch the same Streamlit navigation.

## 2025 data audit

| Measure | Result |
|---|---:|
| Canonical player-week-role rows | 7,413 |
| Regular-season games | 272 |
| Played weeks | 1–18 |
| Unique players | 545 |
| Duplicate canonical keys | 0 |
| Required-field missing cells | 0 |
| Identity coverage | 100.000% |
| Opportunity-to-identity coverage | 100.000% |
| Participating-player identity coverage | 99.961% |
| Participation-play coverage | 100.000% |
| Carry-player identity coverage | 100.000% |
| Quality-pass rate | 100.000% |
| Qualifying rate | 100.000% |
| Confirmed partial player-games | 20 |
| Suspected partial player-games | 45 |
| PBP injury identity resolution | 97.062% |

Confirmed partial games are excluded. Suspected partial games remain visible and included. The 2025 injury feed does not provide a usable report-modification timestamp, so no confirmed injury was inferred from reduced usage or a statistical pattern. The only confirmed evidence path is an explicit PBP injury with no offensive return and a representative role drop.

The local PBP source hash is `3b7dfe911b842c990f5191f4a911aecac83fcac568eef0df33d720528f0ce32a`. The detailed nflverse input paths and hashes are in `source_input_manifest_2025.csv`.

## Deterministic outputs

- 2025 canonical: `3c02f26718288adf36b9f7d0759c13722520314998c0d745f1ac76c96535cdfe`
- 2025 partial-status file: `cfb20829157e3b9a52efe8ef55fb5b8ad412b517437f6790f8e28dfd2dd5976b`
- Situational output: `aec6cd6a11ef36b35bc18ab3468ff6b561951164e75b13b845d5b6d220c88a5c`
- Production output: `45f2a601ebe02118c12f93e16dc312a06dacfc8ab8d7f59fec5f64aeb8f06ab2`
- Opportunity-event output: `9c67605493993ae74191f5ddd865a519afb431caac3611b92e083c90bbbf42d5`

The canonical public profile now covers 57,928 rows across 2018–2025 with zero duplicate keys, zero required missing cells, and 100% canonical identity coverage. The play-level situational, production, and opportunity-event products cover 2023–2025. All-play and normal-game reconciliations have zero absolute numerator or denominator difference.

## Verification

- Targeted tests: 12 passed
- Full repository suite: 41 passed
- Frozen-config clean-checkout tests: 3 passed
- Independent output validator: PASS
- Python compilation: PASS
- `git diff --check`: PASS
- `git diff --cached --check`: PASS
- Frozen detector-candidate fingerprint after a new worktree checkout: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`

The first clean production worktree exposed CRLF conversion of the frozen YAML candidate. The fix only pins validation YAML checkout line endings to LF in `.gitattributes`; no frozen candidate bytes, expected fingerprint, detector rule, release gate, protocol, or locked decision changed.

## Browser QA and deployment

Live URL: https://propwar.streamlit.app/

Home, Teams, Players, Games, Reports, and Explorer were directly loaded locally and live. The separated Research Admin route was also checked locally. Desktop and 390-by-844 mobile screenshots were captured outside the repository at:

`C:\Users\tucka\.codex\visualizations\2026\07\14\propwar-role-research-2025`

The final live hard reload showed the expected home heading, 2025 as the latest completed season, the 2026-not-started statement, and no Streamlit exception. Local interaction QA changed team and week selectors, switched the report type, and enabled the Explorer two-minute filter.

## Limitations

- The public data is descriptive historical research; it does not validate a detector or establish predictive value.
- The 89.071% receiver-assignment rate is calculated over all valid pass attempts, including sacks, throwaways, and unassigned incompletions. It is not an identity-join rate; targeted opportunity-to-identity coverage is 100%.
- Streamlit Community Cloud displays its own fixed mobile footer/banner, which can overlay the bottom edge of a viewport; application content remains vertically scrollable.
