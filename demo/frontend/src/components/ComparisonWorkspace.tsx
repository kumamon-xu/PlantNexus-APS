import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { DemoApi } from "../api/client";
import { DemoContractError } from "../api/contracts";
import type {
  ChangeClassification,
  ComparisonOperation,
  ComparisonReference,
  DemoComparisonView,
} from "../api/types";
import {
  formatLongDuration,
  formatNumber,
  formatRatio,
  noticeFor,
  shortId,
} from "../domain/copy";

interface ComparisonWorkspaceProps {
  readonly api: DemoApi;
  readonly runId: string;
  readonly reference: ComparisonReference;
}

const modes = {
  changed: ["ADDED", "CHANGED", "REMOVED_BY_FACT"],
  unchanged: ["UNCHANGED"],
  all: ["ADDED", "CHANGED", "REMOVED_BY_FACT", "UNCHANGED"],
} as const satisfies Record<string, readonly ChangeClassification[]>;

type Mode = keyof typeof modes;

const classificationLabels: Record<ChangeClassification, string> = {
  ADDED: "新增工序",
  CHANGED: "已移动",
  UNCHANGED: "保持不变",
  REMOVED_BY_FACT: "由执行事实移除",
};

const reasonLabels: Readonly<Record<string, string>> = {
  URGENT_ORDER_ADDED: "加急订单新增",
  RESOURCE_CHANGED: "设备发生变化",
  START_TIME_CHANGED: "开始时间偏移",
  END_TIME_CHANGED: "结束时间偏移",
  DURATION_CHANGED: "加工时长变化",
  ASSIGNMENT_UNCHANGED: "设备与时间均未变化",
  REMOVED_BY_EXECUTION_FACT: "已由执行事实消耗",
  TRIGGER_EVENT: "由本次加急事件触发",
  UNATTRIBUTED_SOLVER_CHANGE: "求解器为满足约束与目标调整",
  NO_CHANGE: "设备与时间保持不变",
};

function signed(value: number): string {
  if (value === 0) return "无变化";
  return `${value > 0 ? "+" : "−"}${formatLongDuration(value)}`;
}

function operationWindow(operations: readonly ComparisonOperation[]) {
  const instants = operations.flatMap((operation) =>
    [operation.base_assignment, operation.new_assignment]
      .filter((item) => item !== null)
      .flatMap((item) => [Date.parse(item.start.utc), Date.parse(item.end.utc)]),
  );
  if (instants.length === 0) return { start: 0, span: 1 };
  const start = Math.min(...instants);
  return { start, span: Math.max(1, Math.max(...instants) - start) };
}

function barStyle(
  assignment: ComparisonOperation["base_assignment"],
  window: { start: number; span: number },
) {
  if (assignment === null) return undefined;
  const left = ((Date.parse(assignment.start.utc) - window.start) / window.span) * 100;
  const width =
    ((Date.parse(assignment.end.utc) - Date.parse(assignment.start.utc)) /
      window.span) *
    100;
  return {
    left: `${Math.max(0, left)}%`,
    width: `${Math.max(1.25, width)}%`,
  };
}

