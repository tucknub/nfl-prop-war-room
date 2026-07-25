import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import type { ZodType } from "zod";
import {
  BundleSchemas,
  type BundleFamily,
  type DataMode,
  type LoaderFailure,
  type Manifest,
  type ManifestEntry,
  ManifestSchema,
} from "@/lib/data-contract";

type RegistryBundle = Record<string, unknown>;

export type PublicationVariant =
  | "published"
  | "no_published_week"
  | "unavailable";

export type DepthSnapRegistry = {
  manifest: Manifest;
  mode: DataMode;
  directory: string;
  bundles: ReadonlyMap<string, RegistryBundle>;
  loadMetrics: RegistryLoadMetrics;
};

export type RegistryLoadMetrics = {
  filesRead: number;
  bytesRead: number;
  entriesValidated: number;
  durationMs: number;
};

export type RegistryResult =
  | { ok: true; registry: DepthSnapRegistry }
  | { ok: false; failure: LoaderFailure };

export type RegistryOptions = {
  mode?: string;
  allowFixtureDefault?: boolean;
  publicationVariant?: PublicationVariant;
  dataRoot?: string;
  readTextFile?: (filePath: string) => Promise<string>;
};

const expectedSchemaVersions: Record<BundleFamily, string> = {
  home: "depthsnap.home.v1",
  reports_index: "depthsnap.reports.index.v1",
  report_backfield: "depthsnap.report.backfield.v1",
  report_targets: "depthsnap.report.targets.v1",
  report_movement: "depthsnap.report.movement.v1",
  teams_index: "depthsnap.teams.index.v1",
  team: "depthsnap.team.v1",
  players_index: "depthsnap.players.index.v1",
  player: "depthsnap.player.v1",
  search: "depthsnap.search.v1",
  status: "depthsnap.status.v1",
};

function fail(
  category: LoaderFailure["category"],
  title: string,
  message: string,
  publicDetail: string,
): RegistryResult {
  return {
    ok: false,
    failure: { category, title, message, publicDetail },
  };
}

function bundleKey(family: BundleFamily, id?: string): string {
  return id ? `${family}:${id}` : family;
}

function safeDirectoryName(
  mode: DataMode,
  variant: PublicationVariant,
): string {
  if (mode === "export") return "export";
  if (variant === "no_published_week") return "fixture-no-published-week";
  if (variant === "unavailable") return "fixture-unavailable";
  return "fixture";
}

function expectedPath(entry: ManifestEntry): string {
  if (entry.family === "team") return `teams/${entry.id}.json`;
  if (entry.family === "player") return `players/${entry.id}.json`;
  return {
    home: "home.json",
    reports_index: "reports/index.json",
    report_backfield: "reports/backfield.json",
    report_targets: "reports/targets.json",
    report_movement: "reports/movement.json",
    teams_index: "teams/index.json",
    players_index: "players/index.json",
    search: "search.json",
    status: "status.json",
  }[entry.family];
}

function countRecords(family: BundleFamily, bundle: RegistryBundle): number {
  if (family === "home") {
    return bundle.status === "published"
      ? 1 + (bundle.findings as unknown[]).length
      : 0;
  }
  if (family === "reports_index")
    return (bundle.modules as unknown[]).length;
  if (
    family === "report_backfield" ||
    family === "report_targets" ||
    family === "report_movement"
  ) {
    return (bundle.views as Array<{ rows: unknown[] }>).reduce(
      (count, view) => count + view.rows.length,
      0,
    );
  }
  if (family === "teams_index") return (bundle.teams as unknown[]).length;
  if (family === "team") return (bundle.linkedPlayers as unknown[]).length;
  if (family === "players_index") return (bundle.players as unknown[]).length;
  if (family === "player") return (bundle.weeklyEvidence as unknown[]).length;
  if (family === "search") return (bundle.records as unknown[]).length;
  return (bundle.checks as unknown[]).length;
}

