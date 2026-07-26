import path from "node:path";
import { defineConfig } from "@playwright/test";

const historicalPort = process.env.DEPTHSNAP_HISTORICAL_E2E_PORT ?? "3300";
const historicalBaseUrl = `http://127.0.0.1:${historicalPort}`;

export default defineConfig({
  testDir: "./tests",
  testMatch: "export-historical.spec.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: "artifacts/playwright-report-export-historical",
        open: "never",
      },
    ],
  ],
  outputDir: "artifacts/test-results-export-historical",
  use: {
    baseURL: historicalBaseUrl,
    browserName: "chromium",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npm run start -- --hostname 127.0.0.1 --port ${historicalPort}`,
    url: historicalBaseUrl,
    env: {
      DEPTHSNAP_DATA_MODE: "export",
      DEPTHSNAP_DATA_ROOT: path.resolve(
        "artifacts/export-e2e-data/depthsnap",
      ),
      DEPTHSNAP_ALLOW_TEST_DATA_ROOT: "1",
    },
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
