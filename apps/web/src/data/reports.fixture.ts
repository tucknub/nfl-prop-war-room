import type {
  CurrentEvidenceRow,
  DataQuality,
  MovementDirection,
  MovementEvidenceRow,
  PublishedCurrentReportFixture,
  PublishedMovementReportFixture,
  ReportFixture,
  ReportMetadata,
  ReportSearchParams,
  ReportSortOption,
} from "@/lib/report-types";
import type {
  PlayerPosition,
  RawShareEvidence,
  ReportFamily,
} from "@/lib/types";
import { getPlayerIdentity, getTeamIdentity } from "@/data/identity.fixture";

const fixtureNotice =
  "Design fixture data — synthetic records for interface review, not a current NFL week.";

const teamOptions = [
  "ALL",
  "JVT",
  "PDX",
  "BHM",
  "SAC",
  "OKC",
  "IND",
  "SEA",
  "MIN",
] as const;

const currentSorts = [
  { id: "authority", label: "Authority" },
  { id: "share", label: "Current share" },
  { id: "player", label: "Player" },
  { id: "team", label: "Team" },
] as const satisfies readonly ReportSortOption[];

const movementSorts = [
  { id: "authority", label: "Authority" },
  { id: "gainers", label: "Gainers" },
  { id: "decliners", label: "Decliners" },
  { id: "absolute_change", label: "Largest absolute change" },
  { id: "player", label: "Player" },
  { id: "team", label: "Team" },
] as const satisfies readonly ReportSortOption[];

function evidence(
  numerator: number,
  denominator: number,
  share: number,
  opportunityLabel: RawShareEvidence["opportunityLabel"],
): RawShareEvidence {
  return { numerator, denominator, share, opportunityLabel };
}

function currentRow(
  id: string,
  rank: number,
  name: string,
  team: string,
  position: PlayerPosition,
  roleFamily: string,
  current: RawShareEvidence,
  classificationLabel: string,
  dataQuality: DataQuality = "complete",
  supportingContext?: CurrentEvidenceRow["supportingContext"],
): CurrentEvidenceRow {
  const identity = getPlayerIdentity(
    id.replace(/-season$/, "").replace(/-move$/, ""),
  );
  const teamIdentity = getTeamIdentity(team);
  if (!identity || !teamIdentity || identity.name !== name || identity.position !== position) {
    throw new Error(`Missing canonical identity for report row: ${id}`);
  }
  return {
    id,
    authoritativeRank: rank,
    player: identity,
    roleFamily,
    current,
    classificationLabel,
    dataQuality,
    supportingContext,
    teamHref: teamIdentity.href,
    playerHref: identity.href,
    evidenceHref: identity.href,
  };
}

function movementRow(
  id: string,
  rank: number,
  name: string,
  team: string,
  position: PlayerPosition,
  roleFamily: string,
  previous: RawShareEvidence,
  current: RawShareEvidence,
  percentagePointChange: number,
  direction: MovementDirection,
  movementLabel: string,
  finding: string,
  dataQuality: DataQuality = "complete",
): MovementEvidenceRow {
  const identity = getPlayerIdentity(
    id.replace(/-season-move$/, "").replace(/-move$/, ""),
  );
  const teamIdentity = getTeamIdentity(team);
  if (!identity || !teamIdentity || identity.name !== name || identity.position !== position) {
    throw new Error(`Missing canonical identity for movement row: ${id}`);
  }
  return {
    id,
    authoritativeRank: rank,
    player: identity,
    roleFamily,
    movement: { previous, current, percentagePointChange },
    direction,
    movementLabel,
    finding,
    dataQuality,
    teamHref: teamIdentity.href,
    playerHref: identity.href,
    evidenceHref: identity.href,
  };
}

const backfieldLast4Rows = [
  currentRow(
    "marcus-hale",
    1,
    "Marcus Hale",
    "JVT",
    "RB",
    "RB opportunity share",
    evidence(27, 34, 0.794, "opportunities"),
    "concentrated lead",
    "complete",
    { label: "Typical game", evidence: evidence(18, 24, 0.75, "opportunities") },
  ),
  currentRow("caleb-stone", 2, "Caleb Stone", "PDX", "RB", "RB opportunity share", evidence(25, 34, 0.735, "opportunities"), "lead role"),
  currentRow("jordan-vale", 3, "Jordan Vale", "BHM", "RB", "RB opportunity share", evidence(23, 33, 0.697, "opportunities"), "lead role", "reviewed_partial_game"),
  currentRow("zion-mercer", 4, "Zion Mercer", "IND", "RB", "RB opportunity share", evidence(22, 35, 0.629, "opportunities"), "shared backfield"),
  currentRow("micah-reed", 5, "Micah Reed", "SAC", "RB", "RB opportunity share", evidence(21, 32, 0.656, "opportunities"), "shared backfield", "unavailable_supporting_context"),
  currentRow("devin-banks", 6, "Devin Banks", "OKC", "RB", "RB opportunity share", evidence(19, 31, 0.613, "opportunities"), "committee"),
] as const;

