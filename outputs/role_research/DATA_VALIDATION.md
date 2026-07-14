# PropWar Role Research Data Validation

Status: **PASS**

- Canonical rows: 50,515
- Seasons: [2018, 2019, 2020, 2021, 2022, 2023, 2024]
- Duplicate canonical keys: 0
- Required missing cells: 0
- Identity coverage: 100.0%
- Confirmed partial rows in source: 150; excluded from public primary rows.
- Suspected partial rows in public primary data: 532; included and visible.
- Situational source seasons physically opened: [2023, 2024, 2025]
- Seasons admitted to situational outputs: [2023, 2024]

| Check | Passed | Observed | Expected |
|---|---:|---|---|
| canonical_seasons | True | `[2018, 2019, 2020, 2021, 2022, 2023, 2024]` | `[2018, 2019, 2020, 2021, 2022, 2023, 2024]` |
| latest_completed_season | True | `2024` | `2024` |
| canonical_duplicate_keys | True | `0` | `0` |
| canonical_required_missing_cells | True | `0` | `0` |
| canonical_identity_coverage | True | `1.0` | `1.0` |
| confirmed_partial_excluded | True | `0` | `0` |
| suspected_partial_visible | True | `532` | `> 0` |
| situational_seasons | True | `[2023, 2024]` | `[2023, 2024]` |
| production_seasons | True | `[2023, 2024]` | `[2023, 2024]` |
| event_seasons | True | `[2023, 2024]` | `[2023, 2024]` |
| situational_share_range | True | `[0.0175438596491228, 1.0]` | `[0, 1]` |
| situational_numerator_le_denominator | True | `0` | `0` |
| situational_unique_grain | True | `0` | `0` |
| event_unique_grain | True | `0` | `0` |
| production_unique_grain | True | `0` | `0` |
| all_play_canonical_reconciliation | True | `{'context': 'all_play', 'matched_rows': 11656, 'raw_absolute_difference': 0.0, 'denominator_absolute_difference': 0.0}` | `zero absolute count difference` |
| normal_game_canonical_reconciliation | True | `{'context': 'normal_game', 'matched_rows': 11258, 'raw_absolute_difference': 0.0, 'denominator_absolute_difference': 0.0}` | `zero absolute count difference` |
| manifest_situational_sha256 | True | `0ecac748315050306046af7a0d7d805999dc682f73658d407923ed6fb1d3723c` | `0ecac748315050306046af7a0d7d805999dc682f73658d407923ed6fb1d3723c` |
| manifest_production_sha256 | True | `1dfcacd983e07faf8dd459138aae61d07d257c55d890119a183a8a1678a31394` | `1dfcacd983e07faf8dd459138aae61d07d257c55d890119a183a8a1678a31394` |
| manifest_opportunity_events_sha256 | True | `2f81a6e615944ff0c06818d9deccef67a614bc696a1a0f67bfd342d2186c80fc` | `2f81a6e615944ff0c06818d9deccef67a614bc696a1a0f67bfd342d2186c80fc` |
| public_language_guardrail | True | `[]` | `[]` |
