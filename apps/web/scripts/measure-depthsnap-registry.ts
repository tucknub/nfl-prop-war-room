import {
  getRegistryCacheMetrics,
  loadCachedDepthSnapRegistry,
  resetRegistryCacheForTests,
} from "../src/lib/data-registry-cache";

async function main() {
  resetRegistryCacheForTests();
  const options = {
    mode: "fixture",
    publicationVariant: "published" as const,
  };
  const cold = await loadCachedDepthSnapRegistry(options);
  if (!cold.ok) {
    throw new Error(
      `Cold registry load failed: ${cold.failure.category} — ${cold.failure.message}`,
    );
  }
  const afterCold = getRegistryCacheMetrics();
  const warm = await loadCachedDepthSnapRegistry(options);
  if (!warm.ok) {
    throw new Error(
      `Warm registry load failed: ${warm.failure.category} — ${warm.failure.message}`,
    );
  }
  const afterWarm = getRegistryCacheMetrics();
  if (cold.registry !== warm.registry) {
    throw new Error("Warm registry load did not reuse the validated registry.");
  }
  console.log(
    [
      `cold registry: ${cold.registry.loadMetrics.entriesValidated} entries validated`,
      `${cold.registry.loadMetrics.filesRead} files read`,
      `${cold.registry.loadMetrics.bytesRead} UTF-8 bytes`,
      `${cold.registry.loadMetrics.durationMs.toFixed(3)} ms`,
    ].join(" · "),
  );
  console.log(
    [
      `warm registry: cache entries ${afterWarm.entries}`,
      `hits ${afterWarm.hits}`,
      `misses ${afterWarm.misses}`,
      `additional files read 0`,
    ].join(" · "),
  );
  if (
    afterCold.entries !== 1 ||
    afterCold.misses !== 1 ||
    afterWarm.hits !== 1 ||
    afterWarm.misses !== 1
  ) {
    throw new Error("Registry cache metrics did not match the expected cold/warm behavior.");
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
