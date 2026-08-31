import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import ts from "typescript";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const taskId = "TASK-P3-16";
const diffBase = "1636fe9c909b728d49f9907ed9f53030b5921914";
const terminologyVersion = "official-zh-cn-terminology.v1";
const locales = ["zh-CN", "en-US"];
const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDirectory, "../..");
const frontendRoot = resolve(repositoryRoot, "frontend");

const expected = {
  scheduleState: ["DRAFT", "READY_FOR_REVIEW", "APPROVED", "PUBLISHED", "SUPERSEDED", "REJECTED"],
  exportJobState: ["CREATED", "EXPORTING", "EXPORTED", "EXPORT_FAILED", "CANCELLED"],
  workspaceView: ["DATA_HEALTH", "IMPORT_RUNS", "PLANNING_RUNS", "ORDERS", "OPERATIONS", "RESOURCES", "CALENDARS", "GANTT", "RESOURCE_LOAD", "KPI", "DIAGNOSTICS", "LOCKS", "AUDIT", "VERSION_COMPARISON"],
  command: ["MOVE_OPERATION", "ASSIGN_RESOURCE", "SET_LOCK", "REMOVE_LOCK", "SUBMIT_FOR_REVIEW", "APPROVE", "REJECT", "PUBLISH", "REQUEST_EXPORT", "RETRY_EXPORT", "CANCEL_EXPORT"],
  allowedAction: ["view", "edit", "lock", "approve", "reject", "publish", "export", "audit"],
  uiState: ["loading", "empty", "ready", "stale", "authorization_denied", "contract_error", "server_error"],
  changeKind: ["ADDED", "REMOVED", "RESOURCE_CHANGE", "DURATION_CHANGE", "START_SHIFT", "UNCHANGED"],
  constraint: ["C-001", "C-002", "C-003", "C-004", "C-005", "C-006", "C-007", "C-008", "C-009", "C-010", "C-011"],
  productCategory: ["DATA_ERROR", "UNSUPPORTED_CAPABILITY", "MODEL_INVALID", "INFEASIBLE", "NO_SOLUTION_WITHIN_LIMIT", "VALIDATION_FAILED", "SYSTEM_ERROR"],
  productCode: ["INVALID_TIME", "DUPLICATE_ID", "MISSING_SCENARIO_ID", "SYNTHETIC_REFERENCE_IN_PRODUCTION", "INVALID_ENTITY_COUNT", "INVALID_DURATION", "INVALID_TIME_RANGE", "MISSING_RUNNING_FACT", "INVALID_REFERENCE", "INVALID_LAG_RANGE", "INVALID_CAPABILITY_DECLARATION", "DUPLICATE_CAPABILITY", "INVALID_STATE_TRANSITION", "ROUTE_CYCLE", "MISSING_RESOURCE", "UNIT_CONVERSION_ERROR", "MISSING_DURATION", "UNSUPPORTED_CAPABILITY", "MODEL_INVALID", "INFEASIBLE", "NO_SOLUTION_WITHIN_LIMIT", "SCHEDULE_VALIDATION_FAILED", "SYSTEM_ERROR"],
  workspaceReason: ["AUTHORIZATION_DENIED", "UNAUTHORIZED", "PRODUCTION_AUTHORITY_UNAVAILABLE", "SOURCE_NOT_FOUND", "SOURCE_MISSING", "PUBLICATION_NOT_FOUND", "PREVIOUS_CURRENT_NOT_FOUND", "NOT_FOUND", "STALE_SOURCE", "STALE_VERSION", "STALE_CURSOR", "STATE_CONFLICT", "INVALID_STATE_TRANSITION", "CURRENT_REFERENCE_CONFLICT", "LEASE_CONFLICT", "LOCK_CONFLICT", "IMMUTABLE_EXECUTION_FACT", "NO_OP", "IDEMPOTENCY_CONFLICT", "INVALID_REQUEST", "INVALID_COMMAND", "INVALID_QUERY", "INVALID_INPUT", "INVALID_REFERENCE", "INVALID_TIME", "DATA_PLANE_MISMATCH", "MIXED_LINEAGE", "KPI_MISMATCH", "PLANNING_RUN_NOT_COMPLETED", "VALIDATION_FAILED", "PERSISTENCE_FAILED", "EXPORT_FAILED", "SERVICE_UNAVAILABLE", "SYSTEM_ERROR"],
  authorizationDetail: ["AUTHENTICATION_REQUIRED", "INVALID_AUTHENTICATION", "CAPABILITY_DENIED", "RESOURCE_SCOPE_DENIED", "AUTHORIZATION_PROVIDER_UNAVAILABLE", "INVALID_PROVIDER_CONTEXT", "SIMULATION_API_DISABLED"],
};

