import { useMemo, useState, type CSSProperties } from "react";

import type {
  DemoFactoryView,
  DemoScheduleView,
  FactoryUnavailableInterval,
  ScheduleAssignment,
  ScheduleQueryInput,
} from "../../api/types";
import { initialWorkspaceQuery } from "../../app/useScheduleWorkspace";
import { formatNumber } from "../../domain/copy";
import {
  assignmentsByResource,
  barGeometry,
  factoryResources,
  formatDurationSeconds,
  formatWorkspaceTime,
  fullHorizonQuery,
  operationStateLabels,
  protectionLabels,
  queryWithFilters,
  shiftedWindowQuery,
  timelineTicks,
  timelineWindow,
} from "../../domain/scheduleWorkspace";

const FREEZE_WINDOW_MS = 900_000;

interface GanttWorkspaceViewProps {
  readonly factory: DemoFactoryView;
  readonly schedule: DemoScheduleView;
  readonly selectedOrderId: string | null;
  readonly refreshing: boolean;
  readonly onQuery: (query: ScheduleQueryInput) => Promise<void>;
}

function geometryStyle(
  start: string,
  end: string,
  window: ReturnType<typeof timelineWindow>,
): CSSProperties | null {
  const geometry = barGeometry(start, end, window);
  if (geometry === null) return null;
  return {
    left: `${geometry.leftPercent}%`,
    width: `${geometry.widthPercent}%`,
  };
}

function intervalLabel(interval: FactoryUnavailableInterval): string {
  return `${interval.kind === "MAINTENANCE" ? "维护停机" : "非工作时段"}：${interval.reason}，${formatWorkspaceTime(interval.start.utc)} 至 ${formatWorkspaceTime(interval.end.utc)}`;
}

function assignmentClass(
  assignment: ScheduleAssignment,
  priority: "NORMAL" | "KEY" | "URGENT",
): string {
  return [
    "gantt-assignment",
    `gantt-assignment--${priority.toLowerCase()}`,
    `gantt-assignment--${assignment.operation_state.toLowerCase()}`,
    `gantt-assignment--${assignment.protection.toLowerCase()}`,
  ].join(" ");
}

