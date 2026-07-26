import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";

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

async function expectInViewport(locator: Locator, viewportHeight: number) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.y).toBeGreaterThanOrEqual(0);
  expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(
    viewportHeight,
  );
}

test("desktop composes the approved four-module dashboard at 1440 by 900", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/");

  await expect(page.getByRole("link", { name: "DepthSnap home" })).toBeVisible();
  await expect(
    page.getByText("NFL Role Intelligence", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/synthetic records/i)).toBeVisible();

  const heroHeading = page.getByRole("heading", {
    name: "Marcus Hale’s RB opportunity share rose from 56.3% to 79.4%.",
  });
  const movementHeading = page.getByRole("heading", {
    name: "Recent role changes",
  });
  const teamHeading = page.getByRole("heading", { name: "Team role snapshot" });
  const leaderboardHeading = page.getByRole("heading", {
    name: "Quick leaders",
  });

  await expect(heroHeading).toBeVisible();
  await expect(movementHeading).toBeVisible();
  await expect(teamHeading).toBeVisible();
  await expect(leaderboardHeading).toBeVisible();
  await expectInViewport(heroHeading, 900);
  await expectInViewport(movementHeading, 900);
  await expectInViewport(teamHeading, 900);
  await expectInViewport(leaderboardHeading, 900);

  const heroPanel = page.locator(".lead-panel");
  const heroMedia = page.getByTestId("lead-media");
  await expect(heroMedia).toBeVisible();
  await expect(
    heroMedia.getByRole("img", {
      name: "Fictional football running back carrying the ball",
    }),
  ).toBeVisible();
  const heroBox = await heroPanel.boundingBox();
  const mediaBox = await heroMedia.boundingBox();
  expect(heroBox).not.toBeNull();
  expect(mediaBox).not.toBeNull();
  const mediaRatio = (mediaBox?.width ?? 0) / (heroBox?.width ?? 1);
  expect(mediaRatio).toBeGreaterThanOrEqual(0.35);
  expect(mediaRatio).toBeLessThanOrEqual(0.5);

  await expect(page.getByTestId("movement-row")).toHaveCount(3);
  await expect(page.getByText("+26.5 pp", { exact: true })).toBeVisible();

  const teamSnapshot = page.getByTestId("team-snapshot");
  await expect(teamSnapshot.getByText("JT", { exact: true })).toBeVisible();
  await expect(
    teamSnapshot.getByText("Jacksonville Tide", { exact: true }),
  ).toBeVisible();
  await expect(teamSnapshot.getByText("Week 18", { exact: true })).toBeVisible();
  await expect(teamSnapshot.getByText("Backfield leader", { exact: true })).toBeVisible();
  await expect(teamSnapshot.getByText("Secondary back", { exact: true })).toBeVisible();
  await expect(teamSnapshot.getByText("WR target leader", { exact: true })).toBeVisible();
  await expect(teamSnapshot.getByText("TE target leader", { exact: true })).toBeVisible();
  await expect(
    teamSnapshot.getByText("Biggest recent change", { exact: true }),
  ).toBeVisible();
  await expect(
    teamSnapshot.getByRole("link", { name: "View team dossier" }),
  ).toBeVisible();

  const leaderboard = page.getByTestId("report-leaderboard");
  const backfieldTab = leaderboard.getByRole("tab", {
    name: "Backfield Control",
  });
  await expect(backfieldTab).toHaveAttribute("aria-selected", "true");
  await expect(
    leaderboard.getByRole("tab", { name: "Target Hierarchy" }),
  ).toBeVisible();
  await expect(
    leaderboard.getByRole("tab", { name: "Role Movement" }),
  ).toBeVisible();
  const backfieldLeaderNames = await leaderboard
    .getByTestId("leaderboard-row")
    .locator(".leaderboard-player strong")
    .allTextContents();
  expect(new Set(backfieldLeaderNames).size).toBe(backfieldLeaderNames.length);
  await expect(leaderboard.getByText(/role score/i)).toHaveCount(0);
  await expectEveryShareHasRawEvidence(page);

  const targetTab = leaderboard.getByRole("tab", {
    name: "Target Hierarchy",
  });
  await targetTab.click();
  await expect(targetTab).toHaveAttribute("aria-selected", "true");
  await expect(leaderboard.getByText("Theo Lane", { exact: true })).toBeVisible();
  const targetLeaderNames = await leaderboard
    .getByTestId("leaderboard-row")
    .locator(".leaderboard-player strong")
    .allTextContents();
  expect(new Set(targetLeaderNames).size).toBe(targetLeaderNames.length);
  await backfieldTab.click();

  await expectNoHorizontalOverflow(page);
  const desktopHeight = await page.evaluate(
    () => document.documentElement.scrollHeight,
  );
  expect(desktopHeight).toBeLessThanOrEqual(900);

  await page
    .getByRole("link", { name: "View evidence", exact: true })
    .click();
  await expect(page).toHaveURL(
    /\/reports\/backfield\?player=player-marcus-hale$/,
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
    animations: "disabled",
  });

  expect(errors).toEqual([]);
});

