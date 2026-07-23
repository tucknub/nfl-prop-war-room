import { readFile } from "node:fs/promises";
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

async function main() {
  const variants: PublicationVariant[] = [
    "published",
    "no_published_week",
    "unavailable",
  ];
  for (const publicationVariant of variants) {
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
      throw new Error(`${publicationVariant}: manifest serialization is not deterministic`);
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

  const exportResult = await loadDepthSnapRegistry({
    mode: "export",
    publicationVariant: "published",
  });
  if (exportResult.ok || exportResult.failure.category !== "bundle_missing") {
    throw new Error(
      "Export isolation failed: an absent export manifest must return bundle_missing without fixture fallback.",
    );
  }
  console.log(
    "export isolation: PASS · missing export manifest returned bundle_missing · no fixture fallback",
  );
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
