import path from "node:path";
import { defineConfig } from "@playwright/test";

const packageRoot = path.resolve("artifacts/production-package");

function server(port: number, dataRoot: string) {
  return {
    command: "node server.js",
    cwd: packageRoot,
    url: `http://127.0.0.1:${port}`,
    env: {
      DEPTHSNAP_DATA_MODE: "export",
      DEPTHSNAP_DATA_ROOT: path.resolve(dataRoot),
      DEPTHSNAP_ALLOW_TEST_DATA_ROOT: "1",
      HOSTNAME: "127.0.0.1",
      NODE_ENV: "production",
      PORT: String(port),
    },
    reuseExistingServer: false,
    timeout: 120_000,
  };
}

export default defineConfig({
  testDir: "./tests",
  testMatch: "release-states.spec.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: "artifacts/playwright-report-release-states",
        open: "never",
      },
    ],
  ],
  outputDir: "artifacts/test-results-release-states",
  use: {
    browserName: "chromium",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  webServer: [
    server(
      3500,
      "artifacts/release-state-data/unavailable/depthsnap",
    ),
    server(
      3501,
      "artifacts/release-state-data/contract-failure/depthsnap",
    ),
  ],
});
