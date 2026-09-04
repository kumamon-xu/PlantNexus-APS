import { useRef, useState } from "react";

import type { DemoApi } from "./api/client";
import { createDemoApi } from "./api/client";
import type { DemoBootstrap, DemoScheduleSummary } from "./api/types";
import { useDemoStory } from "./app/useDemoStory";
import { ConfirmationDialog } from "./components/ConfirmationDialog";
import { ComparisonWorkspace } from "./components/ComparisonWorkspace";
import { JobPanel } from "./components/JobPanel";
import { ScheduleWorkspace } from "./components/ScheduleWorkspace";
import { StepFlow } from "./components/StepFlow";
import { TechnicalEvidence } from "./components/TechnicalEvidence";
import { UrgentOrderPanel } from "./components/UrgentOrderPanel";
import {
  formatNumber,
  formatRatio,
  formatSeconds,
  horizonDays,
  scheduleStateLabels,
  shortId,
  solverCopy,
  storyCopy,
} from "./domain/copy";

const defaultApi = createDemoApi();

interface DemoAppProps {
  readonly api?: DemoApi;
  readonly profile?: "smoke" | "showcase";
  readonly pollIntervalMs?: number;
}

const expectedProfiles = {
  smoke: { orders: 24, operations: 108, resources: 12, days: 7 },
  showcase: { orders: 132, operations: 610, resources: 24, days: 10 },
} as const;

