import { cp, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  loadDepthSnapRegistry,
  type PublicationVariant,
} from "../src/lib/data-registry-core";

function deterministicJson(value: unknown): string {
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

async function assertDeterministicRegistry(
  publicationVariant: PublicationVariant,
) {
  const result = await loadDepthSnapRegistry({
    mode: "fixture",
    publicationVariant,
  });
  if (!result.ok) {
    throw new Error(
      `${publicationVariant}: ${result.failure.category} — ${result.failure.message}`,
    );
  }
  console.log(
    `${publicationVariant}: PASS · ${result.registry.manifest.entries.length} bundles · ${result.registry.manifest.schemaVersion}`,
  );
  const manifestBytes = await readFile(
    path.join(result.registry.directory, "manifest.json"),
    "utf8",
  );
  if (manifestBytes !== deterministicJson(JSON.parse(manifestBytes))) {
    throw new Error(
      `${publicationVariant}: manifest serialization is not deterministic`,
    );
  }
  for (const entry of result.registry.manifest.entries) {
    const bytes = await readFile(
      path.join(result.registry.directory, ...entry.path.split("/")),
      "utf8",
    );
    if (bytes !== deterministicJson(JSON.parse(bytes))) {
      throw new Error(
        `${publicationVariant}: ${entry.path} serialization is not deterministic`,
      );
    }
  }
  console.log(
    `${publicationVariant}: deterministic serialization PASS · sorted compact UTF-8 JSON · one trailing newline`,
  );
}

async function main() {
  const variants: PublicationVariant[] = [
    "published",
    "no_published_week",
    "unavailable",
  ];
  for (const publicationVariant of variants) {
    await assertDeterministicRegistry(publicationVariant);
  }

  const activeExportResult = await loadDepthSnapRegistry({
    mode: "export",
    publicationVariant: "published",
  });
  if (!activeExportResult.ok) {
    throw new Error(
      `Active export validation failed: ${activeExportResult.failure.category} — ${activeExportResult.failure.message}`,
    );
  }
  const activeStatus = activeExportResult.registry.bundles.get("status") as
    | { season?: number; status?: string }
    | undefined;
  if (
    activeStatus?.season !== 2026 ||
    activeStatus.status !== "no_published_week" ||
    activeExportResult.registry.manifest.entries.length !== 9
  ) {
    throw new Error(
      "Active export validation failed: expected the 2026 no_published_week registry with 9 bundles.",
    );
  }
  console.log(
    "active export: PASS · 2026 no_published_week · 9 bundles · no fixture fallback",
  );

  const historicalSource = path.resolve(
    "public/data/depthsnap/export-historical-2025",
  );
  const historicalRoot = await mkdtemp(
    path.join(tmpdir(), "depthsnap-historical-validation-"),
  );
  try {
    await cp(historicalSource, path.join(historicalRoot, "export"), {
      recursive: true,
    });
    const historicalExportResult = await loadDepthSnapRegistry({
      dataRoot: historicalRoot,
      mode: "export",
      publicationVariant: "published",
    });
    if (!historicalExportResult.ok) {
      throw new Error(
        `Historical export validation failed: ${historicalExportResult.failure.category} — ${historicalExportResult.failure.message}`,
      );
    }
    const historicalStatus = historicalExportResult.registry.bundles.get(
      "status",
    ) as { season?: number; status?: string } | undefined;
    if (
      historicalStatus?.season !== 2025 ||
      historicalStatus.status !== "published" ||
      historicalExportResult.registry.manifest.entries.length !== 586
    ) {
      throw new Error(
        "Historical export validation failed: expected the temporary completed-2025 published registry with 586 bundles.",
      );
    }
    console.log(
      "historical export: PASS · 2025 published · 586 bundles · independently rooted",
    );
  } finally {
    await rm(historicalRoot, { recursive: true, force: true });
  }

  const productionUnset = await loadDepthSnapRegistry({
    publicationVariant: "published",
  });
  if (
    productionUnset.ok ||
    productionUnset.failure.category !== "unsupported_data_mode"
  ) {
    throw new Error(
      "Production mode isolation failed: an unset mode must fail closed.",
    );
  }
  const developmentDefault = await loadDepthSnapRegistry({
    allowFixtureDefault: true,
    publicationVariant: "published",
  });
  if (!developmentDefault.ok || developmentDefault.registry.mode !== "fixture") {
    throw new Error(
      "Development fixture default failed: the explicitly scoped default must load fixture mode.",
    );
  }
  console.log(
    "mode selection: PASS · production unset failed closed · explicitly scoped development default loaded fixture mode",
  );
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
