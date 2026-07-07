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
