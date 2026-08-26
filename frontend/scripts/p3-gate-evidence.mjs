import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { relative, resolve } from "node:path";

import { argument, codeCommit, completedCheck, writeReport } from "./report-utils.mjs";

const reportVersion = "p3-frontend-gate-report.v1";
const taskId = "TASK-P3-14";
const diffBase = "6a3e02f00bf46f19915cb59c3c4af7daaac95be4";
const projectionVersion = "p3-playwright-semantic-projection.v1";
const expectedProject = "chromium-p3-human-control";
const expectedCheckIds = [
  "frozen-human-control-report",
  "two-complete-chromium-replays",
  "json-junit-html-and-failure-retention",
  "stable-browser-semantic-projection",
  "phase-boundary",
];
const boundaries = {
  browser_runtime: "CHROMIUM",
  data_plane: "SIMULATION_ONLY",
  mock_transport: true,
  failure_media_policy: "RETAIN_ON_FAILURE",
  p3_15_exit_gate_audit: "NOT_PERFORMED",
  p4: "NOT_STARTED",
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
  const root = `../build/playwright/p3-gate/replay-${index}`;
  const jsonPath = `${root}/results.json`;
  const junitPath = `${root}/results.xml`;
  const htmlPath = `${root}/html/index.html`;
  const report = JSON.parse(readFileSync(jsonPath, "utf8"));
  const specs = collectSpecs(report);
  const controlSpecs = specs.filter((spec) => spec.file === "human-control-actions.spec.ts");
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
  if (!allPassed || specs.length !== 12 || controlSpecs.length !== 8) {
    throw new Error("Playwright replay did not preserve the 12/8 PASS contract");
  }
  const junit = junitCounts(readFileSync(junitPath, "utf8"));
  if (junit.tests !== 12 || junit.failures !== 0 || junit.skipped !== 0 || junit.errors !== 0) {
    throw new Error("Playwright JUnit counts did not preserve the 12/0/0/0 contract");
  }
  const semanticProjection = {
    projection_version: projectionVersion,
    project_name: expectedProject,
    spec_count: specs.length,
    human_control_spec_count: controlSpecs.length,
    specs,
  };
  return {
    replay_index: index,
    status: "PASS",
    project_name: expectedProject,
    spec_count: specs.length,
    human_control_spec_count: controlSpecs.length,
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
const humanControlPath = argument("--human-control-report");
let report;

try {
  const human = JSON.parse(readFileSync(humanControlPath, "utf8"));
  if (
    human.report_version !== "p3-frontend-human-control-report.v1" ||
    human.task_id !== "TASK-P3-13" ||
    human.code_commit !== codeCommit() ||
    human.status !== "PASS" ||
    human.browser_spec_count !== 12 ||
    human.human_control_browser_spec_count !== 8 ||
    human.issues?.length !== 0
  ) {
    throw new Error("frozen TASK-P3-13 frontend evidence is invalid");
  }
  const replays = [replayEvidence(1), replayEvidence(2)];
  const fingerprints = replays.map((replay) => replay.semantic_fingerprint);
  if (new Set(fingerprints).size !== 1) {
    throw new Error("Playwright business semantics changed across Gate replays");
  }
  const checks = [
    completedCheck("frozen-human-control-report", "TASK-P3-13 report PASS / exact SHA / 12 specs / 8 controls"),
    completedCheck("two-complete-chromium-replays", "2 fresh isolated replays / 24 spec executions"),
    completedCheck("json-junit-html-and-failure-retention", "raw JSON/JUnit/HTML retained; trace/video/screenshot retained on failure"),
    completedCheck("stable-browser-semantic-projection", `${projectionVersion} / 1 unique fingerprint`),
    completedCheck("phase-boundary", "P3 Gate only; Exit/P4/Production not started"),
  ];
  if (checks.map((check) => check.id).join("|") !== expectedCheckIds.join("|")) {
    throw new Error("frontend Gate check order changed");
  }
  report = {
    report_version: reportVersion,
    task_id: taskId,
    code_commit: codeCommit(),
    diff_base: diffBase,
    status: "PASS",
    repeat_count: replays.length,
    playwright_contract_version: projectionVersion,
    human_control_report: {
      path: repoPath(humanControlPath),
      sha256: sha256Bytes(readFileSync(humanControlPath)),
      report_version: human.report_version,
      task_id: human.task_id,
      code_commit: human.code_commit,
      diff_base: human.diff_base,
      status: human.status,
      browser_spec_count: human.browser_spec_count,
      human_control_browser_spec_count: human.human_control_browser_spec_count,
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
    issues: [{ issue_id: "P3-FRONTEND-GATE-EXECUTION-001", error_type: error?.constructor?.name ?? "Error" }],
    blocking_gaps: [
      {
        gap_id: "P3-FRONTEND-GATE-EXECUTION-001",
        stage: "frontend-gate-orchestrator",
        status: "BLOCKING",
        remediation: "REQUIRES_SEPARATE_BOUNDED_TASK",
      },
    ],
    boundaries,
  };
}

const written = writeReport(target, report);
process.stdout.write(`${report.status} ${written}\n`);
if (report.status !== "PASS") process.exitCode = 1;
