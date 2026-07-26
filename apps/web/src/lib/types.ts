export type DataStatus = "published" | "no_published_week" | "unavailable";

export type ReportFamily =
  | "backfield_control"
  | "target_hierarchy"
  | "role_movement";

export type PlayerPosition = "RB" | "WR" | "TE";

export type PlayerIdentity = {
  id: string;
  name: string;
  team?: string;
  teamId?: string;
  position: PlayerPosition;
  href?: string;
  jerseyNumber?: number;
  searchAliases?: readonly string[];
};

export type RawShareEvidence = {
  numerator: number;
  denominator: number;
  share: number;
  opportunityLabel: "opportunities" | "carries" | "targets";
};

export type MovementEvidence = {
  previous: RawShareEvidence;
  current: RawShareEvidence;
  percentagePointChange: number;
};

export type FeedFindingKind =
  | "opportunity_gained"
  | "opportunity_lost"
  | "box_score_overstated_role"
  | "strong_opportunity_weak_production";

export type FeedFinding = {
  id: string;
  kind: FeedFindingKind;
  reportFamily: ReportFamily;
  roleFamily: string;
  roleLabel: string;
  player: PlayerIdentity;
  evidenceTeam: {
    id: string;
    abbreviation: string;
    name: string;
    monogram: string;
    accent: "teal" | "amber" | "slate";
    href: string;
    searchAliases: readonly string[];
    conference?: string;
    division?: string;
  };
  headline: string;
  current: RawShareEvidence;
  movement?: MovementEvidence;
  evidenceHref: string;
  participationQuality:
    | "complete"
    | "suspected_statistical"
    | "suspected_corroborated"
    | "reviewed_partial_game";
  supportingContextStatus: "available" | "unavailable";
};

export type ReportLink = {
  family: ReportFamily;
  label: string;
  description: string;
  href: string;
};

type HomepageFixtureMetadata = {
  schemaVersion: "depthsnap.home.fixture.v1";
  fixture: true;
  dataNotice: string;
  season: number;
  throughWeek: number;
  generatedAt: string;
  reportLinks: readonly ReportLink[];
};

export type PublishedHomepageFixture = HomepageFixtureMetadata & {
  status: "published";
  leadFinding: FeedFinding;
  findings: readonly FeedFinding[];
};

export type NoPublishedWeekHomepageFixture = HomepageFixtureMetadata & {
  status: "no_published_week";
  stateTitle: string;
  stateMessage: string;
};

export type UnavailableHomepageFixture = HomepageFixtureMetadata & {
  status: "unavailable";
  stateTitle: string;
  stateMessage: string;
};

export type HomepageFixture =
  | PublishedHomepageFixture
  | NoPublishedWeekHomepageFixture
  | UnavailableHomepageFixture;
