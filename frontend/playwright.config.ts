import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  timeout: 30_000,
  outputDir: "../build/playwright/artifacts",
  reporter: [
    ["line"],
    ["json", { outputFile: "../build/playwright/results.json" }],
    ["junit", { outputFile: "../build/playwright/results.xml" }],
    ["html", { outputFolder: "../build/playwright/html", open: "never" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-p3-human-control",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --mode e2e --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
