import { createHash } from "node:crypto";

import { expect, test, type Page, type Route } from "@playwright/test";

const baseVersionId = "schedule-version-e2e-001";
const comparedVersionId = "schedule-version-e2e-002";
const syntheticSegmentCount = 120;
const fingerprint = (digit: string) => `sha256:${digit.repeat(64)}`;

function canonical(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`).join(",")}}`;
}

function sha(value: unknown): string {
  return `sha256:${createHash("sha256").update(canonical(value)).digest("hex")}`;
}

function version(id: string) {
  const compared = id === comparedVersionId;
  return {
    schedule_version_version: "schedule-version.v1",
    schema_set_version: "2.6.0",
    canonicalization_version: "canonical-json.v1",
    schedule_version_id: id,
    revision: compared ? 2 : 1,
    state: compared ? "READY_FOR_REVIEW" : "DRAFT",
    data_plane: "PRODUCTION",
    environment: "PRODUCTION",
    synthetic: false,
    parent_schedule_version: null,
    source_kind: "VALIDATED_SOLUTION",
    lineage: {
      planning_run_id: "planning-run-e2e-001",
      snapshot: { document_version: "planning-snapshot.v2", artifact_id: "snapshot-e2e-001", fingerprint: fingerprint("1") },
      problem: { document_version: "planning-problem.v2", artifact_id: "problem-e2e-001", fingerprint: fingerprint("2") },
      planning_solution: { document_version: "planning-solution.v1", artifact_id: "solution-e2e-001", fingerprint: fingerprint("3") },
      validation_report: { document_version: "validation-report.v2", artifact_id: "validation-e2e-001", fingerprint: fingerprint("4") },
      kpi: { document_version: "kpi.v2", artifact_id: "kpi-e2e-001", fingerprint: fingerprint("5") },
      solver_report: { document_version: "solver-report.v1", artifact_id: "solver-e2e-001", fingerprint: fingerprint("6") },
      code_commit: "3bca1cc10ebedc4d47227bafb2f3f66854ccb526",
    },
    content: { assignments: [], locks: [] },
    content_fingerprint: compared ? fingerprint("b") : fingerprint("a"),
    validation: { status: "PASS", hard_violation_count: 0, validated_at_utc: "2026-08-25T00:00:00Z" },
    decision: null,
    publication: null,
    superseded_by: null,
    allowed_actions: ["view"],
    created_at_utc: compared ? "2026-08-25T00:02:00Z" : "2026-08-25T00:01:00Z",
    created_by_actor_ref: "actor:e2e-reader",
  };
}

function ganttPayload(index: number) {
  const start = new Date(Date.UTC(2026, 7, 25, 0, index * 5));
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  return {
    operation_id: `operation-e2e-${String(index + 1).padStart(3, "0")}`,
    order_id: `order-e2e-${Math.floor(index / 4) + 1}`,
    resource_id: `resource-e2e-${(index % 6) + 1}`,
    resource_code: `M-${(index % 6) + 1}`,
    factory_id: "factory-e2e-1",
    workshop_id: `workshop-e2e-${(index % 2) + 1}`,
    production_line_id: null,
    resource_group_id: "group-e2e-1",
    start_at_utc: start.toISOString().replace(".000Z", "Z"),
    end_at_utc: end.toISOString().replace(".000Z", "Z"),
    duration_seconds: 3600,
    start_tick: index * 5,
    end_tick: index * 5 + 60,
    lock_ids: [],
    execution_fact_ids: [],
  };
}

const loadPayload = {
  resource_id: "resource-e2e-1",
  resource_code: "M-1",
  calendar_id: "calendar-e2e-1",
  start_at_utc: "2026-08-25T00:00:00Z",
  end_at_utc: "2026-08-26T00:00:00Z",
  bucket_kind: "PLANNING_HORIZON",
  assignment_count: 12,
  planned_busy_seconds: 43200,
  available_seconds: 57600,
  utilization: 0.75,
};

