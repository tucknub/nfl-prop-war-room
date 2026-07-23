import { readFileSync } from "node:fs";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const screenshotDirectory = path.join(process.cwd(), "artifacts", "screenshots");

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
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
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

async function screenshot(
  page: Page,
  name: string,
  fullPage = true,
) {
  await page.screenshot({
    path: path.join(screenshotDirectory, name),
    fullPage,
    animations: "disabled",
  });
}

async function expectEveryCurrentShareHasRawEvidence(page: Page) {
  const evidence = page.locator(".report-result-row [data-share-evidence]");
  const count = await evidence.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    const text = await evidence.nth(index).innerText();
    expect(text).toMatch(/\d+\.\d%/);
    expect(text).toMatch(/\d+ of \d+ (opportunities|targets)/);
  }
}

test("reports overview presents exactly three evidence families and working routes", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);
  await page.goto("/reports");

  await expect(page.getByRole("heading", { name: "Reports" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Follow the evidence" }),
  ).toBeVisible();
  await expect(page.getByText(/synthetic records/i)).toBeVisible();
  await expect(page.locator(".report-family-card")).toHaveCount(3);
  await expect(
    page.getByRole("heading", {
      name: "Who owns each team’s documented RB opportunities?",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Who owns each team’s documented WR and TE targets?",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Whose documented role changed most between supplied periods?",
    }),
  ).toBeVisible();

  const routes = [
    ["Open Backfield Control", "/reports/backfield"],
    ["Open Target Hierarchy", "/reports/targets"],
    ["Open Role Movement", "/reports/movement"],
  ] as const;
  for (const [label, route] of routes) {
    await expect(page.getByRole("link", { name: label })).toHaveAttribute(
      "href",
      route,
    );
  }

  await expectNoHorizontalOverflow(page);
  await screenshot(page, "phase2-desktop-reports-overview.png", false);
  expect(errors).toEqual([]);
});

test("Backfield Control preserves authority, raw evidence, filters, sorts, and details", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);
  await page.goto("/reports/backfield");

  await expect(
    page.getByRole("heading", { name: "Backfield Control" }),
  ).toBeVisible();
  await expect(page.getByText(/synthetic records/i)).toBeVisible();
  await expect(page.getByTestId("report-row")).toHaveCount(6);
  await expect(
    page.getByTestId("report-row").first().getByText("Marcus Hale", {
      exact: true,
    }),
  ).toBeVisible();
  await expectEveryCurrentShareHasRawEvidence(page);
  await expectNoHorizontalOverflow(page);
  await screenshot(page, "phase2-desktop-backfield.png", false);

  await page.getByLabel("View", { exact: true }).selectOption("season");
  await expect(page).toHaveURL(/view=season/);
  await expect(page.getByTestId("report-row")).toHaveCount(4);

  await page.getByLabel("Team", { exact: true }).selectOption("JVT");
  await expect(page).toHaveURL(/team=JVT/);
  await expect(page.getByTestId("report-row")).toHaveCount(1);

  await page.getByLabel("Team", { exact: true }).selectOption("ALL");
  await page.getByLabel("View", { exact: true }).selectOption("last4");
  await page.getByLabel("Sort", { exact: true }).selectOption("share");
  await expect(page).toHaveURL(/sort=share/);
  const sortedPlayers = await page
    .locator(".report-player-cell > strong")
    .allTextContents();
  expect(sortedPlayers.slice(0, 5)).toEqual([
    "Marcus Hale",
    "Caleb Stone",
    "Jordan Vale",
    "Micah Reed",
    "Zion Mercer",
  ]);

  const evidenceTrigger = page.getByRole("button", {
    name: "Open evidence for Marcus Hale",
  });
  await evidenceTrigger.click();
  const dialog = page.getByRole("dialog", { name: "Marcus Hale" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("27 of 34 opportunities")).toBeVisible();
  await screenshot(page, "phase2-desktop-backfield-detail.png", false);
  await dialog.getByRole("button", { name: "Close evidence detail" }).click();
  await expect(dialog).toBeHidden();
  await expect(evidenceTrigger).toBeFocused();
  expect(errors).toEqual([]);
});

