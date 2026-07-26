import type {
  CanonicalPlayerIdentity,
  HierarchyEvidenceRow,
  SuppliedMovementRecord,
  TeamIdentity,
  WeeklyEvidencePoint,
} from "@/lib/identity-types";
import type { PlayerPosition, RawShareEvidence } from "@/lib/types";

export const identityDataNotice =
  "Design fixture data — synthetic records for interface review, not a current NFL week.";

export const identityFixtureMetadata = {
  schemaVersion: "depthsnap.identity.fixture.v1",
  fixture: true,
  dataNotice: identityDataNotice,
  status: "published",
  season: 2025,
  throughWeek: 18,
  generatedAt: "2026-07-23T12:00:00Z",
  sourceVersion: "fixture-role-export-2025-w18-v1",
} as const;

export const teams = [
  team("JVT", "Jacksonville Tide", "AFC", "South", "JT", "teal", ["Jacksonville"]),
  team("PDX", "Portland Pioneers", "NFC", "West", "PP", "amber", ["Portland"]),
  team("BHM", "Birmingham Forge", "AFC", "North", "BF", "slate", ["Birmingham"]),
  team("SAC", "Sacramento Sol", "NFC", "West", "SS", "amber", ["Sacramento"]),
  team("OKC", "Oklahoma City Outriders", "AFC", "West", "OO", "slate", ["Oklahoma City"]),
  team("IND", "Indianapolis Union", "AFC", "South", "IU", "teal", ["Indianapolis"]),
  team("SEA", "Seattle Cascades", "NFC", "West", "SC", "teal", ["Seattle"]),
  team("MIN", "Minnesota North", "NFC", "North", "MN", "slate", ["Minnesota"]),
] as const satisfies readonly TeamIdentity[];

function team(
  abbreviation: string,
  name: string,
  conference: string,
  division: string,
  monogram: string,
  accent: TeamIdentity["accent"],
  searchAliases: readonly string[],
): TeamIdentity {
  return {
    id: abbreviation,
    abbreviation,
    name,
    conference,
    division,
    monogram,
    accent,
    href: `/teams/${abbreviation}`,
    searchAliases,
  };
}

function player(
  slug: string,
  name: string,
  teamId: string,
  position: PlayerPosition,
  aliases: readonly string[] = [],
): CanonicalPlayerIdentity {
  return {
    id: `player-${slug}`,
    name,
    currentTeamId: teamId,
    position,
    href: `/players/player-${slug}`,
    searchAliases: aliases,
  };
}

export const players = [
  player("marcus-hale", "Marcus Hale", "JVT", "RB", ["M Hale"]),
  player("elijah-north", "Elijah North", "JVT", "RB"),
  player("jonah-pike", "Jonah Pike", "JVT", "WR"),
  player("cole-mercer", "Cole Mercer", "JVT", "TE"),
  player("caleb-stone", "Caleb Stone", "PDX", "RB"),
  player("luca-ward", "Luca Ward", "PDX", "WR"),
  player("rowan-quill", "Rowan Quill", "PDX", "TE"),
  player("jordan-vale", "Jordan Vale", "BHM", "RB"),
  player("owen-black", "Owen Black", "BHM", "RB"),
  player("asher-king", "Asher King", "BHM", "WR"),
  player("nolan-frost", "Nolan Frost", "BHM", "TE"),
  player("micah-reed", "Micah Reed", "SAC", "RB"),
  player("miles-redd", "Miles Redd", "SAC", "RB"),
  player("omar-voss", "Omar Voss", "SAC", "WR"),
  player("ezra-hart", "Ezra Hart", "SAC", "TE"),
  player("devin-banks", "Devin Banks", "OKC", "RB"),
  player("kian-west", "Kian West", "OKC", "WR"),
  player("eli-rhodes", "Eli Rhodes", "OKC", "TE"),
  player("zion-mercer", "Zion Mercer", "IND", "RB"),
  player("avery-cross", "Avery Cross", "IND", "WR"),
  player("leo-wynn", "Leo Wynn", "IND", "TE"),
  player("noah-rivers", "Noah Rivers", "SEA", "RB"),
  player("theo-lane", "Theo Lane", "SEA", "WR"),
  player("isaac-gray", "Isaac Gray", "SEA", "TE"),
  player("sam-rowe", "Sam Rowe", "MIN", "RB"),
  player("evan-lake", "Evan Lake", "MIN", "WR"),
  player("drew-keaton", "Drew Keaton", "MIN", "TE"),
] as const satisfies readonly CanonicalPlayerIdentity[];

