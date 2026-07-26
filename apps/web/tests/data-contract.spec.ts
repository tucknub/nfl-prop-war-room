import { createHash } from "node:crypto";
import {
  cp,
  mkdtemp,
  readFile,
  rm,
  unlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { expect, test } from "@playwright/test";
import type { Manifest } from "../src/lib/data-contract";
import {
  getRegistryCacheMetrics,
  loadCachedDepthSnapRegistry,
  resetRegistryCacheForTests,
} from "../src/lib/data-registry-cache";
import {
  loadDepthSnapRegistry,
  type PublicationVariant,
} from "../src/lib/data-registry-core";
import { resolveRuntimeDataConfiguration } from "../src/lib/runtime-config";

const fixtureSource = path.resolve(
  process.cwd(),
  "public",
  "data",
  "depthsnap",
  "fixture",
);
const historicalExportSource = path.resolve(
  process.cwd(),
  "public",
  "data",
  "depthsnap",
  "export-historical-2025",
);

async function temporaryDataRoot() {
  const temporaryRoot = await mkdtemp(
    path.join(tmpdir(), "depthsnap-contract-"),
  );
  const dataRoot = path.join(temporaryRoot, "depthsnap");
  await cp(fixtureSource, path.join(dataRoot, "fixture"), {
    recursive: true,
  });
  return { temporaryRoot, dataRoot };
}

async function temporaryExportDataRoot(source: string) {
  const temporaryRoot = await mkdtemp(
    path.join(tmpdir(), "depthsnap-export-contract-"),
  );
  const dataRoot = path.join(temporaryRoot, "depthsnap");
  await cp(source, path.join(dataRoot, "export"), { recursive: true });
  return { temporaryRoot, dataRoot };
}

async function readManifest(dataRoot: string) {
  const manifestPath = path.join(dataRoot, "fixture", "manifest.json");
  return {
    manifestPath,
    manifest: JSON.parse(await readFile(manifestPath, "utf8")) as Manifest,
  };
}

async function writeManifest(manifestPath: string, manifest: Manifest) {
  await writeFile(manifestPath, `${JSON.stringify(manifest)}\n`, "utf8");
}

async function mutateBundle(
  dataRoot: string,
  family: string,
  mutate: (bundle: Record<string, unknown>) => void,
  id?: string,
) {
  const { manifestPath, manifest } = await readManifest(dataRoot);
  const entry = manifest.entries.find(
    (candidate) => candidate.family === family && candidate.id === id,
  );
  if (!entry) throw new Error(`Missing test entry ${family}:${id ?? ""}`);
  const bundlePath = path.join(
    dataRoot,
    "fixture",
    ...entry.path.split("/"),
  );
  const bundle = JSON.parse(
    await readFile(bundlePath, "utf8"),
  ) as Record<string, unknown>;
  mutate(bundle);
  const bytes = `${JSON.stringify(bundle)}\n`;
  await writeFile(bundlePath, bytes, "utf8");
  entry.sha256 = createHash("sha256").update(bytes).digest("hex");
  await writeManifest(manifestPath, manifest);
}

test("all three complete fixture registries validate with deterministic hashes", async () => {
  for (const publicationVariant of [
    "published",
    "no_published_week",
    "unavailable",
  ] as PublicationVariant[]) {
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      publicationVariant,
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.registry.manifest.entries).toHaveLength(44);
      expect(result.registry.manifest).toMatchObject({
        productId: "depthsnap",
        publicationStatus:
          publicationVariant === "published"
            ? "published"
            : publicationVariant,
        validationResult:
          publicationVariant === "unavailable" ? "not_applicable" : "pass",
        season: 2025,
        throughWeek: publicationVariant === "published" ? 18 : null,
        formulaVersion: "python-current-role-contract-v1",
        pipelineRunId: "synthetic-fixture-build-v1",
      });
      expect(
        new Set(result.registry.manifest.entries.map((entry) => entry.sha256))
          .size,
      ).toBe(44);
      expect(result.registry.bundles.get("status")?.status).toBe(
        publicationVariant === "published"
          ? "published"
          : publicationVariant,
      );
      const checks = result.registry.bundles.get("status")
        ?.checks as Array<Record<string, unknown>>;
      expect(checks).toHaveLength(3);
      expect(checks[0]).toMatchObject({
        required: true,
        blocking: true,
        numerator: 44,
        denominator: 44,
        percentage: 100,
      });
    }
  }
});

