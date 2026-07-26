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

test("historical export renders source-backed home and report evidence", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "2 of 3 opportunities occurred outside normal-game context.",
    }),
  ).toBeVisible();
  await expect(
    page
      .getByLabel("2 of 3 opportunities occurred outside normal-game context.")
      .getByText("Emanuel Wilson", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("[data-share-evidence]").first()).toBeVisible();
  await expectNoFixtureFallback(page);
  const targetHierarchyTab = page.getByRole("tab", {
    name: "Target Hierarchy",
  });
  await targetHierarchyTab.click();
  await expect(targetHierarchyTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("leaderboard-row")).toHaveCount(3);
  await expect(
    page.getByText("Jaxon Smith-Njigba", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(reviewDirectory, "historical-2025-desktop-home.png"),
    animations: "disabled",
    fullPage: true,
  });

  await page.goto("/reports/backfield");
  await expect(
    page.getByRole("heading", { name: "Backfield Control", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("report-row").first()).toBeVisible();
  await expect(page.getByText("Ashton Jeanty", { exact: true }).first()).toBeVisible();
  await expect(
    page.getByText(/LV .* RB .* RB opportunity share/).first(),
  ).toBeVisible();
  await expectNoFixtureFallback(page);

  expect(errors).toEqual([]);
});

test("historical export exposes ATL and team-neutral cross-team player evidence", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const errors = monitorPageErrors(page);

  await page.goto("/teams");
  await expect(page.locator(".team-directory-item")).toHaveCount(32);
  await page.getByLabel("Search teams").fill("ATL");
  const atl = page.locator(".team-directory-item");
  await expect(atl).toHaveCount(1);
  await expect(atl.getByText("Atlanta Falcons", { exact: true })).toBeVisible();
  await atl.getByRole("link", { name: "Open team dossier" }).click();
  await expect(page).toHaveURL("/teams/ATL");
  await expect(
    page.getByRole("heading", { name: "Atlanta Falcons" }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(reviewDirectory, "historical-2025-desktop-atl.png"),
    animations: "disabled",
    fullPage: true,
  });

  await page.goto("/players/00-0030035");
  await expect(page.getByRole("heading", { name: "Adam Thielen" })).toBeVisible();
  await expect(page.getByText("Team-neutral player ID", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Pittsburgh Steelers" }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("rowheader", {
        name: /Week 1 .* MIN .* WR target share/,
      })
      .first(),
  ).toBeVisible();
  await expectNoFixtureFallback(page);
  await page.screenshot({
    path: path.join(
      reviewDirectory,
      "historical-2025-desktop-team-neutral-player.png",
    ),
    animations: "disabled",
    fullPage: true,
  });

  expect(errors).toEqual([]);
});

test("historical export publishes 586 bundles and remains mobile-safe", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const errors = monitorPageErrors(page);

  await page.goto("/data-status");
  await expect(
    page.getByLabel("Publication state: Published"),
  ).toBeVisible();
  await expect(page.getByText("export", { exact: true })).toBeVisible();
  await expect(page.getByText("586 declared bundles")).toBeVisible();
  await expect(page.getByText("Week 18", { exact: true })).toBeVisible();
  await expectNoFixtureFallback(page);

  await page.goto("/");
  await expect(
    page.getByRole("navigation", { name: "Mobile navigation" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "2 of 3 opportunities occurred outside normal-game context.",
    }),
  ).toBeVisible();
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport);
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport);
  await page.screenshot({
    path: path.join(reviewDirectory, "historical-2025-mobile-home.png"),
    animations: "disabled",
    fullPage: true,
  });

  expect(errors).toEqual([]);
});
