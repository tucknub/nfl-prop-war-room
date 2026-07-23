import { createHash } from "node:crypto";
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  publishedHomeFixture,
} from "../src/data/home.fixture";
import {
  reportLeaderboardFixture,
  teamSnapshotFixture,
} from "../src/data/home.presentation.fixture";
import {
  identityFixtureMetadata,
  players,
  teams,
} from "../src/data/identity.fixture";
import {
  getPlayerBundle,
  getTeamBundle,
  playerDirectoryRecords,
  searchIndex,
  teamDirectoryRecords,
} from "../src/data/identity-data";
import {
  backfieldReportFixture,
  movementReportFixture,
  targetReportFixture,
} from "../src/data/reports.fixture";

type JsonObject = Record<string, unknown>;
type PublicationState = "published" | "no_published_week" | "unavailable";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(scriptDirectory, "..");
const dataRoot = path.join(webRoot, "public", "data", "depthsnap");
const generatedAt = identityFixtureMetadata.generatedAt;
const sourceVersion = identityFixtureMetadata.sourceVersion;
const fixtureNotice =
  "Design fixture data — synthetic records for interface review, not a current NFL week.";

function sortedJson(value: unknown): string {
  function sort(input: unknown): unknown {
    if (Array.isArray(input)) return input.map(sort);
    if (input && typeof input === "object") {
      return Object.fromEntries(
        Object.entries(input as Record<string, unknown>)
          .sort(([left], [right]) => left.localeCompare(right))
          .map(([key, child]) => [key, sort(child)]),
      );
    }
    return input;
  }
  return `${JSON.stringify(sort(value))}\n`;
}

function sha256(bytes: string): string {
  return createHash("sha256").update(bytes, "utf8").digest("hex");
}

function canonicalPlayer(player: { name: string; team: string }) {
  const match = players.find((candidate) => candidate.name === player.name);
  if (!match) {
    throw new Error(
      `Fixture generation could not resolve ${player.name} (${player.team})`,
    );
  }
  return match;
}

function normalizePlayerReferences<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map(normalizePlayerReferences) as T;
  }
  if (typeof value === "string") {
    return value.replaceAll("fixture-", "player-") as T;
  }
  if (!value || typeof value !== "object") return value;
  const object = value as Record<string, unknown>;
  if (
    typeof object.name === "string" &&
    typeof object.team === "string" &&
    typeof object.position === "string" &&
    "id" in object
  ) {
    return canonicalPlayer({
      name: object.name,
      team: object.team,
    }) as T;
  }
  return Object.fromEntries(
    Object.entries(object).map(([key, child]) => [
      key,
      normalizePlayerReferences(child),
    ]),
  ) as T;
}

function productionNeutral<T extends JsonObject>(
  source: T,
  schemaVersion: string,
): JsonObject {
  const {
    fixture: _fixture,
    schemaVersion: _schemaVersion,
    ...content
  } = source;
  return normalizePlayerReferences({
    ...content,
    schemaVersion,
    dataMode: "fixture",
    fixtureNotice,
    sourceVersion,
  });
}

const homeBundle = productionNeutral(
  {
    ...publishedHomeFixture,
    teamSnapshot: teamSnapshotFixture,
    reportLeaderboard: reportLeaderboardFixture,
  },
  "depthsnap.home.v1",
);

const backfieldBundle = productionNeutral(
  backfieldReportFixture as unknown as JsonObject,
  "depthsnap.report.backfield.v1",
);
const targetBundle = productionNeutral(
  targetReportFixture as unknown as JsonObject,
  "depthsnap.report.targets.v1",
);
const movementBundle = productionNeutral(
  movementReportFixture as unknown as JsonObject,
  "depthsnap.report.movement.v1",
);

