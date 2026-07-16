# Phase B3 Supplemental Gap Matrix

- Existing B3 commit audited: `b0ba36213ca7c5c45938e1146f8fdc9a5dd2cc35`
- Audit rule: preserve working B3 behavior and implement only confirmed workflow gaps.

| ID | Requirement | Classification | Evidence and decision |
|---|---|---|---|
| A1 | Newest relevant season is the normal default | **Already satisfied** | available_seasons() begins with 2025; all normal selectors use the descending source order or an explicit 2025 current default. |
| A2 | Latest completed week is the active-season default | **Already satisfied** | No active-season partition exists in the committed source. Games defaults to Week 18; Home intentionally defaults to Week 17 for the completed 2025 season and keeps Week 18 directly selectable with its existing caution. |
| A3 | Latest game, Last 2, Last 4, and Season are prominent | **Already satisfied** | Player displays Season, Last 8, Last 4, and Last 2 at the top; Games defaults to the latest available week and Player weekly counts retain the latest game. |
| A4 | Recent comparisons do not cross seasons | **Already satisfied** | Player, Team, Report, Game, and Home calculations filter one selected season before building windows or baselines. |
| B1 | Older seasons are secondary but accessible | **Already satisfied** | 2018–2024 appear only inside season selectors; current findings occupy the default page and direct historical query links remain accepted. |
| C1 | Compact Player Role Fingerprint | **Implemented narrowly** | RB contexts are early_down, passing_down, two_minute, red_zone, inside_5; target contexts add end_zone. The public helper returns at most six contexts and every displayed row retains player count, team denominator, and share. |
| C2 | No default individual-down data wall | **Already satisfied** | Player does not render individual first/second/third/fourth-down splits; only compact assignment contexts are shown. |
| D1 | Exact numeric down and distance remains in Advanced Research | **Blocked by unavailable trusted data** | The committed public event extract has no numeric down or yards-to-go columns. Advanced Research retains only the verified Early down, Passing down, and Short yardage flags. |
| D2 | Player down-and-distance expander | **Deferred intentionally** | Optional item not added: the required exact numeric source is unavailable, and duplicating the existing grouped Advanced Research flags would make Player harder to understand. |
| E1 | Home evidence-chain continuity | **Implemented narrowly** | Home-rendered evidence URLs now carry origin, focus player, and focus family. Supporting pages recover the exact verified Home headline; ordinary direct visits show no origin message. |
| F1 | Thirty-second usability at 390×844 | **Already satisfied** | All six routes passed the real-browser question-first audit with zero horizontal overflow and no table or methodology dependency. |
| F2 | Thirty-second usability at 1440×900 | **Already satisfied** | All six routes passed the real-browser question-first audit with zero horizontal overflow and no table or methodology dependency. |
| G1 | Trusted refresh timestamp | **Blocked by unavailable trusted data** | No committed extract contains a dataset refresh timestamp. File modification times and injury-report timestamps were rejected as substitutes. |
| G2 | Trusted latest completed week | **Implemented narrowly** | The header now displays 'Data through 2025 Week 18' from the latest season-week whose game_partition_complete flag is true for every game. |
| G3 | Trusted completed-game status | **Already satisfied** | The canonical source contains game_partition_complete; 16 of 16 Week 18 games pass after game-level aggregation. |
| P1 | Six Advanced Research presets are distinct | **Already satisfied** | 6 presets have 6 distinct filter signatures and retain visible active conditions plus Reset. |
| P2 | Third/fourth-and-short preset | **Deferred intentionally** | Short-yardage data already exists, but a seventh preset was not added because the six current presets are distinct and the optional addition does not materially improve the normal workflow. |
