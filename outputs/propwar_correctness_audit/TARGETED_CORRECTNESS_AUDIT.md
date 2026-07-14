# Targeted Correctness Audit

**Phase status: FAILED**

**Production status: UNCHANGED**
**Baseline commit:** `8b759f18c34708300acf5e3ef84d0e4cbbbde597`

## Overall correctness judgment

Player windows and ordinary ownership shares reconcile. Phase A fails because High issues remain in Home current-week eligibility, situational team denominators, Explorer zero-opportunity denominators, Report context filtering, and invalid URL handling.

## Coverage

- Players: 10 RB, 10 WR, 10 TE, plus traded and suspected-partial samples.
- Teams: 10 teams across all four role families.
- Games: 10 games, including the requested edge categories when present in 2025 source schedules.
- Home: top 25 displayed rows.
- Reports: all 7 reports.
- Explorer: 18 filter combinations.

## Findings

### High — HOME_STALE_WEEK_ROWS

- **Affected page:** Home
- **Evidence:** 6 of the displayed top 25 rows use a player week earlier than selected Week 18.
- **User impact:** The Week 18 discovery feed mixes stale changes from earlier weeks into the ranking.
- **Likely cause:** observable_changes takes each player-team-family's latest row at or before the selected week without requiring equality.
- **Proposed fix:** Require current.week == selected week before ranking.
- **Production must remain blocked:** Yes

### High — EXPLORER_ZERO_GAMES

- **Affected page:** Explorer
- **Evidence:** 791 player/case reconciliations fail against zero-inclusive eligible-game denominators.
- **User impact:** Shares can be inflated and game samples understated when a qualifying player records zero selected opportunities.
- **Likely cause:** Player-week rows are created from numerator events only.
- **Proposed fix:** Start from eligible player-game rows and left join numerator counts, filling zero.
- **Production must remain blocked:** Yes

### High — SITUATIONAL_ZERO_FAMILY_GAMES

- **Affected page:** Teams / Reports
- **Evidence:** 71 displayed situational shares disagree with complete same-context team-event denominators.
- **User impact:** Situational shares can be inflated when a team has context opportunities but no opportunity credited to the selected position family in that game.
- **Likely cause:** The situational extract has no family row for a zero-family-numerator game, so that game's team denominator disappears when weeks are summed.
- **Proposed fix:** Build situational denominators from the full eligible team-game-context spine before joining family/player numerators.
- **Production must remain blocked:** Yes

### High — REPORT_CONTEXT_IGNORED

- **Affected page:** Reports
- **Evidence:** 3 situational reports return identical Normal game and All plays results.
- **User impact:** The visible context filter does not describe the calculation for situational reports.
- **Likely cause:** league_situational_summary is called without intersecting the selected normal-game context.
- **Proposed fix:** Apply the selected all-play/normal-game filter to situational source rows or disable and relabel the control.
- **Production must remain blocked:** Yes

### High — INVALID_URL_FALLBACK

- **Affected page:** Players / Teams
- **Evidence:** Invalid player queries silently select the first player; Teams ignores team query parameters.
- **User impact:** A malformed or stale link can show a valid but wrong entity without warning.
- **Likely cause:** Query values are used only when present in current options; no invalid-state branch exists, and Teams has no query parsing.
- **Proposed fix:** Add explicit invalid-entity states and a documented team URL contract.
- **Production must remain blocked:** Yes

### Medium — TRADED_SELECTOR_TEAM

- **Affected page:** Players
- **Evidence:** 5 sampled multi-team players have a selector team that differs from the latest team.
- **User impact:** The selector can name the former team while the selected profile summary names the current team.
- **Likely cause:** drop_duplicates(player_id) keeps the first season row for selector labels.
- **Proposed fix:** Use latest-week identity for selector labels and retain week-level team attribution in logs.
- **Production must remain blocked:** No

### Medium — MISSING_TEAM_LINKS

- **Affected page:** Home
- **Evidence:** Home displays team text but renders no team link; Teams has no query-parameter URL contract.
- **User impact:** Requested cross-page team navigation cannot be validated or used.
- **Likely cause:** Only player hrefs are implemented.
- **Proposed fix:** Add documented team deep links in a later authorized correctness-fix phase.
- **Production must remain blocked:** No

### Medium — GAME_FIELDS_UNAVAILABLE

- **Affected page:** Games
- **Evidence:** Source schedules contain scores, and situational data contains inside-five counts, but the page does not display them; one-play production share is not implemented.
- **User impact:** Several requested game facts cannot be checked in the public box score.
- **Likely cause:** The committed public game view intentionally omits schedule scores and several advanced fields.
- **Proposed fix:** Backlog the missing factual fields without changing definitions during Phase A.
- **Production must remain blocked:** No

### Low — EMPTY_CHART_WARNINGS

