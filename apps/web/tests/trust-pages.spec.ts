import { expect, test, type Page } from "@playwright/test";

function captureErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

async function expectNoOverflow(page: Page) {
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
}

test("Methodology exposes the supplied definitions and report navigation accessibly", async ({
  page,
}) => {
  const errors = captureErrors(page);
  await page.goto("/methodology");
  await expect(
    page.getByRole("heading", { name: "Read the count before the share." }),
  ).toBeVisible();
  for (const heading of [
    "What DepthSnap measures",
    "Three questions, one evidence grammar",
    "Numerator, denominator, and share",
    "All-play evidence leads; typical-game context supports",
    "Current, prior, and percentage-point movement",
    "A week publishes only after the operational checks pass",
    "Data quality has three supplied states",
    "Descriptive by design",
  ]) {
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();
  }
  await expect(
    page.getByRole("link", { name: "Open report" }),
  ).toHaveCount(3);
  await expect(
    page.getByRole("link", { name: "Open Data Status" }),
  ).toBeVisible();
  await expectNoOverflow(page);
  expect(errors).toEqual([]);
});

test("Data Status renders supplied publication metadata, checks, and manifest hashes", async ({
  page,
}) => {
  const errors = captureErrors(page);
  await page.goto("/data-status");
  await expect(
    page.getByRole("heading", { name: "Publication integrity, in public." }),
  ).toBeVisible();
  await expect(page.getByText("Published", { exact: true })).toBeVisible();
  await expect(page.getByText("fixture", { exact: true })).toBeVisible();
  await expect(page.getByText("44 declared bundles")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Manifest integrity" }),
  ).toBeVisible();
  await page
    .getByText("Show 44 manifest entries", { exact: false })
    .click();
  await expect(page.locator("code")).toHaveCount(44);
  await expectNoOverflow(page);
  expect(errors).toEqual([]);
});

test("Data Status preserves no-week and unavailable publication states", async ({
  page,
}) => {
  await page.goto("/data-status?state=unpublished");
  await expect(
    page.getByLabel("Publication state: No published week"),
  ).toBeVisible();
  await expect(page.getByText("no week supplied")).toBeVisible();
  await page.goto("/data-status?state=unavailable");
  await expect(
    page.getByLabel("Publication state: Unavailable"),
  ).toBeVisible();
  await expect(
    page.getByText(/intentionally represents an unavailable publication/i),
  ).toBeVisible();
});

test("trust pages and representative existing workflows remain mobile-safe", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const route of [
    "/methodology",
    "/data-status",
    "/",
    "/reports/backfield",
    "/teams/JVT",
    "/players/player-marcus-hale",
    "/search?q=Marcus",
  ]) {
    const errors = captureErrors(page);
    await page.goto(route);
    await expect(page.locator("main")).toBeVisible();
    await expectNoOverflow(page);
    const bottomNavigation = page.getByRole("navigation", {
      name: "Mobile navigation",
    });
    await expect(bottomNavigation).toBeVisible();
    const bottomBox = await bottomNavigation.boundingBox();
    const lastVisible = page.locator("main").locator("*:visible").last();
    const lastBox = await lastVisible.boundingBox();
    if (bottomBox && lastBox) {
      expect(lastBox.y + lastBox.height).toBeLessThanOrEqual(
        Math.max(
          bottomBox.y,
          await page.evaluate(() => document.documentElement.scrollHeight),
        ),
      );
    }
    expect(errors).toEqual([]);
  }
});

test("invalid public data copy does not appear in the rendered trust routes", async ({
  page,
}) => {
  for (const route of ["/methodology", "/data-status"]) {
    await page.goto(route);
    const copy = (await page.locator("main").innerText()).toLowerCase();
    for (const banned of [
      "confidence score",
      "impact score",
      "role score",
      "sportsbook",
      "start/sit",
      "lineup recommendation",
    ]) {
      expect(copy).not.toContain(banned);
    }
  }
});
