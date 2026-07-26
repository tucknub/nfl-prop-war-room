import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const reviewDirectory = path.resolve(
  process.cwd(),
  "../../docs/depthsnap/reviews/consumer-ux-simplification",
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

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport);
}

async function screenshot(
  page: Page,
  name: string,
  options: { fullPage?: boolean } = {},
) {
  await page.screenshot({
    path: path.join(reviewDirectory, name),
    animations: "disabled",
    fullPage: options.fullPage ?? false,
  });
}

test("historical 2025 home and reports present consumer answers with exact evidence", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Emanuel Wilson’s RB carry share fell from 20.0% to 7.7%.",
    }),
  ).toBeVisible();
  await expect(page.getByText("22 of 110 carries", { exact: true })).toBeVisible();
  await expect(page.getByText("1 of 13 carries", { exact: true })).toBeVisible();
  await expect(page.getByText("Decline", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("-12.3 pp", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("note")).toContainText("unusual game context");
  await expect(
    page.getByText("Weeks 15–18 compared with Weeks 11–14", { exact: true }).first(),
  ).toBeVisible();
  await expectNoFixtureFallback(page);
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "desktop-home.png");

  await page.goto("/reports/backfield");
  await expect(
    page.getByRole("heading", { name: "Backfield Control", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Total opportunities" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Sort")).toHaveValue("share");
  const backfieldRows = page.getByTestId("report-row");
  await expect(backfieldRows.first()).toContainText("Ashton Jeanty");
  await expect(backfieldRows.first()).toContainText("Las Vegas Raiders");
  await expect(backfieldRows.first()).toContainText("90 of 98 opportunities");
  const backfieldPlayers = await backfieldRows.locator(".report-player-cell strong").allTextContents();
  expect(new Set(backfieldPlayers).size).toBe(backfieldPlayers.length);
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "desktop-backfield-control.png");

  await page.getByRole("button", { name: "Carries", exact: true }).click();
  await expect(backfieldRows.first()).toContainText("75 of 92 carries");
  const carryPlayers = await backfieldRows.locator(".report-player-cell strong").allTextContents();
  expect(new Set(carryPlayers).size).toBe(carryPlayers.length);

  await page.goto("/reports/targets");
  await expect(
    page.getByRole("button", { name: "Wide receivers" }),
  ).toHaveAttribute("aria-pressed", "true");
  const targetRows = page.getByTestId("report-row");
  await expect(targetRows.first()).toContainText("Jaxon Smith-Njigba");
  await expect(targetRows.first()).toContainText("Seattle Seahawks");
  await expect(targetRows.first()).toContainText("42 of 116 targets");
  const targetPlayers = await targetRows.locator(".report-player-cell strong").allTextContents();
  expect(new Set(targetPlayers).size).toBe(targetPlayers.length);
  await screenshot(page, "desktop-target-hierarchy.png");

  await page.goto("/reports/movement");
  await expect(
    page.getByRole("button", { name: "Biggest gains" }),
  ).toHaveAttribute("aria-pressed", "true");
  const movementRows = page.getByTestId("report-row");
  await expect(movementRows.first()).toContainText("Audric Estimé");
  await expect(movementRows.first()).toContainText("Gain");
  await expect(movementRows.first()).toContainText("+68.2 pp");
  await expect(movementRows.first()).toContainText("3 of 66 opportunities");
  await expect(movementRows.first()).toContainText("56 of 77 opportunities");
  await screenshot(page, "desktop-role-movement-gainers.png");

  await page.getByRole("button", { name: "Biggest declines" }).click();
  await expect(movementRows.first()).toContainText("Decline");
  await expect(movementRows.first().locator(".movement-finding-decline")).toBeVisible();
  await screenshot(page, "desktop-role-movement-declines.png");

  expect(errors).toEqual([]);
});

