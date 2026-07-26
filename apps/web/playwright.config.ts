import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testIgnore: [
    "export-active.spec.ts",
    "export-historical.spec.ts",
    "production-smoke.spec.ts",
    "release-states.spec.ts",
  ],
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: "artifacts/playwright-report", open: "never" }],
  ],
  outputDir: "artifacts/test-results",
  use: {
    baseURL: "http://127.0.0.1:3100",
    browserName: "chromium",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run start -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100",
    env: {
      DEPTHSNAP_DATA_MODE: "fixture",
      DEPTHSNAP_ALLOW_TEST_DATA_MODE: "1",
    },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
