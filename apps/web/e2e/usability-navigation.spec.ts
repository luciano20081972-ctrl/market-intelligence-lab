import { expect, test } from "@playwright/test";

test("beginner dashboard and advanced navigation remain usable on mobile", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => {
    if (message.type() === "error") severe.push(message.text());
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Research dashboard" })).toBeVisible();
  await expect(page.getByText("System ready")).toBeVisible();
  await expect(page.getByRole("link", { name: /View Watchlists/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Open Paper Portfolio/ })).toBeVisible();

  const advanced = page.locator("details.advanced-nav");
  await expect(advanced).not.toHaveAttribute("open", "");
  await advanced.getByText("More & administration").click();
  await expect(page.getByRole("link", { name: "System Services" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Activity Log" })).toBeVisible();
  expect(severe).toEqual([]);
});