- **Affected page:** Players
- **Evidence:** Live browser QA recorded no console errors but repeated Vega infinite-extent warnings for empty chart series.
- **User impact:** No incorrect value was observed, but empty or sparse chart states generate noisy diagnostics and may render inconsistently.
- **Likely cause:** An empty series is still passed to the chart scale without an explicit empty-state branch.
- **Proposed fix:** Add an explicit no-series chart state in a later authorized correctness-fix phase.
- **Production must remain blocked:** No

## Calculation results

- Player window checks: 392 passed, 0 failed. Season, Last 8, Last 4, and Last 2 use summed player and same-context team counts over qualifying games.
- Team role-ownership checks: 240 passed, 0 failed.
- Team situational checks: 311 passed, 71 failed. Every failure is preserved in `calculation_discrepancies.csv` with source play IDs, numerator, denominator, expected share, displayed share, and difference.
- The 25.0% versus 8.3% descending sort regression passes using numeric values with nulls last.
- Canonical duplicate keys: 0. Week range: 1–18 only. Confirmed partial rows are absent from the public primary set; suspected rows remain visible.

## Home results

- Top 25 audited: 19 pass selected-week eligibility and 6 fail.
- Stale rows: Alvin Kamara (NO, rb_opportunity_share, Week 12); Bam Knight (ARI, rb_opportunity_share, Week 15); Alvin Kamara (NO, rb_carry_share, Week 12); Quinshon Judkins (CLE, rb_carry_share, Week 16); Bam Knight (ARI, rb_carry_share, Week 15); Omarion Hampton (LAC, rb_opportunity_share, Week 17).
- All audited baselines remain within 2025 and strictly precede each row's triggering player week; no future-game leakage was found.
- Baseline and recent numerators, denominators, shares, sample sizes, ranks, and link targets are archived in `home_validation.csv`.

## Player and Team results

- Player weekly rows audited: 791; all displayed all-play and normal-game shares equal their row numerator divided by denominator, and no Week 0 exists.
- Multi-team selector mismatches: 5 sampled players. Live Tank Bigsby evidence showed PHI in the summary but JAX in the selector label.
- Independent team-role ranks match the displayed rank calculation on 791 of 791 archived player-week evidence rows.
- Ordinary Team ownership values agree with Reports under identical season, window, role-family, and context filters.
- Team quality checks: 0 duplicate keys, 0 shares above 100%, 0 non-positive denominators, and 0 inconsistent team-game-family denominators.
- Situational same-context discrepancies: 71; these occur when a zero-family-numerator game drops its team denominator.

## Game results

- Games audited: 10; required categories present: blowout, confirmed_partial, overtime, suspected_partial, traded_player, week_18.
- Player production rows reconciled to weekly source: 212 of 212.
- Matchup, score, overtime, carries, targets, receptions, team grouping, partial-game categories, and source reconciliation are in `game_validation.csv`.
- The public page does not display score, inside-five counts, or one-play production share, so those requested display checks are recorded as unavailable rather than inferred.

## Report results

- All seven reports were executed for 2025 Last 4 with their default minimum sample.
- Context-sensitive ordinary reports: 4 pass; situational reports ignoring the visible Normal game / All plays selector: 3.
- Report definitions, row counts, numeric-sort status, and label assessments are in `report_validation.csv`.

## Explorer results

- Filter cases: 18; row-level comparisons: 1254; failures: 791.
- Failures retain matching player numerators but show understated team denominators and sample games when the player had zero selected opportunities in an otherwise eligible game.
- Live Reset testing restored 2025, All teams, All players, RB carry share, Weeks 1–18, all context filters, Normal game, and minimum sample 5.

## Cross-page and link/state results

- Identical-filter cross-page comparisons: 111; failures: 0.
- Link/state checks: 20; recorded failures: 7. Static and live duplicate observations are intentionally retained as separate evidence rows.
- Valid player URLs, Explorer Reset, back/forward, and public navigation pass. Invalid player URLs and team query URLs fail safely identifiable behavior; Home has no team deep links.

## Edge cases and public language

- Covered traded and multi-team players, bye weeks, Week 18, overtime, blowout, confirmed partial, suspected partial, tiny samples, zero denominators, missing recent windows, and absence of fabricated 2026 usage.
- Public-language matches reviewed: 12; prohibited analytical uses: 0.
- Late-season outcome censoring is not applicable to these descriptive displays because the audit evaluates no future outcome metric.

## Result summary

- Calculation checks: 1014 rows; 71 failures.
- Home rows failing selected-week eligibility: 6.
- Cross-page checks: 111 rows; 0 failures.
- Explorer checks: 1254 rows; 791 failures.
- Findings: 0 Critical, 5 High, 3 Medium, 1 Low.

## Acceptance gate

Phase A is **FAILED**. No production change is authorized. The next authorized action is to wait for the user's screen-recording review.

## Reproducibility

Run `python scripts/run_targeted_correctness_audit.py`, execute the audit notebook, then run the independent validators listed in `COMMANDS_RUN.md`.
