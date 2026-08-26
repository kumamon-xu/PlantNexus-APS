import { defineConfig } from "@playwright/test";

import baseConfig from "./playwright.config";

const replayIndex = process.env.PLANTNEXUS_P3_GATE_REPLAY_INDEX;

if (replayIndex !== "1" && replayIndex !== "2") {
  throw new Error("PLANTNEXUS_P3_GATE_REPLAY_INDEX must be 1 or 2");
}

const evidenceRoot = `../build/playwright/p3-gate/replay-${replayIndex}`;

export default defineConfig(baseConfig, {
  outputDir: `${evidenceRoot}/artifacts`,
  reporter: [
    ["line"],
    ["json", { outputFile: `${evidenceRoot}/results.json` }],
    ["junit", { outputFile: `${evidenceRoot}/results.xml` }],
    ["html", { outputFolder: `${evidenceRoot}/html`, open: "never" }],
  ],
});