test("Backfield Control distinguishes a no-match filter from report availability", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/reports/backfield?team=SEA");
  await expect(
    page.getByRole("heading", { name: "No supplied rows match this view" }),
  ).toBeVisible();
  await expect(page.getByText("6 supplied results")).toHaveCount(0);
  await expect(page.getByText("0 supplied results")).toBeVisible();
  await screenshot(page, "phase2-desktop-no-matching-filters.png", false);
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page).toHaveURL("/reports/backfield");
  await expect(page.getByTestId("report-row")).toHaveCount(6);
});

test("Target Hierarchy exposes All, WR, and TE URL-backed views with raw target counts", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);
  await page.goto("/reports/targets?view=season&position=TE&team=MIN");

  await expect(page.getByLabel("View", { exact: true })).toHaveValue("season");
  await expect(page.getByLabel("Position")).toHaveValue("TE");
  await expect(page.getByLabel("Team", { exact: true })).toHaveValue("MIN");
  await expect(page.getByTestId("report-row")).toHaveCount(1);
  await expect(
    page.getByTestId("report-row").getByText("Drew Keaton", { exact: true }),
  ).toBeVisible();
  await expectEveryCurrentShareHasRawEvidence(page);

  await page.getByLabel("View", { exact: true }).selectOption("last4");
  await page.getByLabel("Team", { exact: true }).selectOption("ALL");
  await page.getByLabel("Position").selectOption("WR");
  await expect(page).toHaveURL(/position=WR/);
  await expect(page.getByTestId("report-row")).toHaveCount(4);

  await page.getByLabel("Position").selectOption("TE");
  await expect(page).toHaveURL(/position=TE/);
  await expect(page.getByTestId("report-row")).toHaveCount(3);
  for (const row of await page.getByTestId("report-row").all()) {
    await expect(row.getByText("TE", { exact: true }).first()).toBeVisible();
  }

  await page.getByRole("button", { name: "Open evidence for Drew Keaton" }).click();
  await expect(page.getByRole("dialog", { name: "Drew Keaton" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  await page.getByLabel("Position").selectOption("ALL");
  await expect(page).not.toHaveURL(/position=/);
  await screenshot(page, "phase2-desktop-targets.png", false);
  await expectNoHorizontalOverflow(page);
  expect(errors).toEqual([]);
});

test("Role Movement renders previous and current raw evidence with explicit direction sorts", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);
  await page.goto("/reports/movement");

  await expect(page.getByTestId("report-row")).toHaveCount(6);
  const rows = page.getByTestId("report-row");
  for (let index = 0; index < (await rows.count()); index += 1) {
    await expect(rows.nth(index).locator("[data-prior-evidence]")).toContainText(
      /\d+ of \d+ (opportunities|carries|targets)/,
    );
    await expect(rows.nth(index).locator("[data-current-evidence]")).toContainText(
      /\d+ of \d+ (opportunities|carries|targets)/,
    );
    await expect(rows.nth(index).locator(".movement-direction")).toHaveAttribute(
      "aria-label",
      /(gain|decline) from previous to current/,
    );
  }
  await screenshot(page, "phase2-desktop-movement.png", false);

  await page.getByLabel("Sort", { exact: true }).selectOption("gainers");
  await expect(page).toHaveURL(/sort=gainers/);
  await expect(
    page.getByTestId("report-row").first().getByText("Zion Mercer", {
      exact: true,
    }),
  ).toBeVisible();

  await page.getByLabel("Sort", { exact: true }).selectOption("decliners");
  await expect(page).toHaveURL(/sort=decliners/);
  await expect(
    page.getByTestId("report-row").first().getByText("Miles Redd", {
      exact: true,
    }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Open evidence for Miles Redd" }).click();
  const dialog = page.getByRole("dialog", { name: "Miles Redd" });
  await expect(dialog.getByText("Previous", { exact: true })).toBeVisible();
  await expect(dialog.getByText("Current", { exact: true })).toBeVisible();
  await expect(dialog.getByText("15 of 26 carries")).toBeVisible();
  await expect(dialog.getByText("8 of 28 carries")).toBeVisible();
  await screenshot(page, "phase2-desktop-movement-detail.png", false);
  await page.keyboard.press("Escape");

  const reportText = (await page.locator("main").innerText()).toLowerCase();
  expect(reportText).not.toMatch(/\b(score|projection|bet|pick|grade)\b/);
  expect(errors).toEqual([]);
});

test("report family switcher and Feed deep links point to the three report routes", async ({
  page,
}) => {
  await page.goto("/reports/backfield?view=season");
  const switcher = page.getByRole("navigation", { name: "Report family" });
  await expect(
    switcher.getByRole("link", { name: "Backfield Control" }),
  ).toHaveAttribute("aria-current", "page");
  await switcher.getByRole("link", { name: "Target Hierarchy" }).click();
  await expect(page).toHaveURL("/reports/targets");
  await expect(
    page.getByRole("heading", { name: "Target Hierarchy" }),
  ).toBeVisible();

  await page.goto("/");
  await expect(page.getByRole("link", { name: "View all" })).toHaveAttribute(
    "href",
    "/reports/movement",
  );
  await expect(
    page.getByRole("link", { name: "Open supporting evidence" }),
  ).toHaveAttribute("href", /\/reports\/backfield/);
  await expect(
    page.getByRole("link", { name: "Full report" }).first(),
  ).toHaveAttribute("href", "/reports/backfield");
});

test("report loading, no-published-week, and unavailable states retain structure", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto("/reports/backfield?state=loading");
  await expect(page.getByLabel("Loading report evidence")).toBeVisible();
  await expect(page.locator(".report-loading-rows > span")).toHaveCount(6);

  await page.goto("/reports/backfield?state=empty");
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published for this report",
    }),
  ).toBeVisible();
  await expect(page.getByText(/No estimated shares are shown/)).toBeVisible();
  await expect(page.getByRole("link", { name: "Data Status" })).toBeVisible();
  await expect(page.getByTestId("report-row")).toHaveCount(0);

  await page.goto("/reports/movement?state=unavailable");
  await expect(
    page.getByRole("heading", {
      name: "This report bundle is temporarily unavailable",
    }),
  ).toBeVisible();
  await expect(page.getByText(/No stale or estimated results/)).toBeVisible();
  await expect(page.getByTestId("report-row")).toHaveCount(0);
  await screenshot(page, "phase2-desktop-unavailable.png", false);
});