export function GanttWorkspaceView({
  factory,
  schedule,
  selectedOrderId,
  refreshing,
  onQuery,
}: GanttWorkspaceViewProps) {
  const [showDetails, setShowDetails] = useState(false);
  const locatedResources = useMemo(() => factoryResources(factory), [factory]);
  const orderById = useMemo(
    () => new Map(schedule.orders.map((order) => [order.demand_order_id, order])),
    [schedule.orders],
  );
  const assignments = useMemo(
    () => assignmentsByResource(schedule.assignments),
    [schedule.assignments],
  );
  const window = timelineWindow(schedule, factory);
  const ticks = timelineTicks(window);
  const selectedWorkshopId = schedule.query.workshop_ids[0] ?? "";
  const selectedResourceId = schedule.query.resource_ids[0] ?? "";
  const selectedOrder = selectedOrderId ? orderById.get(selectedOrderId) ?? null : null;
  const visibleResources = locatedResources.filter(({ resource, workshop }) => {
    if (selectedResourceId && resource.resource_id !== selectedResourceId) return false;
    if (selectedWorkshopId && workshop.workshop_id !== selectedWorkshopId) return false;
    return true;
  });
  const resourceOptions = locatedResources.filter(
    ({ workshop }) => !selectedWorkshopId || workshop.workshop_id === selectedWorkshopId,
  );
  const completedByResource = new Map(
    visibleResources.map(({ resource }) => [
      resource.resource_id,
      schedule.execution_segments.filter(
        (segment) =>
          segment.resource_id === resource.resource_id && segment.status === "COMPLETED",
      ),
    ]),
  );
  const freezeStart = factory.horizon_start.utc;
  const freezeEnd = new Date(Date.parse(freezeStart) + FREEZE_WINDOW_MS).toISOString();
  const freezeStyle = geometryStyle(freezeStart, freezeEnd, window);
  const lowerBound = Date.parse(factory.horizon_start.utc) - 6 * 3_600_000;
  const upperBound = Date.parse(factory.horizon_end.utc);
  const canMoveBack =
    schedule.query.start_at_utc !== null &&
    Date.parse(schedule.query.start_at_utc) > lowerBound;
  const canMoveForward =
    schedule.query.end_at_utc !== null &&
    Date.parse(schedule.query.end_at_utc) < upperBound;
  const visibleMaintenance = factory.maintenance_events.filter(
    (event) =>
      visibleResources.some(({ resource }) => resource.resource_id === event.resource_id) &&
      Date.parse(event.end.utc) > window.startMs &&
      Date.parse(event.start.utc) < window.endMs,
  );

  const updateQuery = (patch: ScheduleQueryInput) => {
    void onQuery(queryWithFilters(schedule.query, patch));
  };

  const restoreDefaultWindow = () => {
    const initial = initialWorkspaceQuery(factory);
    void onQuery({
      ...schedule.query,
      start_at_utc: initial.start_at_utc,
      end_at_utc: initial.end_at_utc,
      offset: 0,
    });
  };

  return (
    <section aria-labelledby="gantt-view-title" aria-busy={refreshing}>
      <div className="workspace-view-heading">
        <div>
          <p className="eyebrow">有限产能排程</p>
          <h3 id="gantt-view-title">工厂—车间—设备甘特图</h3>
          <p>当前只挂载一个服务端分页，班次、维护、执行状态与锁定均有文字说明。</p>
        </div>
        <span className="result-count">
          当前 {formatNumber(schedule.page.returned)} / 匹配 {formatNumber(schedule.page.filtered_total)} 道
        </span>
      </div>

      {selectedOrder && (
        <div className="focus-chip" role="status">
          <span>正在聚焦订单</span>
          <strong>{selectedOrder.order_code}</strong>
          <small>{selectedOrder.product_code} · {selectedOrder.operation_count} 道工序</small>
          <button
            type="button"
            onClick={() => {
              updateQuery({ demand_order_ids: [], sort: "ORDER_START_ASC" });
            }}
          >
            清除聚焦
          </button>
        </div>
      )}

      <div className="gantt-toolbar" aria-label="甘特筛选与时间窗">
        <label>
          <span>车间层级</span>
          <select
            aria-label="选择车间"
            value={selectedWorkshopId}
            onChange={(event) =>
              updateQuery({
                workshop_ids: event.target.value ? [event.target.value] : [],
                resource_ids: [],
                sort: "RESOURCE_START_ASC",
              })
            }
          >
            <option value="">全工厂 · {factory.counts.resources} 台设备</option>
            {factory.factory.workshops.map((workshop) => (
              <option key={workshop.workshop_id} value={workshop.workshop_id}>
                {workshop.workshop_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>设备层级</span>
          <select
            aria-label="选择设备"
            value={selectedResourceId}
            onChange={(event) => {
              const located = locatedResources.find(
                ({ resource }) => resource.resource_id === event.target.value,
              );
              updateQuery({
                resource_ids: event.target.value ? [event.target.value] : [],
                workshop_ids: located ? [located.workshop.workshop_id] : schedule.query.workshop_ids,
                sort: "RESOURCE_START_ASC",
              });
            }}
          >
            <option value="">全部设备</option>
            {resourceOptions.map(({ resource }) => (
              <option key={resource.resource_id} value={resource.resource_id}>
                {resource.resource_code} · {resource.resource_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>工序状态</span>
          <select
            aria-label="选择工序状态"
            value={schedule.query.states[0] ?? ""}
            onChange={(event) =>
              updateQuery({
                states: event.target.value
                  ? [event.target.value as "NOT_STARTED" | "RUNNING"]
                  : [],
              })
            }
          >
            <option value="">全部状态</option>
            <option value="RUNNING">正在加工</option>
            <option value="NOT_STARTED">待加工</option>
          </select>
        </label>
        <div className="window-controls">
          <span>时间窗</span>
          <div>
            <button
              className="icon-control"
              type="button"
              aria-label="查看前一个时间窗"
              disabled={!canMoveBack || refreshing}
              onClick={() => void onQuery(shiftedWindowQuery(schedule.query, factory, -1))}
            >
              ←
            </button>
            <button
              className="window-label"
              type="button"
              onClick={restoreDefaultWindow}
              title="恢复默认 72 小时时间窗"
            >
              {formatWorkspaceTime(window.startMs)} — {formatWorkspaceTime(window.endMs)}
            </button>
            <button
              className="icon-control"
              type="button"
              aria-label="查看后一个时间窗"
              disabled={!canMoveForward || refreshing}
              onClick={() => void onQuery(shiftedWindowQuery(schedule.query, factory, 1))}
            >
              →
            </button>
          </div>
        </div>
        <button
          className="button button--small button--quiet gantt-full-window"
          type="button"
          onClick={() => void onQuery(fullHorizonQuery(schedule.query))}
          disabled={schedule.query.start_at_utc === null && schedule.query.end_at_utc === null}
        >
          显示全周期
        </button>
      </div>

      <div className="gantt-legend" aria-label="甘特图例">
        <span><i className="legend-swatch legend-swatch--planned" />计划任务</span>
        <span><i className="legend-swatch legend-swatch--key" />重点订单</span>
        <span><i className="legend-swatch legend-swatch--urgent" />加急订单</span>
        <span><i className="legend-swatch legend-swatch--running" />进行中 ▧</span>
        <span><i className="legend-swatch legend-swatch--completed" />已完成 ✓</span>
        <span><i className="legend-swatch legend-swatch--hard" />硬锁 🔒</span>
        <span><i className="legend-swatch legend-swatch--soft" />软锁 ┄</span>
        <span><i className="legend-swatch legend-swatch--freeze" />冻结窗口 ❄</span>
        <span><i className="legend-swatch legend-swatch--offshift" />非工作时段</span>
        <span><i className="legend-swatch legend-swatch--maintenance" />维护停机 ⚠</span>
      </div>

      <div className="freeze-explanation">
        <span aria-hidden="true">❄</span>
        <p><strong>冻结窗口独立标注：</strong>浅蓝区域是开排时点后 15 分钟的演示重排保护策略；显式硬锁仍以“🔒 硬锁定”单独展示。</p>
      </div>

      <div className="gantt-scroll" data-testid="gantt-scroll" tabIndex={0}>
        <div className="gantt-board">
          <div className="gantt-axis-row">
            <div className="gantt-resource-label gantt-resource-label--axis">
              <strong>设备</strong>
              <small>{visibleResources.length} 台 · 北京时间</small>
            </div>
            <div className="gantt-axis">
              {ticks.map((tick) => (
                <span key={tick.value} style={{ left: `${tick.leftPercent}%` }}>
                  {formatWorkspaceTime(tick.value)}
                </span>
              ))}
            </div>
          </div>

          {visibleResources.map(({ resource, workshop }) => {
            const rowAssignments = assignments.get(resource.resource_id) ?? [];
            const completedSegments = completedByResource.get(resource.resource_id) ?? [];
            return (
              <div className="gantt-resource-row" key={resource.resource_id}>
                <div className="gantt-resource-label">
                  <strong>{resource.resource_code}</strong>
                  <small>{resource.resource_name}</small>
                  <span>{workshop.workshop_name}</span>
                </div>
                <div className="gantt-lane" aria-label={`${resource.resource_code} 排程轨道`}>
                  {ticks.map((tick) => (
                    <i
                      aria-hidden="true"
                      className="gantt-gridline"
                      key={tick.value}
                      style={{ left: `${tick.leftPercent}%` }}
                    />
                  ))}
                  {resource.unavailable_intervals.map((interval) => {
                    const style = geometryStyle(interval.start.utc, interval.end.utc, window);
                    if (style === null) return null;
                    return (
                      <span
                        key={interval.interval_id}
                        className={`calendar-block calendar-block--${interval.kind.toLowerCase()}`}
                        style={style}
                        title={intervalLabel(interval)}
                        aria-label={intervalLabel(interval)}
                      />
                    );
                  })}
                  {freezeStyle && (
                    <span
                      className="gantt-freeze-window"
                      style={freezeStyle}
                      title="冻结窗口：开排时点后 15 分钟"
                      aria-label="冻结窗口：开排时点后 15 分钟"
                    />
                  )}
                  {completedSegments.map((segment) => {
                    if (segment.actual_end === null) return null;
                    const style = geometryStyle(
                      segment.actual_start.utc,
                      segment.actual_end.utc,
                      window,
                    );
                    if (style === null) return null;
                    return (
                      <span
                        className="gantt-completed"
                        data-testid="gantt-completed"
                        key={segment.execution_fact_id}
                        style={style}
                        title={`✓ 已完成事实 · ${resource.resource_code} · ${formatWorkspaceTime(segment.actual_start.utc)} 至 ${formatWorkspaceTime(segment.actual_end.utc)}`}
                      >
                        ✓ 已完成
                      </span>
                    );
                  })}
                  {rowAssignments.map((assignment) => {
                    const style = geometryStyle(assignment.start.utc, assignment.end.utc, window);
                    if (style === null) return null;
                    const order = orderById.get(assignment.demand_order_id);
                    const priority = order?.priority_class ?? "NORMAL";
                    const semantic = `${operationStateLabels[assignment.operation_state]} · ${protectionLabels[assignment.protection]}`;
                    return (
                      <span
                        className={assignmentClass(assignment, priority)}
                        data-testid="gantt-assignment"
                        data-state={assignment.operation_state}
                        data-protection={assignment.protection}
                        key={assignment.operation_id}
                        style={style}
                        title={`${assignment.order_code} · ${assignment.operation_name} · ${semantic} · ${formatWorkspaceTime(assignment.start.utc)} 至 ${formatWorkspaceTime(assignment.end.utc)}`}
                      >
                        <b>{assignment.protection === "HARD_LOCK" ? "🔒 " : assignment.protection === "SOFT_LOCK" ? "┄ " : assignment.operation_state === "RUNNING" ? "▧ " : ""}</b>
                        {assignment.order_code.replace("demand-order-", "")} · {assignment.operation_name}
                      </span>
                    );
                  })}
                  {rowAssignments.length === 0 && completedSegments.length === 0 && (
                    <span className="gantt-lane-empty">当前筛选无任务</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {visibleResources.length === 0 && (
        <div className="workspace-empty">
          <strong>当前层级没有设备</strong>
          <p>请切回全工厂或选择其他车间。</p>
        </div>
      )}

      <div className="gantt-pagination">
        <span>
          服务端分页 {Math.floor(schedule.page.offset / schedule.page.limit) + 1} · 每页最多 {schedule.page.limit} 道 · 全版本 {formatNumber(schedule.page.unfiltered_total)} 道
        </span>
        <div>
          <button
            className="button button--small button--quiet"
            type="button"
            disabled={schedule.page.offset === 0 || refreshing}
            onClick={() =>
              updateQuery({
                offset: Math.max(0, schedule.page.offset - schedule.page.limit),
              })
            }
          >
            上一批工序
          </button>
          <button
            className="button button--small button--quiet"
            type="button"
            disabled={!schedule.page.has_more || refreshing}
            onClick={() => updateQuery({ offset: schedule.page.offset + schedule.page.limit })}
          >
            下一批工序
          </button>
        </div>
      </div>

      <div className="calendar-summary">
        <div>
          <strong>日历口径</strong>
          <p>灰色斜纹表示班次之外的不可用时段；红色斜纹表示计划维护，均来自工厂展示契约。</p>
        </div>
        {visibleMaintenance.length > 0 ? (
          <ul>
            {visibleMaintenance.map((event) => (
              <li key={event.event_id}>
                <span>⚠ 维护停机</span>
                <strong>{event.resource_code} · {event.reason}</strong>
                <small>{formatWorkspaceTime(event.start.utc)} — {formatWorkspaceTime(event.end.utc)}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p>当前时间窗没有计划维护事件。</p>
        )}
      </div>

      <button
        className="detail-toggle"
        type="button"
        aria-expanded={showDetails}
        onClick={() => setShowDetails((current) => !current)}
      >
        <span>
          <strong>无障碍等价明细</strong>
          <small>用文字表格读取每道工序的状态、锁定、设备与时间</small>
        </span>
        <span aria-hidden="true">{showDetails ? "收起" : "展开"}</span>
      </button>

      {showDetails && (
        <div className="data-table-scroll gantt-detail-table">
          <table>
            <caption className="sr-only">当前甘特分页的工序文字明细</caption>
            <thead>
              <tr>
                <th scope="col">订单</th>
                <th scope="col">工序</th>
                <th scope="col">设备</th>
                <th scope="col">状态</th>
                <th scope="col">保护方式</th>
                <th scope="col">开始</th>
                <th scope="col">结束</th>
                <th scope="col">候选设备</th>
              </tr>
            </thead>
            <tbody>
              {schedule.assignments.map((assignment) => (
                <tr key={assignment.operation_id}>
                  <td>{assignment.order_code}</td>
                  <td>{assignment.operation_sequence}. {assignment.operation_name}</td>
                  <td>{assignment.resource_code}</td>
                  <td>{operationStateLabels[assignment.operation_state]}</td>
                  <td>{protectionLabels[assignment.protection]}</td>
                  <td>{formatWorkspaceTime(assignment.start.utc)}</td>
                  <td>{formatWorkspaceTime(assignment.end.utc)}</td>
                  <td>{assignment.candidate_resource_count} 台</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="detail-caption">
            当前页最长工序 {schedule.assignments.length > 0
              ? formatDurationSeconds(Math.max(...schedule.assignments.map((item) => item.duration_seconds)))
              : "不适用"}；已完成执行事实另以“✓ 已完成”绘制，不计入待排工序页。
          </p>
        </div>
      )}
    </section>
  );
}
