import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DemoApi } from "../src/api/client";
import { DemoContractError } from "../src/api/contracts";
import type { DemoBootstrap, DemoJob } from "../src/api/types";
import { DemoApp } from "../src/DemoApp";
import {
  completedResetJob,
  comparisonBootstrap,
  comparisonView,
  draftScheduleSummary,
  draftScheduleView,
  emptyBootstrap,
  factoryView,
  initializedBootstrap,
  publishedBootstrap,
  readyBootstrap,
  runningPlanJob,
  scheduleView,
  scheduleSummary,
} from "./fixtures";

function mockApi(overrides: Partial<DemoApi> = {}): DemoApi {
  return {
    establishSession: vi.fn().mockResolvedValue(undefined),
    bootstrap: vi.fn().mockResolvedValue(emptyBootstrap()),
    getFactory: vi.fn().mockResolvedValue(factoryView()),
    getJob: vi.fn().mockResolvedValue(runningPlanJob()),
    getSchedulePage: vi.fn().mockResolvedValue(scheduleView()),
    getScheduleSummary: vi.fn().mockResolvedValue(scheduleSummary()),
    reset: vi.fn().mockResolvedValue({
      job_accepted_version: "cnc-demo-job-accepted.v1",
      job_id: "job-reset-demo-1",
      job_kind: "RESET",
      run_id: "run-new",
      status: "QUEUED",
      replayed: false,
    }),
    createInitialPlan: vi.fn().mockRejectedValue(new Error("not expected")),
    activateBaseline: vi.fn().mockRejectedValue(new Error("not expected")),
    submitUrgentOrder: vi.fn().mockRejectedValue(new Error("not expected")),
    getComparison: vi.fn().mockRejectedValue(new Error("not expected")),
    ...overrides,
  };
}

