import path from "node:path";
import { defineConfig } from "@playwright/test";

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
    baseURL: "http://127.0.0.1:3300",
    browserName: "chromium",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run start -- --hostname 127.0.0.1 --port 3300",
    url: "http://127.0.0.1:3300",
    env: {
      DEPTHSNAP_DATA_MODE: "export",
      DEPTHSNAP_DATA_ROOT: path.resolve(
        "artifacts/export-e2e-data/depthsnap",
      ),
    },
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
