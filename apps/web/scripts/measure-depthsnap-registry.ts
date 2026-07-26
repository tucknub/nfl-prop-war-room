import { cp, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import {
  getRegistryCacheMetrics,
  loadCachedDepthSnapRegistry,
  resetRegistryCacheForTests,
} from "../src/lib/data-registry-cache";
import type { RegistryOptions } from "../src/lib/data-registry-core";

async function measure(label: string, options: RegistryOptions) {
  resetRegistryCacheForTests();
  const cold = await loadCachedDepthSnapRegistry(options);
  if (!cold.ok) {
    throw new Error(
      `${label} cold load failed: ${cold.failure.category} — ${cold.failure.message}`,
    );
  }
  const afterCold = getRegistryCacheMetrics();
  const warm = await loadCachedDepthSnapRegistry(options);
  if (!warm.ok) {
    throw new Error(
      `${label} warm load failed: ${warm.failure.category} — ${warm.failure.message}`,
    );
  }
  const afterWarm = getRegistryCacheMetrics();
  if (cold.registry !== warm.registry) {
    throw new Error(`${label} warm load did not reuse the validated registry.`);
  }
  console.log(
    [
      `${label} cold registry: ${cold.registry.loadMetrics.entriesValidated} entries validated`,
      `${cold.registry.loadMetrics.filesRead} files read`,
      `${cold.registry.loadMetrics.bytesRead} UTF-8 bytes`,
      `${cold.registry.loadMetrics.durationMs.toFixed(3)} ms`,
    ].join(" · "),
  );
  console.log(
    [
      `${label} warm registry: cache entries ${afterWarm.entries}`,
      `hits ${afterWarm.hits}`,
      `misses ${afterWarm.misses}`,
      "additional files read 0",
    ].join(" · "),
  );
  if (
    afterCold.entries !== 1 ||
    afterCold.misses !== 1 ||
    afterWarm.hits !== 1 ||
    afterWarm.misses !== 1
  ) {
    throw new Error(
      `${label} registry cache metrics did not match the expected cold/warm behavior.`,
    );
  }
}

async function main() {
  await measure("fixture", {
    mode: "fixture",
    publicationVariant: "published",
  });
  await measure("active export", {
    mode: "export",
    publicationVariant: "published",
  });

  const historicalRoot = await mkdtemp(
    path.join(tmpdir(), "depthsnap-historical-measure-"),
  );
  try {
    await cp(
      path.resolve("public/data/depthsnap/export-historical-2025"),
      path.join(historicalRoot, "export"),
      { recursive: true },
    );
    await measure("historical export", {
      dataRoot: historicalRoot,
      mode: "export",
      publicationVariant: "published",
    });
  } finally {
    await rm(historicalRoot, { recursive: true, force: true });
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
