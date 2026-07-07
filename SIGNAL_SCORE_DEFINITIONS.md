# Signal Score Definitions

Signal scores are transparent, conservative, and limited to sourced data. V1 is a foundation layer, not a betting recommendation system.

## Principles

- Do not double-count correlated inputs.
- Group related inputs into score families.
- Missing data reduces data quality and creates visible review context.
- Recent form, opponent fit, and game script can be used only when exported by the context feature layer.
- Weather, practice trend, route share, first-read share, and detailed coverage context are planned first-class signals but are not faked.
- DefenseFit is reliability-adjusted and shrunk toward league average because defense-vs-position data is noisy.

## Score Families

- `ProjectionScore`: available in V1 from existing projection outputs. It uses percentile rank inside each available projection family.
- `UsageFoundationScore`: partial/support-only in V1. It uses grouped market support rather than counting every correlated projection separately.
- `RecentFormScore`: sourced in Context V1 from pre-target L3/L5/L8 weekly player form.
- `OpponentFitScore`: sourced in Context V1 from historical opponent allowed stats by position, reliability-adjusted with shrinkage.
- `GameScriptScore`: sourced in Context V1 from `schedules.csv` spread/total fields when present.
- `WeatherScore`: `NOT_AVAILABLE` until weather data is sourced.
- `RoleAvailabilityScore`: gate-backed but production currently `NEEDS DATA`, so live context cannot be green.
- `VolatilityScore`: available only from existing quality/confidence fields in V1.
- `DataQualityScore`: available in V1 and penalizes missing IDs, missing context, unavailable signal families, and missing live context.
- `OverallSignalScore`: conservative weighted blend from available sourced score families only.

## Context V1 Weights

- `ProjectionScore`: 35%
- `UsageFoundationScore`: 20%
- `RecentFormScore`: 15%
- `OpponentFitScore`: 10%
- `GameScriptScore`: 10%
- `RoleAvailabilityScore`: 5%
- `DataQualityScore`: 5%

If a score family is not sourced for a row, it is omitted from the denominator and data quality is reduced. This avoids painting missing data as neutral.

## V1 Limits

`ELITE_SIGNAL` requires a strong projection score, acceptable data quality, no major review/block reason, and at least one sourced context family from recent form, opponent fit, or game script. A player should not become elite simply because a projection is high while context is missing.

## Signal Score Audit V1

Signal Score Audit V1 checks whether the signal system is behaving logically. It audits:

- Score distributions by board family.
- Component correlations and possible double-counting risk.
- Per-player positive and negative score drivers.
- Plain-English explanations and signal-only recommended actions.

The audit does not prove profitability, does not use pricing/line movement logic, and does not change projection math or scoring weights. Outcome validation is generated only when a safe historical signal table with actual outcome columns exists. Until then, outcome validation is labeled `NEEDS HISTORICAL SIGNAL BACKTEST DATA`.

## Historical Signal Backtest V1

Historical Signal Backtest V1 creates historical player-week-market-family rows from shifted pregame features and evaluates actual outcomes afterward. It checks:

- Whether stronger tiers show lift versus baseline production.
- Whether higher score buckets generally produce stronger actual outcomes.
- Which score components have useful, weak, noisy, inverted, or low-sample relationships to actual outcomes.
- Which market family appears strongest historically.

This is a research audit only. It does not use actual outcomes to create pregame scores, does not use future rows in rolling features, and does not change production score weights.

## Signal Weight Tuning Lab V1

Signal Weight Tuning Lab V1 uses the historical backtest rows to compare `current_v1` weights against challenger profiles. The lab re-scores historical rows from existing pregame component scores only; it does not recalculate raw features and does not use actual outcomes to create pregame signals.

It evaluates profile and family combinations for correlation with actual outcomes, tier lift, top-versus-bottom separation, monotonicity, low-sample risk, and one-component dominance. It also uses component audit outputs to flag noisy, inverted, weak, or potentially double-counted components.

`current_v1` remains the champion profile. Any recommended YAML is a research-only challenger and is not applied to `player_week_signal_master.csv` unless explicitly promoted in a later change.

## Champion vs Challenger Signal Preview V1

Champion vs Challenger Signal Preview V1 applies the recommended challenger profile to copied production rows and writes separate research-only preview files. It preserves current production fields as `current_*` columns, writes challenger fields as `challenger_*` columns, and leaves the production master signal table on `current_v1`.

The preview can show rushing and passing challenger behavior, but it does not replace the main signal boards and does not promote weights. Promotion requires explicit approval after reviewing historical tuning results and preview board behavior.