test("invalid report parameters fall back safely without preserving invalid state", async ({
  page,
}) => {
  await page.goto(
    "/reports/targets?view=invalid&sort=invalid&team=XXX&position=QB&page=-5",
  );
  await expect(page.getByLabel("View", { exact: true })).toHaveValue("last4");
  await expect(page.getByLabel("Sort", { exact: true })).toHaveValue("authority");
  await expect(page.getByLabel("Team", { exact: true })).toHaveValue("ALL");
  await expect(page.getByLabel("Position")).toHaveValue("ALL");
  await expect(page.getByTestId("report-row")).toHaveCount(7);
});

test.describe("mobile report composition", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("overview and each report fit without horizontal overflow or bottom-nav overlap", async ({
    page,
  }) => {
    const errors = monitorPageErrors(page);
    const routes = [
      ["/reports", "phase2-mobile-reports-overview.png"],
      ["/reports/backfield", "phase2-mobile-backfield.png"],
      ["/reports/targets", "phase2-mobile-targets.png"],
      ["/reports/movement", "phase2-mobile-movement.png"],
    ] as const;

    for (const [route, image] of routes) {
      await page.goto(route);
      await expectNoHorizontalOverflow(page);
      const navigation = page.getByRole("navigation", {
        name: "Mobile navigation",
      });
      await expect(navigation).toBeVisible();
      const clearance = await page.locator(".page-shell").evaluate((element) =>
        Number.parseFloat(getComputedStyle(element).paddingBottom),
      );
      expect(clearance).toBeGreaterThanOrEqual(112);
      await screenshot(page, image);
    }

    await page.goto("/reports/movement");
    const footer = page.locator(".report-footer");
    await footer.scrollIntoViewIfNeeded();
    const footerBox = await footer.boundingBox();
    const navBox = await page
      .getByRole("navigation", { name: "Mobile navigation" })
      .boundingBox();
    expect(footerBox).not.toBeNull();
    expect(navBox).not.toBeNull();
    expect(footerBox?.y).toBeLessThan(navBox?.y ?? 0);
    expect(errors).toEqual([]);
  });

  test("mobile filters are compact and keep position visible", async ({ page }) => {
    await page.goto("/reports/targets");
    const controls = page.locator(".report-controls");
    await expect(controls).not.toHaveAttribute("open");
    await controls.locator("summary").click();
    await expect(controls).toHaveAttribute("open", "");
    await expect(page.getByLabel("Position")).toBeVisible();
    await screenshot(page, "phase2-mobile-open-filters.png", false);

    await page.getByLabel("Position").selectOption("TE");
    await expect(page).toHaveURL(/position=TE/);
    const rows = page.getByTestId("report-row");
    await expect(rows).toHaveCount(3);
    await expect(rows.first().locator(".report-player-cell")).toContainText("TE");
  });

  test("mobile evidence uses a closeable sheet with readable previous and current values", async ({
    page,
  }) => {
    await page.goto("/reports/movement");
    await page
      .getByRole("button", { name: "Open evidence for Zion Mercer" })
      .click();
    const dialog = page.getByRole("dialog", { name: "Zion Mercer" });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Previous", { exact: true })).toBeVisible();
    await expect(dialog.getByText("Current", { exact: true })).toBeVisible();
    await screenshot(page, "phase2-mobile-evidence-detail.png", false);
    await dialog.getByRole("button", { name: "Close evidence detail" }).focus();
    await expect(
      dialog.getByRole("button", { name: "Close evidence detail" }),
    ).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(dialog).toBeHidden();
  });

  test("mobile no-match and unavailable states remain clear of navigation", async ({
    page,
  }) => {
    await page.goto("/reports/backfield?team=SEA");
    await expect(
      page.getByRole("heading", { name: "No supplied rows match this view" }),
    ).toBeVisible();
    await screenshot(page, "phase2-mobile-no-matching-filters.png");

    await page.goto("/reports/targets?state=unavailable");
    await expect(
      page.getByRole("heading", {
        name: "This report bundle is temporarily unavailable",
      }),
    ).toBeVisible();
    await screenshot(page, "phase2-mobile-unavailable.png");
    await expectNoHorizontalOverflow(page);
  });
});

test("public report source excludes score, grade, projection, and betting constructs", () => {
  const sources = [
    "src/lib/report-types.ts",
    "src/lib/report-query.ts",
    "src/data/reports.fixture.ts",
    "src/components/report-experience.tsx",
    "src/components/reports-overview.tsx",
    "src/components/report-page.tsx",
    "src/components/report-state.tsx",
  ].map((file) => readFileSync(path.join(process.cwd(), file), "utf8"));
  const reportSource = sources.join("\n");

  for (const banned of [
    "RoleScore",
    "ImpactScore",
    "ConfidenceScore",
    "projection",
    "betting recommendation",
    "universal grade",
  ]) {
    expect(reportSource).not.toContain(banned);
  }
});
