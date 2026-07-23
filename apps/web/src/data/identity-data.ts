import {
  backfieldReportFixture,
  movementReportFixture,
  targetReportFixture,
} from "@/data/reports.fixture";
import {
  getPlayerIdentity,
  getTeamIdentity,
  identityFixtureMetadata,
  players,
  supplementalHierarchyEvidence,
  supplementalMovements,
  teams,
  weeklyEvidenceByPlayer,
} from "@/data/identity.fixture";
import type {
  HierarchyEvidenceRow,
  PlayerDirectoryRecord,
  PlayerEvidenceBundle,
  ReportMembership,
  SearchIdentity,
  SuppliedMovementRecord,
  TeamDirectoryRecord,
  TeamEvidenceBundle,
  WeeklyEvidencePoint,
} from "@/lib/identity-types";
import type { CurrentEvidenceRow, MovementEvidenceRow } from "@/lib/report-types";
import type { ReportFamily } from "@/lib/types";

const backfieldRows = backfieldReportFixture.views[0].rows;
const targetRows = targetReportFixture.views[0].rows;
const movementRows = movementReportFixture.views[0].rows;

function fromCurrentRow(row: CurrentEvidenceRow): HierarchyEvidenceRow {
  const player = getPlayerIdentity(row.player.id);
  if (!player) {
    throw new Error(`Identity fixture is missing ${row.player.id}`);
  }
  return {
    authoritativeOrder: row.authoritativeRank,
    player,
    roleFamily: row.roleFamily,
    evidence: row.current,
    classificationLabel: row.classificationLabel,
    dataQuality: row.dataQuality,
  };
}

function fromMovementRow(row: MovementEvidenceRow): SuppliedMovementRecord {
  const player = getPlayerIdentity(row.player.id);
  if (!player) {
    throw new Error(`Identity fixture is missing ${row.player.id}`);
  }
  return {
    authoritativeOrder: row.authoritativeRank,
    player,
    reportFamily: "role_movement",
    roleFamily: row.roleFamily,
    movement: row.movement,
    direction: row.direction,
    finding: row.finding,
    reportHref: "/reports/movement?view=last4-vs-prior4",
    dataQuality: row.dataQuality,
  };
}

const allHierarchy = [
  ...backfieldRows.map(fromCurrentRow),
  ...targetRows.map(fromCurrentRow),
  ...supplementalHierarchyEvidence,
];

const allMovements = [
  ...movementRows.map(fromMovementRow),
  ...supplementalMovements,
];

function topRows(
  teamId: string,
  position: "RB" | "WR" | "TE",
): readonly HierarchyEvidenceRow[] {
  return allHierarchy
    .filter(
      (row) =>
        row.player.teamId === teamId && row.player.position === position,
    )
    .sort((left, right) => left.authoritativeOrder - right.authoritativeOrder);
}

export function getTeamBundle(
  teamId: string,
  state?: string,
): TeamEvidenceBundle | undefined {
  const team = getTeamIdentity(teamId);
  if (!team) {
    return undefined;
  }
  const backfieldHierarchy = topRows(team.id, "RB");
  const wrTargetHierarchy = topRows(team.id, "WR");
  const teTargetHierarchy = topRows(team.id, "TE");
  const movements = allMovements
    .filter((movement) => movement.player.teamId === team.id)
    .sort(
      (left, right) =>
        Math.abs(right.movement.percentagePointChange) -
        Math.abs(left.movement.percentagePointChange),
    );
  const linkedPlayers = players.filter((player) => player.teamId === team.id);
  const status =
    state === "unpublished"
      ? "no_published_week"
      : state === "unavailable"
        ? "unavailable"
        : "published";

  return {
    ...identityFixtureMetadata,
    status,
    team,
    suppliedSummary:
      status === "published"
        ? `${team.name} combines supplied backfield, WR, TE, and movement evidence in one team view.`
        : "Role evidence is not available for this fixture state.",
    backfieldHierarchy: status === "published" ? backfieldHierarchy : [],
    wrTargetHierarchy: status === "published" ? wrTargetHierarchy : [],
    teTargetHierarchy: status === "published" ? teTargetHierarchy : [],
    movements: status === "published" ? movements : [],
    linkedPlayers,
    availableViews: ["last4", "season"],
    dataQuality: "complete",
  };
}

function membershipForPlayer(playerId: string): readonly ReportMembership[] {
  const memberships: ReportMembership[] = [];
  const candidates: readonly [
    ReportFamily,
    string,
    string,
    readonly (CurrentEvidenceRow | MovementEvidenceRow)[],
  ][] = [
    ["backfield_control", "Backfield Control", "/reports/backfield", backfieldRows],
    ["target_hierarchy", "Target Hierarchy", "/reports/targets", targetRows],
    ["role_movement", "Role Movement", "/reports/movement", movementRows],
  ];
  for (const [family, label, href, rows] of candidates) {
    const row = rows.find((candidate) => candidate.player.id === playerId);
    if (row) {
      memberships.push({
        family,
        label,
        href,
        authoritativeRank: row.authoritativeRank,
      });
    }
  }
  return memberships;
}

function currentHierarchyForPlayer(
  playerId: string,
): HierarchyEvidenceRow | undefined {
  return allHierarchy.find((row) => row.player.id === playerId);
}

function currentMovementForPlayer(
  playerId: string,
): SuppliedMovementRecord | undefined {
  return allMovements.find((movement) => movement.player.id === playerId);
}

