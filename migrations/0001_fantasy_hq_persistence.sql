-- Fantasy League HQ persistence foundation.
-- SQLite-compatible by design so this migration can be applied to Cloudflare D1 later.
-- This migration defines storage only; it does not configure or deploy a D1 database.

CREATE TABLE fantasy_league_families (
    league_family_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (length(trim(league_family_id)) > 0),
    CHECK (length(trim(display_name)) > 0)
);

CREATE TABLE fantasy_league_seasons (
    league_season_id TEXT PRIMARY KEY,
    league_family_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_league_id TEXT NOT NULL,
    season TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (length(trim(league_season_id)) > 0),
    CHECK (length(trim(platform)) > 0),
    CHECK (length(trim(platform_league_id)) > 0),
    CHECK (length(trim(season)) > 0),
    CHECK (length(trim(display_name)) > 0),
    UNIQUE (platform, platform_league_id, season),
    UNIQUE (league_family_id, season),
    UNIQUE (league_season_id, platform, platform_league_id, season),
    FOREIGN KEY (league_family_id)
        REFERENCES fantasy_league_families(league_family_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE fantasy_state_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    league_season_id TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL,
    observed_at_ms INTEGER NOT NULL CHECK (observed_at_ms >= 0),
    accepted_at_ms INTEGER NOT NULL CHECK (accepted_at_ms >= 0),
    provider_status TEXT NOT NULL,
    rules_ready INTEGER NOT NULL CHECK (rules_ready IN (0, 1)),
    draft_ready INTEGER NOT NULL CHECK (draft_ready IN (0, 1)),
    ownership_ready INTEGER NOT NULL CHECK (ownership_ready IN (0, 1)),
    normalized_state_json TEXT NOT NULL,
    source_metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (length(trim(snapshot_id)) > 0),
    CHECK (length(trim(content_fingerprint)) > 0),
    CHECK (length(trim(provider_status)) > 0),
    CHECK (accepted_at_ms >= observed_at_ms),
    UNIQUE (snapshot_id, league_season_id),
    FOREIGN KEY (league_season_id)
        REFERENCES fantasy_league_seasons(league_season_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE fantasy_change_events (
    event_fingerprint TEXT PRIMARY KEY,
    league_season_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_league_id TEXT NOT NULL,
    season TEXT NOT NULL,
    before_snapshot_id TEXT NOT NULL,
    after_snapshot_id TEXT NOT NULL,
    platform_roster_id TEXT,
    platform_player_id TEXT,
    before_value_json TEXT,
    after_value_json TEXT,
    source_transaction_ids_json TEXT NOT NULL DEFAULT '[]',
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    derived_at_ms INTEGER NOT NULL CHECK (derived_at_ms >= 0),
    CHECK (length(trim(event_fingerprint)) > 0),
    CHECK (length(trim(event_type)) > 0),
    CHECK (before_snapshot_id <> after_snapshot_id),
    FOREIGN KEY (league_season_id, platform, platform_league_id, season)
        REFERENCES fantasy_league_seasons(
            league_season_id, platform, platform_league_id, season
        )
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    FOREIGN KEY (before_snapshot_id, league_season_id)
        REFERENCES fantasy_state_snapshots(snapshot_id, league_season_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    FOREIGN KEY (after_snapshot_id, league_season_id)
        REFERENCES fantasy_state_snapshots(snapshot_id, league_season_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE fantasy_sync_runs (
    sync_run_id TEXT PRIMARY KEY,
    league_season_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_league_id TEXT NOT NULL,
    season TEXT NOT NULL,
    started_at_ms INTEGER NOT NULL CHECK (started_at_ms >= 0),
    completed_at_ms INTEGER CHECK (
        completed_at_ms IS NULL OR completed_at_ms >= started_at_ms
    ),
    status TEXT NOT NULL,
    accepted_snapshot_id TEXT,
    error_code TEXT,
    error_summary TEXT,
    request_metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (length(trim(sync_run_id)) > 0),
    CHECK (length(trim(status)) > 0),
    FOREIGN KEY (league_season_id, platform, platform_league_id, season)
        REFERENCES fantasy_league_seasons(
            league_season_id, platform, platform_league_id, season
        )
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    FOREIGN KEY (accepted_snapshot_id, league_season_id)
        REFERENCES fantasy_state_snapshots(snapshot_id, league_season_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE football_entities (
    propwar_entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    position TEXT,
    nfl_team TEXT,
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    updated_at_ms INTEGER NOT NULL CHECK (updated_at_ms >= created_at_ms),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    CHECK (length(trim(propwar_entity_id)) > 0),
    CHECK (length(trim(entity_type)) > 0),
    CHECK (length(trim(canonical_name)) > 0)
);

CREATE TABLE football_external_ids (
    external_identity_id TEXT PRIMARY KEY,
    propwar_entity_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_scope TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL,
    linked_at_ms INTEGER NOT NULL CHECK (linked_at_ms >= 0),
    verification_method TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    CHECK (length(trim(external_identity_id)) > 0),
    CHECK (length(trim(provider)) > 0),
    CHECK (length(trim(external_id)) > 0),
    CHECK (length(trim(verification_method)) > 0),
    UNIQUE (provider, provider_scope, external_id),
    UNIQUE (propwar_entity_id, provider, provider_scope),
    FOREIGN KEY (propwar_entity_id)
        REFERENCES football_entities(propwar_entity_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE football_identity_review_events (
    identity_review_event_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_scope TEXT NOT NULL DEFAULT '',
    external_id TEXT NOT NULL,
    candidate_propwar_entity_id TEXT,
    previous_propwar_entity_id TEXT,
    decision TEXT NOT NULL,
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at_ms INTEGER NOT NULL CHECK (created_at_ms >= 0),
    decided_at_ms INTEGER CHECK (
        decided_at_ms IS NULL OR decided_at_ms >= created_at_ms
    ),
    reviewed_by TEXT,
    CHECK (length(trim(identity_review_event_id)) > 0),
    CHECK (length(trim(provider)) > 0),
    CHECK (length(trim(external_id)) > 0),
    CHECK (length(trim(decision)) > 0),
    FOREIGN KEY (candidate_propwar_entity_id)
        REFERENCES football_entities(propwar_entity_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    FOREIGN KEY (previous_propwar_entity_id)
        REFERENCES football_entities(propwar_entity_id)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE INDEX idx_fantasy_league_seasons_family
    ON fantasy_league_seasons(league_family_id, season);

CREATE INDEX idx_fantasy_snapshots_season_observed
    ON fantasy_state_snapshots(league_season_id, observed_at_ms DESC);

CREATE INDEX idx_fantasy_snapshots_content
    ON fantasy_state_snapshots(league_season_id, content_fingerprint);

CREATE INDEX idx_fantasy_events_season_derived
    ON fantasy_change_events(league_season_id, derived_at_ms DESC);

CREATE INDEX idx_fantasy_events_player
    ON fantasy_change_events(platform, platform_player_id, derived_at_ms DESC);

CREATE INDEX idx_fantasy_events_after_snapshot
    ON fantasy_change_events(after_snapshot_id, league_season_id);

CREATE INDEX idx_fantasy_sync_runs_season_started
    ON fantasy_sync_runs(league_season_id, started_at_ms DESC);

CREATE INDEX idx_football_external_ids_entity
    ON football_external_ids(propwar_entity_id);

CREATE INDEX idx_football_identity_reviews_lookup
    ON football_identity_review_events(
        provider, provider_scope, external_id, created_at_ms DESC
    );