const backfieldSeasonRows = [
  currentRow("marcus-hale-season", 1, "Marcus Hale", "JVT", "RB", "RB opportunity share", evidence(211, 296, 0.713, "opportunities"), "concentrated lead"),
  currentRow("caleb-stone-season", 2, "Caleb Stone", "PDX", "RB", "RB opportunity share", evidence(198, 291, 0.68, "opportunities"), "lead role"),
  currentRow("jordan-vale-season", 3, "Jordan Vale", "BHM", "RB", "RB opportunity share", evidence(184, 286, 0.643, "opportunities"), "lead role"),
  currentRow("devin-banks-season", 4, "Devin Banks", "OKC", "RB", "RB opportunity share", evidence(166, 279, 0.595, "opportunities"), "committee"),
] as const;

const targetLast4Rows = [
  currentRow("jonah-pike", 1, "Jonah Pike", "JVT", "WR", "WR target share", evidence(11, 32, 0.344, "targets"), "clear team target leader"),
  currentRow("theo-lane", 2, "Theo Lane", "SEA", "WR", "WR target share", evidence(10, 31, 0.323, "targets"), "leading WR"),
  currentRow("drew-keaton", 3, "Drew Keaton", "MIN", "TE", "TE target share", evidence(9, 29, 0.31, "targets"), "leading TE"),
  currentRow("luca-ward", 4, "Luca Ward", "PDX", "WR", "WR target share", evidence(9, 30, 0.3, "targets"), "shared target tier"),
  currentRow("omar-voss", 5, "Omar Voss", "SAC", "WR", "WR target share", evidence(8, 28, 0.286, "targets"), "emerging concentration"),
  currentRow("eli-rhodes", 6, "Eli Rhodes", "OKC", "TE", "TE target share", evidence(7, 28, 0.25, "targets"), "leading TE"),
  currentRow("cole-mercer", 7, "Cole Mercer", "JVT", "TE", "TE target share", evidence(7, 32, 0.219, "targets"), "shared target tier", "unavailable_supporting_context"),
] as const;

const targetSeasonRows = [
  currentRow("jonah-pike-season", 1, "Jonah Pike", "JVT", "WR", "WR target share", evidence(88, 278, 0.317, "targets"), "clear team target leader"),
  currentRow("theo-lane-season", 2, "Theo Lane", "SEA", "WR", "WR target share", evidence(82, 271, 0.303, "targets"), "leading WR"),
  currentRow("drew-keaton-season", 3, "Drew Keaton", "MIN", "TE", "TE target share", evidence(75, 265, 0.283, "targets"), "leading TE"),
  currentRow("eli-rhodes-season", 4, "Eli Rhodes", "OKC", "TE", "TE target share", evidence(61, 254, 0.24, "targets"), "leading TE"),
] as const;

const movementLast4Rows = [
  movementRow("zion-mercer-move", 1, "Zion Mercer", "IND", "RB", "RB opportunity share", evidence(12, 33, 0.364, "opportunities"), evidence(22, 35, 0.629, "opportunities"), 26.5, "gain", "Backfield share gain", "gained documented backfield share"),
  movementRow("marcus-hale-move", 2, "Marcus Hale", "JVT", "RB", "RB opportunity share", evidence(18, 32, 0.563, "opportunities"), evidence(27, 34, 0.794, "opportunities"), 23.1, "gain", "Backfield share gain", "role became more concentrated"),
  movementRow("theo-lane-move", 3, "Theo Lane", "SEA", "WR", "WR target share", evidence(5, 29, 0.172, "targets"), evidence(10, 31, 0.323, "targets"), 15.1, "gain", "Target share gain", "gained documented team target share"),
  movementRow("miles-redd-move", 4, "Miles Redd", "SAC", "RB", "RB carry share", evidence(15, 26, 0.577, "carries"), evidence(8, 28, 0.286, "carries"), -29.1, "decline", "Carry share decline", "lost documented carry share"),
  movementRow("owen-black-move", 5, "Owen Black", "BHM", "RB", "RB opportunity share", evidence(21, 29, 0.724, "opportunities"), evidence(13, 30, 0.433, "opportunities"), -29.1, "decline", "Committee movement", "moved toward a committee"),
  movementRow("cole-mercer-move", 6, "Cole Mercer", "JVT", "TE", "TE target share", evidence(4, 30, 0.133, "targets"), evidence(7, 32, 0.219, "targets"), 8.6, "gain", "Target share gain", "gained documented team target share", "reviewed_partial_game"),
] as const;

