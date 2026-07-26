import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const reviewDirectory = path.resolve(
  process.cwd(),
  "../../docs/depthsnap/reviews/phase4b-export",
);

test.beforeAll(() => mkdirSync(reviewDirectory, { recursive: true }));

function monitorPageErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  return errors;
}

async function expectNoFixtureFallback(page: Page) {
  await expect(page.getByText(/synthetic records/i)).toHaveCount(0);
  await expect(page.locator(".fixture-notice")).toHaveCount(0);
}

test("active export renders the 2026 no-published-week registry without fixture fallback", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published yet",
    }),
  ).toBeVisible();
  await expect(page.locator("[data-share-evidence]")).toHaveCount(0);
  await expectNoFixtureFallback(page);
  await page.screenshot({
    path: path.join(reviewDirectory, "active-2026-desktop-home.png"),
    animations: "disabled",
    fullPage: true,
  });

  await page.goto("/data-status");
  await expect(
    page.getByLabel("Publication state: No published week"),
  ).toBeVisible();
  await expect(page.getByText("export", { exact: true })).toBeVisible();
  await expect(page.getByText("9 declared bundles")).toBeVisible();
  await expect(page.getByText("No week supplied", { exact: true })).toBeVisible();
  await expectNoFixtureFallback(page);
  await page.screenshot({
    path: path.join(reviewDirectory, "active-2026-desktop-data-status.png"),
    animations: "disabled",
    fullPage: true,
  });

  expect(errors).toEqual([]);
});

test("active export keeps empty identity routes explicit on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = monitorPageErrors(page);

  await page.goto("/teams");
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published for the team directory",
    }),
  ).toBeVisible();
  await expectNoFixtureFallback(page);

  await page.goto("/players");
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published for the player directory",
    }),
  ).toBeVisible();
  await expectNoFixtureFallback(page);

  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published yet",
    }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(reviewDirectory, "active-2026-mobile-home.png"),
    animations: "disabled",
    fullPage: true,
  });

  expect(errors).toEqual([]);
});
