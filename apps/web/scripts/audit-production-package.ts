import { createHash } from "node:crypto";
import {
  mkdir,
  readFile,
  readdir,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { loadDepthSnapRegistry } from "../src/lib/data-registry-core";

export const productionPackageRoot = path.resolve(
  "artifacts/production-package",
);

type Inventory = {
  activeBundles: number;
  activePublicationStatus: string;
  activeSeason: number;
  activeSourceVersion: string;
  files: number;
  sha256: string;
  totalBytes: number;
};

async function walk(directory: string): Promise<string[]> {
  const files: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await walk(target)));
    else if (entry.isFile()) files.push(target);
  }
  return files;
}

function relative(root: string, file: string): string {
  return path.relative(root, file).split(path.sep).join("/");
}

function assertSafePackageRoot(root: string) {
  const resolved = path.resolve(root);
  const expectedParent = path.resolve("artifacts");
  if (resolved === expectedParent || !resolved.startsWith(`${expectedParent}${path.sep}`)) {
    throw new Error("Production package must remain under apps/web/artifacts.");
  }
}

export async function auditProductionPackage(
  root = productionPackageRoot,
): Promise<Inventory> {
  assertSafePackageRoot(root);
  const required = [
    "server.js",
    ".next/static",
    "public/data/depthsnap/export/manifest.json",
    "public/data/depthsnap/export/status.json",
  ];
  for (const item of required) {
    try {
      await stat(path.join(root, ...item.split("/")));
    } catch {
      throw new Error(`Production package is missing required runtime content: ${item}`);
    }
  }

  const dataRoot = path.join(root, "public", "data", "depthsnap");
  const dataDirectories = (await readdir(dataRoot, { withFileTypes: true }))
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  if (JSON.stringify(dataDirectories) !== JSON.stringify(["export"])) {
    throw new Error(
      `Production data root must contain only export; observed ${dataDirectories.join(", ") || "none"}.`,
    );
  }
  const registry = await loadDepthSnapRegistry({
    mode: "export",
    dataRoot,
    publicationVariant: "published",
  });
  if (!registry.ok) {
    throw new Error(
      `Production active export failed validation: ${registry.failure.category}.`,
    );
  }
  if (registry.registry.manifest.season < 2026) {
    throw new Error("Production package cannot contain historical parity as active data.");
  }
  for (const excludedRuntimeDependency of ["postcss", "sharp"]) {
    try {
      await stat(path.join(root, "node_modules", excludedRuntimeDependency));
      throw new Error(
        `Production package contains unused build/image dependency: ${excludedRuntimeDependency}.`,
      );
    } catch (error: unknown) {
      if (
        error instanceof Error &&
        error.message.startsWith("Production package contains")
      ) {
        throw error;
      }
    }
  }

  const files = await walk(root);
  const forbiddenPathPatterns = [
    /(^|\/)fixtures?(?:-|\/)/i,
    /(^|\/)export-historical-2025(\/|$)/i,
    /(^|[./_-])staging(?:[./_-]|$)/i,
    /(^|[./_-])rollback(?:[./_-]|$)/i,
    /(^|\/)(outputs|docs|artifacts)(\/|$)/i,
    /(^|\/)(playwright-report|test-results|traces|screenshots)(\/|$)/i,
    /(^|\/)__pycache__(\/|$)/i,
    /\.(py|pyc|pyo)$/i,
  ];
  const forbiddenPaths = files
    .map((file) => relative(root, file))
    .filter(
      (file) =>
        forbiddenPathPatterns.some((pattern) => pattern.test(file)) ||
        /^playwright(?:[.-]|\/)/i.test(file),
    );
  if (forbiddenPaths.length) {
    throw new Error(
      `Production package contains forbidden paths: ${forbiddenPaths.slice(0, 10).join(", ")}`,
    );
  }

  const workspace = process.cwd();
  const localPathTokens = [
    workspace,
    workspace.replaceAll("\\", "/"),
    "C:\\Users\\",
    "C:\\\\Users\\\\",
    "C:/Users/",
    "/Users/",
    "/home/runner/work/",
    "/__w/",
  ].map((value) => value.toLowerCase());
  const secretPatterns = [
    /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
    /\bgh[pousr]_[A-Za-z0-9_]{20,}\b/,
    /\bAKIA[0-9A-Z]{16}\b/,
    /\bsk_live_[A-Za-z0-9]{16,}\b/,
  ];
  const privateContentTokens = [
    "opportunity_context_preservation_2025",
    "outputs/role_research",
    "export-historical-2025",
  ];
  const textExtensions = new Set([
    ".css",
    ".html",
    ".js",
    ".json",
    ".mjs",
    ".txt",
  ]);
  for (const file of files) {
    const fileName = relative(root, file);
    if (
      fileName.startsWith("node_modules/") ||
      !textExtensions.has(path.extname(file).toLowerCase())
    ) {
      continue;
    }
    const info = await stat(file);
    if (info.size > 10 * 1024 * 1024) continue;
    const content = await readFile(file, "utf8");
    const lower = content.toLowerCase();
    if (localPathTokens.some((token) => token && lower.includes(token))) {
      throw new Error(`Production package exposes an absolute local path in ${fileName}.`);
    }
    if (privateContentTokens.some((token) => lower.includes(token))) {
      throw new Error(`Production package exposes private/test content in ${fileName}.`);
    }
    if (secretPatterns.some((pattern) => pattern.test(content))) {
      throw new Error(`Production package contains a possible secret in ${fileName}.`);
    }
  }

  const digest = createHash("sha256");
  let totalBytes = 0;
  for (const file of files.sort()) {
    const bytes = await readFile(file);
    const name = relative(root, file);
    digest.update(name);
    digest.update("\0");
    digest.update(bytes);
    totalBytes += bytes.length;
  }
  const inventory: Inventory = {
    activeBundles: registry.registry.manifest.entries.length,
    activePublicationStatus: registry.registry.manifest.publicationStatus,
    activeSeason: registry.registry.manifest.season,
    activeSourceVersion: registry.registry.manifest.sourceVersion,
    files: files.length,
    sha256: digest.digest("hex"),
    totalBytes,
  };
  await mkdir(path.resolve("artifacts"), { recursive: true });
  await writeFile(
    path.resolve("artifacts/production-package-audit.json"),
    `${JSON.stringify(inventory, null, 2)}\n`,
    "utf8",
  );
  console.log(JSON.stringify(inventory, null, 2));
  return inventory;
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(import.meta.filename)) {
  auditProductionPackage().catch((error: unknown) => {
    console.error(error instanceof Error ? error.message : "Production package audit failed.");
    process.exitCode = 1;
  });
}
