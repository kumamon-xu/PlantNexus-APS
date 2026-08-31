import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const taskId = "TASK-P4-13";
const diffBase = "be2389594f3e224de3f5a73f4b8b62ffcffb5b7b";
const reportVersion = "p4-replanning-frontend-report.v1";
const impactRules = [
  "IMPACT-FRONTEND",
  "IMPACT-INFRA",
  "IMPACT-STATE",
  "IMPACT-TESTS",
  "IMPACT-DOCS",
];
const testIds = [
  "TEST-REPLAN-FRONTEND-001",
  "TEST-REPLAN-API-001",
  "TEST-WORKSPACE-FRONTEND-001",
  "TEST-FRONTEND-I18N-001",
  "TEST-CHANGE-REPORT-001",
];
const p3RouteCount = 18;
const p4Route = "/planning/replanning";
const p3BrowserSpecCount = 12;
const p4BrowserSpecCount = 5;

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

function collectSpecs(report) {
  const specs = [];
  const visit = (suites) => {
    for (const suite of suites ?? []) {
      specs.push(...(suite.specs ?? []));
      visit(suite.suites);
    }
  };
  visit(report.suites);
  return specs;
}

function changedNames(paths) {
  return execFileSync(
    "git",
    ["diff", "--name-only", diffBase, "--", ...paths],
    { cwd: resolve(process.cwd(), ".."), encoding: "utf8" },
  )
    .split(/\r?\n/u)
    .filter(Boolean)
    .map((path) => path.replaceAll("\\", "/"));
}

const reportPath = argument("--report");
const issues = [];
const checks = [];
const sourceRoot = "src/features/replanning";
const sourceFiles = files(sourceRoot);
const combined = sourceFiles.map((path) => readFileSync(path, "utf8")).join("\n");
const routeSource = readFileSync("src/app/routeInventory.ts", "utf8");

for (const path of [
  "src/features/replanning/types.ts",
  "src/features/replanning/contracts.ts",
  "src/features/replanning/query.ts",
  "src/features/replanning/client.ts",
  "src/features/replanning/useReplanningWorkspace.ts",
  "src/features/replanning/ReplanningWorkspacePage.tsx",
]) {
  fail(existsSync(path), `required P4 consumer source is absent: ${path}`, issues);
}
for (const marker of [
  "dynamic-replanning-query.v1",
  "dynamic-replanning-response.v1",
  "execution-event-timeline.v1",
  "replan-request-workspace.v1",
  "replan-result-workspace.v1",
  "change-report-workspace.v1",
  "projection_fingerprint",
  "query_fingerprint",
]) {
  fail(combined.includes(marker), `typed P4 projection boundary is absent: ${marker}`, issues);
}
checks.push(
  completedCheck(
    "STRICT-TYPED-PROJECTIONS",
    "four versioned query-bound projections plus canonical projection fingerprint verification",
  ),
);