test("production mode is explicit and the development fixture default is opt-in", async () => {
  const productionUnset = await loadDepthSnapRegistry();
  expect(productionUnset).toMatchObject({
    ok: false,
    failure: { category: "unsupported_data_mode" },
  });

  const developmentDefault = await loadDepthSnapRegistry({
    allowFixtureDefault: true,
  });
  expect(developmentDefault).toMatchObject({
    ok: true,
    registry: { mode: "fixture" },
  });
});

test("production runtime requires export mode and the approved data root", () => {
  const cwd = path.resolve(process.cwd());
  expect(resolveRuntimeDataConfiguration({ NODE_ENV: "production" }, cwd)).toMatchObject({
    ok: false,
    failure: { category: "unsupported_data_mode" },
  });
  expect(
    resolveRuntimeDataConfiguration(
      { NODE_ENV: "production", DEPTHSNAP_DATA_MODE: "export" },
      cwd,
    ),
  ).toMatchObject({
    ok: false,
    failure: { category: "unsupported_data_mode" },
  });
  expect(
    resolveRuntimeDataConfiguration(
      {
        NODE_ENV: "production",
        DEPTHSNAP_DATA_MODE: "export",
        DEPTHSNAP_DATA_ROOT: "artifacts/test-data",
      },
      cwd,
    ),
  ).toMatchObject({
    ok: false,
    failure: { category: "unsupported_data_mode" },
  });

  const valid = resolveRuntimeDataConfiguration(
    {
      NODE_ENV: "production",
      DEPTHSNAP_DATA_MODE: "export",
      DEPTHSNAP_DATA_ROOT: "public/data/depthsnap",
    },
    cwd,
  );
  expect(valid).toEqual({
    ok: true,
    mode: "export",
    dataRoot: path.resolve(cwd, "public", "data", "depthsnap"),
    allowFixtureDefault: false,
  });
});

test("validated registries are cached for the process lifetime after one cold load", async () => {
  resetRegistryCacheForTests();
  const cold = await loadCachedDepthSnapRegistry({
    mode: "fixture",
    publicationVariant: "published",
  });
  expect(cold.ok).toBe(true);
  if (!cold.ok) return;
  expect(cold.registry.loadMetrics).toMatchObject({
    filesRead: 45,
    entriesValidated: 44,
  });
  expect(cold.registry.loadMetrics.bytesRead).toBeGreaterThan(0);

  const warm = await loadCachedDepthSnapRegistry({
    mode: "fixture",
    publicationVariant: "published",
  });
  expect(warm.ok).toBe(true);
  if (!warm.ok) return;
  expect(warm.registry).toBe(cold.registry);
  expect(getRegistryCacheMetrics()).toEqual({
    entries: 1,
    hits: 1,
    misses: 1,
  });
});

test("status coverage and manifest run metadata fail closed when inconsistent", async () => {
  const coverageCase = await temporaryDataRoot();
  try {
    await mutateBundle(coverageCase.dataRoot, "status", (bundle) => {
      const checks = bundle.checks as Array<{ percentage?: number }>;
      checks[0].percentage = 99;
    });
    const coverageResult = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: coverageCase.dataRoot,
    });
    expect(coverageResult).toMatchObject({
      ok: false,
      failure: { category: "invalid_bundle" },
    });
  } finally {
    await rm(coverageCase.temporaryRoot, { recursive: true, force: true });
  }

  const runCase = await temporaryDataRoot();
  try {
    const { manifestPath, manifest } = await readManifest(runCase.dataRoot);
    manifest.pipelineRunId = "different-run";
    await writeManifest(manifestPath, manifest);
    const runResult = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: runCase.dataRoot,
    });
    expect(runResult).toMatchObject({
      ok: false,
      failure: { category: "manifest_mismatch" },
    });
  } finally {
    await rm(runCase.temporaryRoot, { recursive: true, force: true });
  }
});

test("raw share/count inconsistency fails closed", async () => {
  const { temporaryRoot, dataRoot } = await temporaryDataRoot();
  try {
    await mutateBundle(dataRoot, "report_backfield", (bundle) => {
      const views = bundle.views as Array<{
        rows: Array<{ current: { share: number } }>;
      }>;
      views[0].rows[0].current.share = 0.2;
    });
    const result = await loadDepthSnapRegistry({ mode: "fixture", dataRoot });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "invalid_bundle" },
    });
  } finally {
    await rm(temporaryRoot, { recursive: true, force: true });
  }
});

