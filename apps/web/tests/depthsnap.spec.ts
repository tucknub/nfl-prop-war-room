import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const screenshotDirectory = path.join(
  process.cwd(),
  "artifacts",
  "screenshots",
);

test.beforeAll(() => {
  mkdirSync(screenshotDirectory, { recursive: true });
});

function monitorPageErrors(page: Page) {
  const errors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(`console: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    errors.push(`page: ${error.message}`);
  });

  return errors;
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));

  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport);
}

async function expectEveryShareHasRawEvidence(page: Page) {
  const evidenceBlocks = page.locator("[data-share-evidence]");
  const count = await evidenceBlocks.count();
  expect(count).toBeGreaterThan(0);

  for (let index = 0; index < count; index += 1) {
    const text = await evidenceBlocks.nth(index).innerText();
    expect(text).toMatch(/\d+\.\d%/);
    expect(text).toMatch(/\d+ of \d+ (opportunities|carries|targets)/);
  }
}

test("desktop feed exposes findings, evidence, navigation, and screenshot", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/");

  await expect(page.getByRole("link", { name: "DepthSnap home" })).toBeVisible();
  await expect(
    page.getByText("NFL Role Intelligence", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Marcus Hale took control of the team backfield.",
    }),
  ).toBeVisible();
  await expect(page.getByText(/synthetic records/i)).toBeVisible();

  const leadBox = await page
    .getByRole("heading", {
      name: "Marcus Hale took control of the team backfield.",
    })
    .boundingBox();
  expect(leadBox).not.toBeNull();
  expect(leadBox?.y).toBeLessThan(900);
  expect(leadBox?.width).toBeLessThan(760);
  await expect(
    page.getByRole("heading", { name: "Role movement feed" }),
  ).toBeVisible();

  await expectEveryShareHasRawEvidence(page);
  await expect(
    page.getByText("+26.5 pp", { exact: true }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  const desktopHeight = await page.evaluate(
    () => document.documentElement.scrollHeight,
  );
  expect(desktopHeight).toBeLessThanOrEqual(1000);

  await page
    .getByRole("link", { name: "Open supporting evidence" })
    .click();
  await expect(page).toHaveURL(
    /\/reports\/backfield\?player=fixture-marcus-hale$/,
  );
  await expect(
    page.getByRole("heading", { name: "Backfield Control" }),
  ).toBeVisible();
  await page.goBack();

  const desktopNavigation = page.getByRole("navigation", {
    name: "Primary navigation",
  });
  await expect(desktopNavigation).toBeVisible();
  await desktopNavigation.getByRole("link", { name: "Reports" }).click();
  await expect(page).toHaveURL(/\/reports$/);
  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  await page.goBack();

  await page.screenshot({
    path: path.join(screenshotDirectory, "desktop-home.png"),
    fullPage: true,
    animations: "disabled",
  });

  expect(errors).toEqual([]);
});

test("mobile feed uses the bottom navigation without overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = monitorPageErrors(page);

  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      name: "Marcus Hale took control of the team backfield.",
    }),
  ).toBeVisible();

  const mobileNavigation = page.getByRole("navigation", {
    name: "Mobile navigation",
  });
  await expect(mobileNavigation).toBeVisible();
  await expect(
    mobileNavigation.getByRole("link", { name: "Search" }),
  ).toBeVisible();
  await expectEveryShareHasRawEvidence(page);
  await expect(
    page.getByText("+26.5 pp", { exact: true }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  const mobileHeight = await page.evaluate(
    () => document.documentElement.scrollHeight,
  );
  expect(mobileHeight).toBeLessThanOrEqual(1800);

  await page.screenshot({
    path: path.join(screenshotDirectory, "mobile-home.png"),
    fullPage: true,
    animations: "disabled",
  });

  await mobileNavigation.getByRole("link", { name: "Teams" }).click();
  await expect(page).toHaveURL(/\/teams$/);
  await expect(page.getByRole("heading", { name: "Teams" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  expect(errors).toEqual([]);
});

test("empty state is explicit on desktop and mobile", async ({ page }) => {
  const errors = monitorPageErrors(page);

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/?state=empty");
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published yet",
    }),
  ).toBeVisible();
  await expect(page.locator("[data-share-evidence]")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(screenshotDirectory, "desktop-empty.png"),
    fullPage: true,
    animations: "disabled",
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published yet",
    }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(screenshotDirectory, "mobile-empty.png"),
    fullPage: true,
    animations: "disabled",
  });

  expect(errors).toEqual([]);
});

test("unavailable state withholds findings", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/?state=unavailable");

  await expect(
    page.getByRole("heading", {
      name: "Role data is temporarily unavailable",
    }),
  ).toBeVisible();
  await expect(page.getByText(/No shares or findings are shown/i)).toBeVisible();
  await expect(page.locator("[data-share-evidence]")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);

  expect(errors).toEqual([]);
});
