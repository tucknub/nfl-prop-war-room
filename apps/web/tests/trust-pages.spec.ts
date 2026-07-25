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
    "The evidence terms used throughout DepthSnap",
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
  await expect(page.locator(".evidence-glossary dt")).toHaveCount(7);
  await expect(page.getByText("Percentage-point change", { exact: true })).toBeVisible();
  await expectNoOverflow(page);
  expect(errors).toEqual([]);
});

test("Data Status renders supplied publication metadata, checks, and manifest hashes", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"], {
    origin: "http://127.0.0.1:3100",
  });
  const errors = captureErrors(page);
  await page.goto("/data-status");
  await expect(
    page.getByRole("heading", { name: "Publication integrity, in public." }),
  ).toBeVisible();
  await expect(page.getByText("Published", { exact: true })).toBeVisible();
  await expect(page.getByText("fixture", { exact: true })).toBeVisible();
  await expect(page.getByText("44 declared bundles")).toBeVisible();
  await expect(page.getByText("depthsnap", { exact: true })).toBeVisible();
  await expect(page.getByText("44 of 44", { exact: true })).toBeVisible();
  await expect(page.getByText("Required", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Blocking", { exact: true }).first()).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Manifest integrity" }),
  ).toBeVisible();
  await page
    .getByText("Show 44 manifest entries", { exact: false })
    .click();
  await expect(page.locator("code")).toHaveCount(44);
  const firstHash = await page.locator("code").first().innerText();
  await page
    .getByRole("button", { name: /Copy SHA-256 for home/i })
    .click();
  await expect(
    page.locator(".hash-copy-action").first().getByRole("status"),
  ).toHaveText("Copied SHA-256");
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe(firstHash);
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
  await expect(page.getByText("No week supplied", { exact: true })).toBeVisible();
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
    if (route === "/data-status") {
      await page.getByText(/Show 44 manifest entries/).click();
      await expect(
        page.getByRole("button", { name: /Copy SHA-256 for home/i }),
      ).toBeVisible();
    }
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