test("duplicate player/team IDs and unresolved team references fail closed", async () => {
  const first = await temporaryDataRoot();
  try {
    await mutateBundle(
      first.dataRoot,
      "player",
      (bundle) => {
        (bundle.player as { id: string }).id = "player-marcus-hale";
      },
      "player-elijah-north",
    );
    const duplicate = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: first.dataRoot,
    });
    expect(duplicate).toMatchObject({
      ok: false,
      failure: { category: "unresolved_reference" },
    });
  } finally {
    await rm(first.temporaryRoot, { recursive: true, force: true });
  }

  const second = await temporaryDataRoot();
  try {
    await mutateBundle(
      second.dataRoot,
      "player",
      (bundle) => {
        (bundle.currentTeam as { id: string }).id = "UNKNOWN";
      },
      "player-marcus-hale",
    );
    const unresolved = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: second.dataRoot,
    });
    expect(unresolved).toMatchObject({
      ok: false,
      failure: { category: "unresolved_reference" },
    });
  } finally {
    await rm(second.temporaryRoot, { recursive: true, force: true });
  }

  const third = await temporaryDataRoot();
  try {
    await mutateBundle(
      third.dataRoot,
      "team",
      (bundle) => {
        (bundle.team as { id: string }).id = "JVT";
      },
      "PDX",
    );
    const duplicateTeam = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: third.dataRoot,
    });
    expect(duplicateTeam).toMatchObject({
      ok: false,
      failure: { category: "unresolved_reference" },
    });
  } finally {
    await rm(third.temporaryRoot, { recursive: true, force: true });
  }
});

test("unsupported schema, wrong family path, and invalid JSON are distinct failures", async () => {
  const schemaCase = await temporaryDataRoot();
  try {
    const { manifestPath, manifest } = await readManifest(schemaCase.dataRoot);
    const entry = manifest.entries.find((item) => item.family === "home");
    if (!entry) throw new Error("Missing home entry");
    entry.schemaVersion = "depthsnap.home.v999";
    await writeManifest(manifestPath, manifest);
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: schemaCase.dataRoot,
    });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "incompatible_schema" },
    });
  } finally {
    await rm(schemaCase.temporaryRoot, { recursive: true, force: true });
  }

  const familyCase = await temporaryDataRoot();
  try {
    const { manifestPath, manifest } = await readManifest(familyCase.dataRoot);
    const entry = manifest.entries.find((item) => item.family === "home");
    if (!entry) throw new Error("Missing home entry");
    entry.path = "reports/index.json";
    await writeManifest(manifestPath, manifest);
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: familyCase.dataRoot,
    });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "manifest_mismatch" },
    });
  } finally {
    await rm(familyCase.temporaryRoot, { recursive: true, force: true });
  }

  const jsonCase = await temporaryDataRoot();
  try {
    const { manifestPath, manifest } = await readManifest(jsonCase.dataRoot);
    const entry = manifest.entries.find(
      (item) => item.family === "reports_index",
    );
    if (!entry) throw new Error("Missing reports index entry");
    const bundlePath = path.join(
      jsonCase.dataRoot,
      "fixture",
      ...entry.path.split("/"),
    );
    const bytes = "{not-json\n";
    await writeFile(bundlePath, bytes, "utf8");
    entry.sha256 = createHash("sha256").update(bytes).digest("hex");
    await writeManifest(manifestPath, manifest);
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: jsonCase.dataRoot,
    });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "invalid_json" },
    });
  } finally {
    await rm(jsonCase.temporaryRoot, { recursive: true, force: true });
  }
});

test("missing files, hash mismatches, and record-count mismatches fail closed", async () => {
  const missingCase = await temporaryDataRoot();
  try {
    const { manifest } = await readManifest(missingCase.dataRoot);
    const entry = manifest.entries.find((item) => item.family === "search");
    if (!entry) throw new Error("Missing search entry");
    await unlink(
      path.join(
        missingCase.dataRoot,
        "fixture",
        ...entry.path.split("/"),
      ),
    );
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: missingCase.dataRoot,
    });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "bundle_missing" },
    });
  } finally {
    await rm(missingCase.temporaryRoot, { recursive: true, force: true });
  }

  const hashCase = await temporaryDataRoot();
  try {
    const { manifest } = await readManifest(hashCase.dataRoot);
    const entry = manifest.entries.find((item) => item.family === "home");
    if (!entry) throw new Error("Missing home entry");
    await writeFile(
      path.join(hashCase.dataRoot, "fixture", ...entry.path.split("/")),
      "{}\n",
      "utf8",
    );
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: hashCase.dataRoot,
    });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "hash_mismatch" },
    });
  } finally {
    await rm(hashCase.temporaryRoot, { recursive: true, force: true });
  }

  const countCase = await temporaryDataRoot();
  try {
    const { manifestPath, manifest } = await readManifest(countCase.dataRoot);
    const entry = manifest.entries.find(
      (item) => item.family === "teams_index",
    );
    if (!entry) throw new Error("Missing teams index entry");
    entry.recordCount += 1;
    await writeManifest(manifestPath, manifest);
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: countCase.dataRoot,
    });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "manifest_mismatch" },
    });
  } finally {
    await rm(countCase.temporaryRoot, { recursive: true, force: true });
  }

  const declarationCase = await temporaryDataRoot();
  try {
    const { manifestPath, manifest } = await readManifest(
      declarationCase.dataRoot,
    );
    manifest.entries = manifest.entries.filter(
      (entry) => entry.family !== "report_movement",
    );
    await writeManifest(manifestPath, manifest);
    const result = await loadDepthSnapRegistry({
      mode: "fixture",
      dataRoot: declarationCase.dataRoot,
    });
    expect(result).toMatchObject({
      ok: false,
      failure: { category: "bundle_missing" },
    });
  } finally {
    await rm(declarationCase.temporaryRoot, {
      recursive: true,
      force: true,
    });
  }
});