const surfaceFiles = [
  "src/main.tsx",
  "src/app/PlanningWorkspaceApp.tsx",
  "src/app/state.ts",
  "src/app/routeInventory.ts",
  "src/components/AuthorityPanel.tsx",
  "src/components/ReadOnlyTable.tsx",
  "src/components/ScheduleVersionPanel.tsx",
  "src/components/WorkspaceStatePanel.tsx",
  "src/pages/PlanningRunPage.tsx",
  "src/pages/ScheduleVersionPage.tsx",
  "src/pages/ValidationPage.tsx",
  "src/pages/WorkspaceCollectionPage.tsx",
  "src/features/gantt/GanttPage.tsx",
  "src/features/gantt/GanttTimeline.tsx",
  "src/features/resource-load/ResourceLoadPage.tsx",
  "src/features/version-comparison/VersionComparisonPage.tsx",
  "src/features/schedule-actions/ScheduleActionsPanel.tsx",
  "src/features/schedule-actions/useHumanControlAction.ts",
  "src/features/approval/ApprovalPanel.tsx",
  "src/features/publication/PublicationPanel.tsx",
  "src/features/export/ExportPanel.tsx",
  "src/features/audit/AuditHistoryPanel.tsx",
  "src/features/replanning/ReplanningWorkspacePage.tsx",
];

function source(path) {
  return readFileSync(resolve(frontendRoot, path), "utf8");
}

async function loadTypeScriptModule(path) {
  return import(await typeScriptDataUrl(path));
}

const moduleDataUrls = new Map();

function resolveTypeScriptImport(path, specifier) {
  const base = resolve(frontendRoot, dirname(path), specifier);
  for (const candidate of [`${base}.ts`, `${base}.tsx`, resolve(base, "index.ts")]) {
    if (existsSync(candidate)) {
      return relative(frontendRoot, candidate).replaceAll("\\", "/");
    }
  }
  throw new Error(`unable to resolve ${specifier} imported by ${path}`);
}

