import type { DemoScheduleView } from "../../api/types";
import {
  formatNumber,
  formatRatio,
  formatSeconds,
  shortId,
  solverCopy,
} from "../../domain/copy";
import { formatDurationSeconds, formatWorkspaceTime } from "../../domain/scheduleWorkspace";

interface EvidenceWorkspaceViewProps {
  readonly schedule: DemoScheduleView;
}

function valueOrDash(value: number | null): string {
  return value === null ? "不适用" : formatNumber(value);
}

function sourceKindLabel(value: string): string {
  if (value === "VALIDATED_SOLUTION") return "已校验求解结果";
  if (value === "URGENT_REPLAN" || value === "DYNAMIC_REPLAN") {
    return "加急重排结果";
  }
  return "服务端已提交结果";
}

export function EvidenceWorkspaceView({ schedule }: EvidenceWorkspaceViewProps) {
  const solver = solverCopy(schedule.solver.solver_status);
  const stabilityApplicable = schedule.kpis.stability.schedule_stability_ratio !== null;
  const isDynamicReplan = schedule.version.source_kind === "DYNAMIC_REPLAN";
  return (
    <section aria-labelledby="evidence-view-title">
      <div className="workspace-view-heading">
        <div>
          <p className="eyebrow">权威展示证据</p>
          <h3 id="evidence-view-title">求解器、独立校验器与关键指标</h3>
          <p>以下数值原样读取服务端已提交证据；浏览器不重新求解、不重算业务关键指标。</p>
        </div>
        <span className="result-count">版本修订 {schedule.version.revision}</span>
      </div>

      <div className="evidence-hero-grid">
        <article className="solver-evidence-card">
          <div className="evidence-card-heading">
            <span aria-hidden="true">◎</span>
            <div>
              <small>求解结论</small>
              <h4>{solver.label}</h4>
            </div>
          </div>
          <p>{solver.detail}</p>
          <dl>
            <div><dt>状态</dt><dd>{schedule.solver.solver_status === "OPTIMAL" ? "已证明最优" : "已验证可行"}</dd></div>
            <div><dt>求解耗时</dt><dd>{formatSeconds(schedule.solver.solve_seconds)}</dd></div>
            <div><dt>端到端耗时</dt><dd>{formatSeconds(schedule.solver.total_seconds)}</dd></div>
            <div><dt>求解上限</dt><dd>{formatSeconds(schedule.solver.limit_seconds)}</dd></div>
            <div><dt>目标值</dt><dd>{valueOrDash(schedule.solver.objective_value)}</dd></div>
            <div><dt>相对差距</dt><dd>{formatRatio(schedule.solver.relative_gap)}</dd></div>
          </dl>
          <small className="evidence-id" title={schedule.solver.report_id}>
            报告 {shortId(schedule.solver.report_id)}
          </small>
        </article>

        <article className="validator-evidence-card">
          <div className="evidence-card-heading">
            <span aria-hidden="true">✓</span>
            <div>
              <small>独立校验器</small>
              <h4>校验通过</h4>
            </div>
          </div>
          <p>当前排程经过独立校验，未发现硬约束违规。</p>
          <strong className="validator-zero">0</strong>
          <span>项硬约束违规</span>
          <small className="evidence-id" title={schedule.validation.fingerprint}>
            指纹 {shortId(schedule.validation.fingerprint)}
          </small>
        </article>
      </div>

      <div className="kpi-evidence-grid" aria-label="服务端关键指标">
        <article>
          <span>按期订单率</span>
          <strong>{formatRatio(schedule.kpis.delivery.on_time_order_ratio)}</strong>
          <small>{formatNumber(schedule.kpis.delivery.on_time_order_count)} / {formatNumber(schedule.kpis.delivery.order_count)} 单按期</small>
        </article>
        <article>
          <span>延期订单</span>
          <strong>{formatNumber(schedule.kpis.delivery.late_order_count)}</strong>
          <small>累计延期 {formatDurationSeconds(schedule.kpis.delivery.total_tardiness_seconds)}</small>
        </article>
        <article>
          <span>完工跨度</span>
          <strong>{formatDurationSeconds(schedule.kpis.planning.makespan_seconds)}</strong>
          <small>服务端完工跨度口径</small>
        </article>
        <article>
          <span>未排工序</span>
          <strong>{formatNumber(schedule.kpis.planning.unscheduled_operation_count)}</strong>
          <small>已排 {formatNumber(schedule.kpis.planning.scheduled_operation_count)} 道</small>
        </article>
      </div>

      <div className="stability-note">
        <span aria-hidden="true">↔</span>
        <div>
          <strong>
            {stabilityApplicable
              ? "已有版本稳定性证据"
              : isDynamicReplan
                ? "稳定性详见版本比较"
                : "初始排程暂无比较基线"}
          </strong>
          <p>
            {stabilityApplicable
              ? `稳定率 ${formatRatio(schedule.kpis.stability.schedule_stability_ratio)}，移动 ${valueOrDash(schedule.kpis.stability.changed_operation_count)} 道工序。`
              : isDynamicReplan
                ? "本排程 KPI 不重复承载稳定性向量；请以上方服务端版本比较和 ChangeReport 为准。"
                : "稳定性指标只在动态重排与基线比较时适用；初始排程不会虚构该数值。"}
          </p>
        </div>
      </div>

      <div className="version-evidence">
        <div className="version-evidence__summary">
          <span>
            <small>排程版本</small>
            <strong>{shortId(schedule.version.schedule_version_id)}</strong>
          </span>
          <span>
            <small>生成时间</small>
            <strong>{formatWorkspaceTime(schedule.version.created_at.utc)}</strong>
          </span>
          <span>
            <small>来源</small>
            <strong>{sourceKindLabel(schedule.version.source_kind)}</strong>
          </span>
          <span>
            <small>数据边界</small>
            <strong>仅仿真 · 不可生产发布</strong>
          </span>
        </div>

        <details>
          <summary>
            <span>查看证据链清单</span>
            <small>{schedule.provenance.artifacts.length} 个不可变引用</small>
          </summary>
          <div className="data-table-scroll">
            <table>
              <caption className="sr-only">排程版本证据链</caption>
              <thead>
                <tr>
                  <th scope="col">文档版本</th>
                  <th scope="col">证据标识</th>
                  <th scope="col">内容指纹</th>
                </tr>
              </thead>
              <tbody>
                {schedule.provenance.artifacts.map((artifact) => (
                  <tr key={`${artifact.document_version}-${artifact.artifact_id}`}>
                    <td>{artifact.document_version}</td>
                    <td title={artifact.artifact_id}>{shortId(artifact.artifact_id)}</td>
                    <td title={artifact.fingerprint}>{shortId(artifact.fingerprint)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>
    </section>
  );
}
