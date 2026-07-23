import type {
  PlayerIdentity,
  RawShareEvidence,
  ReportFamily,
} from "@/lib/types";

export type TeamSnapshotRole = "RB1" | "RB2" | "WR1" | "TE1";

export type TeamSnapshotRow = {
  role: TeamSnapshotRole;
  player: string;
  evidence: RawShareEvidence;
  tone: "lead" | "secondary";
};

export type TeamSnapshotFixture = {
  monogram: string;
  teamName: string;
  teamCode: string;
  week: number;
  rows: readonly TeamSnapshotRow[];
  biggestMovement: {
    player: string;
    summary: string;
    percentagePointChange: number;
    evidenceHref: string;
  };
  reportHref: string;
};

export type LeaderboardRow = {
  rank: number;
  player: PlayerIdentity;
  evidence: RawShareEvidence;
  movementPoints: number;
  evidenceHref: string;
};

export type ReportLeaderboardFixture = Record<
  ReportFamily,
  readonly LeaderboardRow[]
>;