test("mobile uses the required module order and keeps navigation clear", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = monitorPageErrors(page);

  await page.goto("/");
  await expect(
    page.getByLabel("Loading DepthSnap findings"),
  ).toHaveCount(0);

  const hero = page.locator(".lead-panel");
  const movement = page.locator(".movement-panel");
  const team = page.getByTestId("team-snapshot");
  const leaderboard = page.getByTestId("report-leaderboard");
  const heroMedia = page.getByTestId("lead-media");
  const movementRows = page.getByTestId("movement-row");

  await expect(hero).toBeVisible();
  await expect(heroMedia).toBeVisible();
  const mobileMediaBox = await heroMedia.boundingBox();
  expect(mobileMediaBox).not.toBeNull();
  expect(mobileMediaBox?.height).toBeGreaterThanOrEqual(140);
  await expect(movementRows).toHaveCount(3);

  const heroBox = await hero.boundingBox();
  const movementBox = await movement.boundingBox();
  const teamBox = await team.boundingBox();
  const leaderboardBox = await leaderboard.boundingBox();
  expect(heroBox).not.toBeNull();
  expect(movementBox).not.toBeNull();
  expect(teamBox).not.toBeNull();
  expect(leaderboardBox).not.toBeNull();
  expect((heroBox?.y ?? 0) + (heroBox?.height ?? 0)).toBeLessThanOrEqual(
    movementBox?.y ?? 0,
  );
  expect((movementBox?.y ?? 0) + (movementBox?.height ?? 0)).toBeLessThanOrEqual(
    teamBox?.y ?? 0,
  );
  expect((teamBox?.y ?? 0) + (teamBox?.height ?? 0)).toBeLessThanOrEqual(
    leaderboardBox?.y ?? 0,
  );

  const mobileNavigation = page.getByRole("navigation", {
    name: "Mobile navigation",
  });
  await expect(mobileNavigation).toBeVisible();
  await expect(
    mobileNavigation.getByRole("link", { name: "Search" }),
  ).toBeVisible();
  const navBox = await mobileNavigation.boundingBox();
  const lastMovementBox = await movementRows.last().boundingBox();
  expect(navBox).not.toBeNull();
  expect(lastMovementBox).not.toBeNull();
  expect(navBox?.y).toBeGreaterThanOrEqual(
    (lastMovementBox?.y ?? 0) + (lastMovementBox?.height ?? 0),
  );

  const mobileClearance = await page.locator(".page-shell").evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).paddingBottom),
  );
  expect(mobileClearance).toBeGreaterThanOrEqual(112);

  await expectEveryShareHasRawEvidence(page);
  await expectNoHorizontalOverflow(page);

  await page.screenshot({
    path: path.join(screenshotDirectory, "mobile-home.png"),
    fullPage: true,
    animations: "disabled",
  });

  await mobileNavigation.getByRole("link", { name: "Teams" }).click();
  await expect(page).toHaveURL(/\/teams$/);
  await expect(page.getByRole("heading", { name: "Teams" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const routeClearance = await page.locator(".page-shell").evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).paddingBottom),
  );
  expect(routeClearance).toBeGreaterThanOrEqual(112);
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
  await expect(page.locator("[data-share-evidence]")).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
  const mobileClearance = await page.locator(".page-shell").evaluate((element) =>
    Number.parseFloat(getComputedStyle(element).paddingBottom),
  );
  expect(mobileClearance).toBeGreaterThanOrEqual(112);
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
