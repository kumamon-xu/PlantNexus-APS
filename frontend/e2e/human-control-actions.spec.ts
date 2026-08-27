import { createHash } from "node:crypto";

import { expect, test, type Page, type Route } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    globalThis.localStorage.setItem("plantnexus.locale.v1", "en-US");
  });
});

const draftId = "schedule-version-e2e-control-draft";
const readyId = "schedule-version-e2e-control-ready";
const approvedId = "schedule-version-e2e-control-approved";
const publishedId = "schedule-version-e2e-control-published";
const exportJobId = `export-job-${"1".repeat(64)}`;
const packageId = `export-package-${"2".repeat(64)}`;
const fingerprint = (digit: string) => `sha256:${digit.repeat(64)}`;
const provenance = {
  scenario_id: "SIM-P3-HUMAN-CONTROL-001",
  scenario_version: "1.0.0",
  seed: 20260826,
  factory_profile_id: "PROFILE-P3-UI-E2E-001",
  profile_version: "1.0.0",
  generator_id: "PLANTNEXUS-P3-PLAYWRIGHT",
  generator_version: "1.0.0",
};

type VersionState =
  | "DRAFT"
  | "READY_FOR_REVIEW"
  | "APPROVED"
  | "PUBLISHED"
  | "SUPERSEDED"
  | "REJECTED";
type ExportState =
  | "CREATED"
  | "EXPORTING"
  | "EXPORTED"
  | "EXPORT_FAILED"
  | "CANCELLED";

function allowedActions(state: VersionState): string[] {
  if (state === "DRAFT") return ["view", "edit", "lock", "audit"];
  if (state === "READY_FOR_REVIEW") return ["view", "approve", "reject", "audit"];
  if (state === "APPROVED") return ["view", "publish", "audit"];
  if (state === "PUBLISHED") return ["view", "export", "audit"];
  return ["view", "audit"];
}

function lineage() {
  return {
    planning_run_id: "planning-run-p3-control-e2e",
    snapshot: {
      document_version: "planning-snapshot.v2",
      artifact_id: "snapshot-p3-control-e2e",
      fingerprint: fingerprint("1"),
    },
    problem: {
      document_version: "planning-problem.v2",
      artifact_id: "problem-p3-control-e2e",
      fingerprint: fingerprint("2"),
    },
    planning_solution: {
      document_version: "planning-solution.v1",
      artifact_id: "solution-p3-control-e2e",
      fingerprint: fingerprint("3"),
    },
    validation_report: {
      document_version: "validation-report.v2",
      artifact_id: "validation-p3-control-e2e",
      fingerprint: fingerprint("4"),
    },
    kpi: {
      document_version: "kpi.v2",
      artifact_id: "kpi-p3-control-e2e",
      fingerprint: fingerprint("5"),
    },
    solver_report: {
      document_version: "solver-report.v1",
      artifact_id: "solver-report-p3-control-e2e",
      fingerprint: fingerprint("6"),
    },
    code_commit: "3dacf83c0f0bf87a9fa673aa75d61f8ad8659386",
  };
}

function version(id: string, state: VersionState) {
  return {
    schedule_version_version: "schedule-version.v1",
    schema_set_version: "2.6.0",
    canonicalization_version: "canonical-json.v1",
    schedule_version_id: id,
    revision: 1,
    state,
    data_plane: "SIMULATION",
    environment: "TEST",
    synthetic: true,
    synthetic_provenance: provenance,
    parent_schedule_version: null,
    source_kind: "VALIDATED_SOLUTION",
    lineage: lineage(),
    content: { assignments: [], locks: [] },
    content_fingerprint: fingerprint(
      state === "DRAFT"
        ? "a"
        : state === "READY_FOR_REVIEW"
          ? "b"
          : state === "APPROVED"
            ? "c"
            : "d",
    ),
    validation: {
      status: "PASS",
      hard_violation_count: 0,
      validated_at_utc: "2026-08-26T00:00:00Z",
    },
    decision: null,
    publication: null,
    superseded_by: null,
    allowed_actions: allowedActions(state),
    created_at_utc: "2026-08-26T00:01:00Z",
    created_by_actor_ref: "actor:p3-e2e-synthetic-controller",
  };
}