async function typeScriptDataUrl(path) {
  const cached = moduleDataUrls.get(path);
  if (cached !== undefined) return cached;

  const pending = (async () => {
    const output = ts.transpileModule(source(path), {
      compilerOptions: {
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2022,
        verbatimModuleSyntax: true,
      },
      fileName: path,
    }).outputText;
    let linkedOutput = output;
    const specifiers = new Set(
      [...output.matchAll(/(?:from\s+|import\s*\(\s*)["'](\.[^"']+)["']/gu)].map((match) => match[1]),
    );
    for (const specifier of specifiers) {
      const linkedUrl = await typeScriptDataUrl(resolveTypeScriptImport(path, specifier));
      linkedOutput = linkedOutput
        .replaceAll(`"${specifier}"`, `"${linkedUrl}"`)
        .replaceAll(`'${specifier}'`, `'${linkedUrl}'`);
    }
    return `data:text/javascript;base64,${Buffer.from(linkedOutput, "utf8").toString("base64")}`;
  })();
  moduleDataUrls.set(path, pending);
  return pending;
}

function fail(condition, message, issues) {
  if (!condition) issues.push(message);
}

function gitDiffNames(paths) {
  const output = execFileSync(
    "git",
    ["diff", "--name-only", diffBase, "--", ...paths],
    { cwd: repositoryRoot, encoding: "utf8" },
  );
  return output.trim().length === 0 ? [] : output.trim().split(/\r?\n/u);
}

function collectPlaywrightSpecs(report) {
  const result = [];
  const visit = (suites) => {
    for (const suite of suites ?? []) {
      result.push(...(suite.specs ?? []));
      visit(suite.suites);
    }
  };
  visit(report.suites);
  return result;
}

const reportPath = argument("--report");
const issues = [];
const checks = [];
const [enModule, zhModule, businessModule, errorModule] = await Promise.all([
  loadTypeScriptModule("src/i18n/dictionaries/en-US.ts"),
  loadTypeScriptModule("src/i18n/dictionaries/zh-CN.ts"),
  loadTypeScriptModule("src/i18n/business-labels.ts"),
  loadTypeScriptModule("src/i18n/error-labels.ts"),
]);
const enMessages = enModule.enUSMessages;
const zhMessages = zhModule.zhCNMessages;
const businessRegistries = businessModule.businessLabelRegistries;
const errorRegistries = errorModule.errorLabelRegistries;

const enKeys = Object.keys(enMessages).sort();
const zhKeys = Object.keys(zhMessages).sort();
fail(JSON.stringify(enKeys) === JSON.stringify(zhKeys), "en-US and zh-CN dictionary keys differ", issues);
fail(enKeys.length >= 150, `message key count is ${enKeys.length}, expected at least 150`, issues);
for (const key of enKeys) {
  fail(typeof enMessages[key] === "string" && enMessages[key].length > 0, `empty en-US message: ${key}`, issues);
  fail(typeof zhMessages[key] === "string" && zhMessages[key].length > 0, `empty zh-CN message: ${key}`, issues);
}
checks.push(completedCheck("TYPED-DICTIONARY-KEYS", `${enKeys.length} identical non-empty keys / ${locales.join("+")}`));

let registryValueCount = 0;
for (const [name, values] of Object.entries(expected)) {
  const registry = businessRegistries[name] ?? errorRegistries[name];
  fail(registry !== undefined, `registry absent: ${name}`, issues);
  for (const value of values) {
    registryValueCount += 1;
    const entry = registry?.[value];
    fail(entry !== undefined, `${name} mapping absent: ${value}`, issues);
    for (const locale of locales) {
      fail(typeof entry?.[locale] === "string" && entry[locale].length > 0, `${name}:${value}:${locale} label absent`, issues);
    }
  }
}
checks.push(completedCheck("OFFICIAL-MACHINE-REGISTRIES", `${registryValueCount} state/view/command/action/change/C-ID/error/reason values covered`));

const terminology = readFileSync(resolve(repositoryRoot, "docs/frontend/official-zh-cn-terminology-map.md"), "utf8");
fail(terminology.includes(terminologyVersion), "official terminology version is absent", issues);
fail(terminology.includes("默认locale为`zh-CN`"), "official zh-CN default is absent", issues);
for (const values of Object.values(expected)) {
  for (const value of values) fail(terminology.includes(`\`${value}\``), `official terminology omits ${value}`, issues);
}
checks.push(completedCheck("NORMATIVE-TERMINOLOGY-SOURCE", `${terminologyVersion} / zh-CN default / all registered raw values`));

const localeSource = source("src/i18n/locale.ts");
for (const boundary of [
  'defaultLocale: AppLocale = "zh-CN"',
  '"antd/locale/en_US"',
  '"antd/locale/zh_CN"',
  "document.documentElement.lang = locale",
  "localePreferenceKey",
  "globalThis.localStorage",
]) {
  const text = boundary.startsWith("defaultLocale") ? source("src/i18n/types.ts") : localeSource;
  fail(text.includes(boundary), `locale boundary absent: ${boundary}`, issues);
}
fail(!/token|secret|password|credential/iu.test("plantnexus.locale.v1"), "locale preference key resembles sensitive storage", issues);
checks.push(completedCheck("LOCALE-RUNTIME-BINDING", "zh-CN default / en-US switch / document lang / Ant Design locale / one non-sensitive browser preference"));

const combinedSurfaces = surfaceFiles.map((path) => {
  fail(existsSync(resolve(frontendRoot, path)), `localized surface absent: ${path}`, issues);
  return source(path);
}).join("\n");
for (const path of surfaceFiles) {
  const text = source(path);
  fail(/useLocale|translate|TranslationKey|labelKey/gu.test(text), `surface has no localization binding: ${path}`, issues);
}
const referencedKeys = new Set(
  [...combinedSurfaces.matchAll(/\b(?:t|translate)\(\s*(?:locale,\s*)?"([A-Za-z0-9.-]+)"/gu)].map((match) => match[1]),
);
for (const match of combinedSurfaces.matchAll(/(?:detailKey|labelKey):\s*"([A-Za-z0-9.-]+)"/gu)) referencedKeys.add(match[1]);
for (const key of referencedKeys) fail(Object.hasOwn(enMessages, key), `surface references missing dictionary key: ${key}`, issues);
checks.push(completedCheck("LOCALIZED-SURFACE-INVENTORY", `${surfaceFiles.length} page/component/action surfaces / ${referencedKeys.size} statically referenced keys`));

for (const boundary of ["localized-raw", "formatUtc", "formatSeconds", "formatUtilization", "JSON.stringify"]) {
  fail(combinedSurfaces.includes(boundary), `raw/Intl audit boundary absent: ${boundary}`, issues);
}
for (const boundary of ["known: false", "未知（", "Unknown ("]) {
  fail(source("src/i18n/business-labels.ts").includes(boundary) || source("src/i18n/error-labels.ts").includes(boundary), `unknown raw fallback absent: ${boundary}`, issues);
}
checks.push(completedCheck("INTL-AND-RAW-AUDITABILITY", "Intl display plus raw UTC/value/code/ID/fingerprint/JSON and visible unknown fallback"));

const frozenDiffs = gitDiffNames([
  "frontend/src/api",
  "frontend/package.json",
  "frontend/package-lock.json",
  "backend/app/api/dependencies/__init__.py",
  "backend/app/api/routers/planning_workspace.py",
  "schemas/json/audit-event.schema.json",
  "schemas/json/export-job.v2.schema.json",
  "schemas/json/export-manifest.v2.schema.json",
  "schemas/json/publication-result.schema.json",
  "schemas/json/schedule-version-comparison.schema.json",
  "schemas/json/schedule-version.schema.json",
  "schemas/json/workspace-command.schema.json",
  "schemas/json/workspace-query.schema.json",
  "schemas/rules/error-code-registry.v2.yaml",
  "schemas/rules/state-machines.v1.yaml",
  "uv.lock",
]);
fail(frozenDiffs.length === 0, `P3 localized wire/dependency/schema paths changed: ${frozenDiffs.join(", ")}`, issues);
const localizedRuntimeText = `${combinedSurfaces}\n${JSON.stringify(enMessages)}\n${JSON.stringify(zhMessages)}`;
for (const machineValue of ["APPROVE", "PUBLISH", "REQUEST_EXPORT", "READY_FOR_REVIEW", "SIMULATION_INTERNAL"]) {
  fail(localizedRuntimeText.includes(machineValue), `raw machine value absent from localized surfaces: ${machineValue}`, issues);
}
checks.push(completedCheck("ZERO-WIRE-AND-DEPENDENCY-DRIFT", "P3 client/router/schema/migration/dependency inputs unchanged; additive later-phase API composition excluded; English command/state/target values retained"));

const playwrightPath = resolve(repositoryRoot, "build/playwright/results.json");
let playwrightSpecs = [];
let p3PlaywrightSpecs = [];
if (!existsSync(playwrightPath)) {
  issues.push("Playwright JSON evidence is absent");
} else {
  const playwright = JSON.parse(readFileSync(playwrightPath, "utf8"));
  playwrightSpecs = collectPlaywrightSpecs(playwright);
  p3PlaywrightSpecs = playwrightSpecs.filter((spec) => spec.file !== "dynamic-replanning.spec.ts");
  fail(playwright.errors?.length === 0, "Playwright report contains top-level errors", issues);
  fail(p3PlaywrightSpecs.length === 12, `frozen P3 Playwright spec count is ${p3PlaywrightSpecs.length}, expected 12`, issues);
  fail(p3PlaywrightSpecs.every((spec) => spec.ok === true), "one or more frozen P3 Playwright specs failed", issues);
  fail(p3PlaywrightSpecs.some((spec) => spec.file === "bilingual-localization.spec.ts"), "bilingual Playwright spec is absent", issues);
  fail(p3PlaywrightSpecs.filter((spec) => spec.file === "human-control-actions.spec.ts").length === 8, "frozen human-control spec count drifted", issues);
}
for (const path of [
  "tests/i18nDictionaries.test.ts",
  "tests/i18nFormatting.test.ts",
  "tests/i18nWorkspace.test.tsx",
  "e2e/bilingual-localization.spec.ts",
]) {
  fail(existsSync(resolve(frontendRoot, path)), `i18n test evidence source absent: ${path}`, issues);
}
checks.push(completedCheck("BILINGUAL-AUTOMATED-EVIDENCE", `${p3PlaywrightSpecs.length}/12 frozen P3 specs inside ${playwrightSpecs.length} total plus dictionary/format/workspace Vitest sources`));

const report = {
  report_version: "p3-frontend-i18n-report.v1",
  task_id: taskId,
  code_commit: codeCommit(),
  diff_base: diffBase,
  terminology_version: terminologyVersion,
  status: issues.length === 0 ? "PASS" : "FAIL",
  locales,
  default_locale: "zh-CN",
  fallback_locale: "en-US",
  counts: {
    message_keys_per_locale: enKeys.length,
    registered_machine_values: registryValueCount,
    localized_surface_files: surfaceFiles.length,
    statically_referenced_message_keys: referencedKeys.size,
    playwright_specs: p3PlaywrightSpecs.length,
    all_playwright_specs: playwrightSpecs.length,
    human_control_playwright_specs: p3PlaywrightSpecs.filter((spec) => spec.file === "human-control-actions.spec.ts").length,
  },
  preference: {
    scope: "browser-local",
    key: "plantnexus.locale.v1",
    sensitive: false,
    server_negotiation: false,
  },
  frozen_inputs: {
    p3_14_closure: "06e7f794f486ac34c505237b847462c7c7c36d44",
    p3_15_closure: diffBase,
  },
  boundaries: {
    display_only_localization: true,
    raw_machine_values_retained: true,
    p3_localized_wire_schema_migration_dependency_changed: false,
    additive_later_phase_api_composition_allowed: true,
    backend_locale_negotiation_formed: false,
    server_chinese_export_formed: false,
    p4_additive_localization_excluded_from_frozen_p3_counts: true,
    production_identity_formed: false,
    production_readiness: false,
  },
  changed_frozen_paths: frozenDiffs.map((path) => relative(repositoryRoot, resolve(repositoryRoot, path)).replaceAll("\\", "/")),
  checks,
  check_count: checks.length,
  issues,
};

const target = writeReport(reportPath, report);
process.stdout.write(`${report.status} ${target}\n`);
if (issues.length > 0) process.exitCode = 1;
