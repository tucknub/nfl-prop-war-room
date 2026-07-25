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

export type DataQuality =
  | "complete"
  | "reviewed_partial_game"
  | "unavailable_supporting_context";

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
  roleFamily: string;
  current: RawShareEvidence;
  supportingContext?: SupportingContext;
  classificationLabel: string;
  teamHref: string;
  playerHref: string;
  evidenceHref: string;
  dataQuality: DataQuality;
};

export type MovementDirection = "gain" | "decline" | "stable";

export type MovementEvidenceRow = {
  id: string;
  authoritativeRank: number;
  player: PlayerIdentity;
  roleFamily: string;
  movement: MovementEvidence;
  direction: MovementDirection;
  movementLabel: string;
  finding: string;
  supportingContext?: SupportingContext;
  teamHref: string;
  playerHref: string;
  evidenceHref: string;
  dataQuality: DataQuality;
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
  page: number;
};

export type ReportSearchParams = {
  view?: string;
  sort?: string;
  team?: string;
  position?: string;
  page?: string;
  state?: string;
};
