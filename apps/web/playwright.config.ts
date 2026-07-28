import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  webServer: [
    { command: "python ../../scripts/dev.py --seed", url: "http://127.0.0.1:5173", reuseExistingServer: true, timeout: 120_000 },
  ],
});
