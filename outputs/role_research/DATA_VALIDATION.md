# PropWar Role Research Data Validation

Status: **PASS**

- Canonical rows: 57,928
- Seasons: [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
- Duplicate canonical keys: 0
- Required missing cells: 0
- Identity coverage: 100.0%
- Confirmed partial rows in source: 173; excluded from public primary rows.
- Suspected partial rows in public primary data: 584; included and visible.
- 2025 played games/weeks: 272 games across Weeks 1–18.
- 2025 opportunity/participation identity coverage: 100.000% / 99.961%.
- 2025 injury PBP identity resolution: 97.062%; injury report timestamps available: False.
- Situational source seasons physically opened: [2023, 2024, 2025]
- Seasons admitted to situational outputs: [2023, 2024, 2025]

| Check | Passed | Observed | Expected |
|---|---:|---|---|
| canonical_seasons | True | `[2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]` | `[2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]` |
| latest_completed_season | True | `2025` | `2025` |
| canonical_duplicate_keys | True | `0` | `0` |
| canonical_required_missing_cells | True | `0` | `0` |
| canonical_identity_coverage | True | `1.0` | `1.0` |
| confirmed_partial_excluded | True | `0` | `0` |
| suspected_partial_visible | True | `584` | `> 0` |
| situational_seasons | True | `[2023, 2024, 2025]` | `[2023, 2024, 2025]` |
| production_seasons | True | `[2023, 2024, 2025]` | `[2023, 2024, 2025]` |
| event_seasons | True | `[2023, 2024, 2025]` | `[2023, 2024, 2025]` |
| situational_share_range | True | `[0.0175438596491228, 1.0]` | `[0, 1]` |
| situational_numerator_le_denominator | True | `0` | `0` |
| situational_unique_grain | True | `0` | `0` |
| event_unique_grain | True | `0` | `0` |
| production_unique_grain | True | `0` | `0` |
| canonical_2025_rows | True | `7413` | `7413` |
| canonical_2025_games | True | `272` | `272` |
| canonical_2025_weeks | True | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]` | `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]` |
| 2025_opportunity_join_coverage | True | `1.0` | `1.0` |
| 2025_participation_join_coverage | True | `0.999606531575841` | `>= 0.999` |
| 2025_participation_play_coverage | True | `1.0` | `1.0` |
| 2025_confirmed_partial_evidence_policy | True | `['EXPLICIT_PBP_INJURY_NO_OFFENSIVE_RETURN_AND_ROLE_DROP']` | `['EXPLICIT_PBP_INJURY_NO_OFFENSIVE_RETURN_AND_ROLE_DROP']` |
| 2025_suspected_partial_visible | True | `52` | `52` |
| 2025_no_detector_or_betting_columns | True | `[]` | `[]` |
| 2025_temporal_and_season_boundary | True | `True` | `True` |
| all_play_canonical_reconciliation | True | `{'context': 'all_play', 'matched_rows': 17469, 'raw_absolute_difference': 0.0, 'denominator_absolute_difference': 0.0}` | `zero absolute count difference` |
| normal_game_canonical_reconciliation | True | `{'context': 'normal_game', 'matched_rows': 16873, 'raw_absolute_difference': 0.0, 'denominator_absolute_difference': 0.0}` | `zero absolute count difference` |
| manifest_situational_sha256 | True | `aec6cd6a11ef36b35bc18ab3468ff6b561951164e75b13b845d5b6d220c88a5c` | `aec6cd6a11ef36b35bc18ab3468ff6b561951164e75b13b845d5b6d220c88a5c` |
| manifest_production_sha256 | True | `45f2a601ebe02118c12f93e16dc312a06dacfc8ab8d7f59fec5f64aeb8f06ab2` | `45f2a601ebe02118c12f93e16dc312a06dacfc8ab8d7f59fec5f64aeb8f06ab2` |
| manifest_opportunity_events_sha256 | True | `9c67605493993ae74191f5ddd865a519afb431caac3611b92e083c90bbbf42d5` | `9c67605493993ae74191f5ddd865a519afb431caac3611b92e083c90bbbf42d5` |
| public_language_guardrail | True | `[]` | `[]` |
