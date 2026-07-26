import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const reviewDirectory = path.resolve(
  process.cwd(),
  "../../docs/depthsnap/reviews/release-readiness",
);
const packagedStatus = JSON.parse(
  readFileSync(
    path.resolve(
      "artifacts/production-package/public/data/depthsnap/export/status.json",
    ),
    "utf8",
  ),
) as { sourceVersion: string };

test.beforeAll(() => mkdirSync(reviewDirectory, { recursive: true }));

function monitorErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  return errors;
}

async function expectNoOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    body: document.body.scrollWidth,
    document: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }));
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport);
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
}

async function expectProductionIdentity(page: Page) {
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator(".fixture-notice")).toHaveCount(0);
  await expect(page.getByText(/synthetic records/i)).toHaveCount(0);
  await expect(page.getByText(/temporary completed-2025/i)).toHaveCount(0);
  await expectNoOverflow(page);
}

test("staged package exposes production metadata, headers, and exact active status", async ({
  page,
  request,
}) => {
  const errors = monitorErrors(page);
  const response = await page.goto("/");
  expect(response?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "No completed week is published yet" }),
  ).toBeVisible();
  await expectProductionIdentity(page);
  await expect(page).toHaveTitle("DepthSnap — NFL Role Intelligence");
  await expect(
    page.locator('meta[name="description"]'),
  ).toHaveAttribute("content", /Documented NFL role changes/);
  await expect(page.locator('meta[property="og:title"]')).toHaveAttribute(
    "content",
    "DepthSnap — NFL Role Intelligence",
  );
  await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute(
    "content",
    "summary_large_image",
  );
  await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
    "content",
    /^http:\/\/127\.0\.0\.1:3400\/opengraph-image/,
  );
  await expect(page.locator('link[rel="icon"]')).toHaveCount(1);
  expect(response?.headers()["x-content-type-options"]).toBe("nosniff");
  expect(response?.headers()["x-frame-options"]).toBe("DENY");
  expect(response?.headers()["referrer-policy"]).toBe(
    "strict-origin-when-cross-origin",
  );
  expect(response?.headers()["permissions-policy"]).toContain("camera=()");
  expect(response?.headers()["strict-transport-security"]).toBeUndefined();
  expect(response?.headers()["content-security-policy"]).toBeUndefined();

  const manifestResponse = await request.get(
    "/data/depthsnap/export/manifest.json",
  );
  expect(manifestResponse.status()).toBe(200);
  expect(manifestResponse.headers()["cache-control"]).toContain("max-age=0");
  expect(manifestResponse.headers()["cache-control"]).toContain("must-revalidate");
  const bundleResponse = await request.get(
    "/data/depthsnap/export/home.json",
  );
  expect(bundleResponse.status()).toBe(200);
  expect(bundleResponse.headers()["cache-control"]).toContain("must-revalidate");

  await page.goto("/data-status");
  await expect(
    page.getByLabel("Publication state: No published week"),
  ).toBeVisible();
  await expect(
    page.getByText(packagedStatus.sourceVersion, { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(reviewDirectory, "production-desktop-data-status.png"),
    animations: "disabled",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("all production routes, deep links, and keyboard navigation fail closed cleanly", async ({
  page,
}) => {
  const errors = monitorErrors(page);
  for (const route of [
    "/",
    "/reports",
    "/reports/backfield",
    "/reports/targets",
    "/reports/movement",
    "/teams",
    "/players",
    "/search",
    "/methodology",
    "/data-status",
    "/teams/ATL",
    "/players/00-0030035",
  ]) {
    await page.goto(route);
    await expectProductionIdentity(page);
  }

  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to findings" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main-content$/);
  await page.keyboard.press("/");
  await expect(page).toHaveURL(/\/search\?focus=1$/);
  await expect(page.getByRole("heading", { name: "Find exact evidence" })).toBeVisible();

  await page.goto("/");
  await page.screenshot({
    path: path.join(reviewDirectory, "production-desktop-home.png"),
    animations: "disabled",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("production preseason package is mobile-safe and announces empty state", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = monitorErrors(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "No completed week is published yet" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  await expectProductionIdentity(page);
  await page.screenshot({
    path: path.join(reviewDirectory, "production-mobile-home.png"),
    animations: "disabled",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
