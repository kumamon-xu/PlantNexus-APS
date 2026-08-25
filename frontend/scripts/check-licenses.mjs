import { readFileSync } from "node:fs";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const allowed = new Set([
  "0BSD",
  "Apache-2.0",
  "BlueOak-1.0.0",
  "BSD-2-Clause",
  "BSD-3-Clause",
  "CC-BY-3.0",
  "CC-BY-4.0",
  "CC0-1.0",
  "ISC",
  "MIT",
  "MIT-0",
  "MPL-2.0",
  "Python-2.0",
  "The-Unlicense",
  "Unicode-3.0",
  "Unlicense",
]);
const deniedPattern = /(?:^|[^A-Z])(?:AGPL|GPL|LGPL|SSPL|BUSL|Commons-Clause)(?:-|[^A-Z]|$)/i;
const ignoredTokens = new Set(["AND", "OR", "WITH"]);

function licenseTokens(expression) {
  return expression
    .replace(/[()]/g, " ")
    .split(/\s+/u)
    .map((value) => value.replace(/\*$/u, ""))
    .filter((value) => value.length > 0 && !ignoredTokens.has(value));
}

const reportPath = argument("--report");
const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
const packages = Object.entries(lock.packages ?? {}).filter(([path]) => path !== "");
const issues = [];
const observed = new Set();
for (const [path, metadata] of packages) {
  const expression = metadata.license;
  const name = metadata.name ?? path.replace(/^node_modules\//u, "");
  if (typeof expression !== "string" || expression.trim().length === 0) {
    issues.push(`${name}: unknown license`);
    continue;
  }
  observed.add(expression);
  if (deniedPattern.test(expression)) {
    issues.push(`${name}: deny-listed license ${expression}`);
    continue;
  }
  const unsupported = licenseTokens(expression).filter((token) => !allowed.has(token));
  if (unsupported.length > 0) {
    issues.push(`${name}: unreviewed license ${expression}`);
  }
}

const report = {
  report_version: "p3-frontend-license-report.v1",
  task: "TASK-P3-11",
  code_commit: codeCommit(),
  status: issues.length === 0 ? "PASS" : "FAIL",
  policy: {
    unknown_is_blocking: true,
    deny_list: ["AGPL", "GPL", "LGPL", "SSPL", "BUSL", "Commons-Clause"],
  },
  package_count: packages.length,
  observed_licenses: [...observed].sort(),
  checks: issues.length === 0 ? [completedCheck("LICENSE-ALLOW-DENY", `${packages.length} packages reviewed`)] : [],
  issues,
};
const target = writeReport(reportPath, report);
process.stdout.write(`${report.status} ${target}\n`);
if (issues.length > 0) process.exitCode = 1;
