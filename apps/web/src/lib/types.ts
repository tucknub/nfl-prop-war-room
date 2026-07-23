export type DataStatus = "published" | "no_published_week" | "unavailable";

export type ReportFamily =
  | "backfield_control"
  | "target_hierarchy"
  | "role_movement";

export type PlayerPosition = "RB" | "WR" | "TE";

export type PlayerIdentity = {
  id: string;
  name: string;
  team: string;
  teamId?: string;
  position: PlayerPosition;
  href?: string;
  jerseyNumber?: number;
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
  | "backfield_increase"
  | "target_share_increase"
  | "role_decline"
  | "concentrated_role"
  | "committee_formation";

export type FeedFinding = {
  id: string;
  kind: FeedFindingKind;
  reportFamily: ReportFamily;
  roleFamily: string;
  player: PlayerIdentity;
  headline: string;
  current: RawShareEvidence;
  movement?: MovementEvidence;
  evidenceHref: string;
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
  fixtureNotice: string;
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