test("fixture and export modes are isolated without silent fallback", async () => {
  const activeExport = await loadDepthSnapRegistry({ mode: "export" });
  expect(activeExport.ok).toBe(true);
  if (activeExport.ok) {
    expect(activeExport.registry.manifest).toMatchObject({
      dataMode: "export",
      publicationStatus: "no_published_week",
      season: 2026,
      throughWeek: null,
      validationResult: "pass",
    });
    expect(activeExport.registry.manifest.entries).toHaveLength(9);
    expect(activeExport.registry.bundles.get("status")).toMatchObject({
      dataMode: "export",
      status: "no_published_week",
      season: 2026,
      bundleCount: 9,
    });
    expect(activeExport.registry.bundles.get("players_index")).toMatchObject({
      players: [],
    });
  }

  const historicalCase = await temporaryExportDataRoot(
    historicalExportSource,
  );
  try {
    const historical = await loadDepthSnapRegistry({
      mode: "export",
      dataRoot: historicalCase.dataRoot,
    });
    expect(historical.ok).toBe(true);
    if (historical.ok) {
      expect(historical.registry.manifest).toMatchObject({
        dataMode: "export",
        publicationStatus: "published",
        season: 2025,
        throughWeek: 18,
        validationResult: "pass",
      });
      expect(historical.registry.manifest.entries).toHaveLength(586);
      expect(
        historical.registry.bundles.get("team:ATL"),
      ).toBeDefined();

      const playerBundles = [...historical.registry.bundles.entries()]
        .filter(([key]) => key.startsWith("player:"))
        .map(([, bundle]) => bundle);
      expect(playerBundles).toHaveLength(545);
      let transferredEvidenceRows = 0;
      for (const bundle of playerBundles) {
        const player = bundle.player as Record<string, unknown>;
        expect(player).not.toHaveProperty("team");
        expect(player).not.toHaveProperty("teamId");
        expect(player).not.toHaveProperty("currentTeam");
        const currentTeam = bundle.currentTeam as
          | { id?: string }
          | undefined;
        const evidenceTeams = [
          ...(bundle.weeklyEvidence as Array<{
            evidenceTeam: { id: string };
          }>),
          ...(bundle.periodSummaries as Array<{
            evidenceTeam: { id: string };
          }>),
          ...(bundle.movementHistory as Array<{
            evidenceTeam: { id: string };
          }>),
        ].map((row) => row.evidenceTeam.id);
        expect(
          (bundle.weeklyEvidence as Array<Record<string, unknown>>).every(
            (row) => "evidenceTeam" in row,
          ),
        ).toBe(true);
        if (currentTeam) {
          transferredEvidenceRows += evidenceTeams.filter(
            (team) => team !== currentTeam.id,
          ).length;
        }
      }
      expect(transferredEvidenceRows).toBeGreaterThan(0);
    }
  } finally {
    await rm(historicalCase.temporaryRoot, {
      recursive: true,
      force: true,
    });
  }

  const { temporaryRoot, dataRoot } = await temporaryDataRoot();
  try {
    await cp(
      path.join(dataRoot, "fixture"),
      path.join(dataRoot, "export"),
      { recursive: true },
    );
    const wrongMode = await loadDepthSnapRegistry({
      mode: "export",
      dataRoot,
    });
    expect(wrongMode).toMatchObject({
      ok: false,
      failure: { category: "manifest_mismatch" },
    });
    const unsupported = await loadDepthSnapRegistry({
      mode: "other",
      dataRoot,
    });
    expect(unsupported).toMatchObject({
      ok: false,
      failure: { category: "unsupported_data_mode" },
    });
  } finally {
    await rm(temporaryRoot, { recursive: true, force: true });
  }
});