describe("中文 Demo 故事首页", () => {
  it("从空状态初始化，并在任务成功后恢复服务端新 run", async () => {
    const user = userEvent.setup();
    const bootstrap = vi
      .fn<() => Promise<DemoBootstrap>>()
      .mockResolvedValueOnce(emptyBootstrap())
      .mockResolvedValue(initializedBootstrap());
    const api = mockApi({
      bootstrap,
      getJob: vi.fn().mockResolvedValue(completedResetJob()),
    });
    render(<DemoApp api={api} profile="smoke" pollIntervalMs={5} />);

    const initialize = await screen.findByRole("button", { name: "初始化演示工厂" });
    expect(screen.getByText("仿真环境 · 非生产")).toBeInTheDocument();
    await user.click(initialize);

    await screen.findByRole("button", { name: "开始自动排产" });
    expect(api.reset).toHaveBeenCalledWith(
      "smoke",
      expect.stringMatching(/^demo-ui-reset-/),
    );
    expect(screen.getByText("24")).toBeInTheDocument();
    expect(screen.getByText("108")).toBeInTheDocument();
  });

  it("刷新后恢复同一 active job，显示真实求解阶段、耗时与上限而无进度百分比", async () => {
    const runningBootstrap: DemoBootstrap = {
      ...initializedBootstrap(),
      story_state: "INITIAL_PLAN_RUNNING",
      active_job: {
        job_id: "job-initial-plan-demo-1",
        job_kind: "INITIAL_PLAN",
        status: "RUNNING",
        stage: "SOLVING",
      },
    };
    const api = mockApi({
      bootstrap: vi.fn().mockResolvedValue(runningBootstrap),
      getJob: vi.fn().mockResolvedValue(runningPlanJob()),
    });
    render(<DemoApp api={api} profile="smoke" pollIntervalMs={10_000} />);

    const panel = await screen.findByTestId("job-panel");
    expect(within(panel).getAllByText("求解排程")).toHaveLength(2);
    expect(within(panel).getByText(/本次上限 5\.0 秒/)).toBeInTheDocument();
    expect(panel.textContent).not.toContain("%");
    expect(api.getJob).toHaveBeenCalledWith("job-initial-plan-demo-1");
    expect(screen.getByText("运行 run-111111…111111")).toBeInTheDocument();
  });

  it("使用服务端 revision 和 fingerprint 显式确认仿真基线", async () => {
    const user = userEvent.setup();
    const bootstrap = vi
      .fn<() => Promise<DemoBootstrap>>()
      .mockResolvedValueOnce(readyBootstrap())
      .mockResolvedValue(publishedBootstrap());
    const getScheduleSummary = vi
      .fn()
      .mockResolvedValueOnce(scheduleSummary("READY_FOR_REVIEW"))
      .mockResolvedValue(scheduleSummary("PUBLISHED"));
    const activateBaseline = vi.fn().mockResolvedValue({
      result_version: "cnc-demo-baseline-activation-result.v1",
      run_id: initializedBootstrap().run?.run_id,
      schedule_version_id: readyBootstrap().schedule_version?.schedule_version_id,
      content_fingerprint: readyBootstrap().schedule_version?.content_fingerprint,
      state: "PUBLISHED",
      state_revision: 3,
      publication_id: "publication-demo-1",
      current_reference_revision: 1,
      replayed: false,
    });
    const api = mockApi({ bootstrap, getScheduleSummary, activateBaseline });
    render(<DemoApp api={api} profile="smoke" />);

    await user.click(await screen.findByRole("button", { name: "设为仿真基线" }));
    const dialog = screen.getByRole("dialog", { name: "设为当前仿真基线？" });
    const confirm = within(dialog).getByRole("button", { name: "确认并发布仿真基线" });
    expect(confirm).toHaveFocus();
    await user.click(confirm);

    await screen.findByText("当前仿真基线");
    expect(activateBaseline).toHaveBeenCalledWith(
      expect.objectContaining({
        expected_state_revision: 1,
        content_fingerprint: readyBootstrap().schedule_version?.content_fingerprint,
        confirmation: "ACTIVATE_SIMULATION_BASELINE",
      }),
      expect.stringMatching(/^demo-ui-activate-/),
    );
  });

  it("发布后读取失败时保留原命令身份，并用同一请求安全恢复", async () => {
    localStorage.clear();
    const user = userEvent.setup();
    const bootstrap = vi
      .fn<() => Promise<DemoBootstrap>>()
      .mockResolvedValueOnce(readyBootstrap())
      .mockRejectedValueOnce(new DemoContractError("bootstrap.current_publication"))
      .mockResolvedValueOnce(readyBootstrap())
      .mockResolvedValue(publishedBootstrap());
    const getScheduleSummary = vi
      .fn()
      .mockResolvedValueOnce(scheduleSummary("READY_FOR_REVIEW"))
      .mockResolvedValueOnce(scheduleSummary("READY_FOR_REVIEW"))
      .mockResolvedValue(scheduleSummary("PUBLISHED"));
    const activateBaseline = vi.fn().mockResolvedValue({
      result_version: "cnc-demo-baseline-activation-result.v1",
      run_id: initializedBootstrap().run?.run_id,
      schedule_version_id: readyBootstrap().schedule_version?.schedule_version_id,
      content_fingerprint: readyBootstrap().schedule_version?.content_fingerprint,
      state: "PUBLISHED",
      state_revision: 3,
      publication_id: "publication-demo-1",
      current_reference_revision: 1,
      replayed: false,
    });
    const api = mockApi({ bootstrap, getScheduleSummary, activateBaseline });
    render(<DemoApp api={api} profile="smoke" />);

    await user.click(await screen.findByRole("button", { name: "设为仿真基线" }));
    await user.click(
      screen.getByRole("button", { name: "确认并发布仿真基线" }),
    );
    await screen.findByText("服务响应契约不匹配");

    await user.click(screen.getByRole("button", { name: "设为仿真基线" }));
    await user.click(
      screen.getByRole("button", { name: "确认并发布仿真基线" }),
    );
    await screen.findByText("当前仿真基线");

    expect(activateBaseline).toHaveBeenCalledTimes(2);
    expect(activateBaseline.mock.calls[1]).toEqual(activateBaseline.mock.calls[0]);
  });

  it("已有运行的重置需要二次确认，并支持 Escape 取消", async () => {
    const user = userEvent.setup();
    const api = mockApi({ bootstrap: vi.fn().mockResolvedValue(initializedBootstrap()) });
    render(<DemoApp api={api} profile="smoke" />);

    const trigger = await screen.findByRole("button", { name: "重置演示" });
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: "重置当前演示运行？" })).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "确认重置" });
    const cancel = screen.getByRole("button", { name: "取消" });
    expect(confirm).toHaveFocus();
    await user.tab();
    expect(cancel).toHaveFocus();
    await user.tab({ shift: true });
    expect(confirm).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(api.reset).not.toHaveBeenCalled();
  });

  it("服务重启后从本地持久任务身份读取 INTERRUPTED 并给出中文恢复边界", async () => {
    localStorage.setItem(
      "plantnexus-demo:pending-job",
      JSON.stringify({
        job_id: "job-initial-plan-demo-1",
        job_kind: "INITIAL_PLAN",
        run_id: initializedBootstrap().run!.run_id,
      }),
    );
    const interrupted: DemoJob = {
      ...runningPlanJob(),
      status: "INTERRUPTED",
      error_code: "PROCESS_INTERRUPTED",
    };
    const api = mockApi({
      bootstrap: vi.fn().mockResolvedValue(initializedBootstrap()),
      getJob: vi.fn().mockResolvedValue(interrupted),
    });

    render(<DemoApp api={api} profile="smoke" pollIntervalMs={5} />);

    expect(await screen.findByText("服务重启中断了后台任务")).toBeInTheDocument();
    expect(screen.getByText(/没有伪装成成功/)).toBeInTheDocument();
    expect(api.getJob).toHaveBeenCalledWith("job-initial-plan-demo-1");
    expect(localStorage.getItem("plantnexus-demo:pending-job")).toBeNull();
  });

  it("未知原始异常只显示中文安全提示", async () => {
    const api = mockApi({
      establishSession: vi.fn().mockRejectedValue(new Error("Bearer secret-value")),
    });
    render(<DemoApp api={api} />);

    await screen.findByText("页面暂时无法继续");
    expect(document.body.textContent).not.toContain("secret-value");
    expect(screen.getByRole("button", { name: "重新连接并读取状态" })).toBeInTheDocument();
  });

  it("用四条批准路线完成中文插单确认，并在成功后自动切换版本比较", async () => {
    localStorage.clear();
    const user = userEvent.setup();
    const bootstrap = vi
      .fn<() => Promise<DemoBootstrap>>()
      .mockResolvedValueOnce(publishedBootstrap())
      .mockResolvedValue(comparisonBootstrap());
    const getScheduleSummary = vi
      .fn()
      .mockResolvedValueOnce(scheduleSummary("PUBLISHED"))
      .mockResolvedValue(draftScheduleSummary());
    const completedUrgent: DemoJob = {
      ...runningPlanJob(),
      job_id: "job-urgent-demo-1",
      job_kind: "URGENT_REPLAN",
      status: "SUCCEEDED",
      stage: "COMPLETE",
      result: {
        result_version: "cnc-demo-urgent-replan-result.v1",
        run_id: publishedBootstrap().run!.run_id,
        demand_order_id: "order-demo-urgent",
        event_id: "event-demo-urgent",
        snapshot_id: "snapshot-demo-urgent",
        problem_hash: `sha256:${"3".repeat(64)}`,
        request_id: "replan-request-demo-1",
        attempt_id: "replan-attempt-demo-1",
        schedule_version_id: comparisonBootstrap().schedule_version!.schedule_version_id,
        schedule_state: "DRAFT",
        solver_status: "FEASIBLE",
        validation_status: "PASS",
        change_report_id: "change-report-demo-1",
        operation_changes: { ADDED: 5, CHANGED: 1, UNCHANGED: 1 },
        current_published_version_id: publishedBootstrap().schedule_version!.schedule_version_id,
        exact_replay: false,
      },
    };
    const submitUrgentOrder = vi.fn().mockResolvedValue({
      job_accepted_version: "cnc-demo-job-accepted.v1",
      job_id: completedUrgent.job_id,
      job_kind: "URGENT_REPLAN",
      run_id: publishedBootstrap().run!.run_id,
      status: "QUEUED",
      replayed: false,
    });
    const api = mockApi({
      bootstrap,
      getScheduleSummary,
      getSchedulePage: vi.fn().mockResolvedValue(draftScheduleView()),
      submitUrgentOrder,
      getJob: vi.fn().mockResolvedValue(completedUrgent),
      getComparison: vi.fn().mockResolvedValue(comparisonView()),
    });
    render(<DemoApp api={api} profile="smoke" pollIntervalMs={5} />);

    await user.click(await screen.findByRole("button", { name: "插入加急订单" }));
    expect(await screen.findByRole("heading", { name: "插入加急订单" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(4);
    expect(screen.getByText("短轴类")).toBeInTheDocument();
    expect(screen.getByText("精密套筒类")).toBeInTheDocument();

    const quantity = screen.getByRole("spinbutton", { name: /订单数量/ });
    await user.clear(quantity);
    await user.type(quantity, "0");
    await user.click(screen.getByRole("button", { name: "核对并提交插单" }));
    expect(screen.getByText("数量须为 1～50 的整数。")).toBeInTheDocument();
    expect(quantity).toHaveFocus();
    expect(quantity).toHaveAttribute(
      "aria-describedby",
      "urgent-quantity-help urgent-quantity-error",
    );
    expect(submitUrgentOrder).not.toHaveBeenCalled();

    await user.clear(quantity);
    await user.type(quantity, "5");
    await user.click(screen.getByRole("button", { name: "核对并提交插单" }));
    let dialog = screen.getByRole("dialog", { name: "确认接收这张加急订单？" });
    expect(within(dialog).getByText("新方案只会保存为草稿")).toBeInTheDocument();
    const urgentConfirm = within(dialog).getByRole("button", {
      name: "确认插单并自动重排",
    });
    const returnToForm = within(dialog).getByRole("button", { name: "返回修改" });
    expect(urgentConfirm).toHaveFocus();
    await user.tab();
    expect(returnToForm).toHaveFocus();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const review = screen.getByRole("button", { name: "核对并提交插单" });
    await waitFor(() => expect(review).toHaveFocus());
    await user.click(review);
    dialog = screen.getByRole("dialog", { name: "确认接收这张加急订单？" });
    await user.click(
      within(dialog).getByRole("button", { name: "确认插单并自动重排" }),
    );

    expect(await screen.findByRole("heading", { name: "插单前后版本比较" })).toBeInTheDocument();
    expect(screen.getByText("新方案为未发布草稿")).toBeInTheDocument();
    expect(await screen.findByText("重排草稿工作区")).toBeInTheDocument();
    expect(await screen.findByText("独立校验通过")).toBeInTheDocument();
    expect(submitUrgentOrder).toHaveBeenCalledWith(
      expect.objectContaining({
        expected_base_version_id: publishedBootstrap().schedule_version!.schedule_version_id,
        route_template_id: "CNC-ROUTE-5",
        quantity: 5,
        due_at_local: "2026-09-09T18:00:00",
        priority_class: "URGENT",
      }),
      expect.stringMatching(/^demo-ui-urgent-/),
    );
  });

  it("重排未找到候选时保留已发布基线并给出中文安全恢复提示", async () => {
    localStorage.clear();
    const user = userEvent.setup();
    const failedUrgent: DemoJob = {
      ...runningPlanJob(),
      job_id: "job-urgent-failed-demo-1",
      job_kind: "URGENT_REPLAN",
      status: "FAILED",
      stage: "SOLVING",
      result: null,
      error_code: "SOLVER_NO_CANDIDATE",
    };
    const api = mockApi({
      bootstrap: vi.fn().mockResolvedValue(publishedBootstrap()),
      getScheduleSummary: vi.fn().mockResolvedValue(scheduleSummary("PUBLISHED")),
      submitUrgentOrder: vi.fn().mockResolvedValue({
        job_accepted_version: "cnc-demo-job-accepted.v1",
        job_id: failedUrgent.job_id,
        job_kind: "URGENT_REPLAN",
        run_id: publishedBootstrap().run!.run_id,
        status: "QUEUED",
        replayed: false,
      }),
      getJob: vi.fn().mockResolvedValue(failedUrgent),
    });
    render(<DemoApp api={api} profile="smoke" pollIntervalMs={5} />);

    await user.click(await screen.findByRole("button", { name: "插入加急订单" }));
    await user.click(screen.getByRole("button", { name: "核对并提交插单" }));
    await user.click(
      within(screen.getByRole("dialog", { name: "确认接收这张加急订单？" }))
        .getByRole("button", { name: "确认插单并自动重排" }),
    );

    expect(await screen.findByText("达到求解限制，未找到可接受排程")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "仿真基线已发布" })).toBeInTheDocument();
    expect(screen.queryByTestId("comparison-workspace")).not.toBeInTheDocument();
    expect(screen.getByText(/原有版本和仿真基线均保持不变/)).toBeInTheDocument();
  });

  it("刷新到 DRAFT 时通过持久比较引用恢复服务端结果", async () => {
    const api = mockApi({
      bootstrap: vi.fn().mockResolvedValue(comparisonBootstrap()),
      getScheduleSummary: vi.fn().mockResolvedValue(draftScheduleSummary()),
      getComparison: vi.fn().mockResolvedValue(comparisonView()),
    });
    render(<DemoApp api={api} profile="smoke" />);

    const workspace = await screen.findByTestId("comparison-workspace");
    expect(within(workspace).getByText("当前已发布仿真基线保持不变")).toBeInTheDocument();
    expect(await within(workspace).findByText("待评审草稿")).toBeInTheDocument();
    expect(api.getComparison).toHaveBeenCalledWith(
      "replan-request-demo-1",
      expect.objectContaining({ limit: 120, sort: "SHIFT_DESC" }),
    );
  });

  it("比较响应与当前筛选查询不一致时停止展示该页", async () => {
    const response = comparisonView();
    const api = mockApi({
      bootstrap: vi.fn().mockResolvedValue(comparisonBootstrap()),
      getScheduleSummary: vi.fn().mockResolvedValue(draftScheduleSummary()),
      getSchedulePage: vi.fn().mockResolvedValue(draftScheduleView()),
      getComparison: vi.fn().mockResolvedValue({
        ...response,
        query: { ...response.query, offset: 120 },
      }),
    });
    render(<DemoApp api={api} profile="smoke" />);

    expect(await screen.findByText("比较证据暂时无法读取")).toBeInTheDocument();
    expect(screen.getByText(/停止使用该响应/)).toBeInTheDocument();
  });
});
