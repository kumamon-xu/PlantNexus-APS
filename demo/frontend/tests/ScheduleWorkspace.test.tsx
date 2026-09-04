import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DemoApi } from "../src/api/client";
import type { DemoScheduleView, ScheduleQueryInput } from "../src/api/types";
import { ScheduleWorkspace } from "../src/components/ScheduleWorkspace";
import { factoryView, scheduleView } from "./fixtures";

function workspaceApi(overrides: Partial<DemoApi> = {}): DemoApi {
  return {
    establishSession: vi.fn().mockResolvedValue(undefined),
    bootstrap: vi.fn().mockRejectedValue(new Error("not expected")),
    getFactory: vi.fn().mockResolvedValue(factoryView()),
    getJob: vi.fn().mockRejectedValue(new Error("not expected")),
    getScheduleSummary: vi.fn().mockRejectedValue(new Error("not expected")),
    getSchedulePage: vi.fn().mockResolvedValue(scheduleView("PUBLISHED")),
    reset: vi.fn().mockRejectedValue(new Error("not expected")),
    createInitialPlan: vi.fn().mockRejectedValue(new Error("not expected")),
    activateBaseline: vi.fn().mockRejectedValue(new Error("not expected")),
    submitUrgentOrder: vi.fn().mockRejectedValue(new Error("not expected")),
    getComparison: vi.fn().mockRejectedValue(new Error("not expected")),
    ...overrides,
  };
}

function renderWorkspace(api: DemoApi) {
  const factory = factoryView();
  const schedule = scheduleView("PUBLISHED");
  return render(
    <ScheduleWorkspace
      api={api}
      runId={factory.run_id}
      versionId={schedule.version.schedule_version_id}
    />,
  );
}

function scheduleForQuery(query: ScheduleQueryInput): DemoScheduleView {
  const base = scheduleView("PUBLISHED");
  return {
    ...base,
    query: {
      ...base.query,
      ...query,
      resource_ids: query.resource_ids ?? base.query.resource_ids,
      workshop_ids: query.workshop_ids ?? base.query.workshop_ids,
      demand_order_ids: query.demand_order_ids ?? base.query.demand_order_ids,
      states: query.states ?? base.query.states,
    },
    page: {
      ...base.page,
      offset: query.offset ?? base.page.offset,
      limit: query.limit ?? base.page.limit,
    },
  };
}

