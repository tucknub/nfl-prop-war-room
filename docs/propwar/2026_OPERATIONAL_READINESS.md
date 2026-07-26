# PropWar 2026 Operational Readiness

## Purpose

This runbook governs how current-season data reaches the public Backfield Control, Target Hierarchy, and Role Movement reports. It does not alter frozen historical validation files or detector rules.

## Required sources

A publishable current-season partition requires these nflverse/nflreadpy datasets for the selected season:

- play-by-play
- schedules
- weekly player statistics
- weekly rosters
- PFR offensive snap counts

Current-season participation data is not substituted or estimated because that source is released after the season. The discontinued current injury dataset is not used. A confirmed partial-game exclusion requires a reviewed row in `data/operations/partial_game_overrides.csv`.

## Completed-week gate

The pipeline admits only consecutive regular-season weeks starting with Week 1. Every scheduled game in an admitted week must have:

1. a final schedule result,
2. play-by-play rows,
3. fourth-quarter-or-later play-by-play,
4. at least 15 valid scrimmage plays for both teams.

An incomplete Monday game, delayed source partition, or missing team blocks that week and every later week from publication.

## Identity and snap-count gates

- Player IDs are authoritative.
- PFR-to-GSIS matching uses the weekly roster crosswalk first.
- Name fallback is allowed only when the normalized name is unique.
- Every completed game-team must have an offensive snap partition.
- Opportunity-player identity coverage must equal 100%.
- RB, WR, and TE snap identity coverage must be at least 99%; these are the public report positions.
- All-offense snap identity coverage is retained as a diagnostic and must remain at least 95% to catch catastrophic source or join failures.
- Opportunity-to-snap coverage must be at least 99.5%.

## Publication behavior

The pipeline builds into `outputs/role_research/.staging/<run-id>` and validates before copying files into the public output directory. A failed source, identity, snap, grain, range, or hash check leaves the last successful public partition unchanged.

Successful seasonal files use explicit names such as:

- `canonical_role_2026_live.csv.gz`
- `situational_player_week_2026_live.csv.gz`
- `game_player_usage_2026_live.csv.gz`
- `opportunity_events_2026_live.csv.gz`
- `role_research_manifest_2026.json`
- `role_research_validation_2026.json`
- `role_research_status_2026.json`

The dashboard discovers these partitions dynamically. It does not require a code release for each new season or week.

## Schedule

GitHub Actions runs at 13:30 UTC on Tuesdays and Thursdays during September–January.

- Tuesday follows the completed weekly slate.
- Thursday allows official corrections and revised source files to be incorporated.
- January resolves to the prior calendar year's NFL season.
- Manual dispatch supports an explicit season and optional maximum week.
- Manual dispatch also supports `dry_run`; it passes `--no-publish` and does
  not promote or commit a DepthSnap registry.
- Ordinary pull-request CI performs no live source refresh. Scheduled and
  non-dry manual operations are the authorized live-refresh paths.

## DepthSnap current-season bridge

After the existing pipeline writes its attempt status, the bridge applies the
same operational authority without changing methodology:

- `PUBLISHED` requires independent validation, then builds, validates, and
  atomically promotes the populated current-season registry;
- `PRESEASON` and `WAITING_FOR_COMPLETED_WEEK` promote the truthful
  `no_published_week` registry;
- `BLOCKED` retains a same-season prior valid registry, or builds
  `unavailable` from the supplied blocked metadata when none exists;
- `VALIDATED_NOT_PUBLISHED` never promotes;
- any identity, schema, hash, parity, loader, or validation failure retains
  the prior valid registry.

The bridge rejects seasons before 2026. A temporary 2025 parity registry is
never used as current evidence.

Apply one supplied state:

```bash
python scripts/publish_current_depthsnap.py \
  outputs/run_reports/role_research/role_research_attempt_2026.json
```

Rehearse failure, retention, rollback, later promotion, and cleanup without
touching the active registry:

```bash
python scripts/rehearse_depthsnap_release.py
```

## Commands

Build and publish after all gates pass:

```bash
python scripts/run_current_role_research.py --season 2026 --refresh
```

Validate the public partition independently:

```bash
python scripts/validate_current_role_outputs.py --season 2026
```

Dry-run staging without public publication:

```bash
python scripts/run_current_role_research.py --season 2026 --refresh --no-publish
```

## Partial-game review

Copy `data/operations/partial_game_overrides_template.csv` to `data/operations/partial_game_overrides.csv` and use one of:

- `CLEAR`
- `SUSPECTED_PARTIAL`
- `CONFIRMED_PARTIAL`

Each row must contain season, week, game ID, player ID, team, reason, and review timestamp. Duplicate keys or unsupported statuses block the run.

## Failure states

- `PRESEASON`: no current-season partition is expected yet.
- `WAITING_FOR_COMPLETED_WEEK`: no consecutive full week is ready; prior published files remain active.
- `BLOCKED`: a required source or validation gate failed; prior published files remain active.
- `VALIDATED_NOT_PUBLISHED`: staging passed under `--no-publish`.
- `PUBLISHED`: the current partition passed all gates and was copied atomically.

## Rollback

Every successful weekly update is one generated-data commit on `streamlit-cloud-deploy`. Reverting that commit restores the previous published partition. Frozen historical files remain unchanged throughout current-season operations.

DepthSnap promotion also retains `export.rollback` until guarded cleanup. A
running web process caches its validated registry for its lifetime, so a
registry commit must trigger the authorized rebuild/redeploy or a controlled
process restart before the new source version is public.
