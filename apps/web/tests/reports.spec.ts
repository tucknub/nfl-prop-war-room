import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";

function monitorPageErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
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

async function expectRawEvidence(rows: Locator) {
  const count = await rows.count();
  expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index += 1) {
    const text = await rows.nth(index).innerText();
    expect(text).toMatch(/\d+\.\d%/);
    expect(text).toMatch(/\d+ of \d+ (opportunities|carries|targets)/);
  }
}

async function playerNames(page: Page) {
  return page.locator(".report-player-cell > strong").allTextContents();
}

test("reports overview explains three football tools with exact evidence", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);
  await page.goto("/reports");

  await expect(
    page.getByRole("heading", {
      name: "Three tools for understanding NFL roles",
    }),
  ).toBeVisible();
  await expect(page.locator(".report-family-card")).toHaveCount(3);
  await expect(
    page.getByRole("heading", {
      name: "Who controls each team’s backfield opportunities?",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Who controls each team’s documented targets?",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Whose documented role changed the most?",
    }),
  ).toBeVisible();
  await expect(page.getByText("27 of 34 opportunities").first()).toBeVisible();
  await expect(page.getByText("11 of 32 targets").first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
  expect(errors).toEqual([]);
});

test("Backfield Control defaults to total opportunities and highest share", async ({
  page,
}) => {
  await page.goto("/reports/backfield");
  const rows = page.getByTestId("report-row");

  await expect(
    page.getByRole("button", { name: "Total opportunities" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Sort")).toHaveValue("share");
  await expect(rows).toHaveCount(6);
  await expect(rows.first()).toContainText("Marcus Hale");
  await expect(rows.first()).toContainText("27 of 34 opportunities");
  await expectRawEvidence(rows);

  const ids = await rows.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("data-player-id")),
  );
  expect(new Set(ids).size).toBe(ids.length);
});

test("Backfield metric and consumer sorts use only displayed source values", async ({
  page,
}) => {
  await page.goto("/reports/backfield");

  await page.getByLabel("Sort").selectOption("share_asc");
  await expect(page).toHaveURL(/sort=share_asc/);
  expect((await playerNames(page))[0]).toBe("Devin Banks");

  await page.getByLabel("Sort").selectOption("authority");
  await expect(page).toHaveURL(/sort=authority/);
  expect((await playerNames(page))[0]).toBe("Marcus Hale");

  await page.getByRole("button", { name: "Carries" }).click();
  await expect(page).toHaveURL(/metric=carries/);
  await expect(
    page.getByRole("heading", { name: "No players match these controls" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Reset controls" }).click();
  await expect(page).toHaveURL("/reports/backfield");
  await expect(page.getByTestId("report-row")).toHaveCount(6);
});

test("Target Hierarchy defaults to wide receivers and identifies both leaders for a team", async ({
  page,
}) => {
  await page.goto("/reports/targets");
  await expect(
    page.getByRole("button", { name: "Wide receivers" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("report-row")).toHaveCount(4);

  await page.getByRole("button", { name: "Tight ends" }).click();
  await expect(page).toHaveURL(/position=TE/);
  await expect(page.getByTestId("report-row")).toHaveCount(3);
  for (const row of await page.getByTestId("report-row").all()) {
    await expect(row).toContainText("TE");
    await expect(row).toContainText(/\d+ of \d+ targets/);
  }

  await page.getByRole("button", { name: "All", exact: true }).click();
  await page.getByLabel("Team", { exact: true }).selectOption("JVT");
  const answer = page.locator("#report-answer");
  await expect(answer).toContainText("Jonah Pike leads WRs");
  await expect(answer).toContainText("Cole Mercer leads TEs");
});

test("Role Movement defaults to gains and exposes declines, all movement, and report order", async ({
  page,
}) => {
  await page.goto("/reports/movement");
  const rows = page.getByTestId("report-row");
  await expect(
    page.getByRole("button", { name: "Biggest gains" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(rows).toHaveCount(4);
  await expect(rows.first()).toContainText("Zion Mercer");
  await expect(rows.first()).toContainText("Gain");
  await expect(rows.first()).toContainText("+26.5 pp");

  await page.getByRole("button", { name: "Biggest declines" }).click();
  await expect(page).toHaveURL(/direction=declines/);
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("Miles Redd");
  await expect(rows.first()).toContainText("Decline");
  await expect(rows.first()).toContainText("-29.1 pp");

  await page.getByRole("button", { name: "All movement" }).click();
  await expect(rows).toHaveCount(6);
  await page.getByLabel("Sort").selectOption("authority");
  await expect(page).toHaveURL(/sort=authority/);
  await expect(rows.first()).toContainText("Zion Mercer");
  await expectRawEvidence(rows);
});

test("movement rows pair semantic colors with arrows, labels, and exact pp values", async ({
  page,
}) => {
  await page.goto("/reports/movement?direction=all");
  const gain = page.locator('[data-movement-direction="gain"]').first();
  const decline = page.locator('[data-movement-direction="decline"]').first();

  await expect(gain).toContainText("Gain");
  await expect(gain).toContainText(/\+\d+\.\d pp/);
  await expect(decline).toContainText("Decline");
  await expect(decline).toContainText(/-\d+\.\d pp/);
  await expect(gain.locator(".movement-finding svg")).toHaveCount(1);
  await expect(decline.locator(".movement-finding svg")).toHaveCount(1);
  const colors = await Promise.all([
    gain.locator(".movement-finding").evaluate((node) => getComputedStyle(node).color),
    decline
      .locator(".movement-finding")
      .evaluate((node) => getComputedStyle(node).color),
  ]);
  expect(colors[0]).not.toBe(colors[1]);
});

test("comparison windows are explicit and evidence details use progressive disclosure", async ({
  page,
}) => {
  await page.goto("/reports/movement");
  await expect(
    page.getByText("Weeks 15–18 compared with Weeks 11–14").first(),
  ).toBeVisible();

  const trigger = page.getByRole("button", {
    name: "View evidence for Zion Mercer",
  });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Zion Mercer" });
  await expect(dialog).toContainText(
    "Zion Mercer’s RB opportunity share rose from 36.4% to 62.9%",
  );
  await expect(dialog).toContainText("12 of 33 opportunities");
  await expect(dialog).toContainText("22 of 35 opportunities");
  await expect(
    dialog.getByRole("link", { name: "View player dossier" }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("link", { name: "View team dossier" }),
  ).toBeVisible();
  await expect(dialog.getByText("Source version")).not.toBeVisible();

  await dialog.getByText("Technical details").click();
  await expect(dialog.getByText("Source version")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
});

test("evidence drawer traps focus and restores the opening control", async ({
  page,
}) => {
  await page.goto("/reports/backfield");
  const trigger = page.getByRole("button", {
    name: "View evidence for Marcus Hale",
  });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Marcus Hale" });
  const close = dialog.getByRole("button", { name: "Close evidence" });
  await expect(close).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.locator("summary")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
});

test("no-match, loading, no-week, and unavailable states stay distinct", async ({
  page,
}) => {
  await page.goto("/reports/backfield?team=SEA");
  await expect(
    page.getByRole("heading", { name: "No players match these controls" }),
  ).toBeVisible();
  await expect(page.getByTestId("report-row")).toHaveCount(0);

  await page.goto("/reports/backfield?state=loading");
  await expect(page.getByLabel("Loading report evidence")).toBeVisible();

  await page.goto("/reports/backfield?state=empty");
  await expect(
    page.getByRole("heading", {
      name: "No completed week is published for this report",
    }),
  ).toBeVisible();
  await expect(page.getByTestId("report-row")).toHaveCount(0);

  await page.goto("/reports/movement?state=unavailable");
  await expect(
    page.getByRole("heading", {
      name: "This report bundle is temporarily unavailable",
    }),
  ).toBeVisible();
  await expect(page.getByTestId("report-row")).toHaveCount(0);
});

test("invalid parameters fall back to consumer defaults", async ({ page }) => {
  await page.goto(
    "/reports/targets?view=invalid&sort=invalid&team=XXX&position=QB&direction=bad&metric=bad&page=-5",
  );
  await expect(page.getByLabel("Window")).toHaveValue("last4");
  await expect(page.getByLabel("Sort")).toHaveValue("share");
  await expect(page.getByLabel("Team", { exact: true })).toHaveValue("ALL");
  await expect(
    page.getByRole("button", { name: "Wide receivers" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("report-row")).toHaveCount(4);
});

test.describe("mobile report composition", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("all reports use stacked rows without horizontal overflow", async ({
    page,
  }) => {
    const errors = monitorPageErrors(page);
    for (const route of [
      "/reports",
      "/reports/backfield",
      "/reports/targets",
      "/reports/movement",
    ]) {
      await page.goto(route);
      await expectNoHorizontalOverflow(page);
    }
    const row = page.getByTestId("report-row").first();
    await expect(row).toBeVisible();
    expect(await row.evaluate((node) => getComputedStyle(node).display)).toBe(
      "grid",
    );
    expect(errors).toEqual([]);
  });

  test("mobile report controls and evidence sheet remain keyboard accessible", async ({
    page,
  }) => {
    await page.goto("/reports/targets");
    const controls = page.locator(".report-controls");
    await expect(controls).not.toHaveAttribute("open");
    await controls.locator("summary").click();
    await expect(
      page.getByRole("button", { name: "Tight ends" }),
    ).toBeVisible();

    await page.goto("/reports/movement");
    await page
      .getByRole("button", { name: "View evidence for Zion Mercer" })
      .click();
    const dialog = page.getByRole("dialog", { name: "Zion Mercer" });
    await expect(dialog).toContainText("Previous");
    await expect(dialog).toContainText("Current");
    await expectNoHorizontalOverflow(page);
    await dialog.getByRole("button", { name: "Close evidence" }).click();
    await expect(dialog).toHaveCount(0);
  });
});

test("normal report pages avoid internal contract wording and unsupported constructs", async ({
  page,
}) => {
  for (const route of [
    "/reports",
    "/reports/backfield",
    "/reports/targets",
    "/reports/movement",
  ]) {
    await page.goto(route);
    const text = (await page.locator("main").innerText()).toLowerCase();
    expect(text).not.toMatch(
      /\b(python-supplied|supplied order|authority rank|authority order|canonical identity|export bundle|evidence-team|future report)\b/,
    );
    expect(text).not.toMatch(
      /\b(role score|impact score|confidence score|projection|recommendation|betting)\b/,
    );
  }
});

test("public report source excludes scores, projections, and betting constructs", () => {
  const sources = [
    "src/lib/report-types.ts",
    "src/lib/report-query.ts",
    "src/lib/consumer-presentation.ts",
    "src/components/report-experience.tsx",
    "src/components/reports-overview.tsx",
  ].map((file) => readFileSync(path.join(process.cwd(), file), "utf8"));
  const source = sources.join("\n");
  for (const banned of [
    "RoleScore",
    "ImpactScore",
    "ConfidenceScore",
    "betting recommendation",
    "universal grade",
  ]) {
    expect(source).not.toContain(banned);
  }
});
