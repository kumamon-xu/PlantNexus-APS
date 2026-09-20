import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "p9-runtime-consumers.spec.ts",
  workers: 1,
  retries: 0,
  timeout: 90_000,
  outputDir: "../build/playwright/p9-runtime/artifacts",
  reporter: [["line"], ["junit", { outputFile: "../build/validation/ci-frontend-p9-runtime.xml" }]],
  use: { actionTimeout: 10_000, ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:4179", screenshot: "only-on-failure", trace: "retain-on-failure" },
  webServer: {
    command: "npm run dev -- --config vite.p9-runtime.config.ts --mode e2e --host 127.0.0.1 --port 4179",
    url: "http://127.0.0.1:4179",
    reuseExistingServer: false,
  },
});