export function DemoApp({
  api = defaultApi,
  profile = "showcase",
  pollIntervalMs,
}: DemoAppProps) {
  const story = useDemoStory(api, { profile, pollIntervalMs });
  const [urgentRunId, setUrgentRunId] = useState<string | null>(null);
  const urgentAnchor = useRef<HTMLDivElement>(null);
  const comparisonAnchor = useRef<HTMLDivElement>(null);
  const bootstrap = story.bootstrap;
  const storyState = bootstrap?.story_state ?? "EMPTY";
  const stateCopy = storyCopy[storyState];
  const counts = scenarioCounts(bootstrap, profile);
  const scheduleState = story.schedule?.version.state ?? bootstrap?.schedule_version?.state ?? null;
  const action = primaryAction(storyState, scheduleState, story.isBusy, story.schedule !== null);
  const solveLimit =
    story.job?.job_kind === "URGENT_REPLAN"
      ? bootstrap?.scenario_manifest?.replan_solve_seconds ?? null
      : bootstrap?.scenario_manifest?.initial_solve_seconds ?? null;

  const runAction = () => {
    if (action.kind === "RESET") story.requestReset();
    if (action.kind === "PLAN") void story.startInitialPlan();
    if (action.kind === "ACTIVATE") story.requestActivation();
    if (action.kind === "URGENT") {
      setUrgentRunId(bootstrap?.run?.run_id ?? null);
      window.setTimeout(
        () => urgentAnchor.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }),
        0,
      );
    }
    if (action.kind === "COMPARE") {
      comparisonAnchor.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <div className="demo-shell">
      <header className="topbar">
        <a className="brand" href="/demo/" aria-label="PlantNexus APS 演示首页">
          <span className="brand-mark" aria-hidden="true">
            PN
          </span>
          <span>
            <strong>PlantNexus APS</strong>
            <small>CNC 精密机加工演示</small>
          </span>
        </a>
        <div className="topbar-status" aria-label="环境与运行状态">
          <span className="simulation-badge">
            <span aria-hidden="true">◇</span> 仿真环境 · 非生产
          </span>
          <span className="run-badge" title={bootstrap?.run?.run_id}>
            运行 {shortId(bootstrap?.run?.run_id)}
          </span>
          <button
            className="icon-button"
            type="button"
            onClick={() => void story.refresh()}
            disabled={story.connecting}
            aria-label="重新读取服务端状态"
            title="重新读取服务端状态"
          >
            ↻
          </button>
          {bootstrap?.run && (
            <button
              className="button button--header"
              type="button"
              onClick={story.requestReset}
              disabled={story.isBusy}
            >
              重置演示
            </button>
          )}
        </div>
      </header>

      <main id="main-content" className="demo-main">
        {story.notice && (
          <section className="notice" role="alert" aria-labelledby="notice-title">
            <span className="notice__icon" aria-hidden="true">
              !
            </span>
            <div>
              <strong id="notice-title">{story.notice.title}</strong>
              <p>{story.notice.detail}</p>
              {story.notice.correlationId && (
                <small>关联标识：{shortId(story.notice.correlationId)}</small>
              )}
            </div>
            <div className="notice__actions">
              <button className="button button--small" type="button" onClick={() => void story.reconnect()}>
                重新连接并读取状态
              </button>
              <button className="text-button" type="button" onClick={story.dismissNotice}>
                收起提示
              </button>
            </div>
          </section>
        )}

        <section className="story-frame" aria-label="演示故事流程">
          <div className="section-kicker">
            <span>演示主线</span>
            <span className="section-kicker__line" />
            <span>共四步</span>
          </div>
          <StepFlow storyState={storyState} scheduleState={scheduleState} />
        </section>

        <section className="hero-grid">
          <div className="hero-copy">
            <div className="hero-copy__status">
              <span className={`status-orb status-orb--${story.isBusy ? "live" : "ready"}`} />
              当前故事状态
            </div>
            <h1>{story.connecting ? "正在连接本地演示服务" : stateCopy.label}</h1>
            <p className="hero-lead">
              {story.connecting
                ? "正在建立安全的本地仿真会话，并从服务端恢复上次进度。"
                : stateCopy.detail}
            </p>
            <div className="hero-meta" aria-label="当前场景摘要">
              <span>精密机械零部件</span>
              <span>单工厂 · 三车间</span>
              <span>北京时间</span>
            </div>
            <div className="primary-action-row">
              <button
                className="button button--primary button--hero"
                type="button"
                onClick={runAction}
                disabled={action.disabled || story.connecting}
              >
                <span>{action.label}</span>
                <span aria-hidden="true">→</span>
              </button>
              <p>{action.hint}</p>
            </div>
          </div>

          <div className="factory-visual" aria-label="三车间设备场景示意">
            <div className="factory-visual__header">
              <span>华东精密制造一厂</span>
              <span>设备在线</span>
            </div>
            {["精密车削车间", "多轴铣削车间", "磨削与检测车间"].map((name, index) => (
              <div className="workshop-track" key={name}>
                <span className="workshop-track__index">0{index + 1}</span>
                <div>
                  <strong>{name}</strong>
                  <span className="machine-dots" aria-hidden="true">
                    {Array.from({ length: index === 2 ? 6 : 9 }, (_, dot) => (
                      <i key={dot} className={dot === 3 && index === 1 ? "maintenance" : ""} />
                    ))}
                  </span>
                </div>
              </div>
            ))}
            <div className="factory-visual__footer">
              <span><i className="legend-dot" /> 可排产设备</span>
              <span><i className="legend-dot legend-dot--maintenance" /> 维护窗口</span>
            </div>
          </div>
        </section>

        <section className="metric-grid" aria-label="场景规模">
          <Metric label="初始订单" value={formatNumber(counts.orders)} unit="单" detail="普通、重点、加急三类" />
          <Metric label="总工序" value={formatNumber(counts.operations)} unit="道" detail={`${formatNumber(counts.activeOperations)} 道进入排程`} />
          <Metric label="生产设备" value={formatNumber(counts.resources)} unit="台" detail="分布于三个专业车间" />
          <Metric label="排程周期" value={formatNumber(counts.days)} unit="天" detail={`固定种子 ${bootstrap?.run?.seed ?? 20260902}`} />
        </section>

        <section className="workspace-grid">
          <JobPanel
            job={story.job}
            pollingJobId={story.pollingJobId}
            solveLimitSeconds={solveLimit}
          />
          <SchedulePanel schedule={story.schedule} bootstrap={bootstrap} />
        </section>

        <div ref={urgentAnchor} className="section-anchor">
          {urgentRunId === bootstrap?.run?.run_id &&
            bootstrap?.story_state === "BASELINE_PUBLISHED" &&
            bootstrap.current_publication &&
            bootstrap.scenario_manifest && (
              <UrgentOrderPanel
                configuration={bootstrap.configuration}
                manifest={bootstrap.scenario_manifest}
                publication={bootstrap.current_publication}
                pending={story.pendingUrgentOrder}
                busy={story.isBusy}
                onSubmit={story.submitUrgentOrder}
                onClose={() => setUrgentRunId(null)}
              />
            )}
        </div>

        <div ref={comparisonAnchor} className="section-anchor">
          {bootstrap?.story_state === "DRAFT_COMPARISON_READY" &&
            bootstrap.run &&
            bootstrap.comparison_reference && (
              <ComparisonWorkspace
                key={bootstrap.comparison_reference.request_id}
                api={api}
                runId={bootstrap.run.run_id}
                reference={bootstrap.comparison_reference}
              />
            )}
        </div>

        {story.schedule && bootstrap?.run && (
          <ScheduleWorkspace
            key={story.schedule.version.schedule_version_id}
            api={api}
            runId={bootstrap.run.run_id}
            versionId={story.schedule.version.schedule_version_id}
          />
        )}

        {bootstrap && (
          <TechnicalEvidence bootstrap={bootstrap} schedule={story.schedule} job={story.job} />
        )}
      </main>

      <footer className="demo-footer">
        <span>PlantNexus APS · 固定合成数据演示</span>
        <span>计划负荷不代表设备实际利用率或综合效率</span>
        <span>{story.lastSyncedAt ? `最近同步 ${new Date(story.lastSyncedAt).toLocaleTimeString("zh-CN", { hour12: false })}` : "尚未同步"}</span>
      </footer>

      <ConfirmationDialog
        kind={story.confirmation}
        busy={story.submitting}
        onConfirm={() => void story.confirmAction()}
        onCancel={story.cancelConfirmation}
      />
    </div>
  );
}

