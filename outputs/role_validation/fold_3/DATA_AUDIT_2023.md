# Fold 3 — 2023 Data Audit

- Grain: one row per season-week-player-team-role family.
- Canonical rows: 7,448; unique players: 531; played games: 272; observed weeks: 18.
- Duplicate canonical keys: 0; required-field null cells: 0.
- Identity, quality, and qualifying coverage: 100.0%, 100.0%, 100.0%.
- PBP/schedule games: 272/272; participation coverage: 100.0%; carry-ID coverage: 100.0%.
- Target-player ID population across pass attempts: 88.9%; target opportunities require a resolved receiver before entering the numerator or denominator.
- Opportunity and participation identity joins: 41,792/41,792.
- Explicit injury mentions resolved: 911/949 (96.0%).
- Confirmed partial family rows excluded from primary: 17; suspected rows retained: 68.
- All trigger timestamps are present. The 32 missing next-game boundaries are the final regular-season team game, as expected.
- Audit judgment: no critical or high-severity blocker; the controlled 2023 evaluation was permitted to proceed.
