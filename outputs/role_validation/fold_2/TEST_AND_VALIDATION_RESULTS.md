# Fold 2 Test and Validation Results

## Verified before evaluation

- Frozen configuration SHA-256 matched the precommitted fingerprint and frozen Fold 1 report.
- Pre-Fold-2 tag resolved to `bdff056fa625eef76152e1b9f3ef0e88fda2bbab`.
- Protected protocol, locked-decision, and release-gate hashes matched the frozen configuration.
- 2022 canonical grain: 7,478 rows, zero duplicate keys, zero required-field nulls.
- Identity, quality-pass, and qualifying coverage: 100%.
- Targeted temporal, partial-game, and equal-volume tests: 16 passed.
- Precheck manifest passed before outcomes were calculated.

## Verified after the single execution

- Execution lock completed and alert archive SHA-256 recorded.
- Only season 2022 appears in Fold 2 canonical and alert archives.
- All 216 family-week-policy cells contain all four methods at exactly equal volume.
- Baselines end before confirmation; confirmation ends on the alert week; both outcome weeks are strictly later.
- Confirmed partial games are excluded from primary; suspected cases remain included.
- Notebook executed top-to-bottom without error.
- Full test suite: 22 passed in 3.66 seconds.
- Independent output validator: PASS, 60 checks before staging.
- No family was reinterpreted as passing after a failed locked gate.

## Final staged-scope validation

Completed immediately before commit:

```powershell
git diff --cached --check
python scripts/validate_fold2_outputs.py --require-staged-scope
```

Results:

- `git diff --cached --check`: clean.
- Independent staged-scope validator: PASS, 64 checks.
- Frozen candidate YAML, locked protocol/decisions, release gates, and dashboard paths: not staged.

## Non-blocking environment notes

- `nbconvert` emitted the standard Windows ZeroMQ selector-thread and unencrypted local-kernel warnings. Execution completed successfully.
- `tabulate` was unavailable; the report generator uses an internal dependency-free Markdown table renderer.