function reference(document: ReturnType<typeof version>) {
  return {
    schedule_version_id: document.schedule_version_id,
    state: document.state,
    content_fingerprint: document.content_fingerprint,
  };
}

function ganttPayload() {
  return {
    operation_id: "operation-p3-control-e2e-001",
    order_id: "order-p3-control-e2e-001",
    resource_id: "resource-p3-control-e2e-001",
    resource_code: "M-P3-01",
    factory_id: "factory-p3-control-e2e",
    workshop_id: "workshop-p3-control-e2e",
    production_line_id: null,
    resource_group_id: "group-p3-control-e2e",
    start_at_utc: "2026-08-26T01:00:00Z",
    end_at_utc: "2026-08-26T02:00:00Z",
    duration_seconds: 3600,
    start_tick: 0,
    end_tick: 60,
    lock_ids: [],
    execution_fact_ids: [],
  };
}

function canonical(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`)
    .join(",")}}`;
}

function sha(value: unknown): string {
  return `sha256:${createHash("sha256").update(canonical(value)).digest("hex")}`;
}

function workspaceResponse(
  query: Record<string, unknown>,
  view: string,
  authority: ReturnType<typeof version>,
) {
  const payloads =
    view === "GANTT"
      ? [ganttPayload()]
      : view === "KPI"
        ? [{ kpi_id: "kpi-p3-control-e2e", delivery: { late_order_count: 0 } }]
        : view === "DIAGNOSTICS"
          ? [{ diagnostic_source: "VALIDATION_REPORT", status: "PASS" }]
          : [
              {
                audit_event_id: "audit-p3-control-e2e",
                correlation_id: "correlation-p3-control-e2e",
                actor_ref: "actor:p3-e2e-synthetic-controller",
              },
            ];
  const items = payloads.map((payload, index) => ({
    item_id: `${view.toLowerCase()}-p3-control-${index + 1}`,
    item_type: view === "GANTT" ? "GANTT_SEGMENT" : view,
    payload,
    payload_fingerprint: sha(payload),
  }));
  const references = items.map(({ item_id, item_type, payload_fingerprint }) => ({
    item_id,
    item_type,
    payload_fingerprint,
  }));
  return {
    document: {
      ...query,
      direction: "RESULT",
      result: {
        result_version: "workspace-query-result.v1",
        found: true,
        authoritative_schedule_version: reference(authority),
        lineage: authority.lineage,
        items: references,
        next_cursor: null,
        observed_count: items.length,
        allowed_actions: authority.allowed_actions,
        freshness: "FRESH",
        generated_at_utc: "2026-08-26T00:02:00Z",
      },
    },
    items,
    collection_fingerprint: sha({ items: references }),
    source_fingerprint: fingerprint("e"),
    correlation_id: query.correlation_id,
  };
}

function exportJob(state: ExportState, attempt: number) {
  return {
    export_job_version: "export-job.v2",
    schema_set_version: "2.7.0",
    canonicalization_version: "canonical-json.v1",
    export_job_id: exportJobId,
    state,
    schedule_version: reference(version(publishedId, "PUBLISHED")),
    data_plane: "SIMULATION",
    environment: "TEST",
    synthetic: true,
    synthetic_provenance: provenance,
    target: "SIMULATION_INTERNAL",
    package_profile: "p3-standard-export.v1",
    attempt,
    artifact_manifest:
      state === "EXPORTED"
        ? {
            export_manifest_version: "export-manifest.v2",
            package_id: packageId,
            manifest_fingerprint: fingerprint("7"),
            storage_reference: fingerprint("8"),
          }
        : null,
    latest_audit_event_id: `audit-export-${state.toLowerCase()}-${attempt}`,
    job_fingerprint: fingerprint("9"),
  };
}

