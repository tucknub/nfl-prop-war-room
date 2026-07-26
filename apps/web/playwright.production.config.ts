import path from "node:path";
import { defineConfig } from "@playwright/test";

const packageRoot = path.resolve("artifacts/production-package");

export default defineConfig({
  testDir: "./tests",
  testMatch: "production-smoke.spec.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: "artifacts/playwright-report-production",
        open: "never",
      },
    ],
  ],
  outputDir: "artifacts/test-results-production",
  use: {
    baseURL: "http://127.0.0.1:3400",
    browserName: "chromium",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "node server.js",
    cwd: packageRoot,
    url: "http://127.0.0.1:3400",
    env: {
      DEPTHSNAP_DATA_MODE: "export",
      DEPTHSNAP_DATA_ROOT: "public/data/depthsnap",
      DEPTHSNAP_PUBLIC_ORIGIN: "http://127.0.0.1:3400",
      HOSTNAME: "127.0.0.1",
      NODE_ENV: "production",
      PORT: "3400",
    },
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
