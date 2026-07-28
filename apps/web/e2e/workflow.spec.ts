import { expect, test } from "@playwright/test";

test("seeded research workflow has no severe console errors", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => { if (message.type() === "error") severe.push(message.text()); });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Market overview" })).toBeVisible();
  await page.getByRole("link", { name: "Asset Explorer" }).click();
  await expect(page.getByRole("link", { name: "AAPL" })).toBeVisible();
  await page.getByRole("link", { name: "Watchlists" }).click();
  await page.getByLabel("New watchlist name").fill("E2E Research");
  await page.getByRole("button", { name: "Create watchlist" }).click();
  await page.getByLabel("Add asset to E2E Research").fill("AAPL");
  await page.getByRole("button", { name: "Add" }).click();
  await page.getByRole("link", { name: /AAPL/ }).click();
  await expect(page.getByRole("heading", { name: "AAPL" })).toBeVisible();
  expect(severe).toEqual([]);
});
