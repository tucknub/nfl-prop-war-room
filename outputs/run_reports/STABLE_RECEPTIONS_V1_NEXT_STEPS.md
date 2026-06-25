# Stable Receptions V1 Next Steps

## Safe Now

- Run `python -m src.run_receptions_pipeline`.
- Run `python -m src.validate_receptions_safety`.
- Run `python -m src.validate_forward_projection_dry_run`.
- Import the local Google Sheets import pack for historical-test/control-room review.
- Review historical-test projections, calibration, backtest, line ladder, gate blockers, and identity reports.
- Use the line ladder for odds-free research and future market-matching preparation only.

## Needed Before 2026 Live Projection

- Obtain real 2026 target-week schedule data.
- Load real 2026 roster/current-team data.
- Load role data with current player role, starter status, route/snap context, and confidence.
- Load injury and availability data.
- Validate all roster, role, and injury rows through the identity resolver.
- Resolve all `UNMATCHED_PLAYER`, `DUPLICATE_PLAYER_NAME`, and `TEAM_VERIFY` rows.
- Switch `projection_mode` to `forward_projection` only after gate data exists and validates.
- Confirm leakage remains `PASS` after changing target season/week.

## Needed Before Betting-Edge Mode

- Load real sportsbook receptions lines and American odds.
- Confirm market odds rows match by player identity, team, prop market, and line.
- Confirm Market Odds Gate is `READY`.
- Confirm final live readiness is `GO`.
- Confirm no live betting output is created while readiness is `NO-GO`.
- Confirm outputs do not remain labeled `HISTORICAL TEST ONLY` before treating them as live.

## Optional Future Improvements

- Add real route participation feeds to replace `ROUTE_PROXY_UNVALIDATED` estimates.
- Add sportsbook-specific line matching and stale-odds checks.
- Add richer QB/team context and matchup features after Receptions V1 is stable.
- Add dashboard visualizations for calibration and probability ladders.
- Add automated comparison between model probabilities and loaded market odds once odds are real.

## Do Not Do Yet

- Do not fabricate 2026 schedule, roster, injury, role, or odds data.
- Do not treat the historical-test board as a live 2026 projection.
- Do not treat line ladder probabilities as betting recommendations.
- Do not create live betting output while final readiness is `NO-GO`.
- Do not bypass the identity resolver for duplicate names or stale team checks.
- Do not add TD, rushing, receiving yards, QB rush, or passing yards markets before Receptions V1 is proven with real gates.
