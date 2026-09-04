import { useMemo, useState } from "react";

import type { DemoFactoryView, DemoScheduleView } from "../../api/types";
import { formatNumber, formatRatio } from "../../domain/copy";
import { formatHours } from "../../domain/scheduleWorkspace";

interface CapacityWorkspaceViewProps {
  readonly factory: DemoFactoryView;
  readonly schedule: DemoScheduleView;
}

export function CapacityWorkspaceView({
  factory,
  schedule,
}: CapacityWorkspaceViewProps) {
  const [workshopId, setWorkshopId] = useState("");
  const workshopNameById = useMemo(
    () =>
      new Map(
        factory.factory.workshops.map((workshop) => [
          workshop.workshop_id,
          workshop.workshop_name,
        ]),
      ),
    [factory.factory.workshops],
  );
  const resources = useMemo(
    () =>
      schedule.resources
        .filter((resource) => !workshopId || resource.workshop_id === workshopId)
        .sort(
          (left, right) =>
            (right.utilization ?? -1) - (left.utilization ?? -1) ||
            left.resource_code.localeCompare(right.resource_code),
        ),
    [schedule.resources, workshopId],
  );
  const bottlenecks = resources.filter((resource) => resource.utilization !== null).slice(0, 3);

  return (
    <section aria-labelledby="capacity-view-title">
      <div className="workspace-view-heading">
        <div>
          <p className="eyebrow">资源负荷</p>
          <h3 id="capacity-view-title">按计划负荷排序设备</h3>
          <p>忙碌时长和可用时长均来自当前排程的服务端展示证据。</p>
        </div>
        <label className="inline-filter">
          <span>查看车间</span>
          <select value={workshopId} onChange={(event) => setWorkshopId(event.target.value)}>
            <option value="">全部车间</option>
            {factory.factory.workshops.map((workshop) => (
              <option value={workshop.workshop_id} key={workshop.workshop_id}>
                {workshop.workshop_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="capacity-caveat" role="note">
        <span aria-hidden="true">i</span>
        <p><strong>这是计划负荷，不是设备综合效率（OEE）。</strong>口径为“已排忙碌秒数 ÷ 排程周期内可用秒数”，不代表设备实际开动率、良率或综合效率。</p>
      </div>

      <div className="bottleneck-strip" aria-label="计划负荷关注设备">
        {bottlenecks.map((resource, index) => (
          <article key={resource.resource_id}>
            <span>关注 {index + 1}</span>
            <strong>{resource.resource_code}</strong>
            <b>{formatRatio(resource.utilization)}</b>
            <small>{workshopNameById.get(resource.workshop_id) ?? resource.workshop_code}</small>
          </article>
        ))}
      </div>

      <div className="capacity-list">
        <div className="capacity-list__header">
          <span>设备与车间</span>
          <span>计划忙碌 / 可用</span>
          <span>计划负荷</span>
        </div>
        {resources.map((resource, index) => (
          <article className="capacity-row" key={resource.resource_id}>
            <div className="capacity-resource">
              <span className={index < 3 ? "capacity-rank is-top" : "capacity-rank"}>
                {String(index + 1).padStart(2, "0")}
              </span>
              <span>
                <strong>{resource.resource_code} · {resource.resource_name}</strong>
                <small>{workshopNameById.get(resource.workshop_id) ?? resource.workshop_code}</small>
              </span>
            </div>
            <div className="capacity-hours">
              <strong>{formatHours(resource.planned_busy_seconds)}</strong>
              <small>/ {formatHours(resource.available_seconds)} 可用</small>
            </div>
            <div className="capacity-meter">
              <span>
                <i style={{ width: `${Math.max(0, Math.min(100, (resource.utilization ?? 0) * 100))}%` }} />
              </span>
              <strong>{formatRatio(resource.utilization)}</strong>
            </div>
          </article>
        ))}
      </div>

      {resources.length === 0 && (
        <div className="workspace-empty">
          <strong>该车间暂无资源负荷</strong>
          <p>切换到全部车间查看当前版本的 {formatNumber(schedule.resources.length)} 台设备。</p>
        </div>
      )}

      <footer className="capacity-source">
        <span>公式：计划忙碌秒数 / 可用秒数</span>
        <span>共 {formatNumber(resources.length)} 台设备 · 按负荷从高到低</span>
        <span>关键指标证据版本 {schedule.resources[0]?.evidence.document_version ?? "不可用"}</span>
      </footer>
    </section>
  );
}
