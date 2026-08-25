import { spawnSync } from "node:child_process";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const reportPath = argument("--report");
const npmExecutable = process.env.npm_execpath;
if (!npmExecutable) throw new Error("npm_execpath is unavailable");
const audit = spawnSync(
  process.execPath,
  [
    npmExecutable,
    "audit",
    "--json",
    "--audit-level=high",
    "--registry=https://registry.npmjs.org",
  ],
  { cwd: process.cwd(), encoding: "utf8" },
);

let document;
const issues = [];
try {
  document = JSON.parse(audit.stdout || "{}");
} catch {
  issues.push("npm audit did not emit valid JSON");
  document = {};
}
const vulnerabilities = document?.metadata?.vulnerabilities ?? {};
const counts = {
  info: Number(vulnerabilities.info ?? 0),
  low: Number(vulnerabilities.low ?? 0),
  moderate: Number(vulnerabilities.moderate ?? 0),
  high: Number(vulnerabilities.high ?? 0),
  critical: Number(vulnerabilities.critical ?? 0),
  total: Number(vulnerabilities.total ?? 0),
};
if (counts.high > 0 || counts.critical > 0) {
  issues.push(
    `npm audit found ${counts.high} high and ${counts.critical} critical advisories`,
  );
}
if (audit.error) issues.push(`npm audit execution failed: ${audit.error.message}`);
if (audit.status !== 0 && counts.high === 0 && counts.critical === 0) {
  issues.push(`npm audit exited ${String(audit.status)} without a high/critical count`);
}

const report = {
  report_version: "p3-frontend-sca-report.v1",
  task: "TASK-P3-11",
  code_commit: codeCommit(),
  status: issues.length === 0 ? "PASS" : "FAIL",
  policy: {
    source: "npm registry point-in-time audit",
    blocking_severities: ["high", "critical"],
    lock_required: true,
  },
  vulnerability_counts: counts,
  checks: issues.length === 0 ? [completedCheck("SCA-HIGH-CRITICAL", "0 blocking advisories")] : [],
  issues,
};
const target = writeReport(reportPath, report);
process.stdout.write(`${report.status} ${target}\n`);
if (issues.length > 0) process.exitCode = 1;