function sameEvidence(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function validateUnique<T>(
  values: readonly T[],
  label: string,
): RegistryResult | undefined {
  if (new Set(values).size !== values.length) {
    return fail(
      "unresolved_reference",
      "Duplicate identity",
      `The selected bundle set contains a duplicate ${label}.`,
      `A duplicate ${label} prevented this fixture from being published.`,
    );
  }
}

function validateReferences(
  bundles: ReadonlyMap<string, RegistryBundle>,
): RegistryResult | undefined {
  const teamBundles = [...bundles.entries()]
    .filter(([key]) => key.startsWith("team:"))
    .map(([, bundle]) => bundle);
  const playerBundles = [...bundles.entries()]
    .filter(([key]) => key.startsWith("player:"))
    .map(([, bundle]) => bundle);
  const teamIds = teamBundles.map(
    (bundle) => (bundle.team as { id: string }).id,
  );
  const playerIds = playerBundles.map(
    (bundle) => (bundle.player as { id: string }).id,
  );
  const duplicateTeam = validateUnique(teamIds, "team ID");
  if (duplicateTeam) return duplicateTeam;
  const duplicatePlayer = validateUnique(playerIds, "player ID");
  if (duplicatePlayer) return duplicatePlayer;

  const teamSet = new Set(teamIds);
  const playerSet = new Set(playerIds);
  const checkPlayer = (player: unknown, context: string) => {
    const identity = player as { id?: string; teamId?: string };
    if (!identity?.id || !playerSet.has(identity.id)) {
      return fail(
        "unresolved_reference",
        "Unresolved player reference",
        `${context} references an unknown player.`,
        "A player reference did not resolve to the supplied identity bundle.",
      );
    }
    if (!identity.teamId || !teamSet.has(identity.teamId)) {
      return fail(
        "unresolved_reference",
        "Unresolved team reference",
        `${context} references an unknown team.`,
        "A team reference did not resolve to the supplied identity bundle.",
      );
    }
  };

  for (const bundle of playerBundles) {
    const playerFailure = checkPlayer(bundle.player, "Player dossier");
    if (playerFailure) return playerFailure;
    const currentTeam = bundle.currentTeam as { id?: string };
    if (!currentTeam?.id || !teamSet.has(currentTeam.id)) {
      return fail(
        "unresolved_reference",
        "Unresolved current team",
        "A player dossier references an unknown current team.",
        "The supplied current-team identity could not be resolved.",
      );
    }
  }

  const playerContainers: Array<[string, unknown[]]> = [];
  const home = bundles.get("home");
  if (home?.status === "published") {
    playerContainers.push([
      "Home",
      [
        (home.leadFinding as { player: unknown }).player,
        ...(home.findings as Array<{ player: unknown }>).map(
          (finding) => finding.player,
        ),
      ],
    ]);
  }
  for (const family of [
    "report_backfield",
    "report_targets",
    "report_movement",
  ]) {
    const report = bundles.get(family);
    if (report?.status === "published") {
      playerContainers.push([
        family,
        (report.views as Array<{ rows: Array<{ player: unknown }> }>).flatMap(
          (view) => view.rows.map((row) => row.player),
        ),
      ]);
    }
  }
  for (const bundle of teamBundles) {
    playerContainers.push([
      `Team ${(bundle.team as { id: string }).id}`,
      [
        ...(bundle.linkedPlayers as unknown[]),
        ...(bundle.backfieldHierarchy as Array<{ player: unknown }>).map(
          (row) => row.player,
        ),
        ...(bundle.wrTargetHierarchy as Array<{ player: unknown }>).map(
          (row) => row.player,
        ),
        ...(bundle.teTargetHierarchy as Array<{ player: unknown }>).map(
          (row) => row.player,
        ),
        ...(bundle.movements as Array<{ player: unknown }>).map(
          (row) => row.player,
        ),
      ],
    ]);
  }
  for (const [context, identities] of playerContainers) {
    for (const identity of identities) {
      const referenceFailure = checkPlayer(identity, context);
      if (referenceFailure) return referenceFailure;
    }
  }

  const currentByReport = new Map<
    string,
    { evidence: unknown; roleFamily: string }
  >();
  for (const family of ["report_backfield", "report_targets"] as const) {
    const report = bundles.get(family);
    if (report?.status !== "published") continue;
    const firstView = (
      report.views as Array<{
        rows: Array<{
          player: { id: string };
          roleFamily: string;
          current: unknown;
        }>;
      }>
    )[0];
    for (const row of firstView?.rows ?? []) {
      currentByReport.set(row.player.id, {
        evidence: row.current,
        roleFamily: row.roleFamily,
      });
    }
  }
  const movementReport = bundles.get("report_movement");
  const movementByPlayer = new Map<string, unknown>();
  if (movementReport?.status === "published") {
    const firstView = (
      movementReport.views as Array<{
        rows: Array<{ player: { id: string }; movement: unknown }>;
      }>
    )[0];
    for (const row of firstView?.rows ?? []) {
      movementByPlayer.set(row.player.id, row.movement);
    }
  }
  for (const bundle of playerBundles) {
    if (bundle.status !== "published") continue;
    const playerId = (bundle.player as { id: string }).id;
    const current = currentByReport.get(playerId);
    if (
      current &&
      bundle.currentEvidence &&
      !sameEvidence(current.evidence, bundle.currentEvidence)
    ) {
      return fail(
        "manifest_mismatch",
        "Cross-route evidence mismatch",
        `Current evidence for ${playerId} differs between report and player bundles.`,
        "Supplied evidence is inconsistent across public routes.",
      );
    }
    const movement = movementByPlayer.get(playerId);
    if (
      movement &&
      bundle.latestMovement &&
      !sameEvidence(
        movement,
        (bundle.latestMovement as { movement: unknown }).movement,
      )
    ) {
      return fail(
        "manifest_mismatch",
        "Cross-route movement mismatch",
        `Movement evidence for ${playerId} differs between report and player bundles.`,
        "Supplied movement evidence is inconsistent across public routes.",
      );
    }
  }
}

function resolveMode(
  value: string | undefined,
  allowFixtureDefault = false,
): DataMode | undefined {
  if (!value && allowFixtureDefault) return "fixture";
  if (value === "fixture" || value === "export") return value;
}

export async function loadDepthSnapRegistry(
  options: RegistryOptions = {},
): Promise<RegistryResult> {
  const mode = resolveMode(options.mode, options.allowFixtureDefault);
  if (!mode) {
    return fail(
      "unsupported_data_mode",
      "Unsupported data mode",
      "DEPTHSNAP_DATA_MODE must be fixture or export.",
      "The application data mode is not supported.",
    );
  }
  const variant = options.publicationVariant ?? "published";
  const dataRoot =
    options.dataRoot ??
    path.join("public", "data", "depthsnap");
  const directory = path.join(dataRoot, safeDirectoryName(mode, variant));
  const startedAt = performance.now();
  let filesRead = 0;
  let bytesRead = 0;
  const readTextFile = async (filePath: string) => {
    const bytes = options.readTextFile
      ? await options.readTextFile(filePath)
      : await readFile(filePath, "utf8");
    filesRead += 1;
    bytesRead += Buffer.byteLength(bytes, "utf8");
    return bytes;
  };
  const manifestPath = path.join(directory, "manifest.json");
  let manifestBytes: string;
  try {
    manifestBytes = await readTextFile(manifestPath);
  } catch {
    return fail(
      "bundle_missing",
      "Data manifest unavailable",
      `The ${mode} manifest could not be read.`,
      `The selected ${mode} bundle set is unavailable. No fallback data was used.`,
    );
  }

  let manifestInput: unknown;
  try {
    manifestInput = JSON.parse(manifestBytes);
  } catch {
    return fail(
      "invalid_json",
      "Invalid data manifest",
      "The selected manifest is not valid JSON.",
      "The data manifest could not be parsed.",
    );
  }
  const manifestResult = ManifestSchema.safeParse(manifestInput);
  if (!manifestResult.success) {
    const version = (manifestInput as { schemaVersion?: unknown })
      ?.schemaVersion;
    return fail(
      version !== "depthsnap.manifest.v1"
        ? "incompatible_schema"
        : "invalid_bundle",
      "Invalid data manifest",
      "The selected manifest failed runtime validation.",
      "The data manifest is incompatible with this application build.",
    );
  }
  const manifest = manifestResult.data;
  if (manifest.dataMode !== mode) {
    return fail(
      "manifest_mismatch",
      "Manifest mode mismatch",
      `The ${mode} loader received a ${manifest.dataMode} manifest.`,
      "The data manifest does not match the selected application mode.",
    );
  }

  const manifestKeys = manifest.entries.map((entry) =>
    bundleKey(entry.family, entry.id),
  );
  const duplicateEntry = validateUnique(manifestKeys, "manifest entry");
  if (duplicateEntry) return duplicateEntry;
  const bundles = new Map<string, RegistryBundle>();
  for (const entry of manifest.entries) {
    if (!entry.required) {
      return fail(
        "manifest_mismatch",
        "Optional public bundle is unsupported",
        `${bundleKey(entry.family, entry.id)} is declared optional.`,
        "Every V1 public bundle must be declared as required.",
      );
    }
    if (
      (entry.family === "team" || entry.family === "player") !==
      Boolean(entry.id)
    ) {
      return fail(
        "manifest_mismatch",
        "Invalid manifest identity",
        "Team and player entries require exactly one stable ID.",
        "A manifest identity entry is incomplete.",
      );
    }
    if (entry.path !== expectedPath(entry)) {
      return fail(
        "manifest_mismatch",
        "Manifest path mismatch",
        `The declared path for ${bundleKey(entry.family, entry.id)} is not canonical.`,
        "A bundle path does not match its declared family.",
      );
    }
    const expectedVersion = expectedSchemaVersions[entry.family];
    if (entry.schemaVersion !== expectedVersion) {
      return fail(
        "incompatible_schema",
        "Unsupported bundle schema",
        `The manifest declares ${entry.schemaVersion} for ${entry.family}.`,
        "A required bundle uses an unsupported schema version.",
      );
    }
    let bytes: string;
    try {
      bytes = await readTextFile(
        path.join(directory, ...entry.path.split("/")),
      );
    } catch {
      return fail(
        "bundle_missing",
        "Required bundle unavailable",
        `The required ${bundleKey(entry.family, entry.id)} bundle is missing.`,
        "A required data bundle could not be read.",
      );
    }
    const observedHash = createHash("sha256")
      .update(bytes, "utf8")
      .digest("hex");
    if (observedHash !== entry.sha256) {
      return fail(
        "hash_mismatch",
        "Bundle integrity check failed",
        `The SHA-256 hash for ${bundleKey(entry.family, entry.id)} does not match its manifest.`,
        "A data bundle failed its integrity check.",
      );
    }
    let input: unknown;
    try {
      input = JSON.parse(bytes);
    } catch {
      return fail(
        "invalid_json",
        "Invalid bundle JSON",
        `${bundleKey(entry.family, entry.id)} is not valid JSON.`,
        "A required data bundle could not be parsed.",
      );
    }
    const inputVersion = (input as { schemaVersion?: unknown })?.schemaVersion;
    if (inputVersion !== expectedVersion) {
      return fail(
        "incompatible_schema",
        "Unsupported bundle schema",
        `${bundleKey(entry.family, entry.id)} uses ${String(inputVersion)}.`,
        "A required data bundle uses an unsupported schema version.",
      );
    }
    const schema = BundleSchemas[entry.family] as ZodType<RegistryBundle>;
    const parsed = schema.safeParse(input);
    if (!parsed.success) {
      return fail(
        "invalid_bundle",
        "Bundle validation failed",
        `${bundleKey(entry.family, entry.id)} failed runtime validation.`,
        "A required data bundle contains invalid fields or evidence.",
      );
    }
    if (parsed.data.dataMode !== mode) {
      return fail(
        "manifest_mismatch",
        "Bundle mode mismatch",
        `${bundleKey(entry.family, entry.id)} does not match ${mode} mode.`,
        "A required bundle does not match the selected application mode.",
      );
    }
    const observedCount = countRecords(entry.family, parsed.data);
    if (observedCount !== entry.recordCount) {
      return fail(
        "manifest_mismatch",
        "Bundle record-count mismatch",
        `${bundleKey(entry.family, entry.id)} contains ${observedCount} records; ${entry.recordCount} were declared.`,
        "A required bundle does not match its declared record count.",
      );
    }
    bundles.set(bundleKey(entry.family, entry.id), parsed.data);
  }

  for (const requiredFamily of [
    "home",
    "reports_index",
    "report_backfield",
    "report_targets",
    "report_movement",
    "teams_index",
    "players_index",
    "search",
    "status",
  ] as const) {
    if (!bundles.has(requiredFamily)) {
      return fail(
        "bundle_missing",
        "Required bundle not declared",
        `The manifest does not declare ${requiredFamily}.`,
        "A required data family is missing from the manifest.",
      );
    }
  }

  const statusBundle = bundles.get("status");
  const suppliedStatus = statusBundle?.status;
  if (
    !statusBundle ||
    statusBundle.bundleCount !== manifest.entries.length ||
    suppliedStatus !== manifest.publicationStatus ||
    statusBundle.season !== manifest.season ||
    statusBundle.throughWeek !== manifest.throughWeek ||
    statusBundle.generatedAt !== manifest.generatedAt ||
    statusBundle.sourceVersion !== manifest.sourceVersion ||
    statusBundle.formulaVersion !== manifest.formulaVersion ||
    statusBundle.pipelineRunId !== manifest.pipelineRunId ||
    [...bundles.values()].some(
      (bundle) =>
        bundle.status !== suppliedStatus ||
        bundle.season !== manifest.season ||
        bundle.throughWeek !== manifest.throughWeek ||
        bundle.generatedAt !== manifest.generatedAt ||
        bundle.sourceVersion !== manifest.sourceVersion,
    )
  ) {
    return fail(
      "manifest_mismatch",
      "Publication metadata mismatch",
      "Bundle count or publication state differs across the selected registry.",
      "The selected bundle set does not share one supplied publication state.",
    );
  }

  const referenceFailure = validateReferences(bundles);
  if (referenceFailure) return referenceFailure;
  return {
    ok: true,
    registry: {
      manifest,
      mode,
      directory,
      bundles,
      loadMetrics: {
        filesRead,
        bytesRead,
        entriesValidated: manifest.entries.length,
        durationMs: Number((performance.now() - startedAt).toFixed(3)),
      },
    },
  };
}

export function getRegistryBundle(
  registry: DepthSnapRegistry,
  family: BundleFamily,
  id?: string,
): RegistryBundle | undefined {
  return registry.bundles.get(bundleKey(family, id));
}
