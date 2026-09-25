# Margin Engine Validation Status

**Status:** Ready for a free/public alpha with caveats. Not ready for a paid performance claim.

**Model freeze:** 2026 Week 4+ expected-points policy is frozen in `validation/margin_model_freeze_2026.json`.

## What is validated

- One-use team allocation and route invariants pass existing engine tests.
- Championship simulation is deterministic and fail-closed when pool state is incomplete.
- Walk-forward replay uses only calibration outcomes strictly before the target week.
- `current_week_only` prevents future target-season spread lines from becoming model inputs.
- A mutation test changes all future scores and spreads after a target week and confirms the recommendation/board do not change.
- The canceled 2022 BUF-CIN game is treated as no Week 17 game, not a synthetic normal game.

## Retrospective realized Margin

Using the frozen default policy against a largest-available-favorite baseline over 2009-2025:

- Optimizer wins: **11 of 17 seasons**
- Baseline wins: **6 of 17 seasons**
- Mean realized advantage: **+10.35 Margin points/season**
- Median realized advantage: **+23.0**
- Bootstrap 95% interval for mean: approximately **-8.06 to +27.47**

This is promising but statistically inconclusive. Realized game margin is noisy and should not be presented as the model's structural expected edge.

## Structural allocation checks

Two less noisy evaluations were added to separate planning value from game-result luck.

### Eventual market-spread allocation

Score each strategy by the spread attached to the team in the week it was ultimately used:

- Mean optimizer advantage: **+2.21 spread points/season**
- Median: **+1.0**
- Seasons positive/tied/negative: **10 / 1 / 6**
- Bootstrap 95% interval: approximately **-0.12 to +4.53**

### Historical spread-conditioned expected Margin

Calibrate expected Margin from outcomes available strictly before each target week:

- Mean optimizer advantage: **+1.98 expected Margin points/season**
- Median: **+0.91**
- Seasons positive/negative: **10 / 7**
- Bootstrap 95% interval: approximately **-0.39 to +4.35**

These checks suggest a modest planning benefit may exist, but they do not support advertising a large guaranteed optimizer edge.

## Data and methodology caveats

- Historical `nflverse/nfldata` regular-season rows from 2009-2025 had zero duplicate game IDs and no missing stored spread, total, or score fields in this audit.
- Historical `spread_line` is not a timestamped pick-deadline snapshot. It is suitable for equal-source retrospective comparison, but publication-grade point-in-time claims need archived odds snapshots or explicit approximation language.
- The current 32-week / 8-half-life / cap-3 / +0.5 policy was already described as validated in the Aug. 23, 2026 repository history. The retained checkout does not prove those values were selected without viewing historical outcomes. Therefore 2009-2025 is retrospective validation, not a pristine untouched holdout.
- The first clean prospective test begins with 2026 Week 4 after the model freeze.

## Product interpretation

The current engine should be marketed as a **Margin planning and decision tool**, not a guaranteed winning system.

Appropriate claims include:

- considers current market strength and future team value;
- builds a one-use remaining-season route;
- shows the opportunity cost of using a team now;
- helps compare reasonable alternatives.

Do not claim a historical +18, +20, or +40 point structural advantage. Large realized-score differences are materially influenced by game-result variance.

## Prospective 2026 protocol

Beginning Week 4:

1. Freeze the expected-points policy. No midseason tuning from outcomes.
2. Capture a source/state SHA and market snapshot before the relevant pick lock.
3. Record the greedy anchor, expected-points pick, model board, future-cost values and provisional route.
4. Track threshold-0 and threshold-1 only as predeclared shadow challengers.
5. Append actual final Margin after games complete without altering the original snapshot.
6. Evaluate expected-points performance separately from the Week-10+ championship layer.

`scripts/snapshot_margin_prospective.py` is intentionally read-only with respect to PDL state and refuses to run when frozen source hashes drift or when current-week market data is incomplete.

## Decision gate

**Continue product development:** Yes.

**Reason:** the engine provides real planning functionality and retrospective evidence is promising enough to justify user testing, while the product can create value through hosting, state tracking, UX and league context even if the pure expected-points edge remains modest.

**Do not base monetization on model superiority yet.** Prospective 2026 evidence and real user retention are the next gates.