test("historical dossiers, weekly trend, search, and evidence drawer use progressive disclosure", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/players/00-0038797");
  await expect(page.getByRole("heading", { name: "Emanuel Wilson" })).toBeVisible();
  const summary = page.getByLabel("Emanuel Wilson role summary");
  await expect(summary.locator("article")).toHaveCount(3);
  await expect(summary).toContainText("Current role");
  await expect(summary).toContainText("Recent change");
  await expect(summary).toContainText("Team position");
  await expect(page.getByText("Source version")).not.toBeVisible();
  await screenshot(page, "desktop-player-dossier-top.png");

  const weeklyTrend = page.locator(".weekly-timeline");
  await weeklyTrend.scrollIntoViewIfNeeded();
  await expect(
    weeklyTrend.getByRole("button", { name: "Total opportunities" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(weeklyTrend.locator(".weekly-trend-chart > li > button")).toHaveCount(18);
  await expect(weeklyTrend.getByRole("table")).toHaveCount(0);
  await weeklyTrend
    .getByRole("button", { name: "Carries", exact: true })
    .click();
  await expect(
    weeklyTrend.getByRole("button", { name: "Carries", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    weeklyTrend.getByRole("button", { name: /Week 18,/ }),
  ).toBeVisible();
  await expect(weeklyTrend.locator(".weekly-text-equivalent")).toContainText("Week 18:");
  await screenshot(page, "desktop-player-weekly-trend.png");

  await weeklyTrend.getByText("View exact weekly counts").click();
  await expect(weeklyTrend.getByRole("table")).toBeVisible();
  await expect(weeklyTrend.getByRole("row")).toHaveCount(19);
  await page.getByText("Technical details", { exact: true }).click();
  await expect(page.getByText(/Team-neutral player ID/)).toBeVisible();
  await expect(page.getByText("Source version")).toBeVisible();

  await page.goto("/teams/ARI");
  await expect(
    page.getByRole("heading", { name: "Arizona Cardinals" }),
  ).toBeVisible();
  await expect(page.locator(".team-dossier-summary")).toContainText(
    "leads Arizona Cardinals’ backfield",
  );
  await expect(page.getByText("View deeper evidence")).toBeVisible();
  await expect(page.getByText("Source version")).not.toBeVisible();
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "desktop-team-dossier.png");

  await page.goto("/search?q=Jaxon");
  await expect(
    page.getByRole("heading", { name: "Search DepthSnap" }),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Search players and teams" }),
  ).toHaveValue("Jaxon");
  const result = page.getByRole("option").first();
  await expect(result).toContainText("Jaxon Smith-Njigba");
  await expect(result).toContainText("Seattle Seahawks");
  await expect(result).toContainText("View player");
  await screenshot(page, "desktop-search.png");

  await page.goto("/reports/targets");
  await page
    .getByRole("button", { name: "View evidence for Jaxon Smith-Njigba" })
    .click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toContainText(
    "Jaxon Smith-Njigba received 42 of Seattle Seahawks’ 116 documented targets",
  );
  await expect(drawer.getByRole("link", { name: "View player dossier" })).toHaveAttribute(
    "href",
    "/players/00-0038543",
  );
  await expect(drawer.getByRole("link", { name: "View team dossier" })).toHaveAttribute(
    "href",
    "/teams/SEA",
  );
  await expect(drawer.getByText("Source version")).not.toBeVisible();
  await screenshot(page, "desktop-evidence-drawer.png");
  await drawer.getByText("Technical details", { exact: true }).click();
  await expect(drawer.getByText("Source version")).toBeVisible();
  await screenshot(page, "desktop-evidence-drawer-technical.png");
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);

  await expectNoFixtureFallback(page);
  expect(errors).toEqual([]);
});

test("historical export remains readable at desktop and mobile review widths", async ({
  page,
}) => {
  const errors = monitorPageErrors(page);

  for (const width of [1280, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ["/", "/reports/backfield", "/reports/targets", "/reports/movement"]) {
      await page.goto(route);
      await expectNoHorizontalOverflow(page);
    }
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "mobile-home.png");

  await page.goto("/reports/movement");
  await expect(page.getByTestId("report-row").first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "mobile-role-movement.png");

  await page.goto("/players/00-0038797");
  const weeklyTrend = page.locator(".weekly-timeline");
  await weeklyTrend.locator("header").scrollIntoViewIfNeeded();
  await expect(weeklyTrend.locator(".weekly-trend-chart > li > button")).toHaveCount(18);
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "mobile-player-weekly-trend.png");

  await page.goto("/search?q=Jaxon");
  await expect(page.getByRole("option").first()).toContainText("Jaxon Smith-Njigba");
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "mobile-search.png");

  await page.setViewportSize({ width: 430, height: 932 });
  for (const route of ["/", "/reports/movement", "/players/00-0038797", "/search?q=Jaxon"]) {
    await page.goto(route);
    await expectNoHorizontalOverflow(page);
  }

  expect(errors).toEqual([]);
});

test("historical export publishes 586 validated bundles without internal or fixture fallback copy", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/data-status");
  await expect(page.getByLabel("Publication state: Published")).toBeVisible();
  await expect(page.getByText("export", { exact: true })).toBeVisible();
  await expect(page.getByText("586 declared bundles")).toBeVisible();
  await expect(page.getByText("Week 18", { exact: true })).toBeVisible();

  for (const route of [
    "/",
    "/reports",
    "/reports/backfield",
    "/reports/targets",
    "/reports/movement",
    "/teams/ARI",
    "/players/00-0038797",
    "/search?q=Jaxon",
  ]) {
    await page.goto(route);
    const text = (await page.locator("main").innerText()).toLowerCase();
    expect(text).not.toMatch(
      /\b(python-supplied|supplied python order|authority rank|canonical identity|export bundle|export identities|evidence-team|supplied membership|supplied hierarchy|supplied periods|supplied role|future player|future team|future report)\b/,
    );
    await expectNoFixtureFallback(page);
  }

  expect(errors).toEqual([]);
});
