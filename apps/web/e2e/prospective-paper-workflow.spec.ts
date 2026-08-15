import { expect, test } from "@playwright/test";

test("prospective calibration and paper portfolio remain separated and simulated", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => {
    if (message.type() === "error") severe.push(message.text());
  });
  await page.goto("/");
  await page.getByLabel("Workspace", { exact: true }).selectOption({ label: "Legacy Development Workspace" });
  await page.getByText("More & administration").click();

  await page.getByRole("link", { name: "Prospective Forecasts" }).click();
  await expect(page.getByRole("heading", { name: "Prospective Forecasts" })).toBeVisible();
  await expect(page.getByText("PROSPECTIVE").first()).toBeVisible();
  await expect(page.getByText("HISTORICAL REPLAY", { exact: true })).toBeVisible();
  await expect(page.getByText("FIXTURE", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Outcome Monitor" }).click();
  await expect(page.getByText(/Early outcomes are rejected/)).toBeVisible();
  await page.getByRole("link", { name: "Forecast Calibration" }).click();
  await expect(page.getByText("INSUFFICIENT_SAMPLE")).toBeVisible();
  await page.getByRole("link", { name: "Research Reliability" }).click();
  await expect(page.getByRole("heading", { name: "Research Reliability" })).toBeVisible();

  await page.getByRole("link", { name: "Paper Portfolio Lab" }).click();
  await expect(page.getByText("SIMULATED / PAPER ONLY").first()).toBeVisible();
  await expect(page.getByText(/No shorting · no leverage/)).toBeVisible();
  await page.getByRole("button", { name: "Preview reference plan" }).click();
  await expect(page.getByText(/APPROVED_FOR_SIMULATION/)).toBeVisible();
  await expect(page.getByText(/brokerage_connectivity/)).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("img", { name: "Market Intelligence Lab" })).toBeVisible();
  expect(severe).toEqual([]);
});
