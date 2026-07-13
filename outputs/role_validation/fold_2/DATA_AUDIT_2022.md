# Fold 2 2022 Data Audit

- Grain: one row per season-week-player-team-role family.
- Rows: 7,478; unique players: 555; played games: 271; weeks: 18.
- Duplicate canonical keys: 0; required-field null cells: 0.
- Identity, data-quality, and qualifying coverage: 100%.
- PBP/schedule played-game coverage: 271/271; participation play coverage: 100.0%.
- Opportunity and participation identity joins: 41,719/41,719.
- Explicit injury mentions: 872; resolved: 831 (95.3%).
- Confirmed partial family rows excluded by primary: 19; suspected family rows included by primary: 93.
- Severity assessment: no critical/high blocker for the controlled 2022 evaluation. Receiver-ID coverage across all pass attempts is 89.6%, but target opportunities require a resolved receiver and the canonical target-share grain passes all required quality checks.
