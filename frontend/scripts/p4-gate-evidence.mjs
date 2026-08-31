import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { relative, resolve } from "node:path";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const reportVersion = "p4-frontend-gate-report.v1";
const taskId = "TASK-P4-14";
const diffBase = "ea05c3d9e94af91ae4525e5fbf1087a4a4198a15";
const projectionVersion = "p4-playwright-semantic-projection.v1";
const expectedProject = "chromium-p4-vertical-slice";
const expectedCheckIds = [
  "frozen-p4-replanning-frontend-report",
  "two-complete-p4-chromium-replays",
  "json-junit-html-and-failure-retention",
  "stable-p4-browser-semantic-projection",
  "p4-gate-phase-boundary",
];
const boundaries = {
  browser_runtime: "CHROMIUM",
  data_plane: "SIMULATION_ONLY",
  mock_transport: true,
  failure_media_policy: "RETAIN_ON_FAILURE",
  p4_exit_gate_audit: "NOT_PERFORMED",
  p4_15: "NOT_STARTED",
  p5: "UNSUPPORTED",
  production_authority: "NOT_FORMED",
  production_readiness: "NOT_CLAIMED",
};

function sha256Bytes(bytes) {
  return `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
}

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

function sha256Json(value) {
  return sha256Bytes(Buffer.from(JSON.stringify(canonicalize(value)), "utf8"));
}

function repoPath(path) {
  return relative(resolve(process.cwd(), ".."), resolve(process.cwd(), path)).replaceAll("\\", "/");
}

function fileEvidence(path) {
  if (!existsSync(path)) throw new Error("required Playwright evidence is absent");
  return { path: repoPath(path), sha256: sha256Bytes(readFileSync(path)) };
}

function collectSpecs(report) {
  const specs = [];
  const visit = (suites, parents = []) => {
    for (const suite of suites ?? []) {
      const path = [...parents, suite.title];
      for (const spec of suite.specs ?? []) {
        const tests = (spec.tests ?? []).map((test) => ({
          project_name: test.projectName,
          expected_status: test.expectedStatus,
          status: test.status,
          result_statuses: (test.results ?? []).map((result) => result.status),
        }));
        specs.push({
          suite_path: path,
          file: spec.file,
          title: spec.title,
          line: spec.line,
          column: spec.column,
          ok: spec.ok,
          tests,
        });
      }
      visit(suite.suites, path);
    }
  };
  visit(report.suites);
  return specs;
}

function junitCounts(source) {
  const opening = source.match(/<testsuites\b[^>]*>/u)?.[0];
  if (!opening) throw new Error("Playwright JUnit root is absent");
  const value = (name) => Number(opening.match(new RegExp(`${name}="(\\d+)"`, "u"))?.[1] ?? "-1");
  return {
    tests: value("tests"),
    failures: value("failures"),
    skipped: value("skipped"),
    errors: value("errors"),
  };
}

function replayEvidence(index) {
  const root = `../build/playwright/p4-gate/replay-${index}`;
  const jsonPath = `${root}/results.json`;
  const junitPath = `${root}/results.xml`;
  const htmlPath = `${root}/html/index.html`;
  const report = JSON.parse(readFileSync(jsonPath, "utf8"));
  const specs = collectSpecs(report);
  const replanningSpecs = specs.filter((spec) => spec.file === "dynamic-replanning.spec.ts");
  const allPassed =
    report.errors?.length === 0 &&
    specs.every(
      (spec) =>
        spec.ok === true &&
        spec.tests.length > 0 &&
        spec.tests.every(
          (test) =>
            test.project_name === expectedProject &&
            test.expected_status === "passed" &&
            test.status === "expected" &&
            test.result_statuses.includes("passed"),
        ),
    );
  if (!allPassed || specs.length !== 5 || replanningSpecs.length !== 5) {
    throw new Error("Playwright replay did not preserve the 5/5 dynamic-replanning PASS contract");
  }
  const junit = junitCounts(readFileSync(junitPath, "utf8"));
  if (junit.tests !== 5 || junit.failures !== 0 || junit.skipped !== 0 || junit.errors !== 0) {
    throw new Error("Playwright JUnit counts did not preserve the 5/0/0/0 contract");
  }
  const semanticProjection = {
    projection_version: projectionVersion,
    project_name: expectedProject,
    spec_count: specs.length,
    dynamic_replanning_spec_count: replanningSpecs.length,
    specs,
  };
  return {
    replay_index: index,
    status: "PASS",
    project_name: expectedProject,
    spec_count: specs.length,
    dynamic_replanning_spec_count: replanningSpecs.length,
    raw_evidence: {
      json: fileEvidence(jsonPath),
      junit: fileEvidence(junitPath),
      html: fileEvidence(htmlPath),
    },
    semantic_projection: semanticProjection,
    semantic_fingerprint: sha256Json(semanticProjection),
  };
}

const target = argument("--report");
const replanningPath = argument("--replanning-report");
let report;

try {
  const replanningBytes = readFileSync(replanningPath);
  const replanning = JSON.parse(replanningBytes.toString("utf8"));
  if (
    replanning.report_version !== "p4-replanning-frontend-report.v1" ||
    replanning.task_id !== "TASK-P4-13" ||
    replanning.code_commit !== codeCommit() ||
    replanning.diff_base !== "be2389594f3e224de3f5a73f4b8b62ffcffb5b7b" ||
    replanning.status !== "PASS" ||
    replanning.check_count !== 8 ||
    replanning.counts?.p4_browser_specs !== 5 ||
    replanning.issues?.length !== 0
  ) {
    throw new Error("frozen TASK-P4-13 frontend evidence is invalid");
  }
  const replays = [replayEvidence(1), replayEvidence(2)];
  const fingerprints = replays.map((replay) => replay.semantic_fingerprint);
  if (new Set(fingerprints).size !== 1) {
    throw new Error("Playwright business semantics changed across P4 Gate replays");
  }
  const checks = [
    completedCheck("frozen-p4-replanning-frontend-report", "TASK-P4-13 report PASS / exact SHA / 8 checks / 5 P4 specs"),
    completedCheck("two-complete-p4-chromium-replays", "2 fresh isolated replays / 10 dynamic-replanning spec executions"),
    completedCheck("json-junit-html-and-failure-retention", "raw JSON/JUnit/HTML retained; trace/video/screenshot retained on failure"),
    completedCheck("stable-p4-browser-semantic-projection", `${projectionVersion} / 1 unique fingerprint`),
    completedCheck("p4-gate-phase-boundary", "P4 vertical-slice Gate only; Exit/P5/Production not started"),
  ];
  if (checks.map((check) => check.id).join("|") !== expectedCheckIds.join("|")) {
    throw new Error("P4 frontend Gate check order changed");
  }
  report = {
    report_version: reportVersion,
    task_id: taskId,
    code_commit: codeCommit(),
    diff_base: diffBase,
    status: "PASS",
    repeat_count: replays.length,
    playwright_contract_version: projectionVersion,
    replanning_report: {
      path: repoPath(replanningPath),
      sha256: sha256Bytes(replanningBytes),
      report_version: replanning.report_version,
      task_id: replanning.task_id,
      code_commit: replanning.code_commit,
      diff_base: replanning.diff_base,
      status: replanning.status,
      check_count: replanning.check_count,
      p4_browser_specs: replanning.counts.p4_browser_specs,
    },
    replays,
    hash_consistency: {
      projection_version: projectionVersion,
      status: "PASS",
      semantic_fingerprints: fingerprints,
      unique_semantic_fingerprints: new Set(fingerprints).size,
      raw_runtime_fields_excluded: ["duration", "startTime", "workerIndex", "parallelIndex", "attachments", "derived spec id"],
    },
    checks,
    check_count: checks.length,
    issues: [],
    blocking_gaps: [],
    boundaries,
  };
} catch (error) {
  report = {
    report_version: reportVersion,
    task_id: taskId,
    code_commit: codeCommit(),
    diff_base: diffBase,
    status: "FAIL",
    repeat_count: 2,
    issues: [{ issue_id: "P4-FRONTEND-GATE-EXECUTION-001", error_type: error?.constructor?.name ?? "Error" }],
    blocking_gaps: [
      {
        gap_id: "P4-FRONTEND-GATE-EXECUTION-001",
        stage: "frontend-gate-orchestrator",
        status: "BLOCKING",
        remediation: "REQUIRES_SEPARATE_BOUNDED_CORRECTIVE_COMMIT",
      },
    ],
    boundaries,
  };
}

const written = writeReport(target, report);
process.stdout.write(`${report.status} ${written}\n`);
if (report.status !== "PASS") process.exitCode = 1;