const reportsIndexBundle = {
  schemaVersion: "depthsnap.reports.index.v1",
  dataMode: "fixture",
  fixtureNotice,
  status: "published",
  season: identityFixtureMetadata.season,
  throughWeek: identityFixtureMetadata.throughWeek,
  generatedAt,
  sourceVersion,
  modules: [
    {
      kind: "current",
      family: "backfield_control",
      title: backfieldReportFixture.title,
      question: "Who owns each team’s documented RB opportunities?",
      description:
        "Player opportunities stay paired with the matching team RB total.",
      href: "/reports/backfield",
      row: normalizePlayerReferences(backfieldReportFixture.views[0].rows[0]),
    },
    {
      kind: "current",
      family: "target_hierarchy",
      title: targetReportFixture.title,
      question: targetReportFixture.question,
      description:
        "WR and TE target evidence uses the supplied team target total.",
      href: "/reports/targets",
      row: normalizePlayerReferences(targetReportFixture.views[0].rows[0]),
    },
    {
      kind: "movement",
      family: "role_movement",
      title: movementReportFixture.title,
      question: "Whose documented role changed most between supplied periods?",
      description:
        "Previous and current evidence remain attached to the supplied movement.",
      href: "/reports/movement",
      row: normalizePlayerReferences(movementReportFixture.views[0].rows[0]),
    },
  ],
};

const publishedTeamBundles = teams.map((team) => {
  const bundle = getTeamBundle(team.id);
  if (!bundle) throw new Error(`Missing generated team source: ${team.id}`);
  return {
    id: team.id,
    bundle: productionNeutral(
      bundle as unknown as JsonObject,
      "depthsnap.team.v1",
    ),
  };
});

const publishedPlayerBundles = players.map((player) => {
  const bundle = getPlayerBundle(player.id);
  if (!bundle) throw new Error(`Missing generated player source: ${player.id}`);
  return {
    id: player.id,
    bundle: productionNeutral(
      bundle as unknown as JsonObject,
      "depthsnap.player.v1",
    ),
  };
});

const teamsIndexBundle = {
  schemaVersion: "depthsnap.teams.index.v1",
  dataMode: "fixture",
  fixtureNotice,
  status: "published",
  season: identityFixtureMetadata.season,
  throughWeek: identityFixtureMetadata.throughWeek,
  generatedAt,
  sourceVersion,
  teams: normalizePlayerReferences(teamDirectoryRecords),
};

const playersIndexBundle = {
  schemaVersion: "depthsnap.players.index.v1",
  dataMode: "fixture",
  fixtureNotice,
  status: "published",
  season: identityFixtureMetadata.season,
  throughWeek: identityFixtureMetadata.throughWeek,
  generatedAt,
  sourceVersion,
  players: normalizePlayerReferences(playerDirectoryRecords),
  teamOptions: teams.map((team) => team.id),
};

const searchBundle = {
  schemaVersion: "depthsnap.search.v1",
  dataMode: "fixture",
  fixtureNotice,
  status: "published",
  season: identityFixtureMetadata.season,
  throughWeek: identityFixtureMetadata.throughWeek,
  generatedAt,
  sourceVersion,
  records: searchIndex,
};

const totalBundleCount =
  1 +
  1 +
  3 +
  1 +
  publishedTeamBundles.length +
  1 +
  publishedPlayerBundles.length +
  1 +
  1;

function statusBundle(state: PublicationState) {
  const published = state === "published";
  return {
    schemaVersion: "depthsnap.status.v1",
    dataMode: "fixture",
    fixtureNotice,
    status: state,
    season: identityFixtureMetadata.season,
    throughWeek: published ? identityFixtureMetadata.throughWeek : null,
    generatedAt,
    sourceVersion,
    formulaVersion: "python-current-role-contract-v1",
    pipelineRunVersion: "synthetic-fixture-build-v1",
    manifestSchemaVersion: "depthsnap.manifest.v1",
    bundleCount: totalBundleCount,
    validationSummary: published
      ? `${totalBundleCount} required fixture bundles passed schema, hash, reference, and record-count validation.`
      : state === "no_published_week"
        ? "The complete fixture bundle set is valid, but it intentionally supplies no published week."
        : "The complete fixture bundle set is valid and intentionally represents an unavailable publication.",
    checks: [
      {
        id: "manifest-integrity",
        label: "Manifest integrity",
        status: published ? "pass" : state === "unavailable" ? "unavailable" : "attention",
        detail: published
          ? "Every required fixture bundle is declared and hashed."
          : "The state bundle is declared and hashed without publishing evidence rows.",
      },
      {
        id: "identity-references",
        label: "Identity references",
        status: published ? "pass" : state === "unavailable" ? "unavailable" : "attention",
        detail: published
          ? "All supplied team and player references resolve to one stable identity."
          : "Identity records remain synthetic and no evidence membership is asserted.",
      },
      {
        id: "raw-share-consistency",
        label: "Raw-share consistency",
        status: published ? "pass" : state === "unavailable" ? "unavailable" : "attention",
        detail: published
          ? "Every supplied share agrees with its raw numerator and denominator."
          : "No share evidence is published in this state.",
      },
    ],
    limitations: [
      "This Phase 4A bundle contains synthetic design-fixture records only.",
      "Current-season participation data is unavailable in-season and is not used.",
      "Current-season injury data is not supplied; partial-game exclusions require a manual reviewed override.",
      "Snap counts and completed-week validation are required before a production week can publish.",
      "The public application is descriptive and does not provide forecasts or recommendations.",
    ],
  };
}

