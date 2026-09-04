import { describe, expect, it } from "vitest";

import {
  DemoContractError,
  parseBootstrap,
  parseComparisonView,
  parseFactoryView,
  parseJob,
  parseScheduleView,
  parseScheduleSummary,
  parseUrgentReplanResult,
} from "../src/api/contracts";
import {
  comparisonBootstrap,
  comparisonView,
  emptyBootstrap,
  factoryView,
  publishedBootstrap,
  runningPlanJob,
  scheduleView,
  scheduleSummary,
} from "./fixtures";

type Mutable<T> = T extends readonly (infer Item)[]
  ? Mutable<Item>[]
  : T extends object
    ? { -readonly [Key in keyof T]: Mutable<T[Key]> }
    : T;

function mutableClone<T>(value: T): Mutable<T> {
  return structuredClone(value) as Mutable<T>;
}

describe("Demo 前端响应契约", () => {
  it("接受明确的仿真 bootstrap、job 与 schedule 摘要", () => {
    expect(parseBootstrap(emptyBootstrap()).story_state).toBe("EMPTY");
    expect(parseBootstrap(publishedBootstrap()).current_publication?.publication_id).toBe(
      "publication-demo-1",
    );
    expect(parseJob(runningPlanJob()).stage).toBe("SOLVING");
    expect(parseScheduleSummary(scheduleSummary()).boundary.publishable).toBe(false);
    expect(parseBootstrap(emptyBootstrap()).configuration.route_templates).toHaveLength(4);
    expect(parseBootstrap(comparisonBootstrap()).comparison_reference?.request_id).toBe(
      "replan-request-demo-1",
    );
  });

  it("生产 authority、未知状态和可发布展示均 fail closed", () => {
    expect(() =>
      parseBootstrap({ ...emptyBootstrap(), production_authority: true }),
    ).toThrow(DemoContractError);
    expect(() =>
      parseBootstrap({ ...emptyBootstrap(), story_state: "DONE" }),
    ).toThrow(DemoContractError);
    expect(() =>
      parseScheduleSummary({
        ...scheduleSummary(),
        boundary: { ...scheduleSummary().boundary, publishable: true },
      }),
    ).toThrow(DemoContractError);
  });

  it("拒绝缺失关键字段的部分可信响应", () => {
    const payload = { ...emptyBootstrap() } as Record<string, unknown>;
    delete payload.correlation_id;
    expect(() => parseBootstrap(payload)).toThrow(DemoContractError);
  });

  it("接受完整工厂与排程页，并校验展示层级和分页", () => {
    expect(parseFactoryView(factoryView()).counts.resources).toBe(2);
    const parsed = parseScheduleView(scheduleView());
    expect(parsed.assignments).toHaveLength(3);
    expect(parsed.page.limit).toBe(160);
    expect(parsed.resources[0]?.formula).toBe(
      "planned_busy_seconds / available_seconds",
    );
  });

  it("拒绝工厂层级计数、维护资源与时间区间不一致", () => {
    const countMismatch = mutableClone(factoryView());
    countMismatch.counts.resources = 3;
    expect(() => parseFactoryView(countMismatch)).toThrow(DemoContractError);

    const unknownResource = mutableClone(factoryView());
    unknownResource.maintenance_events[0]!.resource_id = "resource-unknown";
    expect(() => parseFactoryView(unknownResource)).toThrow(DemoContractError);

    const invalidRange = mutableClone(factoryView());
    invalidRange.factory.workshops[0]!.production_line.resource_groups[0]!
      .resources[0]!.unavailable_intervals[0]!.end =
      invalidRange.factory.workshops[0]!.production_line.resource_groups[0]!
        .resources[0]!.unavailable_intervals[0]!.start;
    expect(() => parseFactoryView(invalidRange)).toThrow(DemoContractError);
  });

  it("拒绝排程分页、枚举、lineage 与仿真边界异常", () => {
    const pageMismatch = mutableClone(scheduleView());
    pageMismatch.page.returned = 2;
    expect(() => parseScheduleView(pageMismatch)).toThrow(DemoContractError);

    const unknownState = mutableClone(scheduleView()) as unknown as Record<
      string,
      unknown
    >;
    const assignments = unknownState.assignments as Record<string, unknown>[];
    assignments[0]!.protection = "FROZEN";
    expect(() => parseScheduleView(unknownState)).toThrow(DemoContractError);

    const staleResource = mutableClone(scheduleView());
    staleResource.assignments[0]!.resource_id = "resource-stale";
    expect(() => parseScheduleView(staleResource)).toThrow(DemoContractError);

    const productionBoundary = mutableClone(scheduleView()) as unknown as {
      boundary: Record<string, unknown>;
    };
    productionBoundary.boundary.production_authority = true;
    expect(() => parseScheduleView(productionBoundary)).toThrow(
      DemoContractError,
    );
  });

  it("完整校验加急结果和服务端版本比较", () => {
    const parsed = parseComparisonView(comparisonView());
    expect(parsed.after.state).toBe("DRAFT");
    expect(parsed.change_counts).toMatchObject({ added: 1, changed: 1 });
    expect(parsed.provenance.validation_status).toBe("PASS");

    const urgent = parseUrgentReplanResult({
      result_version: "cnc-demo-urgent-replan-result.v1",
      run_id: "run-demo",
      demand_order_id: "demand-demo",
      event_id: "event-demo",
      snapshot_id: "snapshot-demo",
      problem_hash: `sha256:${"2".repeat(64)}`,
      request_id: "request-demo",
      attempt_id: "attempt-demo",
      schedule_version_id: "schedule-draft-demo",
      schedule_state: "DRAFT",
      solver_status: "FEASIBLE",
      validation_status: "PASS",
      change_report_id: "report-demo",
      operation_changes: { ADDED: 5, CHANGED: 2, UNCHANGED: 100 },
      current_published_version_id: "schedule-base-demo",
      exact_replay: false,
    });
    expect(urgent.operation_changes.ADDED).toBe(5);
  });

  it("拒绝比较版本、分类形状、派生指标、分页和仿真边界漂移", () => {
    const staleParent = mutableClone(comparisonView());
    staleParent.after.parent_schedule_version_id = "schedule-other";
    expect(() => parseComparisonView(staleParent)).toThrow(DemoContractError);

    const missingBase = mutableClone(comparisonView());
    missingBase.operations[0]!.base_assignment = null;
    expect(() => parseComparisonView(missingBase)).toThrow(DemoContractError);

    const forgedDelta = mutableClone(comparisonView());
    forgedDelta.delivery_delta.late_order_count = 9;
    expect(() => parseComparisonView(forgedDelta)).toThrow(DemoContractError);

    const badPage = mutableClone(comparisonView());
    badPage.page.returned = 1;
    expect(() => parseComparisonView(badPage)).toThrow(DemoContractError);

    const production = mutableClone(comparisonView()) as unknown as {
      boundary: Record<string, unknown>;
    };
    production.boundary.production_authority = true;
    expect(() => parseComparisonView(production)).toThrow(DemoContractError);
  });

  it("DRAFT 状态缺少持久比较引用时 fail closed", () => {
    const broken = mutableClone(comparisonBootstrap());
    broken.comparison_reference = null;
    expect(() => parseBootstrap(broken)).toThrow(DemoContractError);
  });
});
