import { expect, test } from "@playwright/test";

test("beginner dashboard and advanced navigation remain usable on mobile", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => {
    if (message.type() === "error") severe.push(message.text());
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.getByRole("img", { name: "Market Intelligence Lab" })).toBeVisible();
  await expect(page.locator('link[rel="icon"][sizes="32x32"]')).toHaveAttribute("href", "/assets/branding/favicon-32.png");
  await expect(page.getByRole("heading", { name: "Research dashboard" })).toBeVisible();
  await expect(page.getByText("REAL MARKET DATA NOT CONFIGURED")).toBeVisible();
  await expect(page.getByText("System ready")).toBeVisible();
  await expect(page.getByRole("link", { name: /View Watchlists/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open Paper Portfolio/ })).toBeVisible();

  const advanced = page.locator("details.advanced-nav");
  await expect(advanced).not.toHaveAttribute("open", "");
  await advanced.getByText("More & administration").click();
  await expect(page.getByRole("link", { name: "System Services" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Activity Log" })).toBeVisible();
  await page.getByRole("link", { name: "Watchlists", exact: true }).click();
  const watchlistName = `Mobile Catalog ${Date.now()}`;
  await page.getByLabel("New watchlist name").fill(watchlistName);
  await page.getByRole("button", { name: "Create watchlist" }).click();
  const watchlist = page.locator("article.watchlist").filter({ hasText: watchlistName });
  await watchlist.getByLabel(`Add asset to ${watchlistName}`).fill("AAPL");
  await watchlist.getByRole("option", { name: /AAPL/ }).click();
  await expect(watchlist.getByText(/DEMO/)).toBeVisible();
  expect(severe).toEqual([]);
});