function fallbackWeekly(
  hierarchy: HierarchyEvidenceRow | undefined,
): readonly WeeklyEvidencePoint[] {
  if (!hierarchy) {
    return [];
  }
  return [
    {
      week: identityFixtureMetadata.throughWeek,
      periodLabel: `Week ${identityFixtureMetadata.throughWeek}`,
      evidence: hierarchy.evidence,
      opportunityLabel: hierarchy.evidence.opportunityLabel,
      dataQuality: hierarchy.dataQuality,
    },
  ];
}

export function getPlayerBundle(
  playerId: string,
  state?: string,
): PlayerEvidenceBundle | undefined {
  const player = getPlayerIdentity(playerId);
  if (!player) {
    return undefined;
  }
  const team = getTeamIdentity(player.teamId);
  if (!team) {
    throw new Error(`Team fixture is missing ${player.teamId}`);
  }
  const hierarchy = currentHierarchyForPlayer(player.id);
  const movement = currentMovementForPlayer(player.id);
  const memberships = membershipForPlayer(player.id);
  const status =
    state === "unpublished"
      ? "no_published_week"
      : state === "unavailable"
        ? "unavailable"
        : "published";
  const supportingContext = backfieldRows
    .concat(targetRows as unknown as typeof backfieldRows)
    .find((row) => row.player.id === player.id)?.supportingContext;
  const teamContext = allHierarchy
    .filter(
      (row) =>
        row.player.teamId === player.teamId &&
        row.player.position === player.position,
    )
    .sort((left, right) => left.authoritativeOrder - right.authoritativeOrder);

  return {
    ...identityFixtureMetadata,
    status,
    player,
    currentTeam: team,
    suppliedRoleDescription:
      hierarchy?.classificationLabel ??
      movement?.finding ??
      "No current hierarchy description supplied",
    currentEvidence: status === "published" ? hierarchy?.evidence ?? movement?.movement.current : undefined,
    supportingContext: status === "published" ? supportingContext : undefined,
    latestMovement: status === "published" ? movement : undefined,
    reportMemberships: status === "published" ? memberships : [],
    weeklyEvidence:
      status === "published"
        ? weeklyEvidenceByPlayer[player.id] ?? fallbackWeekly(hierarchy)
        : [],
    periodSummaries:
      status === "published" && hierarchy
        ? [{ label: "Supplied current window", evidence: hierarchy.evidence }]
        : [],
    movementHistory: status === "published" && movement ? [movement] : [],
    teamHierarchyContext: status === "published" ? teamContext : [],
    dataQuality: hierarchy?.dataQuality ?? movement?.dataQuality ?? "complete",
  };
}

export const teamDirectoryRecords: readonly TeamDirectoryRecord[] = teams
  .map((team) => {
    const bundle = getTeamBundle(team.id);
    if (!bundle) {
      throw new Error(`Missing team bundle: ${team.id}`);
    }
    return {
      team,
      topBackfield: bundle.backfieldHierarchy[0],
      topWr: bundle.wrTargetHierarchy[0],
      topTe: bundle.teTargetHierarchy[0],
      largestMovement: bundle.movements[0],
    };
  })
  .sort((left, right) => left.team.name.localeCompare(right.team.name));

export const playerDirectoryRecords: readonly PlayerDirectoryRecord[] = players
  .map((player) => {
    const hierarchy = currentHierarchyForPlayer(player.id);
    return {
      player,
      currentEvidence: hierarchy?.evidence ?? currentMovementForPlayer(player.id)?.movement.current,
      suppliedRoleDescription:
        hierarchy?.classificationLabel ??
        currentMovementForPlayer(player.id)?.finding ??
        "Fixture identity record",
      memberships: membershipForPlayer(player.id),
      latestMovement: currentMovementForPlayer(player.id),
    };
  })
  .sort((left, right) => left.player.name.localeCompare(right.player.name));

function formatEvidence(row?: HierarchyEvidenceRow): string {
  if (!row) {
    return "No current hierarchy evidence supplied";
  }
  return `${row.evidence.numerator} of ${row.evidence.denominator} ${row.evidence.opportunityLabel} · ${(row.evidence.share * 100).toFixed(1)}%`;
}

export const searchIndex: readonly SearchIdentity[] = [
  ...teamDirectoryRecords.map((record) => ({
    type: "team" as const,
    id: `search-team-${record.team.id}`,
    displayName: record.team.name,
    secondaryLabel: `Team · ${record.team.abbreviation}`,
    summary: `Top backfield: ${formatEvidence(record.topBackfield)}`,
    href: record.team.href,
    searchAliases: [
      record.team.abbreviation,
      ...record.team.searchAliases,
    ],
  })),
  ...playerDirectoryRecords.map((record) => ({
    type: "player" as const,
    id: `search-${record.player.id}`,
    displayName: record.player.name,
    secondaryLabel: `${record.player.position} · ${record.player.team}`,
    summary: record.currentEvidence
      ? `${record.currentEvidence.numerator} of ${record.currentEvidence.denominator} ${record.currentEvidence.opportunityLabel} · ${(record.currentEvidence.share * 100).toFixed(1)}%`
      : record.suppliedRoleDescription,
    href: record.player.href,
    searchAliases: record.player.searchAliases,
  })),
];

export function searchIdentities(query: string): readonly SearchIdentity[] {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return searchIndex.slice(0, 8);
  }
  const score = (item: SearchIdentity) => {
    const values = [item.displayName, ...item.searchAliases].map((value) =>
      value.toLowerCase(),
    );
    if (values.some((value) => value === normalized)) return 0;
    if (values.some((value) => value.startsWith(normalized))) return 1;
    if (values.some((value) => value.includes(normalized))) return 2;
    return 3;
  };
  return searchIndex
    .filter((item) => score(item) < 3)
    .sort(
      (left, right) =>
        score(left) - score(right) ||
        left.displayName.localeCompare(right.displayName),
    );
}