function comparisonPayload() {
  return {
    schedule_version_comparison_version: "schedule-version-comparison.v1",
    schema_set_version: "2.6.0",
    canonicalization_version: "canonical-json.v1",
    comparison_id: "comparison-e2e-001",
    data_plane: "PRODUCTION",
    environment: "PRODUCTION",
    synthetic: false,
    base_version: { schedule_version_id: baseVersionId, state: "DRAFT", content_fingerprint: fingerprint("a") },
    compared_version: { schedule_version_id: comparedVersionId, state: "READY_FOR_REVIEW", content_fingerprint: fingerprint("b") },
    query_fingerprint: fingerprint("c"),
    operation_deltas: [
      { operation_id: "operation-e2e-001", change_kind: "START_SHIFT", base_resource_id: "resource-e2e-1", compared_resource_id: "resource-e2e-1", base_start_at_utc: "2026-08-25T00:00:00Z", compared_start_at_utc: "2026-08-25T00:30:00Z", base_end_at_utc: "2026-08-25T01:00:00Z", compared_end_at_utc: "2026-08-25T01:30:00Z" },
      { operation_id: "operation-e2e-002", change_kind: "UNCHANGED", base_resource_id: "resource-e2e-2", compared_resource_id: "resource-e2e-2", base_start_at_utc: "2026-08-25T01:00:00Z", compared_start_at_utc: "2026-08-25T01:00:00Z", base_end_at_utc: "2026-08-25T02:00:00Z", compared_end_at_utc: "2026-08-25T02:00:00Z" },
    ],
    kpi_deltas: [{ metric: "WEIGHTED_TARDINESS", base_value: 10, compared_value: 5, delta: -5 }],
    summary: { operation_count: 2, changed_operation_count: 1, added_operation_count: 0, removed_operation_count: 0, resource_changed_count: 0 },
    comparison_fingerprint: fingerprint("d"),
    generated_at_utc: "2026-08-25T03:04:05Z",
  };
}

function resultResponse(query: Record<string, unknown>, view: string, payloads: unknown[]) {
  const itemType = view === "GANTT" ? "GANTT_SEGMENT" : view === "RESOURCE_LOAD" ? "RESOURCE_LOAD" : view === "DIAGNOSTICS" ? "DIAGNOSTIC" : view;
  const items = payloads.map((payload, index) => ({
    item_id: `${view.toLowerCase()}-e2e-${index + 1}`,
    item_type: itemType,
    payload,
    payload_fingerprint: sha(payload),
  }));
  const references = items.map(({ item_id, item_type, payload_fingerprint }) => ({ item_id, item_type, payload_fingerprint }));
  const base = version(baseVersionId);
  return {
    document: {
      ...query,
      direction: "RESULT",
      result: {
        result_version: "workspace-query-result.v1",
        found: true,
        authoritative_schedule_version: { schedule_version_id: base.schedule_version_id, state: base.state, content_fingerprint: base.content_fingerprint },
        lineage: base.lineage,
        items: references,
        next_cursor: null,
        observed_count: items.length,
        allowed_actions: [],
        freshness: "FRESH",
        generated_at_utc: "2026-08-25T03:04:05Z",
      },
    },
    items,
    collection_fingerprint: sha({ items: references }),
    source_fingerprint: fingerprint("e"),
    correlation_id: query.correlation_id,
  };
}

interface MockObservation {
  ganttFilters: Record<string, unknown> | null;
  comparison: { method: string; idempotency: string | null; queryKind: unknown } | null;
}

