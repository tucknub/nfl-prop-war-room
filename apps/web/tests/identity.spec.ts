import { readFileSync, readdirSync, mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const screenshotDirectory = path.join(process.cwd(), "artifacts", "screenshots");

test.beforeAll(() => mkdirSync(screenshotDirectory, { recursive: true }));

function monitorPageErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  return errors;
}

async function expectNoOverflow(page: Page) {
  const sizes = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(sizes.document).toBeLessThanOrEqual(sizes.viewport);
  expect(sizes.body).toBeLessThanOrEqual(sizes.viewport);
}

async function capture(page: Page, name: string, fullPage = false) {
  await page.screenshot({
    path: path.join(screenshotDirectory, name),
    animations: "disabled",
    fullPage,
  });
}

test("teams directory filters supplied teams and preserves exact raw evidence", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);
  await page.goto("/teams");
  await expect(page.getByRole("heading", { name: "Team role structure" })).toBeVisible();
  await expect(page.getByText(/synthetic records/i)).toBeVisible();
  await expect(page.locator(".team-directory-item")).toHaveCount(8);
  const jvt = page.locator(".team-directory-item").filter({ hasText: "Jacksonville Tide" });
  await expect(jvt).toContainText("27 of 34 opportunities");
  await expect(jvt).toContainText("11 of 32 targets");
  await capture(page, "phase3-desktop-teams.png");

  await page.getByLabel("Search teams").fill("Portland");
  await expect(page.locator(".team-directory-item")).toHaveCount(1);
  await page.getByRole("link", { name: "Open team dossier" }).click();
  await expect(page).toHaveURL("/teams/PDX");
  await expect(page.getByRole("heading", { name: "Portland Pioneers" })).toBeVisible();
  await expectNoOverflow(page);
  expect(errors).toEqual([]);
});

test("team dossier combines all three report families and stable player links", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/teams/JVT");
  await expect(page.getByRole("heading", { name: "Jacksonville Tide" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Backfield hierarchy" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "WR target hierarchy" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "TE target hierarchy" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Biggest supplied movements" })).toBeVisible();
  await expect(page.getByText("27 of 34 opportunities", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("11 of 32 targets", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Marcus Hale" }).first()).toHaveAttribute("href", "/players/player-marcus-hale");
  await capture(page, "phase3-desktop-team-dossier.png");

  await page.getByRole("link", { name: "Marcus Hale" }).first().click();
  await expect(page).toHaveURL("/players/player-marcus-hale");
  await expect(page.getByRole("heading", { name: "Marcus Hale" })).toBeVisible();
});

test("players directory filters by identity and supplied report membership", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/players");
  await expect(page.getByRole("heading", { name: "Player role evidence" })).toBeVisible();
  await expect(page.locator(".player-directory-list > article")).toHaveCount(27);
  await capture(page, "phase3-desktop-players.png");
  await page.getByLabel("Team", { exact: true }).selectOption("JVT");
  await page.getByLabel("Position", { exact: true }).selectOption("RB");
  await expect(page.locator(".player-directory-list > article")).toHaveCount(2);
  await page.getByLabel("Report", { exact: true }).selectOption("backfield_control");
  await expect(page.locator(".player-directory-list > article")).toHaveCount(1);
  await expect(page.getByText("27 of 34 opportunities", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Open dossier" }).click();
  await expect(page).toHaveURL("/players/player-marcus-hale");
});

test("player dossier exposes exact weekly chronology, context, movements, and memberships", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);
  await page.goto("/players/player-marcus-hale");
  await expect(page.getByRole("heading", { name: "Marcus Hale" })).toBeVisible();
  await expect(page.getByText("27 of 34 opportunities", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Weekly role timeline" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Week 18");
  await expect(page.getByRole("table")).toContainText("27 of 34 opportunities");
  await expect(page.getByRole("table")).toContainText("No supplied evidence");
  await expect(page.getByRole("heading", { name: "Current reports" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Team hierarchy context" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Movement history" })).toBeVisible();
  await capture(page, "phase3-desktop-player-dossier.png");
  await page.getByRole("heading", { name: "Weekly role timeline" }).scrollIntoViewIfNeeded();
  await capture(page, "phase3-desktop-player-timeline.png");
  await expectNoOverflow(page);
  expect(errors).toEqual([]);
});

test("global search prioritizes supplied identities and supports keyboard navigation", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page.getByRole("link", { name: "Search players and teams" }).click();
  await expect(page).toHaveURL(/\/search\?focus=1/);
  await expect(page.getByRole("combobox", { name: "Search fixture identities" })).toBeFocused();
  await page.goto("/");
  await page.keyboard.press("/");
  await expect(page).toHaveURL(/\/search\?focus=1/);
  const input = page.getByRole("combobox", { name: "Search fixture identities" });
  await expect(input).toBeFocused();
  await input.fill("mar");
  await expect(page.getByRole("option").first()).toContainText("Marcus Hale");
  await capture(page, "phase3-desktop-search.png");
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("option").nth(1)).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowUp");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/players/player-marcus-hale");

  await page.goto("/search?focus=1");
  await input.fill("JVT");
  await expect(page.getByRole("option").first()).toContainText("Jacksonville Tide");
  await page.keyboard.press("Escape");
  await expect(input).toHaveValue("");
  const ids = await page.getByRole("option").evaluateAll((elements) => elements.map((element) => element.id));
  expect(new Set(ids).size).toBe(ids.length);
});

