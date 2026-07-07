# Signal Score Definitions

Signal scores are transparent, conservative, and limited to sourced data. V1 is a foundation layer, not a betting recommendation system.

## Principles

- Do not double-count correlated inputs.
- Group related inputs into score families.
- Missing data reduces data quality and creates visible review context.
- Opponent fit, game script, weather, practice trend, and detailed defense context are planned first-class signals but are not faked.
- DefenseFit is low reliability until real opponent and defensive context data exists.

## Score Families

- `ProjectionScore`: available in V1 from existing projection outputs. It uses percentile rank inside each available projection family.
- `UsageFoundationScore`: partial/support-only in V1. It uses grouped market support rather than counting every correlated projection separately.
- `RecentFormScore`: `NOT_AVAILABLE` unless real recent-form columns are present.
- `OpponentFitScore`: `NOT_AVAILABLE` until opponent/defense data is sourced.
- `GameScriptScore`: `NOT_AVAILABLE` until spread/total/schedule context is sourced.
- `WeatherScore`: `NOT_AVAILABLE` until weather data is sourced.
- `RoleAvailabilityScore`: gate-backed but production currently `NEEDS DATA`, so live context cannot be green.
- `VolatilityScore`: available only from existing quality/confidence fields in V1.
- `DataQualityScore`: available in V1 and penalizes missing IDs, missing context, unavailable signal families, and missing live context.
- `OverallSignalScore`: limited V1 composite from available score families only.

## V1 Limits

`OverallSignalScore` is capped by missing live and matchup context. A player should not become `ELITE_SIGNAL` simply because a projection is high while opponent fit, game script, weather, and live role/injury context are missing.
