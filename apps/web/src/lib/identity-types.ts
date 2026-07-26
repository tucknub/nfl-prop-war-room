import type {
  MovementEvidence,
  PlayerIdentity,
  PlayerPosition,
  RawShareEvidence,
  ReportFamily,
} from "@/lib/types";
import type {
  ParticipationQuality,
  SupportingContextStatus,
} from "@/lib/report-types";

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
  currentTeamId: string;
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
  dataNotice: string;
  status: IdentityBundleStatus;
  season: number;
  throughWeek: number;
  generatedAt: string;
  sourceVersion: string;
};

export type HierarchyEvidenceRow = {
  authoritativeOrder: number;
  player: CanonicalPlayerIdentity;
  evidenceTeam: TeamIdentity;
  roleFamily: string;
  roleLabel: string;
  evidence: RawShareEvidence;
  participationQuality: ParticipationQuality;
  supportingContextStatus: SupportingContextStatus;
};

export type SuppliedMovementRecord = {
  authoritativeOrder: number;
  player: CanonicalPlayerIdentity;
  evidenceTeam: TeamIdentity;
  reportFamily: ReportFamily;
  roleFamily: string;
  roleLabel: string;
  movement: MovementEvidence;
  direction: "gain" | "decline" | "stable";
  finding: string;
  reportHref: string;
  participationQuality: ParticipationQuality;
  supportingContextStatus: SupportingContextStatus;
};

export type TeamEvidenceBundle = IdentityBundleMetadata & {
  team: TeamIdentity;
  suppliedSummary?: string;
  backfieldHierarchy: readonly HierarchyEvidenceRow[];
  wrTargetHierarchy: readonly HierarchyEvidenceRow[];
  teTargetHierarchy: readonly HierarchyEvidenceRow[];
  movements: readonly SuppliedMovementRecord[];
  linkedPlayers: readonly CanonicalPlayerIdentity[];
  availableViews: readonly string[];
};

export type WeeklyEvidencePoint = {
  week: number;
  periodLabel: string;
  evidenceTeam?: TeamIdentity;
  roleFamily?: string;
  roleLabel?: string;
  evidence?: RawShareEvidence;
  opportunityLabel: RawShareEvidence["opportunityLabel"];
  participationQuality: ParticipationQuality;
  supportingContextStatus: SupportingContextStatus;
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
  suppliedRoleDescription?: string;
  currentEvidence?: RawShareEvidence;
  currentEvidenceTeam?: TeamIdentity;
  currentRoleFamily?: string;
  currentRoleLabel?: string;
  supportingContext?: {
    label: string;
    evidence: RawShareEvidence;
  };
  latestMovement?: SuppliedMovementRecord;
  reportMemberships: readonly ReportMembership[];
  weeklyEvidence: readonly WeeklyEvidencePoint[];
  periodSummaries: readonly {
    label: string;
    evidenceTeam: TeamIdentity;
    roleFamily: string;
    roleLabel: string;
    evidence: RawShareEvidence;
  }[];
  movementHistory: readonly SuppliedMovementRecord[];
  teamHierarchyContext: readonly HierarchyEvidenceRow[];
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
  currentTeam: TeamIdentity;
  currentEvidence?: RawShareEvidence;
  currentEvidenceTeam?: TeamIdentity;
  roleFamily?: string;
  roleLabel?: string;
  suppliedRoleDescription?: string;
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
