# Desktop QA — 1440×900

## Result

PASS. The calibrated Home report was exercised at exactly 1440×900 and through the connected Codex Browser.

- `window.innerWidth`: 1440
- `document.documentElement.scrollWidth`: 1440
- Horizontal overflow: 0 px
- Clipped `.pw-report-card` elements: 0
- Default Week 17 cards: 12
- Expanded reciprocal evidence: operable and readable
- Home console errors: 0
- Player evidence link state: Tank Bigsby opened as `Tank Bigsby · PHI · RB`; the searchable selector also displayed PHI
- Supporting routes: Teams, Players, Games, Reports, and Explorer loaded without an exception

The supporting-route smoke test reproduced only the previously documented low-severity sparse Vega infinite-extent warnings. No new Home error or correctness regression was observed.

## Evidence

- `screenshots/desktop_home_week17.png`
- `screenshots/desktop_home_week8_minnesota.png`

Both images were generated after the final code edit. The Week 17 image was inspected at original resolution.