export function getTeamIdentity(teamId: string): TeamIdentity | undefined {
  return teams.find(
    (candidate) => candidate.id.toLowerCase() === teamId.toLowerCase(),
  );
}

export function getPlayerIdentity(
  playerIdOrSlug: string,
): CanonicalPlayerIdentity | undefined {
  const normalized = playerIdOrSlug.toLowerCase();
  const id = normalized.startsWith("player-")
    ? normalized
    : `player-${normalized}`;
  return players.find((candidate) => candidate.id === id);
}

export function evidence(
  numerator: number,
  denominator: number,
  share: number,
  opportunityLabel: RawShareEvidence["opportunityLabel"],
): RawShareEvidence {
  return { numerator, denominator, share, opportunityLabel };
}

function hierarchy(
  slug: string,
  authoritativeOrder: number,
  roleFamily: string,
  raw: RawShareEvidence,
  _fixtureRoleDescription: string,
): HierarchyEvidenceRow {
  const identity = getPlayerIdentity(slug);
  const evidenceTeam = identity
    ? getTeamIdentity(identity.currentTeamId)
    : undefined;
  if (!identity || !evidenceTeam) {
    throw new Error(`Missing fixture identity: ${slug}`);
  }
  const roleFamilySlug = {
    "RB carry share": "rb_carry_share",
    "RB opportunity share": "rb_opportunity_share",
    "WR target share": "wr_target_share",
    "TE target share": "te_target_share",
  }[roleFamily];
  if (!roleFamilySlug) {
    throw new Error(`Unsupported fixture role family: ${roleFamily}`);
  }
  return {
    authoritativeOrder,
    player: identity,
    evidenceTeam,
    roleFamily: roleFamilySlug,
    roleLabel: roleFamily,
    evidence: raw,
    participationQuality: "complete",
    supportingContextStatus: "available",
  };
}

export const supplementalHierarchyEvidence = [
  hierarchy("elijah-north", 2, "RB opportunity share", evidence(6, 34, 0.176, "opportunities"), "supporting backfield role"),
  hierarchy("rowan-quill", 1, "TE target share", evidence(6, 30, 0.2, "targets"), "leading TE"),
  hierarchy("asher-king", 1, "WR target share", evidence(8, 31, 0.258, "targets"), "leading WR"),
  hierarchy("nolan-frost", 1, "TE target share", evidence(5, 31, 0.161, "targets"), "leading TE"),
  hierarchy("ezra-hart", 1, "TE target share", evidence(4, 28, 0.143, "targets"), "leading TE"),
  hierarchy("kian-west", 1, "WR target share", evidence(8, 28, 0.286, "targets"), "leading WR"),
  hierarchy("avery-cross", 1, "WR target share", evidence(9, 30, 0.3, "targets"), "leading WR"),
  hierarchy("leo-wynn", 1, "TE target share", evidence(6, 30, 0.2, "targets"), "leading TE"),
  hierarchy("noah-rivers", 1, "RB opportunity share", evidence(20, 32, 0.625, "opportunities"), "shared backfield"),
  hierarchy("isaac-gray", 1, "TE target share", evidence(6, 31, 0.194, "targets"), "leading TE"),
  hierarchy("sam-rowe", 1, "RB opportunity share", evidence(18, 30, 0.6, "opportunities"), "shared backfield"),
  hierarchy("evan-lake", 1, "WR target share", evidence(9, 29, 0.31, "targets"), "leading WR"),
] as const;