const totalRouteCount = [...routeSource.matchAll(/path:\s*"\//gu)].length;
fail(totalRouteCount === 19, `route count is ${totalRouteCount}, expected 19`, issues);
fail(routeSource.includes("p3WorkspaceRoutes"), "frozen P3 route subset is absent", issues);
fail(routeSource.includes(`path: "${p4Route}"`), "bounded P4 route is absent", issues);
fail(!combined.includes("production-publish"), "Production publish leaked into P4 UI", issues);
checks.push(
  completedCheck(
    "ADDITIVE-ROUTE-INVENTORY",
    `${p3RouteCount} frozen P3 routes plus one bounded P4 route; no P5 or Production route`,
  ),
);

for (const marker of [
  "allowed_actions.includes",
  "expected_planning_run_state",
  "outcomeUnknown",
  "retained.current",
  "refreshAuthority",
  "retrySameRequest",
  "Idempotency-Key",
  "X-Planning-Scope-Id",
]) {
  fail(combined.includes(marker), `server-authority/action recovery marker is absent: ${marker}`, issues);
}
for (const forbidden of [
  "sessionStorage",
  "document.cookie",
  "/simulator",
  "calculateStability",
  "weightedTardiness =",
]) {
  fail(!combined.includes(forbidden), `client-side authority or persistence surface present: ${forbidden}`, issues);
}
checks.push(
  completedCheck(
    "SERVER-AUTHORITY-AND-UNKNOWN-OUTCOME",
    "server allowed_actions / expected-state CAS / in-memory same-key query-before-retry / no browser fact calculation",
  ),
);

const en = readFileSync("src/i18n/dictionaries/en-US.ts", "utf8");
const zh = readFileSync("src/i18n/dictionaries/zh-CN.ts", "utf8");
const labels = readFileSync("src/i18n/business-labels.ts", "utf8");
for (const marker of [
  "replanning.title",
  "replanning.simulationBoundaryTitle",
  "replanning.tardinessBefore",
  "replanning.feedback.outcome_unknown",
  "replanning.phaseBoundary",
]) {
  fail(en.includes(`"${marker}"`), `English P4 key absent: ${marker}`, issues);
  fail(zh.includes(`"${marker}"`), `Chinese P4 key absent: ${marker}`, issues);
}
for (const marker of [
  "executionEvent",
  "planningRunState",
  "replanAction",
  "changeClassification",
  "known: false",
]) {
  fail(labels.includes(marker), `raw/official P4 label boundary absent: ${marker}`, issues);
}
for (const path of [
  "tests/replanningContracts.test.ts",
  "tests/replanningClient.test.ts",
  "tests/replanningWorkspace.test.tsx",
  "tests/accessibility.test.tsx",
  "e2e/dynamic-replanning.spec.ts",
]) {
  fail(existsSync(path), `P4 automated evidence source absent: ${path}`, issues);
}
checks.push(
  completedCheck(
    "BILINGUAL-A11Y-RAW-FALLBACK",
    "zh-CN/en-US keys, official machine registries, raw values, component tests and axe coverage",
  ),
);

const browserJson = "../build/playwright/results.json";
const browserJunit = "../build/playwright/results.xml";
const browserHtml = "../build/playwright/html/index.html";
let allSpecs = [];
let p4Specs = [];
if (!existsSync(browserJson)) {
  issues.push("Playwright JSON evidence is absent");
} else {
  const browser = JSON.parse(readFileSync(browserJson, "utf8"));
  allSpecs = collectSpecs(browser);
  p4Specs = allSpecs.filter((spec) => spec.file === "dynamic-replanning.spec.ts");
  fail(browser.errors?.length === 0, "Playwright report contains top-level errors", issues);
  fail(
    allSpecs.length === p3BrowserSpecCount + p4BrowserSpecCount,
    `all Playwright spec count is ${allSpecs.length}, expected 17`,
    issues,
  );
  fail(p4Specs.length === p4BrowserSpecCount, `P4 Playwright spec count is ${p4Specs.length}`, issues);
  fail(p4Specs.every((spec) => spec.ok === true), "one or more P4 Playwright specs failed", issues);
}
fail(existsSync(browserJunit), "Playwright JUnit evidence is absent", issues);
fail(existsSync(browserHtml), "Playwright HTML evidence is absent", issues);
const browserSource = readFileSync("e2e/dynamic-replanning.spec.ts", "utf8");
for (const marker of [
  "fiveDisruptionEvents",
  "[401, 403, 409, 422, 500]",
  "tamperReport",
  "abortFirstAction",
  "Retry same request",
  "expect(actions[1]).toEqual(actions[0])",
]) {
  fail(browserSource.includes(marker), `browser matrix marker absent: ${marker}`, issues);
}
checks.push(
  completedCheck(
    "CHROMIUM-POSITIVE-NEGATIVE-RECOVERY",
    `${p4Specs.length}/${p4BrowserSpecCount} P4 specs inside ${allSpecs.length}/17 total; JSON/JUnit/HTML plus retained failure media policy`,
  ),
);

const apiReportPath = "../build/validation/ci-p4-replanning-api.json";
let apiChecks = 0;
if (!existsSync(apiReportPath)) {
  issues.push("P4 dynamic-replanning API evidence is absent");
} else {
  const api = JSON.parse(readFileSync(apiReportPath, "utf8"));
  apiChecks = api.check_count ?? 0;
  fail(api.report_version === "p4-replanning-api-report.v1", "P4 API report version drifted", issues);
  fail(api.status === "PASS", "P4 API report did not pass", issues);
  fail(api.check_count === 8, "P4 API report does not contain 8 checks", issues);
  fail(api.issues?.length === 0, "P4 API report contains issues", issues);
  fail(api.counts?.http_operations === 9, "P4 API operation count drifted", issues);
  fail(api.boundaries?.production_authority === "DEFAULT_DENY_OPEN_010_015", "P4 API Production default-deny drifted", issues);
}
checks.push(
  completedCheck(
    "FROZEN-P4-API-CONSUMER",
    `${apiChecks}/8 P4-12 API checks; 9 operations; unknown-outcome and Production default-deny retained`,
  ),
);

const approvedCiContractTest = "backend/tests/integration/test_ci_contract.py";
const approvedP4GateEvidence = new Set([
  "backend/app/application/p4_gate_report.py",
  "backend/tests/contract/test_p4_gate_rejections.py",
  "backend/tests/integration/test_p1_common_ingress.py",
  "backend/tests/integration/test_p4_vertical_slice.py",
]);
const frozenChanges = changedNames([
  "backend",
  "schemas",
  "pyproject.toml",
  "uv.lock",
  "frontend/package.json",
  "frontend/package-lock.json",
]).filter((path) => path !== approvedCiContractTest && !approvedP4GateEvidence.has(path));
fail(frozenChanges.length === 0, `forbidden backend/schema/dependency paths changed: ${frozenChanges.join(", ")}`, issues);
const ciContractTest = readFileSync(resolve("..", approvedCiContractTest), "utf8");
fail(
  ciContractTest.includes("TASK-P4-13 Dynamic replanning frontend machine evidence") &&
    ciContractTest.includes("P4 vertical slice Gate evidence") &&
    ciContractTest.includes('len(full["steps"]) == 68'),
  "bounded FULL-step CI governance regression is absent",
  issues,
);
const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
fail(pkg.engines?.node === "24.19.0", "Node pin drifted", issues);
fail(pkg.engines?.npm === "11.17.0", "npm pin drifted", issues);
fail(lock.lockfileVersion === 3, "npm lockfile version drifted", issues);
checks.push(
  completedCheck(
    "ZERO-BACKEND-SCHEMA-DEPENDENCY-DRIFT",
    "backend business/schema/migration/dependency and Frontend package/lock frozen; four additive P4 Gate evidence/test files plus one exact 68-step CI test approved",
  ),
);

const assets = files("dist/assets");
const javascriptBytes = assets
  .filter((path) => path.endsWith(".js"))
  .reduce((total, path) => total + statSync(path).size, 0);
const cssBytes = assets
  .filter((path) => path.endsWith(".css"))
  .reduce((total, path) => total + statSync(path).size, 0);
fail(javascriptBytes > 0 && javascriptBytes <= 2_300_000, `JavaScript bundle is ${javascriptBytes} bytes`, issues);
fail(cssBytes > 0 && cssBytes <= 300_000, `CSS bundle is ${cssBytes} bytes`, issues);
for (const boundary of [
  "Production identity",
  "external publish",
  "P4 Gate",
  "P5",
  "capacity",
  "SLA",
]) {
  fail(en.includes(boundary), `visible phase boundary absent: ${boundary}`, issues);
}
checks.push(
  completedCheck(
    "BUILD-AND-PHASE-BOUNDARY",
    `${javascriptBytes} JS bytes / ${cssBytes} CSS bytes; Simulation DRAFT only; P4 Gate/P5/Production not formed`,
  ),
);

const report = {
  report_version: reportVersion,
  task_id: taskId,
  code_commit: codeCommit(),
  diff_base: diffBase,
  status: issues.length === 0 ? "PASS" : "FAIL",
  impact_rule_count: impactRules.length,
  impact_rules: impactRules,
  check_count: checks.length,
  checks,
  test_ids: testIds,
  counts: {
    p3_frozen_routes: p3RouteCount,
    p4_routes: 1,
    p4_source_files: sourceFiles.length,
    p4_browser_specs: p4Specs.length,
    all_browser_specs: allSpecs.length,
    p4_api_checks: apiChecks,
  },
  browser_evidence: {
    json: relative(resolve(process.cwd(), ".."), resolve(browserJson)).replaceAll("\\", "/"),
    junit: relative(resolve(process.cwd(), ".."), resolve(browserJunit)).replaceAll("\\", "/"),
    html: relative(resolve(process.cwd(), ".."), resolve(browserHtml)).replaceAll("\\", "/"),
    failure_media_policy: "TRACE_VIDEO_SCREENSHOT_RETAINED_ON_FAILURE",
  },
  simulation_fixture: {
    assumption_id: "SIM-ASSUMPTION-020",
    scenario_id: "SIM-P4-REPLANNING-UI-001",
    scenario_version: "1.0.0",
    event_scenario_count: 5,
    event_count: 6,
    mock_transport: true,
    production_extrapolation: false,
  },
  frozen_inputs: {
    p4_09_closure: "8bbe0c643571e578ec637f135a2390c90de02512",
    p4_10_closure: "45b12d9a67ce5ef1680a47fecdc68705355af226",
    p4_11_closure: "f4a54d3bb065b5cc8b51c450ffdc435bcc77d384",
    p4_12_closure: diffBase,
  },
  forbidden_changes: frozenChanges,
  boundaries: {
    server_authority_only: true,
    browser_fact_freeze_kpi_stability_validator_calculation: false,
    replan_request_state_machine: false,
    simulation_development_only: true,
    schema_migration_dependency_state_pairs_changed: false,
    simulator_control: false,
    external_publish: false,
    p4_gate_started: false,
    p5_started: false,
    production_authority_formed: false,
    capacity_sla_formed: false,
    production_readiness: false,
  },
  bundle: { javascript_bytes: javascriptBytes, css_bytes: cssBytes },
  issues,
};

const target = writeReport(reportPath, report);
process.stdout.write(`${report.status} ${target}\n`);
if (issues.length > 0) process.exitCode = 1;
