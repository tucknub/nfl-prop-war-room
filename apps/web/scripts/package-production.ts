import { spawn } from "node:child_process";
import {
  cp,
  mkdir,
  readFile,
  readdir,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import {
  auditProductionPackage,
  productionPackageRoot,
} from "./audit-production-package";
import { loadDepthSnapRegistry } from "../src/lib/data-registry-core";

const sourceDataRoot = path.resolve("public/data/depthsnap");
const sourceExport = path.join(sourceDataRoot, "export");
const standaloneRoot = path.resolve(".next/standalone");
const staticRoot = path.resolve(".next/static");

function run(command: string, args: string[], environment: NodeJS.ProcessEnv) {
  return new Promise<void>((resolve, reject) => {
    const child = spawn(command, args, {
      env: environment,
      shell: false,
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(" ")} exited with ${code}.`));
    });
  });
}

async function requirePath(target: string, label: string) {
  try {
    await stat(target);
  } catch {
    throw new Error(`Production packaging is missing ${label}.`);
  }
}

async function main() {
  if (
    process.env.DEPTHSNAP_DATA_MODE &&
    process.env.DEPTHSNAP_DATA_MODE !== "export"
  ) {
    throw new Error("Production packaging requires DEPTHSNAP_DATA_MODE=export.");
  }
  const source = await loadDepthSnapRegistry({
    mode: "export",
    dataRoot: sourceDataRoot,
    publicationVariant: "published",
  });
  if (!source.ok) {
    throw new Error(
      `Active export is missing or invalid: ${source.failure.category}.`,
    );
  }
  if (source.registry.manifest.season < 2026) {
    throw new Error("Historical parity cannot be packaged as active production data.");
  }

  const artifactsRoot = path.resolve("artifacts");
  if (
    productionPackageRoot === artifactsRoot ||
    !productionPackageRoot.startsWith(`${artifactsRoot}${path.sep}`)
  ) {
    throw new Error("Unsafe production package target.");
  }
  await rm(productionPackageRoot, { recursive: true, force: true });

  const buildCommand =
    process.platform === "win32"
      ? { command: "cmd.exe", args: ["/d", "/s", "/c", "npm run build"] }
      : { command: "npm", args: ["run", "build"] };
  await run(buildCommand.command, buildCommand.args, {
    ...process.env,
    DEPTHSNAP_DATA_MODE: "export",
    DEPTHSNAP_DATA_ROOT: sourceDataRoot,
    DEPTHSNAP_PUBLIC_ORIGIN:
      process.env.DEPTHSNAP_PUBLIC_ORIGIN ?? "http://127.0.0.1:3400",
  });
  await requirePath(path.join(standaloneRoot, "server.js"), "standalone server.js");
  await requirePath(staticRoot, "Next.js static assets");

  await mkdir(productionPackageRoot, { recursive: true });
  await cp(standaloneRoot, productionPackageRoot, { recursive: true });
  for (const runtimeExcludedPath of [
    "artifacts",
    "node_modules/@img",
    "node_modules/detect-libc",
    "node_modules/sharp",
    "playwright.config.ts",
    "scripts",
    "src",
    "tests",
    "playwright.export-active.config.ts",
    "playwright.export-historical.config.ts",
    "playwright.production.config.ts",
    "playwright.release-states.config.ts",
  ]) {
    await rm(path.join(productionPackageRoot, runtimeExcludedPath), {
      recursive: true,
      force: true,
    });
  }
  const generatedEntries = await readdir(productionPackageRoot, {
    recursive: true,
    withFileTypes: true,
  });
  for (const entry of generatedEntries) {
    if (entry.isFile() && entry.name.endsWith(".nft.json")) {
      await rm(path.join(entry.parentPath, entry.name), { force: true });
    }
  }
  const generatedPathTokens = [
    process.cwd().replaceAll("\\", "\\\\"),
    process.cwd(),
    process.cwd().replaceAll("\\", "/"),
  ];
  const scrubExtensions = new Set([".js", ".json", ".mjs"]);
  for (const entry of generatedEntries) {
    if (!entry.isFile() || entry.name.endsWith(".nft.json")) continue;
    const file = path.join(entry.parentPath, entry.name);
    const fileName = path.relative(productionPackageRoot, file);
    if (
      fileName.startsWith(`node_modules${path.sep}`) ||
      !scrubExtensions.has(path.extname(file).toLowerCase())
    ) {
      continue;
    }
    const content = await readFile(file, "utf8");
    let scrubbed = content;
    for (const token of generatedPathTokens) {
      scrubbed = scrubbed.replaceAll(token, ".");
    }
    if (scrubbed !== content) await writeFile(file, scrubbed, "utf8");
  }

  const packagedPublic = path.join(productionPackageRoot, "public");
  await rm(packagedPublic, { recursive: true, force: true });
  await mkdir(path.join(packagedPublic, "data", "depthsnap"), {
    recursive: true,
  });
  await cp(
    sourceExport,
    path.join(packagedPublic, "data", "depthsnap", "export"),
    { recursive: true },
  );
  const sourceImages = path.resolve("public/images");
  try {
    await stat(sourceImages);
    await cp(sourceImages, path.join(packagedPublic, "images"), {
      recursive: true,
    });
  } catch {
    // Images are optional; the validated data root and runtime assets are not.
  }
  await mkdir(path.join(productionPackageRoot, ".next"), { recursive: true });
  await cp(staticRoot, path.join(productionPackageRoot, ".next", "static"), {
    recursive: true,
  });
  const sourcePackage = JSON.parse(
    await readFile(path.resolve("package.json"), "utf8"),
  ) as {
    engines?: Record<string, string>;
    name: string;
    version: string;
  };
  await writeFile(
    path.join(productionPackageRoot, "package.json"),
    `${JSON.stringify(
      {
        name: sourcePackage.name,
        version: sourcePackage.version,
        private: true,
        engines: sourcePackage.engines,
        scripts: { start: "node server.js" },
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  await auditProductionPackage(productionPackageRoot);
  console.log(
    "Production package staged under apps/web/artifacts/production-package.",
  );
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : "Production packaging failed.");
  process.exitCode = 1;
});
