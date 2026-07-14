# Fold 4 precheck correction note

The first real-data precheck under execution-package commit
`12cdb1bf34352392b6fba5a40c7cec82d532f4bc` stopped before alert generation.

- Failure: `KeyError: 'season'` while selecting the cached participation source.
- Cause: participation stores season in `nflverse_game_id`; the new audit loader
  filtered it correctly but then incorrectly required a physical `season` column.
- Detector outputs created: none.
- Outcome metrics, gates, or 2024 recommendations visible: none.
- Fold 4 execution lock created: no.
- Machine-readable record: `precheck_failure.json`.

The confirmed schema-normalization bug was corrected without changing detector
rules, thresholds, opportunity floors, baselines, confirmation, repeat suppression,
partial-game policy, scoring, outcomes, or release gates. The correction added the
derived `season` column to the already-filtered participation rows and a regression
test covering 2023-2025 physical-file access with 2024-only admission.

Correction commits:

- `5287232d03d918b3f8bdcd02e15ea4bac37588c0` - normalize season from
  `nflverse_game_id` and add the regression test.
- `6446d4ef7fa554e20978c90fda6ddefbedafc4fa` - make the audit trail explicitly
  distinguish first file access from result access.

The corrected execution package was frozen before any 2024 alert, outcome, metric,
or gate result was calculated. The successful audit then authorized one and only one
Fold 4 execution. The final frozen manifest preserves both the original package and
the invalidated precheck record.
