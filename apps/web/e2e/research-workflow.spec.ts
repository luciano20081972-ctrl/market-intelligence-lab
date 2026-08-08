import { expect, test } from "@playwright/test";

test("progressive research fixture is temporal, explainable, and budgeted", async ({ page }) => {
  const severe: string[] = [];
  page.on("console", message => { if (message.type() === "error") severe.push(message.text()); });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Market overview" })).toBeVisible();
  await page.getByLabel("Workspace", { exact: true }).selectOption({
    label: "Legacy Development Workspace",
  });

  await page.getByRole("link", { name: "Research Universe" }).click();
  await expect(page.getByRole("heading", { name: "Research Universe", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Research Funnel" }).click();
  await page.getByRole("button", { name: "Run reference screen" }).click();
  await expect(page.getByText("AI Candidates")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("3", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: /Inspect screening decisions/ }).click();
  await expect(page.getByRole("heading", { name: "Screening Run Detail" })).toBeVisible();
  await expect(page.getByText("DATA_COMPLETE").first()).toBeVisible();

  await page.getByRole("link", { name: "Feature Matrix" }).click();
  await expect(page.getByText("POINT-IN-TIME SAFE")).toBeVisible();
  await page.getByRole("link", { name: "Trace" }).first().click();
  await expect(page.getByRole("heading", { name: "Feature Lineage Viewer" })).toBeVisible();
  await expect(page.getByText(/mil-feature-v1/)).toBeVisible();

  await page.getByRole("link", { name: "Research Budgets" }).click();
  await expect(page.getByRole("heading", { name: "Research Budget Dashboard" })).toBeVisible();
  await expect(page.getByText("Maximum companies: 3")).toBeVisible();

  const response = await page.request.get("http://127.0.0.1:8000/api/v1/research/candidates");
  expect(response.ok()).toBeTruthy();
  const payload = await response.json() as { items: Array<{ id: string; archetype: string }> };
  for (const archetype of ["semiconductor", "airline", "agriculture"]) {
    const candidate = payload.items.find(item => item.archetype === archetype);
    expect(candidate).toBeTruthy();
    await page.goto(`/research/candidates/${candidate!.id}`);
    await expect(page.getByText("Irrelevant pipelines skipped")).toBeVisible();
    await expect(page.getByText("Yes", { exact: true })).toBeVisible();
  }
  expect(severe).toEqual([]);
});