async function mockApi(page: Page, options: { denyGantt?: boolean } = {}) {
  const observation: MockObservation = { ganttFilters: null, comparison: null };
  await page.route("**/api/v1/**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const versionMatch = url.pathname.match(/\/schedule-versions\/([^/]+)$/u);
    if (request.method() === "GET" && versionMatch !== null) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(version(decodeURIComponent(versionMatch[1] ?? ""))) });
      return;
    }
    if (url.pathname.endsWith("/schedule-version-comparisons")) {
      const query = request.postDataJSON() as Record<string, unknown>;
      observation.comparison = { method: request.method(), idempotency: request.headers()["idempotency-key"] ?? null, queryKind: query.query_kind };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(resultResponse(query, "VERSION_COMPARISON", [comparisonPayload()])) });
      return;
    }
    const viewMatch = url.pathname.match(/\/workspace\/([^/]+)$/u);
    if (request.method() === "GET" && viewMatch !== null) {
      const view = decodeURIComponent(viewMatch[1] ?? "");
      const query = JSON.parse(url.searchParams.get("query") ?? "{}") as Record<string, unknown>;
      if (view === "GANTT") {
        observation.ganttFilters = query.filters as Record<string, unknown>;
        if (options.denyGantt) {
          await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ message: "view capability denied", correlation_id: query.correlation_id }) });
          return;
        }
      }
      const payloads = view === "GANTT"
        ? Array.from({ length: syntheticSegmentCount }, (_, index) => ganttPayload(index))
        : view === "RESOURCE_LOAD"
          ? [loadPayload]
          : view === "KPI"
            ? [{ kpi_id: "kpi-e2e-001", delivery: { late_order_count: 0 } }]
            : [{ diagnostic_source: "VALIDATION_REPORT", status: "PASS" }];
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(resultResponse(query, view, payloads)) });
      return;
    }
    await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ message: "unmocked read path" }) });
  });
  return observation;
}

test("virtualizes 120 Gantt rows, exposes the table fallback and sends server filters", async ({ page }) => {
  const observation = await mockApi(page);
  await page.goto(`/planning/versions/${baseVersionId}/gantt/factory`);
  const viewport = page.getByTestId("gantt-viewport");
  await expect(viewport).toHaveAttribute("data-total-row-count", "120");
  const rendered = Number(await viewport.getAttribute("data-rendered-row-count"));
  expect(rendered).toBeLessThanOrEqual(24);
  await page.getByText("Accessible table view (120 operations)").click();
  await expect(page.getByRole("button", { name: "operation-e2e-120" })).toBeVisible();
  await page.getByLabel("Order ID").fill("order-e2e-2");
  await page.getByRole("button", { name: "Apply server filters" }).click();
  await expect.poll(() => observation.ganttFilters?.order_ids).toEqual(["order-e2e-2"]);
});

test("links Resource Load facts back to a resource-filtered machine Gantt", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/resource-load?schedule_version_id=${baseVersionId}&resource_id=resource-e2e-1`);
  await expect(page.getByText("43200")).toBeVisible();
  await expect(page.locator("output").getByText("0.75", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Machine Gantt" })).toHaveAttribute("href", /resource_id=resource-e2e-1/u);
});

test("uses a comparison read-query without idempotency or client delta classification", async ({ page }) => {
  const observation = await mockApi(page);
  await page.goto(`/compare?schedule_version_id=${baseVersionId}&compared_schedule_version_id=${comparedVersionId}`);
  const deltaTable = page.getByRole("table", { name: /Server-classified operation changes/u });
  await expect(deltaTable.getByText("START_SHIFT", { exact: true })).toBeVisible();
  await expect(deltaTable.getByText("UNCHANGED", { exact: true })).toHaveCount(0);
  await page.getByLabel("Operation delta visibility").getByText("Unchanged").click();
  await expect(deltaTable.getByText("UNCHANGED", { exact: true })).toBeVisible();
  expect(observation.comparison).toEqual({ method: "POST", idempotency: null, queryKind: "SCHEDULE_VERSION_COMPARISON" });
});

test("keeps authorization denial distinct from empty or ready data", async ({ page }) => {
  await mockApi(page, { denyGantt: true });
  await page.goto(`/planning/versions/${baseVersionId}/gantt/machines`);
  await expect(page.getByRole("alert")).toContainText("Authorization denied");
  await expect(page.getByText("view capability denied")).toBeVisible();
  await expect(page.getByTestId("gantt-viewport")).toHaveCount(0);
});