test("identity states distinguish loading, unpublished, unavailable, filters, and not found", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/teams?state=loading");
  await expect(page.getByLabel("Loading team directory")).toBeVisible();
  await page.goto("/players?state=unpublished");
  await expect(page.getByRole("heading", { name: /No completed week is published/ })).toBeVisible();
  await page.goto("/teams/JVT?state=unavailable");
  await expect(page.getByRole("heading", { name: "Jacksonville Tide evidence is unavailable" })).toBeVisible();
  await capture(page, "phase3-desktop-unavailable-team.png");
  await page.goto("/players/player-marcus-hale?state=unavailable");
  await expect(page.getByRole("heading", { name: "Marcus Hale evidence is unavailable" })).toBeVisible();
  await capture(page, "phase3-desktop-unavailable-player.png");

  await page.goto("/teams/unknown-team");
  await expect(page.getByRole("heading", { name: "This team identity is not in the fixture bundle" })).toBeVisible();
  await capture(page, "phase3-desktop-unknown-team.png");
  await page.goto("/players/player-unknown");
  await expect(page.getByRole("heading", { name: "This player identity is not in the fixture bundle" })).toBeVisible();
  await capture(page, "phase3-desktop-unknown-player.png");

  await page.goto("/teams");
  await page.getByLabel("Search teams").fill("no such team");
  await expect(page.getByRole("heading", { name: /No fixture teams match/ })).toBeVisible();
  await page.getByRole("button", { name: "Reset team search" }).click();
  await expect(page.locator(".team-directory-item")).toHaveCount(8);
});

test("normalized evidence agrees across Feed, report, team, player, and search", async ({ page }) => {
  const exact = "27 of 34 opportunities";
  await page.goto("/");
  await expect(page.getByText(exact, { exact: true }).first()).toBeVisible();
  await page.goto("/reports/backfield");
  await expect(page.getByTestId("report-row").first()).toContainText(exact);
  await page.goto("/teams/jvt");
  await expect(page.getByText(exact, { exact: true }).first()).toBeVisible();
  await page.goto("/players/PLAYER-MARCUS-HALE");
  await expect(page.getByText(exact, { exact: true }).first()).toBeVisible();
  await page.goto("/search?q=Marcus");
  await expect(page.getByRole("option").first()).toContainText(exact);
});

test("mobile identity routes are purpose built, overflow free, and clear the fixed navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const routes = [
    ["/teams", "phase3-mobile-teams.png"],
    ["/teams/JVT", "phase3-mobile-team-dossier.png"],
    ["/players", "phase3-mobile-players.png"],
    ["/players/player-marcus-hale", "phase3-mobile-player-dossier.png"],
    ["/search?q=mar", "phase3-mobile-search.png"],
  ] as const;
  for (const [route, image] of routes) {
    await page.goto(route);
    await expect(page.locator(".identity-page-shell:not([aria-busy='true'])")).toBeVisible();
    await expectNoOverflow(page);
    const clearance = await page.locator(".identity-page-shell:not([aria-busy='true'])").evaluate((element) => Number.parseFloat(getComputedStyle(element).paddingBottom));
    expect(clearance).toBeGreaterThanOrEqual(112);
    const navigation = page.getByRole("navigation", { name: "Mobile navigation" });
    await expect(navigation).toBeVisible();
    await capture(page, image, true);
  }

  await page.goto("/search?focus=1");
  await expect(page.getByRole("combobox")).toBeFocused();
  await page.getByRole("combobox").fill("JVT");
  await capture(page, "phase3-mobile-search-open.png");

  await page.goto("/players/player-marcus-hale");
  await page.getByRole("heading", { name: "Weekly role timeline" }).scrollIntoViewIfNeeded();
  await expectNoOverflow(page);
  await capture(page, "phase3-mobile-player-timeline.png");

  await page.goto("/teams/unknown");
  await capture(page, "phase3-mobile-unknown-team.png");
  await page.goto("/players/player-unknown");
  await capture(page, "phase3-mobile-unknown-player.png");
});

test("mobile Search navigation opens and active controls remain accessible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Mobile navigation" });
  await nav.getByRole("link", { name: "Search" }).click();
  await expect(page).toHaveURL("/search");
  await expect(page.getByRole("combobox")).toBeFocused();
  await page.getByRole("combobox").fill("Theo");
  await expect(page.getByRole("option").first()).toContainText("Theo Lane");
  await page.getByRole("option").first().getByRole("link").focus();
  await expect(page.getByRole("option").first().getByRole("link")).toBeFocused();
});

test("captures Phase 1 and Phase 2 regression views without changing their layout", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await capture(page, "phase3-regression-desktop-feed.png");
  await page.goto("/reports/backfield");
  await capture(page, "phase3-regression-desktop-backfield.png");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await capture(page, "phase3-regression-mobile-feed.png", true);
  await page.goto("/reports/backfield");
  await capture(page, "phase3-regression-mobile-backfield.png", true);
});

test("Phase 3 public source contains no score, projection, recommendation, betting, or fantasy constructs", () => {
  const sourceRoot = path.join(process.cwd(), "src");
  const files: string[] = [];
  const visit = (directory: string) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(target);
      else if (/\.(ts|tsx)$/.test(entry.name)) files.push(target);
    }
  };
  visit(sourceRoot);
  const phase3Files = files.filter((file) =>
    /(identity|team-|player-|weekly|search-experience|\[team\]|\[playerId\])/.test(file),
  );
  const source = phase3Files.map((file) => readFileSync(file, "utf8")).join("\n");
  expect(source).not.toMatch(/\b(RoleScore|ImpactScore|ConfidenceScore)\b/i);
  expect(source).not.toMatch(/\b(projection|betting|sportsbook|fantasy advice|recommendation)\b/i);
});