function withoutPublicationEvidence(
  bundle: JsonObject,
  family: string,
  state: Exclude<PublicationState, "published">,
): JsonObject {
  const common: JsonObject = {
    ...bundle,
    status: state,
    throughWeek: null,
  };
  const stateTitle =
    state === "no_published_week"
      ? "No validated week is published"
      : "This evidence bundle is unavailable";
  const stateMessage =
    state === "no_published_week"
      ? "A completed, validated week has not been published for this synthetic bundle."
      : "The selected evidence bundle could not be read. No stale or estimated values are shown.";

  if (family === "home") {
    const {
      leadFinding: _leadFinding,
      findings: _findings,
      teamSnapshot: _teamSnapshot,
      reportLeaderboard: _reportLeaderboard,
      ...metadata
    } = common;
    return {
      ...metadata,
      stateTitle:
        state === "no_published_week"
          ? "No completed week is published yet"
          : "Role data is temporarily unavailable",
      stateMessage:
        state === "no_published_week"
          ? "DepthSnap will show role findings after the authoritative pipeline validates and publishes a completed week."
          : "The published bundle could not be read. No shares or findings are shown until validated data is available again.",
    };
  }
  if (family.startsWith("report_")) {
    return {
      ...common,
      stateTitle:
        state === "no_published_week"
          ? "No completed week is published for this report"
          : "This report bundle is temporarily unavailable",
      stateMessage:
        state === "no_published_week"
          ? "A completed validated week has not been published. No estimated shares are shown."
          : "The report bundle could not be read. No stale or estimated results are shown.",
      resultCount: 0,
      views: [],
    };
  }
  if (family === "reports_index") return { ...common, modules: [] };
  if (family === "teams_index") return { ...common, teams: [] };
  if (family === "players_index") return { ...common, players: [] };
  if (family === "search") {
    return {
      ...common,
      records: (bundle.records as Array<JsonObject>).map((record) => ({
        ...record,
        summary: "Synthetic fixture identity; no published evidence.",
      })),
    };
  }
  if (family === "team") {
    return {
      ...common,
      suppliedSummary: stateMessage,
      backfieldHierarchy: [],
      wrTargetHierarchy: [],
      teTargetHierarchy: [],
      movements: [],
      dataQuality: "unavailable_supporting_context",
    };
  }
  if (family === "player") {
    const {
      currentEvidence: _currentEvidence,
      supportingContext: _supportingContext,
      latestMovement: _latestMovement,
      ...identity
    } = common;
    return {
      ...identity,
      suppliedRoleDescription: stateMessage,
      reportMemberships: [],
      weeklyEvidence: [],
      periodSummaries: [],
      movementHistory: [],
      teamHierarchyContext: [],
      dataQuality: "unavailable_supporting_context",
    };
  }
  return common;
}

type PlannedBundle = {
  family:
    | "home"
    | "reports_index"
    | "report_backfield"
    | "report_targets"
    | "report_movement"
    | "teams_index"
    | "team"
    | "players_index"
    | "player"
    | "search"
    | "status";
  id?: string;
  path: string;
  schemaVersion: string;
  recordCount: number;
  bundle: JsonObject;
};

