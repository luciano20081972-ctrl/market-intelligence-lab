import { expect, test } from "@playwright/test";

test("bounded hypothesis research preserves scientific validation boundaries", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => {
    if (message.type() === "error") severe.push(message.text());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Research dashboard" })).toBeVisible();
  await page.getByLabel("Workspace", { exact: true }).selectOption({
    label: "Legacy Development Workspace",
  });

  await page.getByText("More & administration").click();
  await page.getByRole("link", { name: "Research Funnel" }).click();
  await page.getByRole("button", { name: "Run reference screen" }).click();
  await expect(page.getByText("AI Candidates")).toBeVisible({ timeout: 60_000 });
  await page.getByRole("link", { name: "Research Candidates" }).click();
  const levelFour = page.locator("article.panel").filter({ hasText: "LEVEL_4" }).first();
  await levelFour.getByRole("link", { name: "Inspect rationale" }).click();
  await expect(page.getByText("Irrelevant pipelines skipped")).toBeVisible();

  await page.getByRole("link", { name: "Factor Research" }).click();
  await page.getByRole("button", { name: "Generate fixture hypotheses" }).click();
  await expect(page.getByRole("heading", {
    name: "Regional electricity-cost pressure may precede semiconductor margin changes",
  })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("heading", {
    name: "Water stress and fertilizer-energy pressure may precede agricultural revenue changes",
  })).toBeVisible();

  const rejected = page.locator("article.panel").filter({ hasText: "REJECTED" });
  await rejected.getByRole("link", { name: "Inspect falsifiable research" }).click();
  await expect(page.getByRole("heading", { name: /Water stress/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Proposed economic mechanism" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Falsification conditions" })).toBeVisible();
  await expect(page.getByText(/No persistent rank IC/)).toBeVisible();

  await page.getByRole("link", { name: "Inspect factor experiment" }).click();
  await expect(page.getByText("TRAIN", { exact: true })).toBeVisible();
  await expect(page.getByText("VALIDATION", { exact: true })).toBeVisible();
  await expect(page.getByText("FINAL OUT-OF-SAMPLE", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Walk-Forward Results" }).click();
  await expect(page.getByRole("heading", { name: "Walk-Forward Results" })).toBeVisible();
  await expect(page.getByText("5 / 5").first()).toBeVisible();
  await page.getByRole("link", { name: "Experiment" }).click();
  await page.getByRole("link", { name: "Robustness Matrix" }).click();
  await expect(page.getByRole("heading", { name: "Negative controls" })).toBeVisible();
  await expect(page.getByText(/methodology valid/).first()).toBeVisible();
  await page.getByRole("link", { name: "Experiment" }).click();
  await page.getByRole("link", { name: "Validation Gates" }).click();
  await expect(page.getByText("REJECTED", { exact: true })).toBeVisible();
  await expect(page.getByText("NO LIVE-TRADING STATUS")).toBeVisible();

  await page.getByText("More & administration").click();
  await page.getByRole("link", { name: "Research Engine Status" }).click();
  await expect(page.getByRole("heading", { name: "Research Engine Status" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "qlib" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "rd-agent" })).toBeVisible();
  expect(severe).toEqual([]);
});
