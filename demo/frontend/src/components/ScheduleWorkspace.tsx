import { useState } from "react";

import type { DemoApi } from "../api/client";
import type { ScheduleOrder } from "../api/types";
import { useScheduleWorkspace } from "../app/useScheduleWorkspace";
import { formatNumber, formatRatio } from "../domain/copy";
import { CapacityWorkspaceView } from "./workspace/CapacityWorkspaceView";
import { EvidenceWorkspaceView } from "./workspace/EvidenceWorkspaceView";
import { GanttWorkspaceView } from "./workspace/GanttWorkspaceView";
import { OrdersWorkspaceView } from "./workspace/OrdersWorkspaceView";

type WorkspaceTab = "orders" | "gantt" | "capacity" | "evidence";

const tabs: readonly { readonly id: WorkspaceTab; readonly label: string }[] = [
  { id: "orders", label: "订单与交期" },
  { id: "gantt", label: "排程甘特" },
  { id: "capacity", label: "计划负荷" },
  { id: "evidence", label: "校验与证据" },
];

interface ScheduleWorkspaceProps {
  readonly api: DemoApi;
  readonly runId: string;
  readonly versionId: string;
}

export function ScheduleWorkspace({
  api,
  runId,
  versionId,
}: ScheduleWorkspaceProps) {
  const workspace = useScheduleWorkspace(api, runId, versionId);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("gantt");
  const schedule = workspace.schedule;
  const factory = workspace.factory;
  const isDynamicReplan = schedule?.version.source_kind === "DYNAMIC_REPLAN";
  const selectedOrderId = schedule?.query.demand_order_ids[0] ?? null;

  const focusOrder = (order: ScheduleOrder) => {
    if (schedule === null) return;
    setActiveTab("gantt");
    void workspace.loadSchedule({
      ...schedule.query,
      demand_order_ids: [order.demand_order_id],
      start_at_utc: null,
      end_at_utc: null,
      sort: "ORDER_START_ASC",
      offset: 0,
    });
  };

  return (
    <section
      className="schedule-workspace"
      aria-labelledby="schedule-workspace-title"
      data-testid="schedule-workspace"
    >
      <header className="workspace-heading">
        <div>
          <p className="eyebrow">
            {isDynamicReplan ? "重排草稿工作区" : "初始排产工作区"}
          </p>
          <h2 id="schedule-workspace-title">订单、设备与交付承诺一屏联动</h2>
          <p>
            {factory?.factory.factory_name ?? "正在读取演示工厂"} · 所有操作仅查询当前仿真版本
          </p>
        </div>
        <div className="workspace-heading__actions">
          <span className="read-only-badge">只读 · GET</span>
          <button
            className="button button--small button--quiet"
            type="button"
            onClick={() => void workspace.refresh()}
            disabled={workspace.loading || workspace.refreshing}
          >
            {workspace.refreshing ? "正在刷新" : "刷新工作区"}
          </button>
        </div>
      </header>

      {workspace.notice && (
        <div className="workspace-notice" role="alert">
          <div>
            <strong>{workspace.notice.title}</strong>
            <p>{workspace.notice.detail}</p>
          </div>
          <button className="text-button" type="button" onClick={workspace.dismissNotice}>
            收起
          </button>
        </div>
      )}

      {workspace.loading && schedule === null && (
        <div className="workspace-loading" role="status">
          <span className="workspace-loading__mark" aria-hidden="true" />
          <div>
            <strong>正在装载排程工作区</strong>
            <p>依次校验工厂层级、排程页、资源日历和证据链。</p>
          </div>
        </div>
      )}

      {!workspace.loading && (schedule === null || factory === null) && (
        <div className="workspace-loading workspace-loading--error">
          <span aria-hidden="true">!</span>
          <div>
            <strong>工作区暂时不可用</strong>
            <p>故事主状态和当前仿真基线均未改变，可以安全地重新读取。</p>
          </div>
          <button className="button button--small" type="button" onClick={() => void workspace.refresh()}>
            重新读取
          </button>
        </div>
      )}

      {schedule && factory && (
        <>
          <div className="workspace-summary" aria-label="当前排程摘要">
            <div>
              <span>订单总数</span>
              <strong>{formatNumber(schedule.kpis.delivery.order_count)}</strong>
              <small>按期率 {formatRatio(schedule.kpis.delivery.on_time_order_ratio)}</small>
            </div>
            <div>
              <span>已排工序</span>
              <strong>{formatNumber(schedule.page.unfiltered_total)}</strong>
              <small>当前窗口匹配 {formatNumber(schedule.page.filtered_total)}</small>
            </div>
            <div>
              <span>生产设备</span>
              <strong>{formatNumber(factory.counts.resources)}</strong>
              <small>{formatNumber(factory.counts.workshops)} 个专业车间</small>
            </div>
            <div>
              <span>延期订单</span>
              <strong>{formatNumber(schedule.kpis.delivery.late_order_count)}</strong>
              <small>来自服务端关键指标证据</small>
            </div>
          </div>

          <div className="workspace-tabs" role="tablist" aria-label="排程工作区视图">
            {tabs.map((tab) => (
              <button
                id={`workspace-tab-${tab.id}`}
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                aria-controls={`workspace-panel-${tab.id}`}
                tabIndex={activeTab === tab.id ? 0 : -1}
                className={activeTab === tab.id ? "is-active" : undefined}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {tabs.map((tab) => (
            <div
              id={`workspace-panel-${tab.id}`}
              key={tab.id}
              className="workspace-panel"
              role="tabpanel"
              aria-labelledby={`workspace-tab-${tab.id}`}
              hidden={activeTab !== tab.id}
            >
              {tab.id === "orders" && activeTab === tab.id && (
                <OrdersWorkspaceView
                  orders={schedule.orders}
                  selectedOrderId={selectedOrderId}
                  onFocusOrder={focusOrder}
                />
              )}
              {tab.id === "gantt" && activeTab === tab.id && (
                <GanttWorkspaceView
                  factory={factory}
                  schedule={schedule}
                  selectedOrderId={selectedOrderId}
                  refreshing={workspace.refreshing}
                  onQuery={workspace.loadSchedule}
                />
              )}
              {tab.id === "capacity" && activeTab === tab.id && (
                <CapacityWorkspaceView factory={factory} schedule={schedule} />
              )}
              {tab.id === "evidence" && activeTab === tab.id && (
                <EvidenceWorkspaceView schedule={schedule} />
              )}
            </div>
          ))}

          <footer className="workspace-footnote">
            <span>
              本页返回 {formatNumber(schedule.page.returned)} 条，单次上限 {formatNumber(schedule.page.limit)} 条
            </span>
            <span>
              {workspace.lastLoadedAt
                ? `最近读取 ${new Date(workspace.lastLoadedAt).toLocaleTimeString("zh-CN", { hour12: false })}`
                : "尚未完成读取"}
            </span>
          </footer>
        </>
      )}
    </section>
  );
}
