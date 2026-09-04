import { describe, expect, it } from "vitest";

import {
  barGeometry,
  factoryResources,
  filterAndSortOrders,
  shiftedWindowQuery,
  timelineWindow,
} from "../src/domain/scheduleWorkspace";
import { factoryView, scheduleView } from "./fixtures";

describe("排程工作区纯展示模型", () => {
  it("按延期、延期时长、优先权重和交期稳定排序订单", () => {
    const schedule = scheduleView();
    const ordered = filterAndSortOrders(schedule.orders, {
      search: "",
      priority: "ALL",
      risk: "ALL",
    });
    expect(ordered.map((order) => order.order_code)).toEqual([
      "CNC-001",
      "CNC-002",
    ]);
    expect(
      filterAndSortOrders(schedule.orders, {
        search: "housing",
        priority: "URGENT",
        risk: "ALL",
      }),
    ).toHaveLength(1);
  });

  it("展平工厂层级且保留车间归属", () => {
    const resources = factoryResources(factoryView());
    expect(resources).toHaveLength(2);
    expect(resources[0]?.workshop.workshop_name).toBe("精密车削车间");
  });

  it("把跨窗工序裁剪到当前时间窗，完全窗外则不绘制", () => {
    const window = timelineWindow(scheduleView(), factoryView());
    expect(
      barGeometry(
        "2026-09-06T15:00:00Z",
        "2026-09-06T17:00:00Z",
        window,
      ),
    ).toMatchObject({ leftPercent: 0 });
    expect(
      barGeometry(
        "2026-09-10T00:00:00Z",
        "2026-09-10T01:00:00Z",
        window,
      ),
    ).toBeNull();
  });

  it("移动时间窗时限制在历史下界与排程周期上界", () => {
    const schedule = scheduleView();
    const factory = factoryView();
    const previous = shiftedWindowQuery(schedule.query, factory, -1);
    expect(previous.start_at_utc).toBe("2026-09-06T16:00:00.000Z");
    const next = shiftedWindowQuery(schedule.query, factory, 1);
    expect(next.start_at_utc).toBe("2026-09-09T16:00:00.000Z");
    expect(next.offset).toBe(0);
  });
});
