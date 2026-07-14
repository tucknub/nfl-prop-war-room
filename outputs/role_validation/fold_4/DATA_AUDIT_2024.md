# Fold 4 - 2024 Data Audit

## Dataset and grain

- Grain: one row per season-week-player-team-role family.
- Played games/weeks: 272/18.
- Canonical rows: 7,390; unique players: 544.
- Duplicate canonical keys: 0 (0.0%).
- Required-field missingness: 0 cells across 0 rows.
- Identity coverage: 100.0%; quality-pass rate: 100.0%; qualifying rate: 100.0%.

## Source and join coverage

- Participation play coverage: 100.0%.
- Carry player identity coverage: 100.0%.
- Target player identity coverage across pass attempts: 89.3%; canonical target opportunities require a resolved receiver.
- PBP/schedule games: 272/272.
- Opportunity and participation joins: 41,393/41,393; every recorded join rate is 100.0% or better.
- Injury mentions resolved: 817/849 (96.2%).
- Confirmed partial-game family rows: 18; suspected rows: 73.

## Integrity judgment

All 8 audit checks and all 6 pre-run temporal checks passed. The canonical grain, hashes, source completeness, identity/opportunity joins, season boundary, and evidence timing authorized the single Fold 4 execution. The full missingness profile is preserved in `missingness_2024.csv`.

## File-access boundary

- `source_seasons_physically_available`: `[2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]`
- `source_seasons_physically_opened`: `[2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]`
- `seasons_admitted_to_feature_generation`: `[2024]`
- `seasons_admitted_to_alert_selection`: `[2024]`
- `seasons_admitted_to_outcome_evaluation`: `[2024]`

Multi-season local files were physically opened and scanned. Only 2024 rows were admitted to feature generation, exclusions, alert selection, and outcome evaluation. No 2025 value was admitted.
