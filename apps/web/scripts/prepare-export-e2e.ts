import { cp, mkdir, rm } from "node:fs/promises";
import path from "node:path";

async function main() {
  const source = path.resolve(
    "public/data/depthsnap/export-historical-2025",
  );
  const dataRoot = path.resolve("artifacts/export-e2e-data/depthsnap");
  const target = path.join(dataRoot, "export");
  await rm(target, { recursive: true, force: true });
  await mkdir(dataRoot, { recursive: true });
  await cp(source, target, { recursive: true });
  console.log(
    `Historical export E2E root prepared at ${path.relative(process.cwd(), target)}.`,
  );
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
