import path from "node:path";
import {
  loadDepthSnapRegistry,
  type RegistryOptions,
  type RegistryResult,
} from "@/lib/data-registry-core";

type CachedRegistryOptions = Omit<RegistryOptions, "readTextFile">;

const registryCache = new Map<string, Promise<RegistryResult>>();
let cacheHits = 0;
let cacheMisses = 0;

function cacheKey(options: CachedRegistryOptions): string {
  const dataRoot = path.normalize(
    options.dataRoot ?? path.join("public", "data", "depthsnap"),
  );
  return JSON.stringify({
    dataRoot,
    mode: options.mode ?? "<unset>",
    publicationVariant: options.publicationVariant ?? "published",
    allowFixtureDefault: options.allowFixtureDefault ?? false,
  });
}

export function loadCachedDepthSnapRegistry(
  options: CachedRegistryOptions = {},
): Promise<RegistryResult> {
  const key = cacheKey(options);
  const cached = registryCache.get(key);
  if (cached) {
    cacheHits += 1;
    return cached;
  }
  cacheMisses += 1;
  const pending = loadDepthSnapRegistry(options);
  registryCache.set(key, pending);
  return pending;
}

export function getRegistryCacheMetrics() {
  return {
    entries: registryCache.size,
    hits: cacheHits,
    misses: cacheMisses,
  };
}

export function resetRegistryCacheForTests() {
  registryCache.clear();
  cacheHits = 0;
  cacheMisses = 0;
}