function suppliedMovement(
  slug: string,
  order: number,
  roleFamily: string,
  previous: RawShareEvidence,
  current: RawShareEvidence,
  percentagePointChange: number,
  finding: string,
): SuppliedMovementRecord {
  const identity = getPlayerIdentity(slug);
  const evidenceTeam = identity
    ? getTeamIdentity(identity.currentTeamId)
    : undefined;
  if (!identity || !evidenceTeam) {
    throw new Error(`Missing fixture identity: ${slug}`);
  }
  const roleFamilySlug = {
    "RB carry share": "rb_carry_share",
    "RB opportunity share": "rb_opportunity_share",
    "WR target share": "wr_target_share",
    "TE target share": "te_target_share",
  }[roleFamily];
  if (!roleFamilySlug) {
    throw new Error(`Unsupported fixture role family: ${roleFamily}`);
  }
  return {
    authoritativeOrder: order,
    player: identity,
    evidenceTeam,
    reportFamily: "role_movement",
    roleFamily: roleFamilySlug,
    roleLabel: roleFamily,
    movement: { previous, current, percentagePointChange },
    direction: percentagePointChange > 0 ? "gain" : percentagePointChange < 0 ? "decline" : "stable",
    finding,
    reportHref: "/reports/movement?view=last4-vs-prior4",
    participationQuality: "complete",
    supportingContextStatus: "available",
  };
}

export const supplementalMovements = [
  suppliedMovement("luca-ward", 20, "WR target share", evidence(6, 29, 0.207, "targets"), evidence(9, 30, 0.3, "targets"), 9.3, "gained documented team target share"),
  suppliedMovement("eli-rhodes", 21, "TE target share", evidence(5, 29, 0.172, "targets"), evidence(7, 28, 0.25, "targets"), 7.8, "gained documented team target share"),
  suppliedMovement("drew-keaton", 22, "TE target share", evidence(6, 28, 0.214, "targets"), evidence(9, 29, 0.31, "targets"), 9.6, "gained documented team target share"),
] as const;

function weekly(
  week: number,
  numerator: number | null,
  denominator: number | null,
  share: number | null,
  opportunityLabel: RawShareEvidence["opportunityLabel"],
  partialGame = false,
): WeeklyEvidencePoint {
  return {
    week,
    periodLabel: `Week ${week}`,
    opportunityLabel,
    evidence:
      numerator === null || denominator === null || share === null
        ? undefined
        : evidence(numerator, denominator, share, opportunityLabel),
    participationQuality: partialGame ? "reviewed_partial_game" : "complete",
    supportingContextStatus: numerator === null ? "unavailable" : "available",
    partialGame: partialGame || undefined,
  };
}

export const weeklyEvidenceByPlayer: Readonly<Record<string, readonly WeeklyEvidencePoint[]>> = {
  "player-marcus-hale": [
    weekly(13, 18, 25, 0.72, "opportunities"),
    weekly(14, null, null, null, "opportunities"),
    weekly(15, 24, 32, 0.75, "opportunities"),
    weekly(16, 25, 33, 0.758, "opportunities"),
    weekly(17, 26, 34, 0.765, "opportunities"),
    weekly(18, 27, 34, 0.794, "opportunities"),
  ],
  "player-zion-mercer": [
    weekly(15, 18, 33, 0.545, "opportunities"),
    weekly(16, 19, 34, 0.559, "opportunities"),
    weekly(17, 21, 34, 0.618, "opportunities"),
    weekly(18, 22, 35, 0.629, "opportunities"),
  ],
  "player-jonah-pike": [
    weekly(15, 8, 30, 0.267, "targets"),
    weekly(16, 9, 31, 0.29, "targets"),
    weekly(17, 10, 31, 0.323, "targets"),
    weekly(18, 11, 32, 0.344, "targets"),
  ],
  "player-theo-lane": [
    weekly(15, 7, 30, 0.233, "targets"),
    weekly(16, 8, 30, 0.267, "targets"),
    weekly(17, 9, 31, 0.29, "targets"),
    weekly(18, 10, 31, 0.323, "targets"),
  ],
  "player-cole-mercer": [
    weekly(15, 4, 30, 0.133, "targets"),
    weekly(16, 5, 31, 0.161, "targets", true),
    weekly(17, 6, 31, 0.194, "targets"),
    weekly(18, 7, 32, 0.219, "targets"),
  ],
};
