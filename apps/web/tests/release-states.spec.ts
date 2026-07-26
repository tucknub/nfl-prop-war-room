import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const reviewDirectory = path.resolve(
  process.cwd(),
  "../../docs/depthsnap/reviews/release-readiness",
);

test.beforeAll(() => mkdirSync(reviewDirectory, { recursive: true }));

function browserErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  return errors;
}

test("blocked current season without prior data renders unavailable safely", async ({
  page,
}) => {
  const errors = browserErrors(page);
  await page.goto("http://127.0.0.1:3500/");
  await expect(
    page.getByRole("heading", { name: "Role data is unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Current-season publication is blocked and no prior valid registry is available.",
    ),
  ).toBeVisible();
  await expect(
    page
      .getByLabel("Role data is unavailable")
      .getByText("Data unavailable", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".fixture-notice")).toHaveCount(0);
  await expect(page.getByText(/2025 historical/i)).toHaveCount(0);
  await page.screenshot({
    path: path.join(reviewDirectory, "production-desktop-unavailable.png"),
    animations: "disabled",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("invalid replacement renders a sanitized contract failure without fallback", async ({
  page,
}) => {
  const errors = browserErrors(page);
  const response = await page.goto("http://127.0.0.1:3501/");
  expect(response?.status()).toBe(200);
  await expect(page.getByTestId("contract-failure")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Bundle integrity check failed" }),
  ).toBeVisible();
  await expect(page.locator("body")).not.toContainText(/C:\\Users\\|\/home\/runner\//);
  await expect(page.locator(".fixture-notice")).toHaveCount(0);
  await expect(page.getByText(/synthetic records/i)).toHaveCount(0);
  await page.screenshot({
    path: path.join(reviewDirectory, "production-desktop-contract-failure.png"),
    animations: "disabled",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
