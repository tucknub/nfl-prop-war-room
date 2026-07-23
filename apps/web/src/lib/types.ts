export type RoleFamily =
  | "rb_carry_share"
  | "rb_opportunity_share"
  | "wr_target_share"
  | "te_target_share";

export type Direction = "up" | "down" | "steady";

export type RoleFinding = {
  id: string;
  playerId: string;
  playerName: string;
  team: string;
  position: "RB" | "WR" | "TE";
  roleFamily: RoleFamily;
  label: string;
  currentRaw: number;
  currentTeamTotal: number;
  currentShare: number;
  priorRaw?: number;
  priorTeamTotal?: number;
  priorShare?: number;
  changePoints?: number;
  direction: Direction;
};

export type TeamSnapshot = {
  team: string;
  name: string;
  backfield: Array<{
    playerName: string;
    share: number;
    raw: number;
    teamTotal: number;
  }>;
  targets: Array<{
    playerName: string;
    position: "WR" | "TE";
    share: number;
    raw: number;
    teamTotal: number;
  }>;
};

export type HomeBundle = {
  schemaVersion: "depthsnap.home.v1";
  fixture: boolean;
  season: number;
  throughWeek: number;
  updatedAt: string;
  status: "PUBLISHED" | "WAITING_FOR_COMPLETED_WEEK" | "BLOCKED";
  lead: RoleFinding;
  movement: RoleFinding[];
  rankings: RoleFinding[];
  teamSnapshot: TeamSnapshot;
};
