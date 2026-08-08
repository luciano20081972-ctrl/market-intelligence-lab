import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  webServer: [
    { command: "python -m scripts.dev --seed --worker", cwd: "../..", url: "http://127.0.0.1:8000/health/ready", reuseExistingServer: true, timeout: 120_000 },
  ],
});
