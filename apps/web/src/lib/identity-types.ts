import type {
  MovementEvidence,
  PlayerIdentity,
  PlayerPosition,
  RawShareEvidence,
  ReportFamily,
} from "@/lib/types";
import type { DataQuality } from "@/lib/report-types";

export type TeamIdentity = {
  id: string;
  abbreviation: string;
  name: string;
  conference?: string;
  division?: string;
  monogram: string;
  accent: "teal" | "amber" | "slate";
  href: string;
  searchAliases: readonly string[];
};

export type CanonicalPlayerIdentity = PlayerIdentity & {
  teamId: string;
  href: string;
  searchAliases: readonly string[];
};

export type IdentityBundleStatus =
  | "published"
  | "no_published_week"
  | "unavailable";

export type IdentityBundleMetadata = {
  schemaVersion: "depthsnap.identity.fixture.v1";
  fixture: true;
  dataMode?: "fixture" | "export";
  fixtureNotice: string;
  status: IdentityBundleStatus;
  season: number;
  throughWeek: number;
  generatedAt: string;
  sourceVersion: string;
};

export type HierarchyEvidenceRow = {
  authoritativeOrder: number;
  player: CanonicalPlayerIdentity;
  roleFamily: string;
  evidence: RawShareEvidence;
  classificationLabel: string;
  dataQuality: DataQuality;
};

export type SuppliedMovementRecord = {
  authoritativeOrder: number;
  player: CanonicalPlayerIdentity;
  reportFamily: ReportFamily;
  roleFamily: string;
  movement: MovementEvidence;
  direction: "gain" | "decline" | "stable";
  finding: string;
  reportHref: string;
  dataQuality: DataQuality;
};

export type TeamEvidenceBundle = IdentityBundleMetadata & {
  team: TeamIdentity;
  suppliedSummary: string;
  backfieldHierarchy: readonly HierarchyEvidenceRow[];
  wrTargetHierarchy: readonly HierarchyEvidenceRow[];
  teTargetHierarchy: readonly HierarchyEvidenceRow[];
  movements: readonly SuppliedMovementRecord[];
  linkedPlayers: readonly CanonicalPlayerIdentity[];
  availableViews: readonly string[];
  dataQuality: DataQuality;
};

export type WeeklyEvidencePoint = {
  week: number;
  periodLabel: string;
  evidence?: RawShareEvidence;
  opportunityLabel: RawShareEvidence["opportunityLabel"];
  dataQuality: DataQuality;
  partialGame?: boolean;
};

export type ReportMembership = {
  family: ReportFamily;
  label: string;
  href: string;
  authoritativeRank: number;
};

export type PlayerEvidenceBundle = IdentityBundleMetadata & {
  player: CanonicalPlayerIdentity;
  currentTeam: TeamIdentity;
  suppliedRoleDescription: string;
  currentEvidence?: RawShareEvidence;
  supportingContext?: {
    label: string;
    evidence: RawShareEvidence;
  };
  latestMovement?: SuppliedMovementRecord;
  reportMemberships: readonly ReportMembership[];
  weeklyEvidence: readonly WeeklyEvidencePoint[];
  periodSummaries: readonly {
    label: string;
    evidence: RawShareEvidence;
  }[];
  movementHistory: readonly SuppliedMovementRecord[];
  teamHierarchyContext: readonly HierarchyEvidenceRow[];
  dataQuality: DataQuality;
};

export type TeamDirectoryRecord = {
  team: TeamIdentity;
  topBackfield?: HierarchyEvidenceRow;
  topWr?: HierarchyEvidenceRow;
  topTe?: HierarchyEvidenceRow;
  largestMovement?: SuppliedMovementRecord;
};

export type PlayerDirectoryRecord = {
  player: CanonicalPlayerIdentity;
  currentEvidence?: RawShareEvidence;
  suppliedRoleDescription: string;
  memberships: readonly ReportMembership[];
  latestMovement?: SuppliedMovementRecord;
};

export type SearchIdentity = {
  type: "team" | "player";
  id: string;
  displayName: string;
  secondaryLabel: string;
  summary: string;
  href: string;
  searchAliases: readonly string[];
};

export type IdentitySearchParams = {
  q?: string;
  team?: string;
  position?: PlayerPosition | "ALL";
  report?: ReportFamily | "ALL";
  sort?: string;
  state?: string;
  focus?: string;
};