const movementSeasonRows = [
  movementRow("zion-mercer-season-move", 1, "Zion Mercer", "IND", "RB", "RB opportunity share", evidence(72, 182, 0.396, "opportunities"), evidence(119, 201, 0.592, "opportunities"), 19.6, "gain", "Backfield share gain", "gained documented backfield share"),
  movementRow("theo-lane-season-move", 2, "Theo Lane", "SEA", "WR", "WR target share", evidence(31, 181, 0.171, "targets"), evidence(56, 194, 0.289, "targets"), 11.8, "gain", "Target share gain", "gained documented team target share"),
  movementRow("miles-redd-season-move", 3, "Miles Redd", "SAC", "RB", "RB carry share", evidence(88, 169, 0.521, "carries"), evidence(53, 184, 0.288, "carries"), -23.3, "decline", "Carry share decline", "lost documented carry share"),
  movementRow("owen-black-season-move", 4, "Owen Black", "BHM", "RB", "RB opportunity share", evidence(103, 171, 0.602, "opportunities"), evidence(72, 181, 0.398, "opportunities"), -20.4, "decline", "Committee movement", "moved toward a committee"),
] as const;

const metadataBase = {
  schemaVersion: "depthsnap.report.fixture.v1",
  fixture: true,
  fixtureNotice,
  season: 2025,
  throughWeek: 18,
  generatedAt: "2026-07-23T12:00:00Z",
  sourceVersion: "fixture-role-export-2025-w18-v1",
  teamOptions,
} as const;

export const backfieldReportFixture = {
  ...metadataBase,
  status: "published",
  reportFamily: "backfield_control",
  title: "Backfield Control",
  question: "Who controls each team’s documented RB opportunities?",
  description: "Player opportunities paired with the matching team RB total.",
  availableViews: [
    { id: "last4", label: "Last 4", description: "Supplied four-game window", currentPeriod: { label: "Weeks 15–18", startWeek: 15, endWeek: 18 } },
    { id: "season", label: "Season", description: "Supplied season-to-date view", currentPeriod: { label: "Weeks 1–18", startWeek: 1, endWeek: 18 } },
  ],
  defaultView: "last4",
  defaultSort: "authority",
  availableSorts: currentSorts,
  resultCount: backfieldLast4Rows.length,
  views: [
    { viewId: "last4", summary: { answer: "Marcus Hale owns the highest fixture-supplied backfield authority rank.", items: [
      { label: "Highest control", value: "79.4%", detail: "Marcus Hale · JVT" },
      { label: "Teams represented", value: "6", detail: "fixture-supplied count" },
      { label: "Concentrated roles", value: "1", detail: "supplied classification" },
      { label: "Committees", value: "1", detail: "supplied classification" },
    ] }, rows: backfieldLast4Rows },
    { viewId: "season", summary: { answer: "The supplied season view keeps Marcus Hale first in authority order.", items: [
      { label: "Highest control", value: "71.3%", detail: "Marcus Hale · JVT" },
      { label: "Teams represented", value: "4", detail: "fixture-supplied count" },
      { label: "Concentrated roles", value: "1", detail: "supplied classification" },
      { label: "Committees", value: "1", detail: "supplied classification" },
    ] }, rows: backfieldSeasonRows },
  ],
} as const satisfies PublishedCurrentReportFixture;

