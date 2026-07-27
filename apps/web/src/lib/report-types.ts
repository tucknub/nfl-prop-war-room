import type {
  TeamIdentity,
} from "@/lib/identity-types";
import type {
  MovementEvidence,
  PlayerIdentity,
  PlayerPosition,
  RawShareEvidence,
  ReportFamily,
} from "@/lib/types";

export type ReportDataStatus =
  | "published"
  | "no_published_week"
  | "unavailable";

export type ParticipationQuality =
  | "complete"
  | "suspected_statistical"
  | "suspected_corroborated"
  | "reviewed_partial_game";

export type SupportingContextStatus = "available" | "unavailable";

export type ReportPeriod = {
  label: string;
  startWeek: number;
  endWeek: number;
};

export type ReportViewOption = {
  id: string;
  label: string;
  description: string;
  currentPeriod: ReportPeriod;
  priorPeriod?: ReportPeriod;
};

export type ReportSort =
  | "authority"
  | "share"
  | "share_asc"
  | "gainers"
  | "decliners"
  | "absolute_change"
  | "player"
  | "team";

export type ReportSortOption = {
  id: ReportSort;
  label: string;
};

export type SupportingContext = {
  label: string;
  evidence: RawShareEvidence;
};

export type ReportSummaryItem = {
  label: string;
  value: string;
  detail: string;
};

export type ReportSummary = {
  answer: string;
  items: readonly ReportSummaryItem[];
};

export type ReportMetadata = {
  schemaVersion: "depthsnap.report.fixture.v1";
  fixture: true;
  dataMode?: "fixture" | "export";
  dataNotice: string;
  reportFamily: ReportFamily;
  title: string;
  question: string;
  description: string;
  season: number;
  throughWeek: number;
  generatedAt: string;
  sourceVersion: string;
  availableViews: readonly ReportViewOption[];
  defaultView: string;
  defaultSort: ReportSort;
  availableSorts: readonly ReportSortOption[];
  teamOptions: readonly string[];
  resultCount: number;
};

export type CurrentEvidenceRow = {
  id: string;
  authoritativeRank: number;
  player: PlayerIdentity;
  evidenceTeam: TeamIdentity;
  roleFamily: string;
  roleLabel: string;
  current: RawShareEvidence;
  supportingContext?: SupportingContext;
  teamHref: string;
  playerHref: string;
  evidenceHref: string;
  participationQuality: ParticipationQuality;
  supportingContextStatus: SupportingContextStatus;
};

export type MovementDirection = "gain" | "decline" | "stable";

export type MovementEvidenceRow = {
  id: string;
  authoritativeRank: number;
  player: PlayerIdentity;
  evidenceTeam: TeamIdentity;
  roleFamily: string;
  roleLabel: string;
  movement: MovementEvidence;
  direction: MovementDirection;
  finding: string;
  supportingContext?: SupportingContext;
  teamHref: string;
  playerHref: string;
  evidenceHref: string;
  participationQuality: ParticipationQuality;
  supportingContextStatus: SupportingContextStatus;
};

export type CurrentReportView = {
  viewId: string;
  summary: ReportSummary;
  rows: readonly CurrentEvidenceRow[];
};

export type MovementReportView = {
  viewId: string;
  summary: ReportSummary;
  rows: readonly MovementEvidenceRow[];
};

type ReportStateMetadata = ReportMetadata & {
  stateTitle: string;
  stateMessage: string;
};

export type PublishedCurrentReportFixture = ReportMetadata & {
  status: "published";
  reportFamily: "backfield_control" | "target_hierarchy";
  views: readonly CurrentReportView[];
};

export type PublishedMovementReportFixture = ReportMetadata & {
  status: "published";
  reportFamily: "role_movement";
  views: readonly MovementReportView[];
};

export type NoPublishedWeekReportFixture = ReportStateMetadata & {
  status: "no_published_week";
};

export type UnavailableReportFixture = ReportStateMetadata & {
  status: "unavailable";
};

export type ReportFixture =
  | PublishedCurrentReportFixture
  | PublishedMovementReportFixture
  | NoPublishedWeekReportFixture
  | UnavailableReportFixture;

export type ParsedReportQuery = {
  view: string;
  sort: ReportSort;
  team: string;
  position: "ALL" | PlayerPosition;
  role:
    | "ALL"
    | "rb_opportunity_share"
    | "rb_carry_share"
    | "wr_target_share"
    | "te_target_share";
  metric: "opportunities" | "carries";
  direction: "gains" | "declines" | "all";
  page: number;
};

export type ReportSearchParams = {
  view?: string;
  sort?: string;
  team?: string;
  position?: string;
  role?: string;
  metric?: string;
  direction?: string;
  page?: string;
  state?: string;
};
