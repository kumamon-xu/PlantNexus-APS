import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, relative } from "node:path";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const taskId = "TASK-P3-13";
const diffBase = "3dacf83c0f0bf87a9fa673aa75d61f8ad8659386";
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
const requiredControlFiles = [
  ".env.e2e",
  "src/api/commands.ts",
  "src/features/schedule-actions/useHumanControlAction.ts",
  "src/features/schedule-actions/ScheduleActionsPanel.tsx",
  "src/features/approval/ApprovalPanel.tsx",
  "src/features/publication/PublicationPanel.tsx",
  "src/features/export/ExportPanel.tsx",
  "src/features/audit/AuditHistoryPanel.tsx",
  "e2e/human-control-actions.spec.ts",
  "e2e/read-only-visualizations.spec.ts",
  "playwright.config.ts",
];
const requiredTestIds = [
  "TEST-WORKSPACE-FRONTEND-001",
  "TEST-GANTT-COMMAND-001",
  "TEST-APPROVAL-AUTHORIZATION-001",
  "TEST-PUBLISH-IDEMPOTENCY-001",
  "TEST-EXPORT-JOB-001",
  "TEST-AUDIT-TRAIL-001",
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
checks.push(completedCheck("RUNTIME-PINS", "Node 24.19.0 / npm 11.17.0"));

for (const [name, version] of Object.entries(runtimePins)) {
  fail(pkg.dependencies?.[name] === version, `runtime pin drift: ${name}`, issues);
  fail(lockRoot.dependencies?.[name] === version, `runtime lock drift: ${name}`, issues);
}
for (const [name, version] of Object.entries(developmentPins)) {
  fail(pkg.devDependencies?.[name] === version, `development pin drift: ${name}`, issues);
  fail(lockRoot.devDependencies?.[name] === version, `development lock drift: ${name}`, issues);
}
fail(lock.lockfileVersion === 3, `lockfileVersion is ${String(lock.lockfileVersion)}`, issues);
checks.push(
  completedCheck(
    "DIRECT-DEPENDENCY-LOCK",
    `${Object.keys(runtimePins).length + Object.keys(developmentPins).length} exact direct pins / npm lockfile v3`,
  ),
);

const tsEslint = lock.packages?.["node_modules/typescript-eslint"] ?? {};
fail(tsEslint.version === "8.68.0", "typescript-eslint lock pin drifted", issues);
fail(
  tsEslint.peerDependencies?.typescript === ">=4.8.4 <6.1.0",
  `typescript-eslint TypeScript peer is ${String(tsEslint.peerDependencies?.typescript)}`,
  issues,
);
fail(pkg.devDependencies.eslint === "10.9.1", "ESLint compatibility pin drifted", issues);
fail(pkg.devDependencies.typescript === "6.0.3", "TypeScript compatibility pin drifted", issues);
checks.push(
  completedCheck(
    "TYPESCRIPT-ESLINT-PEER",
    "8.68.0 / ESLint 10.9.1 / TypeScript 6.0.3 inside >=4.8.4 <6.1.0",
  ),
);

const inventory = readFileSync("src/app/routeInventory.ts", "utf8");
for (const route of expectedRoutes) {
  fail(inventory.includes(`"${route}"`), `route absent: ${route}`, issues);
}
const totalPathCount = [...inventory.matchAll(/path:\s*"\//gu)].length;
const p3PathCount = expectedRoutes.length;
fail(totalPathCount === 19, `route inventory contains ${totalPathCount}, expected 19`, issues);
fail(
  inventory.includes('path: "/planning/replanning"') &&
    inventory.includes("p3WorkspaceRoutes") &&
    inventory.includes("p4WorkspaceRoutes"),
  "bounded additive P4 route is not separated from the frozen P3 subset",
  issues,
);
checks.push(completedCheck("WORKSPACE-ROUTES", "18 exact P3 routes preserved plus one bounded additive P4 route"));

for (const path of requiredControlFiles) {
  fail(existsSync(path), `required P3-13 control file absent: ${path}`, issues);
}
const sourceFiles = files("src");
const sourcePaths = sourceFiles.map((path) => relative("src", path).replaceAll("\\", "/"));
const combined = sourceFiles.map((path) => readFileSync(path, "utf8")).join("\n");
for (const forbidden of ["sessionStorage", "document.cookie"]) {
  fail(!combined.includes(forbidden), `credential persistence surface present: ${forbidden}`, issues);
}
const localStoragePaths = sourceFiles
  .filter((path) => readFileSync(path, "utf8").includes("localStorage"))
  .map((path) => relative("src", path).replaceAll("\\", "/"));
fail(
  JSON.stringify(localStoragePaths) === JSON.stringify(["i18n/locale.ts"]),
  `localStorage is only allowed for the versioned locale preference: ${localStoragePaths.join(", ")}`,
  issues,
);
const localeSource = readFileSync("src/i18n/locale.ts", "utf8");
const localeTypesSource = readFileSync("src/i18n/types.ts", "utf8");
fail(localeSource.includes("localePreferenceKey"), "locale storage does not use the typed preference key", issues);
fail(
  localeTypesSource.includes('localePreferenceKey = "plantnexus.locale.v1"'),
  "versioned locale preference key is absent",
  issues,
);
const p4SourcePaths = sourcePaths.filter((path) => path.startsWith("features/replanning/"));
fail(p4SourcePaths.length === 6, `bounded P4 module count is ${p4SourcePaths.length}, expected 6`, issues);
for (const command of [
  "MOVE_OPERATION",
  "ASSIGN_RESOURCE",
  "SET_LOCK",
  "SUBMIT_FOR_REVIEW",
  "APPROVE",
  "REJECT",
  "PUBLISH",
  "REQUEST_EXPORT",
  "RETRY_EXPORT",
]) {
  fail(combined.includes(command), `required human-control command absent: ${command}`, issues);
}
checks.push(
  completedCheck(
    "HUMAN-CONTROL-MODULES",
    "frozen P3 state/capability controls and command carrier; no browser credential persistence; additive P4 module isolated",
  ),
);

const runtimeSource = readFileSync("src/api/runtime.ts", "utf8");
for (const boundary of [
  'env.DEV === true',
  'env.VITE_PLANTNEXUS_E2E_SIMULATION === "true"',
  'requestedPlane === "SIMULATION"',
  'requestedEnvironment === "TEST"',
  "SIM-P3-HUMAN-CONTROL-001",
]) {
  fail(runtimeSource.includes(boundary), `isolated E2E runtime boundary absent: ${boundary}`, issues);
}
const envSource = readFileSync(".env.e2e", "utf8");
fail(!/token|secret|password|key=/iu.test(envSource), "E2E environment contains credential-like material", issues);
checks.push(
  completedCheck(
    "SIMULATION-ISOLATION",
    "development-only TEST synthetic fixture; Production remains default-deny",
  ),
);

const commandSource = readFileSync("src/api/commands.ts", "utf8");
const actionSource = readFileSync(
  "src/features/schedule-actions/useHumanControlAction.ts",
  "utf8",
);
for (const boundary of [
  "workspaceCommandFingerprint",
  "expected_content_fingerprint",
  "idempotency_scope",
  "SIMULATION_INTERNAL",
  "credentialLike",
]) {
  fail(commandSource.includes(boundary), `command producer boundary absent: ${boundary}`, issues);
}
for (const boundary of [
  "inFlight.current",
  "outcome_unknown",
  "refreshAuthority",
  "retained.current",
  "retryReady",
]) {
  fail(actionSource.includes(boundary), `unknown-outcome guard absent: ${boundary}`, issues);
}
checks.push(
  completedCheck(
    "IDEMPOTENCY-AND-FAILURE",
    "double-submit guard and refresh-before-same-command retry are explicit",
  ),
);

const downloadClient = readFileSync("src/api/client.ts", "utf8");
const exportPanel = readFileSync("src/features/export/ExportPanel.tsx", "utf8");
for (const boundary of [
  "/download",
  "application/zip",
  "X-PlantNexus-Archive-Fingerprint",
  "sha256BytesFingerprint",
  "maxExportArchiveBytes",
]) {
  fail(downloadClient.includes(boundary), `verified download boundary absent: ${boundary}`, issues);
}
for (const boundary of [
  'job?.state === "EXPORT_FAILED"',
  'job?.state === "EXPORTED"',
  "artifact_manifest.manifest_fingerprint",
  "URL.createObjectURL",
]) {
  fail(exportPanel.includes(boundary), `Export UI boundary absent: ${boundary}`, issues);
}
checks.push(
  completedCheck(
    "EXPORT-RETRY-DOWNLOAD",
    "visible job states, explicit retry, EXPORTED-only manifest/hash-bound download",
  ),
);

const apiReportPath = "../build/validation/ci-p3-planning-workspace-api.json";
let apiOperationCount = 0;
let apiOpenapiFingerprint = null;
if (!existsSync(apiReportPath)) {
  issues.push("P3 planning-workspace API evidence is absent");
} else {
  const apiReport = JSON.parse(readFileSync(apiReportPath, "utf8"));
  apiOperationCount = apiReport.counts?.http_operations ?? 0;
  apiOpenapiFingerprint = apiReport.openapi_fingerprint ?? null;
  fail(apiReport.status === "PASS", "P3 API machine report did not pass", issues);
  fail(apiReport.issues?.length === 0, "P3 API machine report contains issues", issues);
  fail(apiReport.counts?.api_paths === 18, "P3 API path count is not 18", issues);
  fail(apiOperationCount === 18, "P3 API operation count is not 18", issues);
  fail(
    apiReport.boundaries?.p3_10_frozen_operations === 17 &&
      apiReport.boundaries?.p3_13_additive_operations === 1,
    "P3-10 frozen/P3-13 additive API boundary drifted",
    issues,
  );
  fail(
    apiReport.boundaries?.internal_simulation_download === "EXPORTED_VERIFIED_ZIP_ONLY",
    "bounded internal download boundary is absent",
    issues,
  );
}
checks.push(
  completedCheck(
    "API-ADDITIVE-BOUNDARY",
    `${apiOperationCount} operations = 17 frozen P3-10 + 1 P3-13 download`,
  ),
);

const browserReportPath = "../build/playwright/results.json";
const browserJunitPath = "../build/playwright/results.xml";
const browserHtmlPath = "../build/playwright/html/index.html";
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
}
const p3BrowserSpecs = browserSpecs.filter(
  (spec) => spec.file !== "dynamic-replanning.spec.ts",
);
fail(p3BrowserSpecs.length === 12, `frozen P3 Playwright spec count is ${p3BrowserSpecs.length}, expected 12`, issues);
for (const spec of p3BrowserSpecs) {
  const results = (spec.tests ?? []).flatMap((item) => item.results ?? []);
  fail(
    spec.ok === true && results.some((result) => result.status === "passed"),
    `frozen P3 Playwright spec failed: ${spec.title}`,
    issues,
  );
}
const controlSpecs = p3BrowserSpecs.filter((spec) => spec.file === "human-control-actions.spec.ts");
fail(controlSpecs.length === 8, `human-control browser spec count is ${controlSpecs.length}, expected 8`, issues);
fail(existsSync(browserJunitPath), "Playwright JUnit evidence is absent", issues);
fail(existsSync(browserHtmlPath), "Playwright HTML evidence is absent", issues);
const browserSource = readFileSync("e2e/human-control-actions.spec.ts", "utf8");
for (const matrix of [
  "[401, 403, 409, 422, 500]",
  "failNextNetwork",
  "Retry same request",
  "PUBLISHED Gantt immutable",
  "Download verified package",
]) {
  fail(browserSource.includes(matrix), `browser state/error matrix absent: ${matrix}`, issues);
}
const playwrightConfig = readFileSync("playwright.config.ts", "utf8");
for (const retention of [
  '["junit", { outputFile: "../build/playwright/results.xml" }]',
  '["html", { outputFolder: "../build/playwright/html", open: "never" }]',
  'trace: "retain-on-failure"',
  'screenshot: "only-on-failure"',
  'video: "retain-on-failure"',
  "--mode e2e",
]) {
  fail(playwrightConfig.includes(retention), `browser reporter/retention drifted: ${retention}`, issues);
}
checks.push(
  completedCheck(
    "BROWSER-EVIDENCE",
    `${p3BrowserSpecs.length}/12 frozen P3 Chromium specs inside ${browserSpecs.length} total; ${controlSpecs.length}/8 controls; JSON/JUnit/HTML and failure retention`,
  ),
);

const publishedGuard = readFileSync(
  "src/features/schedule-actions/ScheduleActionsPanel.tsx",
  "utf8",
);
fail(
  publishedGuard.includes('version.state === "PUBLISHED"') &&
    publishedGuard.includes("Published history is immutable"),
  "PUBLISHED mutation guard is absent",
  issues,
);
const frozenP3Client = readFileSync("src/api/client.ts", "utf8");
fail(!frozenP3Client.includes("/replan-requests"), "P4 Replan route leaked into the frozen P3 client", issues);
fail(!frozenP3Client.includes("/execution-events"), "P4 ExecutionEvent route leaked into the frozen P3 client", issues);
checks.push(
  completedCheck(
    "PHASE-BOUNDARY",
    "PUBLISHED immutable; P4 consumer remains additive and isolated; no MES, external storage, Production authority or readiness claim",
  ),
);

const assets = files("dist/assets");
const javascriptBytes = assets
  .filter((path) => path.endsWith(".js"))
  .reduce((total, path) => total + statSync(path).size, 0);
const cssBytes = assets
  .filter((path) => path.endsWith(".css"))
  .reduce((total, path) => total + statSync(path).size, 0);
fail(
  javascriptBytes > 0 && javascriptBytes <= 2_100_000,
  `JavaScript bundle bytes ${javascriptBytes} exceed development boundary`,
  issues,
);
fail(
  cssBytes > 0 && cssBytes <= 275_000,
  `CSS bundle bytes ${cssBytes} exceed development boundary`,
  issues,
);
checks.push(
  completedCheck(
    "BUILD-OBSERVATION",
    `${javascriptBytes} JS bytes / ${cssBytes} CSS bytes; development observation only`,
  ),
);

const report = {
  report_version: "p3-frontend-human-control-report.v1",
  task_id: taskId,
  code_commit: codeCommit(),
  diff_base: diffBase,
  status: issues.length === 0 ? "PASS" : "FAIL",
  direct_dependency_count: Object.keys(runtimePins).length + Object.keys(developmentPins).length,
  route_count: p3PathCount,
  all_route_count: totalPathCount,
  api_operation_count: apiOperationCount,
  api_openapi_fingerprint: apiOpenapiFingerprint,
  source_file_count: sourceFiles.length,
  browser_spec_count: p3BrowserSpecs.length,
  all_browser_spec_count: browserSpecs.length,
  human_control_browser_spec_count: controlSpecs.length,
  test_ids: requiredTestIds,
  bundle: { javascript_bytes: javascriptBytes, css_bytes: cssBytes },
  simulation_fixture: {
    scenario_id: "SIM-P3-HUMAN-CONTROL-001",
    scenario_version: "1.0.0",
    actor_ref: "actor:p3-e2e-synthetic-controller",
    mock_transport: true,
    production_extrapolation: false,
  },
  frozen_inputs: {
    p3_10_api_closure: "26dd519b1f1f84e08d415cfdfce43f286fa82988",
    p3_11_frontend_closure: "3bca1cc10ebedc4d47227bafb2f3f66854ccb526",
    p3_12_visualization_closure: "3dacf83c0f0bf87a9fa673aa75d61f8ad8659386",
  },
  boundaries: {
    p3_10_frozen_http_operations: 17,
    p3_13_additive_download_operations: 1,
    server_authority_only: true,
    internal_simulation_controls: true,
    verified_export_download: true,
    browser_e2e_formed: true,
    schema_migration_dependency_state_pairs_changed: false,
    client_solver_validator_kpi_formed: false,
    external_identity_mes_storage_formed: false,
    p4_additive_route_excluded_from_frozen_p3_counts: true,
    production_identity_formed: false,
    production_readiness: false,
  },
  checks,
  issues,
};
const target = writeReport(reportPath, report);
process.stdout.write(`${report.status} ${target}\n`);
if (issues.length > 0) process.exitCode = 1;