function publishedPlan(): PlannedBundle[] {
  const plan: PlannedBundle[] = [
    {
      family: "home",
      path: "home.json",
      schemaVersion: "depthsnap.home.v1",
      recordCount: 1 + (homeBundle.findings as unknown[]).length,
      bundle: homeBundle,
    },
    {
      family: "reports_index",
      path: "reports/index.json",
      schemaVersion: "depthsnap.reports.index.v1",
      recordCount: reportsIndexBundle.modules.length,
      bundle: reportsIndexBundle,
    },
    {
      family: "report_backfield",
      path: "reports/backfield.json",
      schemaVersion: "depthsnap.report.backfield.v1",
      recordCount: (backfieldReportFixture.views as unknown as Array<{ rows: unknown[] }>).reduce(
        (count, view) => count + view.rows.length,
        0,
      ),
      bundle: backfieldBundle,
    },
    {
      family: "report_targets",
      path: "reports/targets.json",
      schemaVersion: "depthsnap.report.targets.v1",
      recordCount: (targetReportFixture.views as unknown as Array<{ rows: unknown[] }>).reduce(
        (count, view) => count + view.rows.length,
        0,
      ),
      bundle: targetBundle,
    },
    {
      family: "report_movement",
      path: "reports/movement.json",
      schemaVersion: "depthsnap.report.movement.v1",
      recordCount: (movementReportFixture.views as unknown as Array<{ rows: unknown[] }>).reduce(
        (count, view) => count + view.rows.length,
        0,
      ),
      bundle: movementBundle,
    },
    {
      family: "teams_index",
      path: "teams/index.json",
      schemaVersion: "depthsnap.teams.index.v1",
      recordCount: teamDirectoryRecords.length,
      bundle: teamsIndexBundle,
    },
    ...publishedTeamBundles.map(({ id, bundle }) => ({
      family: "team" as const,
      id,
      path: `teams/${id}.json`,
      schemaVersion: "depthsnap.team.v1",
      recordCount: (bundle.linkedPlayers as unknown[]).length,
      bundle,
    })),
    {
      family: "players_index",
      path: "players/index.json",
      schemaVersion: "depthsnap.players.index.v1",
      recordCount: playerDirectoryRecords.length,
      bundle: playersIndexBundle,
    },
    ...publishedPlayerBundles.map(({ id, bundle }) => ({
      family: "player" as const,
      id,
      path: `players/${id}.json`,
      schemaVersion: "depthsnap.player.v1",
      recordCount: (bundle.weeklyEvidence as unknown[]).length,
      bundle,
    })),
    {
      family: "search",
      path: "search.json",
      schemaVersion: "depthsnap.search.v1",
      recordCount: searchIndex.length,
      bundle: searchBundle,
    },
    {
      family: "status",
      path: "status.json",
      schemaVersion: "depthsnap.status.v1",
      recordCount: statusBundle("published").checks.length,
      bundle: statusBundle("published"),
    },
  ];
  return plan;
}

function planForState(state: PublicationState): PlannedBundle[] {
  const plan = publishedPlan();
  if (state === "published") return plan;
  return plan.map((item) => {
    const bundle: JsonObject =
      item.family === "status"
        ? (statusBundle(state) as JsonObject)
        : withoutPublicationEvidence(item.bundle, item.family, state);
    const recordCount =
      item.family === "status"
        ? (bundle.checks as unknown[]).length
        : item.family === "search"
          ? (bundle.records as unknown[]).length
          : item.family === "team"
            ? (bundle.linkedPlayers as unknown[]).length
            : 0;
    return { ...item, bundle, recordCount };
  });
}

async function writeStateDirectory(
  directoryName: string,
  state: PublicationState,
) {
  const target = path.join(dataRoot, directoryName);
  await rm(target, { recursive: true, force: true });
  await mkdir(target, { recursive: true });
  const entries = [];
  for (const item of planForState(state)) {
    const output = sortedJson(item.bundle);
    const destination = path.join(target, ...item.path.split("/"));
    await mkdir(path.dirname(destination), { recursive: true });
    await writeFile(destination, output, "utf8");
    entries.push({
      family: item.family,
      ...(item.id ? { id: item.id } : {}),
      path: item.path,
      schemaVersion: item.schemaVersion,
      sha256: sha256(output),
      required: true,
      recordCount: item.recordCount,
    });
  }
  const manifest = {
    schemaVersion: "depthsnap.manifest.v1",
    dataMode: "fixture",
    generatedAt,
    sourceVersion,
    entries,
  };
  await writeFile(path.join(target, "manifest.json"), sortedJson(manifest), "utf8");
}

async function main() {
  await writeStateDirectory("fixture", "published");
  await writeStateDirectory("fixture-no-published-week", "no_published_week");
  await writeStateDirectory("fixture-unavailable", "unavailable");
  console.log(
    `Generated ${totalBundleCount} deterministic bundles for each of 3 fixture publication states.`,
  );
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