export function ComparisonWorkspace({
  api,
  runId,
  reference,
}: ComparisonWorkspaceProps) {
  const [mode, setMode] = useState<Mode>("changed");
  const [orderId, setOrderId] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [offset, setOffset] = useState(0);
  const [view, setView] = useState<DemoComparisonView | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<ReturnType<typeof noticeFor> | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setFailure(null);
    try {
      const next = await api.getComparison(reference.request_id, {
        classifications: modes[mode],
        demand_order_ids: orderId ? [orderId] : [],
        resource_ids: resourceId ? [resourceId] : [],
        sort: mode === "unchanged" ? "OPERATION_ASC" : "SHIFT_DESC",
        offset,
        limit: 120,
      });
      if (
        next.run_id !== runId ||
        next.request_id !== reference.request_id ||
        next.before.schedule_version_id !== reference.before_schedule_version_id ||
        next.after.schedule_version_id !== reference.after_schedule_version_id ||
        next.provenance.change_report.artifact_id !== reference.change_report_id
      ) {
        throw new DemoContractError("comparison.bootstrap_lineage");
      }
      const expectedClassifications = [...modes[mode]].sort();
      const expectedOrders = orderId ? [orderId] : [];
      const expectedResources = resourceId ? [resourceId] : [];
      const expectedSort = mode === "unchanged" ? "OPERATION_ASC" : "SHIFT_DESC";
      if (
        JSON.stringify(next.query.classifications) !==
          JSON.stringify(expectedClassifications) ||
        JSON.stringify(next.query.demand_order_ids) !==
          JSON.stringify(expectedOrders) ||
        JSON.stringify(next.query.resource_ids) !==
          JSON.stringify(expectedResources) ||
        next.query.workshop_ids.length !== 0 ||
        next.query.start_at_utc !== null ||
        next.query.end_at_utc !== null ||
        next.query.sort !== expectedSort ||
        next.query.offset !== offset ||
        next.query.limit !== 120
      ) {
        throw new DemoContractError("comparison.request_response_query");
      }
      setView(next);
    } catch (error) {
      setFailure(noticeFor(error));
    } finally {
      setLoading(false);
    }
  }, [api, mode, offset, orderId, reference, resourceId, runId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const resourceOptions = useMemo(() => {
    const values = new Map<string, string>();
    for (const operation of view?.operations ?? []) {
      for (const assignment of [operation.base_assignment, operation.new_assignment]) {
        if (assignment !== null) values.set(assignment.resource_id, assignment.resource_code);
      }
    }
    return [...values].sort((left, right) => left[1].localeCompare(right[1], "zh-CN"));
  }, [view]);
  const timelineWindow = operationWindow(view?.operations ?? []);

  if (failure !== null) {
    return (
      <section className="comparison-workspace comparison-workspace--error" aria-labelledby="comparison-title">
        <p className="eyebrow">版本比较</p>
        <h2 id="comparison-title">比较证据暂时无法读取</h2>
        <p>{failure.detail}</p>
        <button className="button" type="button" onClick={() => void load()}>
          重新读取比较结果
        </button>
      </section>
    );
  }

  return (
    <section className="comparison-workspace" aria-labelledby="comparison-title" data-testid="comparison-workspace">
      <div className="comparison-heading">
        <div>
          <p className="eyebrow">服务端权威比较</p>
          <h2 ref={headingRef} id="comparison-title" tabIndex={-1}>插单前后版本比较</h2>
          <p>变更分类、交付指标和稳定性均直接读取本次 ChangeReport 与 KPI。</p>
        </div>
        <div className="draft-boundary">
          <strong>新方案为未发布草稿</strong>
          <span>当前已发布仿真基线保持不变</span>
        </div>
      </div>

      {view === null ? (
        <div className="comparison-loading" role="status">
          <span className="status-orb status-orb--live" /> 正在读取版本比较证据…
        </div>
      ) : (
        <>
          <div className="version-rail" aria-label="版本关系">
            <div>
              <span>插单前</span>
              <strong>已发布基线</strong>
              <small title={view.before.schedule_version_id}>{shortId(view.before.schedule_version_id)}</small>
            </div>
            <span className="version-rail__arrow" aria-hidden="true">→</span>
            <div>
              <span>插单后</span>
              <strong>待评审草稿</strong>
              <small title={view.after.schedule_version_id}>{shortId(view.after.schedule_version_id)}</small>
            </div>
            <div className="validator-seal">
              <span aria-hidden="true">✓</span>
              <div><strong>独立校验通过</strong><small>无硬约束违规</small></div>
            </div>
          </div>

          <div className="comparison-metrics">
            <article><span>新增工序</span><strong>{formatNumber(view.change_counts.added)}</strong><small>来自加急路线</small></article>
            <article><span>移动工序</span><strong>{formatNumber(view.change_counts.changed)}</strong><small>既有工序发生变化</small></article>
            <article><span>保持不变</span><strong>{formatRatio(view.stability.unchanged_ratio)}</strong><small>{formatNumber(view.stability.unchanged_existing)} / {formatNumber(view.stability.comparable_existing)} 道</small></article>
            <article><span>设备变更</span><strong>{formatNumber(view.stability.resource_changes)}</strong><small>跨设备调整工序</small></article>
          </div>

          <div className="stability-strip">
            <strong>稳定性说明</strong>
            <span>
              软锁偏离 {formatNumber(view.stability.soft_lock_violations)} 道（允许的稳定性代价）；
              累计开始时间偏移 {formatLongDuration(view.stability.absolute_start_shift_seconds)}；
              独立 Validator 仍为通过，无硬约束违规。
            </span>
          </div>

          <div className="delivery-comparison">
            <h3>交付与完工变化</h3>
            <div className="delivery-comparison__grid">
              <MetricDelta label="按期订单率" before={formatRatio(view.before_kpis.delivery.on_time_order_ratio)} after={formatRatio(view.after_kpis.delivery.on_time_order_ratio)} delta={view.delivery_delta.on_time_order_ratio === null ? "不适用" : `${view.delivery_delta.on_time_order_ratio >= 0 ? "+" : ""}${(view.delivery_delta.on_time_order_ratio * 100).toFixed(1)} 个百分点`} />
              <MetricDelta label="延期订单" before={`${formatNumber(view.before_kpis.delivery.late_order_count)} 单`} after={`${formatNumber(view.after_kpis.delivery.late_order_count)} 单`} delta={`${view.delivery_delta.late_order_count >= 0 ? "+" : ""}${formatNumber(view.delivery_delta.late_order_count)} 单`} />
              <MetricDelta label="总延期" before={formatLongDuration(view.before_kpis.delivery.total_tardiness_seconds)} after={formatLongDuration(view.after_kpis.delivery.total_tardiness_seconds)} delta={signed(view.delivery_delta.total_tardiness_seconds)} />
              <MetricDelta label="排程完工跨度" before={formatLongDuration(view.before_kpis.planning.makespan_seconds)} after={formatLongDuration(view.after_kpis.planning.makespan_seconds)} delta={signed(view.delivery_delta.makespan_seconds)} />
            </div>
          </div>

          <div className="comparison-toolbar">
            <div className="segmented" aria-label="变更分类">
              {(["changed", "unchanged", "all"] as const).map((value) => (
                <button
                  type="button"
                  key={value}
                  className={mode === value ? "is-active" : ""}
                  aria-pressed={mode === value}
                  onClick={() => { setMode(value); setOffset(0); }}
                >
                  {value === "changed" ? "仅看变化" : value === "unchanged" ? "保持不变" : "全部工序"}
                </button>
              ))}
            </div>
            <label>
              <span>订单</span>
              <select value={orderId} onChange={(event) => { setOrderId(event.target.value); setOffset(0); }}>
                <option value="">全部订单</option>
                {view.affected_orders.map((order) => (
                  <option value={order.demand_order_id} key={order.demand_order_id}>{order.order_code} · {order.change_count} 处变化</option>
                ))}
              </select>
            </label>
            <label>
              <span>设备</span>
              <select value={resourceId} onChange={(event) => { setResourceId(event.target.value); setOffset(0); }}>
                <option value="">全部设备</option>
                {resourceOptions.map(([id, code]) => <option value={id} key={id}>{code}</option>)}
              </select>
            </label>
            {loading && <span className="toolbar-loading" role="status">正在更新…</span>}
          </div>

          <div className="comparison-list" aria-label="工序前后对比">
            {view.operations.length === 0 ? (
              <div className="comparison-empty">当前筛选条件下没有工序。</div>
            ) : view.operations.map((operation) => (
              <article className="comparison-operation" key={operation.operation_id}>
                <div className="comparison-operation__title">
                  <span className={`change-badge change-badge--${operation.classification.toLowerCase()}`}>{classificationLabels[operation.classification]}</span>
                  <div><strong>{operation.operation_name}</strong><small>{operation.order_code} · {operation.operation_code}</small></div>
                  <span className={`shift-value ${operation.deltas.start_shift_seconds > 0 ? "shift-value--late" : ""}`}>{operation.classification === "ADDED" ? "新加入" : signed(operation.deltas.start_shift_seconds)}</span>
                </div>
                <div className="paired-timeline" aria-label={`${operation.operation_name} 前后时间`}>
                  <TimelineRow label="原方案" assignment={operation.base_assignment} style={barStyle(operation.base_assignment, timelineWindow)} tone="base" />
                  <TimelineRow label="新方案" assignment={operation.new_assignment} style={barStyle(operation.new_assignment, timelineWindow)} tone="new" />
                </div>
                <div className="reason-row">
                  {operation.reason_codes.map((reason) => <span key={reason}>{reasonLabels[reason] ?? "服务端记录的排程原因"}</span>)}
                </div>
              </article>
            ))}
          </div>

          <div className="comparison-pagination">
            <span>{view.page.returned === 0 ? "当前页 0 道" : `已显示 ${view.page.offset + 1}～${view.page.offset + view.page.returned}`}，共 {formatNumber(view.page.filtered_total)} 道</span>
            <div>
              <button className="button button--small" type="button" disabled={view.page.offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - view.page.limit))}>上一页</button>
              <button className="button button--small" type="button" disabled={!view.page.has_more || loading} onClick={() => setOffset(offset + view.page.limit)}>下一页</button>
            </div>
          </div>

          <details className="comparison-evidence">
            <summary>查看 ChangeReport 与校验证据</summary>
            <dl>
              <div><dt>重排请求</dt><dd>{reference.request_id}</dd></div>
              <div><dt>变更报告</dt><dd>{view.provenance.change_report.artifact_id}</dd></div>
              <div><dt>求解尝试</dt><dd>{view.provenance.attempt_id}</dd></div>
              <div><dt>校验结果</dt><dd>通过（PASS）</dd></div>
              <div><dt>报告指纹</dt><dd>{view.provenance.change_report.fingerprint}</dd></div>
            </dl>
          </details>
        </>
      )}
    </section>
  );
}

function MetricDelta({ label, before, after, delta }: { readonly label: string; readonly before: string; readonly after: string; readonly delta: string }) {
  return <div><span>{label}</span><small>原方案 {before}</small><strong>新方案 {after}</strong><b>{delta}</b></div>;
}

function TimelineRow({ label, assignment, style, tone }: { readonly label: string; readonly assignment: ComparisonOperation["base_assignment"]; readonly style: { left: string; width: string } | undefined; readonly tone: "base" | "new" }) {
  return (
    <div className="timeline-row">
      <span>{label}</span>
      <div className="timeline-track">
        {assignment === null ? <i className="timeline-none">无</i> : <i className={`timeline-bar timeline-bar--${tone}`} style={style} />}
      </div>
      <small>{assignment === null ? "—" : `${assignment.resource_code} · ${assignment.start.local.slice(5, 16).replace("T", " ")}`}</small>
    </div>
  );
}