interface MetricProps {
  readonly label: string;
  readonly value: string;
  readonly unit: string;
  readonly detail: string;
}

function Metric({ label, value, unit, detail }: MetricProps) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <p><strong>{value}</strong><b>{unit}</b></p>
      <small>{detail}</small>
    </article>
  );
}

function SchedulePanel({
  schedule,
  bootstrap,
}: {
  readonly schedule: DemoScheduleSummary | null;
  readonly bootstrap: DemoBootstrap | null;
}) {
  if (schedule === null) {
    return (
      <section className="panel schedule-panel" aria-labelledby="schedule-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">方案质量</p>
            <h2 id="schedule-title">排程与校验</h2>
          </div>
          <span className="muted-badge">等待排产</span>
        </div>
        <div className="schedule-empty">
          <div className="schedule-empty__rings" aria-hidden="true"><span /><span /><span /></div>
          <h3>权威结果将在这里呈现</h3>
          <p>自动排产完成后，页面只读取服务端求解器、独立校验器和关键指标证据，不在浏览器重新计算。</p>
        </div>
      </section>
    );
  }

  const solver = solverCopy(schedule.solver.solver_status);
  const isPublished = bootstrap?.current_publication?.schedule_version_id === schedule.version.schedule_version_id;
  const isDraftComparison = schedule.version.state === "DRAFT" && bootstrap?.current_publication != null;
  return (
    <section className="panel schedule-panel" aria-labelledby="schedule-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">方案质量</p>
          <h2 id="schedule-title">排程与校验</h2>
        </div>
        <span className={`schedule-badge schedule-badge--${schedule.version.state.toLowerCase()}`}>
          {scheduleStateLabels[schedule.version.state]}
        </span>
      </div>
      <div className="quality-callout">
        <span className="quality-callout__mark" aria-hidden="true">✓</span>
        <div>
          <strong>{solver.label}</strong>
          <p>{solver.detail}</p>
        </div>
      </div>
      <dl className="quality-metrics">
        <div><dt>独立校验</dt><dd>通过 · 无硬约束违规</dd></div>
        <div><dt>按期订单率</dt><dd>{formatRatio(schedule.kpis.delivery.on_time_order_ratio)}</dd></div>
        <div><dt>延期订单</dt><dd>{formatNumber(schedule.kpis.delivery.late_order_count)} 单</dd></div>
        <div><dt>实际求解</dt><dd>{formatSeconds(schedule.solver.solve_seconds)}</dd></div>
      </dl>
      <div className="publication-boundary">
        <span aria-hidden="true">{isPublished ? "●" : "○"}</span>
        <div>
          <strong>{isPublished ? "当前仿真基线" : isDraftComparison ? "未发布的重排草稿" : "尚未成为仿真基线"}</strong>
          <p>{isPublished ? "只发布到仿真内部目标，不具备生产权限。" : isDraftComparison ? "当前已发布基线保持不变；本演示不会自动发布新方案。" : "需要演示人员显式确认，系统不会自动发布。"}</p>
        </div>
      </div>
    </section>
  );
}

