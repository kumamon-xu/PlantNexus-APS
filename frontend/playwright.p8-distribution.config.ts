import { defineConfig, devices } from "@playwright/test";

import baseConfig from "./playwright.config";

const evidenceRoot = "../build/playwright/p8-distribution";

export default defineConfig({
  ...baseConfig,
  testIgnore: [],
  testMatch: "headless-distribution.spec.ts",
  outputDir: `${evidenceRoot}/artifacts`,
  reporter: [
    ["line"],
    ["json", { outputFile: `${evidenceRoot}/results.json` }],
    ["junit", { outputFile: `${evidenceRoot}/results.xml` }],
    ["html", { outputFolder: `${evidenceRoot}/html`, open: "never" }],
  ],
  use: {
    ...baseConfig.use,
    baseURL: "http://127.0.0.1:4183",
  },
  projects: [
    {
      name: "chromium-p8-headless-distribution",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command:
      "npm run build:headless -- --mode e2e && npm exec -- vite preview --config vite.headless.config.ts --host 127.0.0.1 --port 4183",
    url: "http://127.0.0.1:4183/headless.html",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
