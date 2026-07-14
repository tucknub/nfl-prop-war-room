# PropWar Role Research UI v1

## Branch scope

This UI branch starts from the completed Fold 4 artifact commit
`f3e4a9d5349215af1ee1b1204511dcc377dc7e2e` and does not change the detector,
protocol, locked decisions, release gates, or Fold artifacts.

The source worktree contained 57 pre-existing modified dashboard, export, Google
Sheets, and run-report files. Those modifications remain in the original
`role-change-validation-v1` worktree and were not copied or staged here. The UI
work was isolated with a second Git worktree and a clean branch named
`propwar-role-research-ui-v1`.

## Public product boundary

The registered public navigation is Home, Teams, Players, Games, Reports, and
Explorer. It presents historical role and opportunity facts only. The former
score-board pages are not registered. Research outputs are isolated on the
non-default Research Admin page, labeled exactly:

`Experimental Shadow Research — Not Validated`

## Data sources

- Canonical audited player-week-team-role-family archives for 2018–2024.
- A compact 2023–2024 situational opportunity extract generated from the local
  play-by-play source using same-game denominators.
- A compact 2023–2024 game usage extract for carries, targets, receptions,
  rushing yards, receiving yards, and touchdowns.

The play-by-play storage file physically contained 2023, 2024, and 2025 rows.
The builder records that fact and admits only 2023–2024 rows to the committed
role-research outputs. No 2025 row enters the UI datasets.

## Metric policy

- Confirmed partial-game player rows are excluded.
- Suspected partial-game rows remain included and visible.
- All windows stay inside the selected season.
- Shares are calculated from summed player opportunities divided by matching
  same-team, same-game denominators.
- Team and league window denominators include every team game in the selected
  window, including games where a displayed player recorded zero opportunities.
- Down, clock, game-state, and field-zone filters are available only for
  2023–2024 and are labeled with that coverage.

## Reconciliation of pre-existing dashboard work

No pre-existing dirty file was reconciled into this branch because those edits
were not committed and their intent could not be safely attributed to this UI
reset. The new public pages were implemented from the clean Fold 4 checkpoint.
The original dirty worktree is preserved for separate review or cherry-picking.
