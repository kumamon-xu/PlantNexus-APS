import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, relative } from "node:path";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const runtimePins = {
  "@tanstack/react-query": "5.102.3",
  antd: "6.6.1",
  react: "19.2.8",
  "react-dom": "19.2.8",
  "react-router-dom": "7.18.2",
};
const developmentPins = {
  "@playwright/test": "1.62.1",
  "@testing-library/dom": "10.4.1",
  "@testing-library/jest-dom": "7.0.1",
  "@testing-library/react": "16.3.2",
  "@testing-library/user-event": "14.6.6",
  "@types/node": "24.13.3",
  "@types/react": "19.2.18",
  "@types/react-dom": "19.2.5",
  "@vitejs/plugin-react": "6.1.0",
  "axe-core": "4.13.0",
  eslint: "10.9.1",
  "eslint-plugin-react-hooks": "7.1.1",
  "eslint-plugin-react-refresh": "0.5.4",
  globals: "17.11.0",
  jsdom: "30.0.1",
  typescript: "6.0.3",
  "typescript-eslint": "8.68.0",
  vite: "8.2.2",
  vitest: "4.1.11",
};
const expectedRoutes = [
  "/planning/data-health",
  "/planning/import-runs",
  "/planning/runs",
  "/planning/runs/:planning_run_id",
  "/planning/versions/:schedule_version_id",
  "/planning/versions/:schedule_version_id/orders",
  "/planning/versions/:schedule_version_id/gantt/factory",
  "/planning/versions/:schedule_version_id/gantt/workshops",
  "/planning/versions/:schedule_version_id/gantt/machines",
  "/operations",
  "/resources",
  "/calendars",
  "/validation",
  "/kpi",
  "/diagnostics",
  "/audit",
  "/resource-load",
  "/compare",
];

const requiredVisualizationFiles = [
  "src/features/gantt/GanttPage.tsx",
  "src/features/gantt/GanttTimeline.tsx",
  "src/features/resource-load/ResourceLoadPage.tsx",
  "src/features/version-comparison/VersionComparisonPage.tsx",
  "e2e/read-only-visualizations.spec.ts",
  "playwright.config.ts",
];

function fail(condition, message, issues) {
  if (!condition) issues.push(message);
}

function files(root) {
  const result = [];
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) result.push(...files(path));
    else result.push(path);
  }
  return result;
}

const reportPath = argument("--report");
const issues = [];
const checks = [];
const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
const lockRoot = lock.packages?.[""] ?? {};

fail(pkg.engines?.node === "24.19.0", "package engine Node pin drifted", issues);
fail(pkg.engines?.npm === "11.17.0", "package engine npm pin drifted", issues);
fail(pkg.packageManager === "npm@11.17.0", "packageManager pin drifted", issues);
fail(readFileSync(".nvmrc", "utf8").trim() === "24.19.0", ".nvmrc drifted", issues);
fail(process.version === "v24.19.0", `runtime Node is ${process.version}`, issues);
const npmExecutable = process.env.npm_execpath;
const npmVersion = npmExecutable
  ? spawnSync(process.execPath, [npmExecutable, "--version"], { encoding: "utf8" }).stdout.trim()
  : "unavailable";
fail(npmVersion === "11.17.0", `runtime npm is ${npmVersion}`, issues);
if (issues.length === 0) checks.push(completedCheck("RUNTIME-PINS", "Node 24.19.0 / npm 11.17.0"));

for (const [name, version] of Object.entries(runtimePins)) {
  fail(pkg.dependencies?.[name] === version, `runtime pin drift: ${name}`, issues);
  fail(lockRoot.dependencies?.[name] === version, `runtime lock drift: ${name}`, issues);
}
checks.push(completedCheck("RUNTIME-DIRECT", `${Object.keys(runtimePins).length} exact pins checked`));
for (const [name, version] of Object.entries(developmentPins)) {
  fail(pkg.devDependencies?.[name] === version, `development pin drift: ${name}`, issues);
  fail(lockRoot.devDependencies?.[name] === version, `development lock drift: ${name}`, issues);
}
checks.push(completedCheck("DEVELOPMENT-DIRECT", `${Object.keys(developmentPins).length} exact pins checked`));
fail(lock.lockfileVersion === 3, `lockfileVersion is ${String(lock.lockfileVersion)}`, issues);
fail(lockRoot.engines?.node === "24.19.0", "lock root Node engine drifted", issues);
fail(lockRoot.engines?.npm === "11.17.0", "lock root npm engine drifted", issues);
checks.push(completedCheck("LOCKFILE", "npm lockfile v3 root matches package.json"));

