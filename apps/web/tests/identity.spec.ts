import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

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

test("team and player directories retain exact evidence with consumer language", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/teams");
  await expect(page.getByRole("heading", { name: "Team role structure" })).toBeVisible();
  await expect(page.locator(".team-directory-item")).toHaveCount(8);
  const jvt = page.locator(".team-directory-item").filter({
    hasText: "Jacksonville Tide",
  });
  await expect(jvt).toContainText("27 of 34 opportunities");
  await expect(jvt).toContainText("11 of 32 targets");
  await expect(jvt).toContainText("Largest recent change");

  await page.goto("/players");
  await expect(page.locator(".player-directory-list > article")).toHaveCount(27);
  await page.getByLabel("Team", { exact: true }).selectOption("JVT");
  await page.getByLabel("Position").selectOption("RB");
  await expect(page.locator(".player-directory-list > article")).toHaveCount(2);
  await page.getByLabel("Report").selectOption("backfield_control");
  await expect(page.locator(".player-directory-list > article")).toHaveCount(1);
  await expect(page.getByText("27 of 34 opportunities", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Order")).toContainText("Report order");
});

test("team dossier starts with a deterministic role summary and progressive detail", async ({
  page,
}) => {
  await page.goto("/teams/JVT");
  await expect(page.getByRole("heading", { name: "Jacksonville Tide" })).toBeVisible();
  const summary = page.locator(".team-dossier-summary");
  await expect(summary).toContainText(
    "Marcus Hale leads Jacksonville Tide’s backfield with 27 of 34 opportunities.",
  );
  await expect(summary).toContainText(
    "Jonah Pike leads WR targets with 11 of 32.",
  );
  await expect(summary).toContainText(
    "Cole Mercer leads TE targets with 7 of 32.",
  );
  await expect(
    page.getByRole("heading", {
      name: "Biggest recent gains and declines",
    }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Backfield hierarchy" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "WR hierarchy" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "TE hierarchy" })).toBeVisible();
  await expect(page.getByText("Source version")).not.toBeVisible();
  await page.getByText("View deeper evidence").click();
  await expect(page.getByText("Source version")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Marcus Hale" }).first(),
  ).toHaveAttribute("href", "/players/player-marcus-hale");
});

test("player dossier uses three summaries, one weekly metric, and collapsed counts", async ({
  page,
}) => {
  const errors = monitorPageErrors(page);
  await page.goto("/players/player-marcus-hale");
  await expect(page.getByRole("heading", { name: "Marcus Hale" })).toBeVisible();
  const cards = page.locator(".player-summary-cards article");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0)).toContainText("Current role");
  await expect(cards.nth(0)).toContainText("27 of 34 opportunities");
  await expect(cards.nth(1)).toContainText("Gain · +23.1 pp");
  await expect(cards.nth(1)).toContainText("18/32");
  await expect(cards.nth(1)).toContainText("27/34");
  await expect(cards.nth(2)).toContainText("Team position");

  await expect(
    page.getByRole("heading", { name: "How the role changed week by week" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Total opportunities" }),
  ).toHaveAttribute("aria-pressed", "true");
  const weekButtons = page.locator(".weekly-chart-point");
  await expect(weekButtons).toHaveCount(18);
  await expect(
    page.getByRole("button", { name: /Week 18, 79\.4%/ }),
  ).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.getByText("View exact weekly counts").click();
  const table = page.getByRole("table");
  await expect(table).toBeVisible();
  await expect(table.locator("tbody tr")).toHaveCount(18);
  await expect(table).toContainText("79.4% · 27/34");
  await expect(table).toContainText("No evidence");

  await expect(page.getByRole("heading", { name: "Teammate comparison" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Movement history" })).toBeVisible();
  await expect(
    page.getByText("Weeks 15–18 compared with Weeks 11–14"),
  ).toBeVisible();
  await expect(page.getByText("Source version")).not.toBeVisible();
  await page.getByText("Technical details").click();
  await expect(page.getByText("Team-neutral player ID")).toBeVisible();
  await expect(page.getByText("Source version")).toBeVisible();
  await expectNoOverflow(page);
  expect(errors).toEqual([]);
});

test("weekly chart exposes focus details and a textual accessible equivalent", async ({
  page,
}) => {
  await page.goto("/players/player-marcus-hale");
  const week15 = page.getByRole("button", { name: /Week 15, 75\.0%/ });
  await week15.focus();
  const detail = page.locator(".weekly-trend-detail");
  await expect(detail).toContainText("Week 15");
  await expect(detail).toContainText("75.0%");
  await expect(detail).toContainText("24 of 32 opportunities");
  await expect(
    page.locator(".weekly-text-equivalent"),
  ).toContainText("Week 15:");
  await expect(page.locator(".weekly-text-equivalent")).toContainText(
    "24 of 32 opportunities",
  );
});

test("search uses plain player and team results with keyboard navigation", async ({
  page,
}) => {
  await page.goto("/search?focus=1");
  await expect(
    page.getByRole("heading", { name: "Search DepthSnap" }),
  ).toBeVisible();
  const input = page.getByRole("combobox", {
    name: "Search players and teams",
  });
  await expect(input).toBeFocused();
  await input.fill("mar");
  const first = page.getByRole("option").first();
  await expect(first).toContainText("Marcus Hale");
  await expect(first).toContainText("RB · Jacksonville Tide");
  await expect(first).toContainText("View player");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/players/player-marcus-hale");

  await page.goto("/search?focus=1");
  await page.getByRole("combobox").fill("JVT");
  await expect(page.getByRole("option").first()).toContainText(
    "Jacksonville Tide",
  );
  await expect(page.getByRole("option").first()).toContainText("View team");

  await page.getByRole("combobox").fill("hale");
  await expect(page.getByRole("option").first()).toContainText("Marcus Hale");

  await page.getByRole("combobox").fill("Jacksonville Tide");
  await expect(page.getByRole("option").first()).toContainText(
    "Jacksonville Tide",
  );

  const teamLink = page.getByRole("link", {
    name: "Jacksonville Tide, view team",
  });
  await expect(teamLink).toHaveCount(1);
  await teamLink.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL("/teams/JVT");
});

test("identity states and not-found pages stay truthful and plain", async ({
  page,
}) => {
  await page.goto("/teams?state=loading");
  await expect(page.getByLabel("Loading team directory")).toBeVisible();
  await page.goto("/players?state=unpublished");
  await expect(
    page.getByRole("heading", { name: /No completed week is published/ }),
  ).toBeVisible();
  await page.goto("/teams/JVT?state=unavailable");
  await expect(
    page.getByRole("heading", {
      name: "Jacksonville Tide evidence is unavailable",
    }),
  ).toBeVisible();
  await page.goto("/players/player-marcus-hale?state=unavailable");
  await expect(
    page.getByRole("heading", {
      name: "Marcus Hale evidence is unavailable",
    }),
  ).toBeVisible();
  await page.goto("/teams/unknown-team");
  await expect(
    page.getByRole("heading", { name: "This team is not available" }),
  ).toBeVisible();
  await page.goto("/players/player-unknown");
  await expect(
    page.getByRole("heading", { name: "This player is not available" }),
  ).toBeVisible();
});

test("normalized evidence agrees across feed, report, team, player, and search", async ({
  page,
}) => {
  const exact = "27 of 34 opportunities";
  for (const route of [
    "/",
    "/reports/backfield",
    "/teams/jvt",
    "/players/PLAYER-MARCUS-HALE",
    "/search?q=Marcus",
  ]) {
    await page.goto(route);
    await expect(page.locator("main")).toContainText(exact);
  }
});

test("mobile identity routes and weekly trend stay overflow free", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = monitorPageErrors(page);
  for (const route of [
    "/teams",
    "/teams/JVT",
    "/players",
    "/players/player-marcus-hale",
    "/search?q=mar",
  ]) {
    await page.goto(route);
    await expectNoOverflow(page);
    await expect(
      page.getByRole("navigation", { name: "Mobile navigation" }),
    ).toBeVisible();
  }
  await page.goto("/players/player-marcus-hale");
  await page
    .getByRole("heading", { name: "How the role changed week by week" })
    .scrollIntoViewIfNeeded();
  await expectNoOverflow(page);
  await expect(
    page.locator(".weekly-chart-point"),
  ).toHaveCount(18);
  expect(errors).toEqual([]);
});

test("normal identity and search pages contain no banned internal wording", async ({
  page,
}) => {
  for (const route of [
    "/teams",
    "/teams/JVT",
    "/players",
    "/players/player-marcus-hale",
    "/search",
  ]) {
    await page.goto(route);
    const text = (await page.locator("main").innerText()).toLowerCase();
    expect(text).not.toMatch(
      /\b(python-supplied|supplied hierarchy|supplied identity|authority rank|canonical identity|export status|export bundle|evidence team|future player|future team|default-report evidence)\b/,
    );
  }
});

test("identity source contains no score, projection, recommendation, or betting constructs", () => {
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
  const identityFiles = files.filter((file) =>
    /(identity|team-|player-|weekly|search-experience|\[team\]|\[playerId\])/.test(
      file,
    ),
  );
  const source = identityFiles
    .map((file) => readFileSync(file, "utf8"))
    .join("\n");
  expect(source).not.toMatch(/\b(RoleScore|ImpactScore|ConfidenceScore)\b/i);
  expect(source).not.toMatch(
    /\b(projection|betting|sportsbook|fantasy advice|recommendation)\b/i,
  );
});