function scenarioCounts(bootstrap: DemoBootstrap | null, profile: "smoke" | "showcase") {
  const expected = expectedProfiles[profile];
  const manifest = bootstrap?.scenario_manifest;
  return {
    orders: manifest?.source_counts.demand_orders ?? expected.orders,
    operations: manifest?.source_counts.routing_operations ?? expected.operations,
    activeOperations: manifest?.problem_counts.active_operations ?? expected.operations,
    resources: manifest?.source_counts.resources ?? expected.resources,
    days: manifest ? horizonDays(manifest.horizon_start_utc, manifest.horizon_end_utc) : expected.days,
  };
}

function primaryAction(
  storyState: DemoBootstrap["story_state"],
  scheduleState: DemoScheduleSummary["version"]["state"] | null,
  busy: boolean,
  scheduleLoaded: boolean,
) {
  if (busy) return { kind: "NONE", label: "任务执行中", hint: "页面会持续读取服务端真实阶段，刷新不会丢失进度。", disabled: true } as const;
  if (scheduleState === "APPROVED") return { kind: "ACTIVATE", label: "继续发布仿真基线", hint: "复用原批准操作身份继续发布，不会重新求解。", disabled: !scheduleLoaded } as const;
  switch (storyState) {
    case "EMPTY":
      return { kind: "RESET", label: "初始化演示工厂", hint: "生成固定随机种子的精密机加工行业数据，并通过标准导入链。", disabled: false } as const;
    case "INITIALIZED":
      return { kind: "PLAN", label: "开始自动排产", hint: "执行真实约束规划求解，并由独立校验器再次校验。", disabled: false } as const;
    case "READY_FOR_REVIEW":
      return { kind: "ACTIVATE", label: "设为仿真基线", hint: "需要明确确认；只发布到仿真内部目标。", disabled: !scheduleLoaded } as const;
    case "BASELINE_PUBLISHED":
      return { kind: "URGENT", label: "插入加急订单", hint: "填写数量、交期、优先级和批准路线，确认后自动重排。", disabled: false } as const;
    case "DRAFT_COMPARISON_READY":
      return { kind: "COMPARE", label: "查看版本比较", hint: "新方案是未发布草稿，不会替换当前仿真基线。", disabled: false } as const;
    case "INITIAL_PLAN_RUNNING":
    case "REPLAN_RUNNING":
      return { kind: "NONE", label: "任务执行中", hint: "页面会持续读取服务端真实阶段。", disabled: true } as const;
  }
}
