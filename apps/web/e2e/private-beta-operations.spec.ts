import { expect, test } from "@playwright/test";

test("private-beta operations remain clear and usable on mobile", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => {
    if (message.type() === "error") severe.push(message.text());
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByText("More & administration").click();
  await page.getByRole("link", { name: "Operations Center" }).click();
  await expect(page.getByRole("heading", { name: "Operations Center" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "System health" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Data freshness" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Schedules" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Operational alerts" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Backup and deployment readiness" })).toBeVisible();
  await expect(page.getByText("No freshness records")).toBeVisible();
  await expect(page.getByText("Official U.S. security-master refresh")).toBeVisible();
  await expect(page.getByText("Real-market historical ingestion")).toBeVisible();
  await expect(page.getByText("No open operational alerts")).toBeVisible();
  await page.getByRole("link", { name: "Paper Portfolios" }).click();
  await expect(page.getByRole("heading", { name: "Paper portfolios" })).toBeVisible();
  await expect(page.getByText(/Simulation only/).first()).toBeVisible();
  expect(severe).toEqual([]);
});
