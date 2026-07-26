import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "export-active.spec.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: "artifacts/playwright-report-export-active",
        open: "never",
      },
    ],
  ],
  outputDir: "artifacts/test-results-export-active",
  use: {
    baseURL: "http://127.0.0.1:3200",
    browserName: "chromium",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run start -- --hostname 127.0.0.1 --port 3200",
    url: "http://127.0.0.1:3200",
    env: {
      DEPTHSNAP_DATA_MODE: "export",
    },
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
