import { expect, test } from "@playwright/test";

test("research memory, independence, and divergence remain research-only", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => {
    if (message.type() === "error") severe.push(message.text());
  });
  await page.goto("/");
  await page.getByLabel("Workspace", { exact: true }).selectOption({
    label: "Legacy Development Workspace",
  });
  await page.getByText("More & administration").click();

  await page.getByRole("link", { name: "Factor Research" }).click();
  await expect(page.getByRole("heading", { name: "Hypothesis Lab" })).toBeVisible();
  await page.getByRole("link", { name: "Research Memory" }).click();
  await page.getByRole("button", { name: "Load reference research memory" }).click();
  await expect(page.getByText("Harvest Fields Cooperative")).toBeVisible({ timeout: 90_000 });
  await page
    .locator("article.panel")
    .filter({ hasText: "Harvest Fields Cooperative" })
    .getByRole("link")
    .click();
  await expect(page.getByText("KNOWN_FAILURE → SUPPRESSED")).toBeVisible();

  await page.getByRole("link", { name: "Signal Independence" }).click();
  await expect(page.getByText("conventional-overlap-factor")).toBeVisible();
  await expect(page.getByText("external-driver-independent-factor")).toBeVisible();

  await page.getByRole("link", { name: "Divergence Monitor" }).click();
  await expect(page.getByText("DIVERGENT ≠ MISPRICED")).toBeVisible();
  await page.getByRole("link", { name: "Inspect divergence evidence" }).click();
  await expect(page.getByText(/Research Candidate/)).toBeVisible();

  await page.getByRole("link", { name: "Information Value" }).click();
  await expect(page.getByText(/research.*efficiency/i)).toBeVisible();

  await page.getByRole("link", { name: "Adversarial Review" }).click();
  await page.getByRole("button", { name: "Load adversarial reference cases" }).click();
  await expect(page.getByText("BLOCKED")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("WHAT COULD BE WRONG?")).toBeVisible();
  await page.getByRole("link", { name: "Skeptic Challenges" }).click();
  await expect(page.getByText("CRITICAL").first()).toBeVisible();
  await page.getByRole("link", { name: "Scenario Lab" }).click();
  await expect(page.getByText("THIS IS A SCENARIO, NOT A FORECAST")).toBeVisible();
  await page.getByRole("link", { name: "Inspect scenario" }).first().click();
  await page.getByRole("button", { name: "Run deterministic scenario" }).click();
  await expect(page.getByText(/transmission_path/)).toBeVisible();
  await page.getByRole("link", { name: "Counterfactual Lab" }).click();
  await page.getByRole("link", { name: "Inspect counterfactual" }).first().click();
  await page.getByRole("button", { name: "Run isolated counterfactual" }).click();
  await expect(page.getByText(/SIMULATED_MECHANISM/)).toBeVisible();
  await page.getByRole("link", { name: "Research Confidence" }).click();
  await expect(page.getByText(/not a probability/i)).toBeVisible();
  await page.getByRole("link", { name: "Research Dossiers" }).click();
  await expect(page.getByText(/never a BUY\/SELL recommendation/i)).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("img", { name: "Market Intelligence Lab" })).toBeVisible();
  expect(severe).toEqual([]);
});