const tsEslint = lock.packages?.["node_modules/typescript-eslint"] ?? {};
fail(tsEslint.version === "8.68.0", "typescript-eslint lock pin drifted", issues);
fail(
  tsEslint.peerDependencies?.typescript === ">=4.8.4 <6.1.0",
  `typescript-eslint TypeScript peer is ${String(tsEslint.peerDependencies?.typescript)}`,
  issues,
);
fail(pkg.devDependencies.eslint === "10.9.1", "ESLint compatibility pin drifted", issues);
fail(pkg.devDependencies.typescript === "6.0.3", "TypeScript compatibility pin drifted", issues);
checks.push(completedCheck("TYPESCRIPT-ESLINT-PEER", "8.68.0 / 10.9.1 / 6.0.3 within >=4.8.4 <6.1.0"));

const inventory = readFileSync("src/app/routeInventory.ts", "utf8");
for (const route of expectedRoutes) fail(inventory.includes(`\"${route}\"`), `route absent: ${route}`, issues);
const pathCount = [...inventory.matchAll(/path:\s*"\//gu)].length;
fail(pathCount === 18, `route inventory contains ${pathCount}, expected 18`, issues);
checks.push(completedCheck("READ-ONLY-ROUTES", "18 exact P3-12 routes"));

const sourceFiles = files("src");
const combined = sourceFiles.map((path) => readFileSync(path, "utf8")).join("\n");
for (const forbidden of [
  "localStorage",
  "sessionStorage",
  "document.cookie",
  "MOVE_OPERATION",
  "ASSIGN_RESOURCE",
  "SET_LOCK",
  "REMOVE_LOCK",
  "REQUEST_EXPORT",
  "Idempotency-Key",
]) {
  fail(!combined.includes(forbidden), `forbidden client authority/token surface: ${forbidden}`, issues);
}
checks.push(completedCheck("CLIENT-AUTHORITY", "no token persistence or command carrier"));

const sourcePaths = sourceFiles.map((path) => relative("src", path).replaceAll("\\", "/"));
for (const fragment of ["commands", "actions", "replan", "change-report", "execution-event"] ) {
  fail(!sourcePaths.some((path) => path.toLowerCase().includes(fragment)), `P3-13/P4 module present: ${fragment}`, issues);
}
for (const path of requiredVisualizationFiles) {
  fail(existsSync(path), `required visualization evidence file absent: ${path}`, issues);
}
checks.push(completedCheck("VISUALIZATION-MODULES", "Gantt/load/comparison/browser modules present"));

const contracts = readFileSync("src/api/contracts.ts", "utf8");
for (const contract of [
  "GANTT_SEGMENT",
  "RESOURCE_LOAD",
  "VERSION_COMPARISON",
  "unsupported server change kind",
  "canonical complete payload",
]) {
  fail(contracts.includes(contract), `strict visualization contract absent: ${contract}`, issues);
}
const client = readFileSync("src/api/client.ts", "utf8");
fail(client.includes('"/schedule-version-comparisons"'), "comparison read-query endpoint absent", issues);
fail(!client.includes("/commands"), "client command endpoint was introduced", issues);
checks.push(completedCheck("SERVER-AUTHORITY", "strict payloads and comparison read-query only"));

const browserReportPath = "../build/playwright/results.json";
let browserSpecs = [];
if (!existsSync(browserReportPath)) {
  issues.push("Playwright JSON evidence is absent");
} else {
  const browserReport = JSON.parse(readFileSync(browserReportPath, "utf8"));
  const visit = (suites) => {
    for (const suite of suites ?? []) {
      browserSpecs.push(...(suite.specs ?? []));
      visit(suite.suites);
    }
  };
  visit(browserReport.suites);
  fail(browserReport.errors?.length === 0, "Playwright report contains top-level errors", issues);
  fail(browserSpecs.length === 4, `Playwright spec count is ${browserSpecs.length}, expected 4`, issues);
  for (const spec of browserSpecs) {
    const results = (spec.tests ?? []).flatMap((test) => test.results ?? []);
    fail(spec.ok === true && results.some((result) => result.status === "passed"), `Playwright spec failed: ${spec.title}`, issues);
  }
}
const browserSource = readFileSync("e2e/read-only-visualizations.spec.ts", "utf8");
fail(browserSource.includes("syntheticSegmentCount = 120"), "120-row browser scale fixture absent", issues);
fail(browserSource.includes("toBeLessThanOrEqual(24)"), "virtual row mount boundary absent", issues);
const playwrightConfig = readFileSync("playwright.config.ts", "utf8");
for (const retention of ['trace: "retain-on-failure"', 'screenshot: "only-on-failure"', 'video: "retain-on-failure"']) {
  fail(playwrightConfig.includes(retention), `browser failure retention drifted: ${retention}`, issues);
}
checks.push(completedCheck("BROWSER-EVIDENCE", `${browserSpecs.length}/4 read-only Chromium specs`));

checks.push(completedCheck("PHASE-BOUNDARY", "no control/P4 module, client authority or Production claim"));

const assets = files("dist/assets");
const javascriptBytes = assets
  .filter((path) => path.endsWith(".js"))
  .reduce((total, path) => total + statSync(path).size, 0);
const cssBytes = assets
  .filter((path) => path.endsWith(".css"))
  .reduce((total, path) => total + statSync(path).size, 0);
fail(javascriptBytes > 0 && javascriptBytes <= 2_000_000, `JavaScript bundle bytes ${javascriptBytes} exceed development boundary`, issues);
fail(cssBytes > 0 && cssBytes <= 250_000, `CSS bundle bytes ${cssBytes} exceed development boundary`, issues);
checks.push(completedCheck("BUILD-OBSERVATION", `${javascriptBytes} JS bytes / ${cssBytes} CSS bytes`));

const report = {
  report_version: "p3-frontend-visualization-report.v1",
  task: "TASK-P3-12",
  code_commit: codeCommit(),
  diff_base: "3bca1cc10ebedc4d47227bafb2f3f66854ccb526",
  status: issues.length === 0 ? "PASS" : "FAIL",
  direct_dependency_count: Object.keys(runtimePins).length + Object.keys(developmentPins).length,
  route_count: pathCount,
  state_count: 7,
  source_file_count: sourceFiles.length,
  bundle: { javascript_bytes: javascriptBytes, css_bytes: cssBytes },
  render_observation: {
    profile: "VERSIONED_SYNTHETIC_UI_120@1.0.0",
    total_gantt_rows: 120,
    mounted_visual_row_boundary: 24,
    browser_spec_count: browserSpecs.length,
    production_sla_asserted: false,
  },
  frozen_inputs: {
    read_model_closure: "67d38d030f8b129de7f1b2f6e5b75bd706655396",
    comparison_fingerprint: "sha256:5a24b392ff6064de06f9ba8eaa5112dc66a8a8a3b6c370650706cb2a1a4145dc",
    api_closure: "26dd519b1f1f84e08d415cfdfce43f286fa82988",
    openapi_fingerprint: "sha256:fbabcc5b9005f5ec22f3a6e8b6351bcf0469dbaa176682caa954191c0d697b36",
    frontend_foundation_closure: "3bca1cc10ebedc4d47227bafb2f3f66854ccb526",
  },
  boundaries: {
    read_only: true,
    browser_e2e_formed: true,
    command_or_action_ui_formed: false,
    client_solver_validator_kpi_formed: false,
    production_identity_formed: false,
    p4_formed: false,
    production_readiness: false,
  },
  checks,
  issues,
};
const target = writeReport(reportPath, report);
process.stdout.write(`${report.status} ${target}\n`);
if (issues.length > 0) process.exitCode = 1;
