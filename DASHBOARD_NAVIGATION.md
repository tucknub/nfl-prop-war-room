# Dashboard Navigation

The NFL Prop War Room dashboard is organized around a signal-first workflow. The app remains `HISTORICAL TEST ONLY` until readiness gates pass.

## Main Signal Workflow

Use these first:

1. Signal Command Center
2. Slate Signal Board
3. By-Game Matchup Board
4. Receiving Signal Board
5. Rushing Signal Board
6. Passing Signal Board
7. Player Signal Drilldown
8. Blocked / Review Board

These pages focus on players, games, recent form, defense fit, game environment, role/injury/readiness, and explainability.

## Research / Audit Lab

Use these to validate the signal system:

- Signal Score Audit
- Historical Signal Backtest
- Signal Weight Tuning Lab
- Champion vs Challenger Signal Preview

These pages compare formulas, audit components, review historical behavior, and inspect challenger profiles. They do not promote challenger weights automatically.

## Readiness / Data Admin

Use these for safety and data quality:

- Live Readiness
- Live Data Intake
- Current Roster / Team Mapping
- Role / Depth Chart Mapping
- Injury / Availability Mapping
- Market Data Mapping
- End-to-End Dry Run
- Gate Status
- Identity Warnings
- Run Reports

These pages explain why Final Readiness remains `NO-GO` and which data gates still need real non-template inputs.

## Legacy Model Outputs

Model output pages remain available for debugging and review, but they are secondary to the signal workflow. Use them when you need to inspect a specific market export or line ladder.

## What To Open First

Start at `Signal Command Center`, then move into the slate, game, family, and player drilldown pages. Treat admin and research pages as validation/support tools, not the main product surface.

Odds and CLV are not the current product focus. The dashboard is a research signal command center until live readiness becomes `GO`.

## Signal UX Polish

The signal workflow uses a Kasper-style scan pattern:

- Top KPI cards summarize the slate.
- Top-player cards call out the best signals.
- Tables use green-to-red heatmap cells for scores.
- Tier/action/reliability badges make status easy to scan.
- By-game summaries help compare both sides before drilling into player details.

Color meaning:

- Dark green = elite
- Green = strong
- Yellow = watch
- Orange = review/risk
- Red = blocked/weak
- Gray = missing/unavailable