describe("中文初始排产工作区", () => {
  it("以 72 小时窗口和 160 条上限装载甘特，并双编码状态、锁与冻结", async () => {
    const api = workspaceApi();
    renderWorkspace(api);

    await screen.findByRole("heading", { name: "工厂—车间—设备甘特图" });
    for (const tab of screen.getAllByRole("tab")) {
      const controlledId = tab.getAttribute("aria-controls");
      expect(controlledId).not.toBeNull();
      expect(document.getElementById(controlledId!)).not.toBeNull();
    }
    expect(screen.getByText("华东精密制造一厂 · 所有操作仅查询当前仿真版本")).toBeInTheDocument();
    expect(screen.getAllByTestId("gantt-assignment")).toHaveLength(3);
    expect(screen.getByText(/冻结窗口独立标注/)).toBeInTheDocument();
    expect(screen.getByText(/显式硬锁仍以/)).toBeInTheDocument();
    expect(screen.getByText("⚠ 维护停机")).toBeInTheDocument();
    expect(api.getSchedulePage).toHaveBeenCalledWith(
      scheduleView().version.schedule_version_id,
      expect.objectContaining({
        start_at_utc: "2026-09-06T16:00:00.000Z",
        end_at_utc: "2026-09-09T16:00:00.000Z",
        limit: 160,
      }),
    );
  });

  it("筛选订单并通过 GET 查询联动到该订单甘特", async () => {
    const user = userEvent.setup();
    const getSchedulePage = vi
      .fn()
      .mockImplementation((_versionId: string, query: ScheduleQueryInput) =>
        Promise.resolve(scheduleForQuery(query)),
      );
    const api = workspaceApi({ getSchedulePage });
    renderWorkspace(api);

    await user.click(await screen.findByRole("tab", { name: "订单与交期" }));
    await user.type(screen.getByRole("searchbox", { name: "搜索订单或产品" }), "CNC-002");
    expect(screen.getByText("匹配 1 / 2 单")).toBeInTheDocument();
    expect(screen.queryByText("CNC-001")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "在甘特中查看订单 CNC-002" }));
    await screen.findByText("正在聚焦订单");
    expect(screen.getByRole("tab", { name: "排程甘特" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(getSchedulePage).toHaveBeenLastCalledWith(
      scheduleView().version.schedule_version_id,
      expect.objectContaining({
        demand_order_ids: ["order-demo-2"],
        start_at_utc: null,
        end_at_utc: null,
        limit: 160,
      }),
    );
    expect(api.reset).not.toHaveBeenCalled();
    expect(api.activateBaseline).not.toHaveBeenCalled();
  });

  it("车间、设备与工序状态筛选保持只读分页查询", async () => {
    const user = userEvent.setup();
    const getSchedulePage = vi.fn().mockResolvedValue(scheduleView("PUBLISHED"));
    const api = workspaceApi({ getSchedulePage });
    renderWorkspace(api);
    await screen.findByRole("heading", { name: "工厂—车间—设备甘特图" });

    await user.selectOptions(screen.getByLabelText("选择车间"), "workshop-demo-ws10");
    await user.selectOptions(screen.getByLabelText("选择设备"), "resource-demo-cmm-01");
    await user.selectOptions(screen.getByLabelText("选择工序状态"), "RUNNING");

    await waitFor(() => expect(getSchedulePage).toHaveBeenCalledTimes(4));
    for (const call of getSchedulePage.mock.calls.slice(1)) {
      const query = call[1];
      expect(query.limit).toBeLessThanOrEqual(200);
    }
    expect(api.createInitialPlan).not.toHaveBeenCalled();
  });

  it("计划负荷明确非 OEE，并按服务端比例显示瓶颈关注", async () => {
    const user = userEvent.setup();
    renderWorkspace(workspaceApi());
    await user.click(await screen.findByRole("tab", { name: "计划负荷" }));

    expect(screen.getByText("这是计划负荷，不是设备综合效率（OEE）。")).toBeInTheDocument();
    const bottlenecks = screen.getByLabelText("计划负荷关注设备");
    expect(within(bottlenecks).getByText("LATHE-01")).toBeInTheDocument();
    expect(within(bottlenecks).getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("公式：计划忙碌秒数 / 可用秒数")).toBeInTheDocument();
  });

  it("FEASIBLE 只表述为已验证可行，并可从读取失败安全恢复", async () => {
    const user = userEvent.setup();
    const feasible: DemoScheduleView = {
      ...scheduleView("PUBLISHED"),
      solver: {
        ...scheduleView("PUBLISHED").solver,
        solver_status: "FEASIBLE",
        optimality_claim: false,
        relative_gap: 0.12,
      },
    };
    const getFactory = vi
      .fn()
      .mockRejectedValueOnce(new Error("sensitive backend trace"))
      .mockResolvedValue(factoryView());
    const api = workspaceApi({
      getFactory,
      getSchedulePage: vi.fn().mockResolvedValue(feasible),
    });
    renderWorkspace(api);

    await screen.findByText("工作区暂时不可用");
    expect(document.body.textContent).not.toContain("sensitive backend trace");
    await user.click(screen.getByRole("button", { name: "重新读取" }));
    await screen.findByRole("heading", { name: "工厂—车间—设备甘特图" });
    await user.click(screen.getByRole("tab", { name: "校验与证据" }));
    expect(screen.getByRole("heading", { name: "已找到并验证可行" })).toBeInTheDocument();
    expect(screen.getByText(/尚未证明最优/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("已证明最优");
  });
});