interface CommandObservation {
  body: Record<string, unknown>;
  idempotency: string | null;
  correlation: string | null;
}

interface ControlMock {
  commands: CommandObservation[];
  setFailure(status: number | null): void;
  failNextNetwork(): void;
  setJobState(state: ExportState): void;
}

async function mockControlApi(page: Page): Promise<ControlMock> {
  const versions = new Map<string, ReturnType<typeof version>>([
    [draftId, version(draftId, "DRAFT")],
    [readyId, version(readyId, "READY_FOR_REVIEW")],
    [approvedId, version(approvedId, "APPROVED")],
    [publishedId, version(publishedId, "PUBLISHED")],
  ]);
  const commands: CommandObservation[] = [];
  let failureStatus: number | null = null;
  let networkFailure = false;
  let currentJob = exportJob("CREATED", 0);

  async function commandResponse(route: Route, sourceId: string) {
    const request = route.request();
    const body = request.postDataJSON() as Record<string, unknown>;
    commands.push({
      body,
      idempotency: request.headers()["idempotency-key"] ?? null,
      correlation: request.headers()["x-correlation-id"] ?? null,
    });
    if (networkFailure) {
      networkFailure = false;
      await route.abort("failed");
      return;
    }
    if (failureStatus !== null) {
      await route.fulfill({
        status: failureStatus,
        contentType: "application/json",
        body: JSON.stringify({
          message: `visible failure ${failureStatus}`,
          correlation_id: body.correlation_id,
        }),
      });
      return;
    }
    const commandType = String(body.command_type);
    if (commandType === "REQUEST_EXPORT") {
      currentJob = exportJob("CREATED", 0);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          document: currentJob,
          command_type: commandType,
          correlation_id: body.correlation_id,
          audit_event_id: currentJob.latest_audit_event_id,
          exact_replay: commands.filter(
            (item) => item.idempotency === request.headers()["idempotency-key"],
          ).length > 1,
        }),
      });
      return;
    }
    if (commandType === "RETRY_EXPORT") {
      currentJob = exportJob("EXPORTING", currentJob.attempt + 1);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          document: currentJob,
          command_type: commandType,
          correlation_id: body.correlation_id,
          audit_event_id: currentJob.latest_audit_event_id,
          exact_replay: false,
        }),
      });
      return;
    }
    const source = versions.get(sourceId) ?? version(sourceId, "DRAFT");
    let target = source;
    if (commandType === "MOVE_OPERATION" || commandType === "ASSIGN_RESOURCE" || commandType === "SET_LOCK") {
      target = {
        ...version("schedule-version-e2e-control-new-draft", "DRAFT"),
        parent_schedule_version: reference(source),
        content_fingerprint: fingerprint("f"),
      };
    } else if (commandType === "SUBMIT_FOR_REVIEW") {
      target = version("schedule-version-e2e-control-ready-new", "READY_FOR_REVIEW");
    } else if (commandType === "APPROVE") {
      target = { ...source, state: "APPROVED", allowed_actions: allowedActions("APPROVED") };
    } else if (commandType === "REJECT") {
      target = { ...source, state: "REJECTED", allowed_actions: allowedActions("REJECTED") };
    } else if (commandType === "PUBLISH") {
      target = { ...source, state: "PUBLISHED", allowed_actions: allowedActions("PUBLISHED") };
    }
    versions.set(target.schedule_version_id, target);
    const sameKeyCount = commands.filter(
      (item) => item.idempotency === request.headers()["idempotency-key"],
    ).length;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        command_type: commandType,
        source_version: reference(source),
        ...(commandType === "PUBLISH"
          ? { published_version: reference(target) }
          : { new_version: reference(target) }),
        audit_event_id: `audit-${commandType.toLowerCase()}-e2e`,
        correlation_id: body.correlation_id,
        exact_replay: sameKeyCount > 1,
      }),
    });
  }

  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const downloadMatch = url.pathname.match(/\/export-jobs\/([^/]+)\/download$/u);
    if (request.method() === "GET" && downloadMatch !== null) {
      const bytes = Buffer.from("p3 verified deterministic zip fixture", "utf8");
      const correlation = request.headers()["x-correlation-id"] ?? "missing";
      await route.fulfill({
        status: 200,
        body: bytes,
        headers: {
          "Content-Type": "application/zip",
          "Content-Length": String(bytes.byteLength),
          "Content-Disposition": `attachment; filename="${packageId}.zip"`,
          "X-PlantNexus-Package-Id": packageId,
          "X-PlantNexus-Manifest-Fingerprint": fingerprint("7"),
          "X-PlantNexus-Archive-Fingerprint": `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
          "X-PlantNexus-Completion-Audit-Event-Id": "audit-export-executed-e2e",
          "X-Correlation-Id": correlation,
        },
      });
      return;
    }
    const retryMatch = url.pathname.match(/\/export-jobs\/([^/]+)\/retry$/u);
    if (request.method() === "POST" && retryMatch !== null) {
      await commandResponse(route, decodeURIComponent(retryMatch[1] ?? ""));
      return;
    }
    const exportJobMatch = url.pathname.match(/\/export-jobs\/([^/]+)$/u);
    if (request.method() === "GET" && exportJobMatch !== null) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(currentJob),
      });
      return;
    }
    const versionMatch = url.pathname.match(/\/schedule-versions\/([^/]+)$/u);
    if (request.method() === "GET" && versionMatch !== null) {
      const id = decodeURIComponent(versionMatch[1] ?? "");
      const document = versions.get(id);
      await route.fulfill({
        status: document === undefined ? 404 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          document ?? { message: "unknown synthetic Version", correlation_id: "missing" },
        ),
      });
      return;
    }
    const scheduleCommandMatch = url.pathname.match(
      /\/schedule-versions\/([^/]+)\/(?:commands|validate|approve|reject|publish|exports)$/u,
    );
    if (request.method() === "POST" && scheduleCommandMatch !== null) {
      await commandResponse(
        route,
        decodeURIComponent(scheduleCommandMatch[1] ?? ""),
      );
      return;
    }
    const viewMatch = url.pathname.match(
      /\/schedule-versions\/([^/]+)\/workspace\/([^/]+)$/u,
    );
    if (request.method() === "GET" && viewMatch !== null) {
      const id = decodeURIComponent(viewMatch[1] ?? "");
      const view = decodeURIComponent(viewMatch[2] ?? "");
      const authority = versions.get(id) ?? version(id, "DRAFT");
      const query = JSON.parse(url.searchParams.get("query") ?? "{}") as Record<
        string,
        unknown
      >;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(workspaceResponse(query, view, authority)),
      });
      return;
    }
    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ message: "unmocked P3 control path" }),
    });
  });
  return {
    commands,
    setFailure(status) {
      failureStatus = status;
    },
    failNextNetwork() {
      networkFailure = true;
    },
    setJobState(state) {
      currentJob = exportJob(state, currentJob.attempt);
    },
  };
}

function assertCommandBinding(observation: CommandObservation) {
  expect(observation.idempotency).toBe(observation.body.idempotency_key);
  expect(observation.correlation).toBe(observation.body.correlation_id);
  expect(observation.body.data_plane).toBe("SIMULATION");
  expect(observation.body.environment).toBe("TEST");
  expect(observation.body.synthetic).toBe(true);
  expect(observation.body.synthetic_provenance).toEqual(provenance);
  expect(String(observation.body.request_fingerprint)).toMatch(/^sha256:[0-9a-f]{64}$/u);
  expect(JSON.stringify(observation.body)).not.toMatch(/bearer|password|secret|api[_-]?key/iu);
}

test("submits one DRAFT validation command and follows the authoritative Version", async ({ page }) => {
  const api = await mockControlApi(page);
  await page.goto(`/planning/versions/${draftId}`);
  await page.getByLabel("Submission reason").fill("Ready for human review");
  const submit = page.getByRole("button", { name: "Submit for review" });
  await submit.evaluate((button) => {
    button.click();
    button.click();
  });
  await expect(page).toHaveURL(/schedule-version-e2e-control-ready-new$/u);
  expect(api.commands).toHaveLength(1);
  expect(api.commands[0]?.body.command_type).toBe("SUBMIT_FOR_REVIEW");
  assertCommandBinding(api.commands[0]!);
  await page.goto(`/planning/versions/${readyId}`);
  await page.getByLabel("Decision reason").fill("Reject infeasible planner choice");
  await page.getByRole("button", { name: "Reject Version" }).click();
  await expect(page.getByText("REJECTED", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Approve Version|Publish internally|Request export/u })).toHaveCount(0);
  expect(api.commands.at(-1)?.body.command_type).toBe("REJECT");
});

test("moves a Gantt operation only through a new authoritative DRAFT", async ({ page }) => {
  const api = await mockControlApi(page);
  await page.goto(`/planning/versions/${draftId}/gantt/factory`);
  await page.getByText("Accessible table view (1 operations)").click();
  await page.getByRole("button", { name: "operation-p3-control-e2e-001" }).click();
  await page.getByLabel("Start UTC").fill("2026-08-26T01:30:00Z");
  await page.getByLabel("End UTC").fill("2026-08-26T02:30:00Z");
  await page.getByLabel("Change reason").fill("Move after planner review");
  await page.getByRole("button", { name: "Move selected operation" }).click();
  await expect(page).toHaveURL(/schedule-version-e2e-control-new-draft\/gantt\/factory$/u);
  const command = api.commands.at(-1);
  expect(command?.body.command_type).toBe("MOVE_OPERATION");
  expect(command?.body.payload).toMatchObject({
    operation_id: "operation-p3-control-e2e-001",
    start_at_utc: "2026-08-26T01:30:00Z",
  });
  assertCommandBinding(command!);
});

test("keeps 401, 403, 409, 422 and 500 failures visibly distinct from success", async ({ page }) => {
  const api = await mockControlApi(page);
  for (const status of [401, 403, 409, 422, 500]) {
    api.setFailure(status);
    await page.goto(`/planning/versions/${readyId}?failure=${status}`);
    await page.getByLabel("Decision reason").fill(`Review decision case ${status}`);
    await page.getByRole("button", { name: "Approve Version" }).click();
    if (status === 500) {
      await expect(page.getByText("Server outcome not assumed")).toBeVisible();
    } else {
      await expect(page.getByText(`visible failure ${status}`)).toBeVisible();
    }
    await expect(page.getByText(/Server confirmed/u)).toHaveCount(0);
  }
});

test("recovers an unknown network outcome only after refresh and with the same key", async ({ page }) => {
  const api = await mockControlApi(page);
  api.failNextNetwork();
  await page.goto(`/planning/versions/${readyId}`);
  await page.getByLabel("Decision reason").fill("Approve after authority refresh");
  await page.getByRole("button", { name: "Approve Version" }).click();
  await expect(page.getByText("Server outcome not assumed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry same request" })).toBeDisabled();
  await page.getByRole("button", { name: "Refresh authority" }).click();
  await expect(page.getByRole("button", { name: "Retry same request" })).toBeEnabled();
  await page.getByRole("button", { name: "Retry same request" }).click();
  await expect(page.getByText("APPROVED", { exact: true })).toBeVisible();
  expect(api.commands).toHaveLength(2);
  expect(api.commands[1]?.idempotency).toBe(api.commands[0]?.idempotency);
  expect(api.commands[1]?.body.command_id).toBe(api.commands[0]?.body.command_id);
  expect(api.commands[1]?.body.request_fingerprint).toBe(
    api.commands[0]?.body.request_fingerprint,
  );
});

test("requires an explicit non-Production publication confirmation", async ({ page }) => {
  const api = await mockControlApi(page);
  await page.goto(`/planning/versions/${approvedId}`);
  await page.getByRole("button", { name: "Review internal publication" }).click();
  const dialog = page.getByRole("dialog", { name: "Confirm SIMULATION_INTERNAL publication" });
  await dialog.getByLabel("Publication reason").fill("Publish approved synthetic plan");
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Publish internally" }).click();
  await expect(page.getByText("PUBLISHED", { exact: true })).toBeVisible();
  const command = api.commands.at(-1);
  expect(command?.body).toMatchObject({
    command_type: "PUBLISH",
    target: "SIMULATION_INTERNAL",
  });
  assertCommandBinding(command!);
});

test("shows ExportJob failure, explicitly retries, and downloads only verified EXPORTED bytes", async ({ page }) => {
  const api = await mockControlApi(page);
  await page.goto(`/planning/versions/${publishedId}`);
  await page.getByLabel("Export or retry reason").fill("Create synthetic handoff package");
  await page.getByRole("button", { name: "Request export" }).click();
  await expect(page.getByText("CREATED", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download verified package" })).toHaveCount(0);

  api.setJobState("EXPORT_FAILED");
  await page.getByRole("button", { name: "Refresh export job" }).click();
  await expect(page.getByText("EXPORT_FAILED", { exact: true })).toBeVisible();
  await page.getByLabel("Export or retry reason").fill("Retry visible synthetic worker failure");
  await page.getByRole("button", { name: "Retry failed export" }).click();
  await expect(page.getByText("EXPORTING", { exact: true })).toBeVisible();

  api.setJobState("EXPORTED");
  await page.getByRole("button", { name: "Refresh export job" }).click();
  await expect(page.getByText("EXPORTED", { exact: true })).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download verified package" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(`${packageId}.zip`);
  await expect(page.getByText("Verified package downloaded")).toBeVisible();
  expect(api.commands.map((item) => item.body.command_type)).toEqual([
    "REQUEST_EXPORT",
    "RETRY_EXPORT",
  ]);
});

test("keeps PUBLISHED Gantt immutable and links append-only audit history", async ({ page }) => {
  await mockControlApi(page);
  await page.goto(`/planning/versions/${publishedId}/gantt/machines`);
  await page.getByText("Accessible table view (1 operations)").click();
  await page.getByRole("button", { name: "operation-p3-control-e2e-001" }).click();
  await expect(page.getByText("Published history is immutable")).toBeVisible();
  await expect(page.getByRole("button", { name: /move|assign|lock/iu })).toHaveCount(0);
  await page.goto(`/planning/versions/${publishedId}`);
  await page.getByRole("link", { name: "Open audit history" }).click();
  await expect(page).toHaveURL(new RegExp(`/audit\\?schedule_version_id=${publishedId}$`, "u"));
  await expect(page.getByText(/audit-p3-control-e2e/u)).toBeVisible();
});

test("replays approve, internal publish and export request in zh-CN without wire drift", async ({ page }) => {
  const api = await mockControlApi(page);
  await page.goto(`/planning/versions/${readyId}`);
  await page.getByRole("combobox", { name: "Language" }).click();
  await page.getByText("简体中文", { exact: true }).click();
  await page.getByLabel("决定原因").fill("批准合成仿真计划");
  await page.getByRole("button", { name: "批准版本" }).click();
  await expect(page.getByText("APPROVED", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "审核内部发布" }).click();
  const dialog = page.getByRole("dialog", { name: "确认 SIMULATION_INTERNAL 发布" });
  await dialog.getByLabel("发布原因").fill("内部发布已批准仿真计划");
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "内部发布" }).click();
  await expect(page.getByText("PUBLISHED", { exact: true })).toBeVisible();

  await page.getByLabel("导出或重试原因").fill("创建已验证的合成成果包");
  await page.getByRole("button", { name: "请求导出" }).click();
  await expect(page.getByText("CREATED", { exact: true })).toBeVisible();
  expect(api.commands.map((item) => item.body.command_type)).toEqual([
    "APPROVE",
    "PUBLISH",
    "REQUEST_EXPORT",
  ]);
  for (const command of api.commands) assertCommandBinding(command);
});
