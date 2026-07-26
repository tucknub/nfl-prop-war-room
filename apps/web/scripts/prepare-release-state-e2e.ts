import { spawn } from "node:child_process";
import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";

const repositoryRoot = path.resolve("../..");
const stateRoot = path.resolve("artifacts/release-state-data");
const unavailableExport = path.join(
  stateRoot,
  "unavailable",
  "depthsnap",
  "export",
);
const failureExport = path.join(
  stateRoot,
  "contract-failure",
  "depthsnap",
  "export",
);

function runPython(args: string[]) {
  const python =
    process.env.PYTHON ?? (process.platform === "win32" ? "python.exe" : "python3");
  return new Promise<void>((resolve, reject) => {
    const child = spawn(python, args, {
      cwd: repositoryRoot,
      env: process.env,
      stdio: "inherit",
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Python release-state preparation exited with ${code}.`));
    });
  });
}

async function main() {
  await rm(stateRoot, { recursive: true, force: true });
  await mkdir(unavailableExport, { recursive: true });
  await runPython([
    "scripts/export_depthsnap.py",
    "build-from-status",
    "tests/fixtures/depthsnap_role_status_blocked_2026.json",
    "--generated-at",
    "2026-07-26T00:00:00Z",
    "--output",
    path.relative(repositoryRoot, unavailableExport),
    "--replace",
  ]);

  await mkdir(path.dirname(failureExport), { recursive: true });
  await cp(path.resolve("public/data/depthsnap/export"), failureExport, {
    recursive: true,
  });
  await writeFile(
    path.join(failureExport, "home.json"),
    '{"invalidContract":true}\n',
    "utf8",
  );
  console.log(
    "Prepared non-production unavailable and contract-failure release roots.",
  );
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