export const targetReportFixture = {
  ...metadataBase,
  status: "published",
  reportFamily: "target_hierarchy",
  title: "Target Hierarchy",
  question: "Who owns each team’s documented WR and TE targets?",
  description: "WR and TE target shares paired with matching team target totals.",
  availableViews: [
    { id: "last4", label: "Last 4", description: "Supplied four-game window", currentPeriod: { label: "Weeks 15–18", startWeek: 15, endWeek: 18 } },
    { id: "season", label: "Season", description: "Supplied season-to-date view", currentPeriod: { label: "Weeks 1–18", startWeek: 1, endWeek: 18 } },
  ],
  defaultView: "last4",
  defaultSort: "authority",
  availableSorts: currentSorts,
  resultCount: targetLast4Rows.length,
  views: [
    { viewId: "last4", summary: { answer: "Jonah Pike leads the supplied target-hierarchy authority order.", items: [
      { label: "Highest share", value: "34.4%", detail: "Jonah Pike · JVT" },
      { label: "Leading WR", value: "Jonah Pike", detail: "11 of 32 targets" },
      { label: "Leading TE", value: "Drew Keaton", detail: "9 of 29 targets" },
      { label: "Teams represented", value: "6", detail: "fixture-supplied count" },
    ] }, rows: targetLast4Rows },
    { viewId: "season", summary: { answer: "Jonah Pike remains first in the supplied season authority order.", items: [
      { label: "Highest share", value: "31.7%", detail: "Jonah Pike · JVT" },
      { label: "Leading WR", value: "Jonah Pike", detail: "88 of 278 targets" },
      { label: "Leading TE", value: "Drew Keaton", detail: "75 of 265 targets" },
      { label: "Teams represented", value: "4", detail: "fixture-supplied count" },
    ] }, rows: targetSeasonRows },
  ],
} as const satisfies PublishedCurrentReportFixture;

export const movementReportFixture = {
  ...metadataBase,
  status: "published",
  reportFamily: "role_movement",
  title: "Role Movement",
  question: "Whose documented role changed most between two supplied periods?",
  description: "Previous and current evidence from fixture-supplied comparison windows.",
  availableViews: [
    { id: "last4-vs-prior4", label: "Last 4 vs prior 4", description: "Two supplied four-game windows", currentPeriod: { label: "Weeks 15–18", startWeek: 15, endWeek: 18 }, priorPeriod: { label: "Weeks 11–14", startWeek: 11, endWeek: 14 } },
    { id: "season-to-date-vs-prior", label: "Season split", description: "Supplied season comparison", currentPeriod: { label: "Weeks 10–18", startWeek: 10, endWeek: 18 }, priorPeriod: { label: "Weeks 1–9", startWeek: 1, endWeek: 9 } },
  ],
  defaultView: "last4-vs-prior4",
  defaultSort: "authority",
  availableSorts: movementSorts,
  resultCount: movementLast4Rows.length,
  views: [
    { viewId: "last4-vs-prior4", summary: { answer: "Zion Mercer is first in the supplied movement authority order.", items: [
      { label: "Largest gain", value: "+26.5 pp", detail: "Zion Mercer · IND" },
      { label: "Largest decline", value: "−29.1 pp", detail: "Miles Redd · SAC" },
      { label: "Role families", value: "4", detail: "fixture-supplied count" },
      { label: "Rows reviewed", value: "6", detail: "published fixture rows" },
    ] }, rows: movementLast4Rows },
    { viewId: "season-to-date-vs-prior", summary: { answer: "The season split places Zion Mercer first in authority order.", items: [
      { label: "Largest gain", value: "+19.6 pp", detail: "Zion Mercer · IND" },
      { label: "Largest decline", value: "−23.3 pp", detail: "Miles Redd · SAC" },
      { label: "Role families", value: "3", detail: "fixture-supplied count" },
      { label: "Rows reviewed", value: "4", detail: "published fixture rows" },
    ] }, rows: movementSeasonRows },
  ],
} as const satisfies PublishedMovementReportFixture;

export const reportFixtures = {
  backfield_control: backfieldReportFixture,
  target_hierarchy: targetReportFixture,
  role_movement: movementReportFixture,
} as const;

export function getReportFixture(
  family: ReportFamily,
  requestedState?: ReportSearchParams["state"],
): ReportFixture {
  const published = reportFixtures[family];

  if (requestedState === "empty") {
    return {
      ...published,
      status: "no_published_week",
      resultCount: 0,
      stateTitle: "No completed week is published for this report",
      stateMessage:
        "A completed validated week has not been published. No estimated shares are shown.",
    };
  }

  if (requestedState === "unavailable") {
    return {
      ...published,
      status: "unavailable",
      resultCount: 0,
      stateTitle: "This report bundle is temporarily unavailable",
      stateMessage:
        "The report bundle could not be read. No stale or estimated results are shown.",
    };
  }

  return published;
}

export function getPublishedReport(family: ReportFamily) {
  return reportFixtures[family];
}

export type PublishedReport =
  | typeof backfieldReportFixture
  | typeof targetReportFixture
  | typeof movementReportFixture;

export type ReportMetadataFixture = ReportMetadata;
