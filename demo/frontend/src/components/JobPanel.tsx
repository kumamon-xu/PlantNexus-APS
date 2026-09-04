import { useEffect, useMemo, useState } from "react";

import type { DemoJob } from "../api/types";
import {
  formatLocalTime,
  formatSeconds,
  jobKindLabels,
  jobStatusLabels,
  shortId,
  stageLabel,
} from "../domain/copy";

interface JobPanelProps {
  readonly job: DemoJob | null;
  readonly pollingJobId: string | null;
  readonly solveLimitSeconds: number | null;
}

function elapsedSince(value: string, now: number): number {
  const started = new Date(value).valueOf();
  return Number.isFinite(started) ? Math.max(0, (now - started) / 1000) : 0;
}

export function JobPanel({ job, pollingJobId, solveLimitSeconds }: JobPanelProps) {
  const [clock, setClock] = useState(0);
  const running = job?.status === "RUNNING" || pollingJobId !== null;
  const now = clock || (job === null ? 0 : new Date(job.updated_at_utc).valueOf());

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  const totalElapsed = useMemo(() => {
    if (job === null) return null;
    const end = terminal(job.status) ? new Date(job.updated_at_utc).valueOf() : now;
    return Math.max(0, (end - new Date(job.created_at_utc).valueOf()) / 1000);
  }, [job, now]);

  if (job === null) {
    return (
      <section className="panel job-panel" aria-labelledby="job-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">执行状态</p>
            <h2 id="job-title">后台任务</h2>
          </div>
          <span className={`status-dot ${pollingJobId ? "status-dot--live" : ""}`} />
        </div>
        <div className="job-empty" role={pollingJobId ? "status" : undefined}>
          <span className="job-empty__mark" aria-hidden="true">
            {pollingJobId ? "⋯" : "✓"}
          </span>
          <div>
            <strong>{pollingJobId ? "正在读取任务状态" : "当前没有执行中的任务"}</strong>
            <p>{pollingJobId ? "已从服务端恢复任务身份。" : "开始主操作后，这里会显示真实阶段和耗时。"}</p>
          </div>
        </div>
      </section>
    );
  }

  const currentStage = [...job.stages].reverse().find((stage) => stage.status === "RUNNING");
  const stageElapsed = currentStage ? elapsedSince(currentStage.started_at_utc, now) : null;
  const currentIsSolving = job.stage === "SOLVING";
  return (
    <section
      className="panel job-panel"
      aria-labelledby="job-title"
      aria-live="polite"
      data-testid="job-panel"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">执行状态</p>
          <h2 id="job-title">{jobKindLabels[job.job_kind]}</h2>
        </div>
        <span className={`job-state job-state--${job.status.toLowerCase()}`}>
          {jobStatusLabels[job.status]}
        </span>
      </div>

      <div className="current-stage">
        <span className="current-stage__pulse" aria-hidden="true" />
        <div>
          <small>当前真实阶段</small>
          <strong>{stageLabel(job.stage)}</strong>
        </div>
        <div className="current-stage__time">
          <small>总经过时间</small>
          <strong>{formatSeconds(totalElapsed)}</strong>
        </div>
      </div>

      {currentIsSolving && (
        <p className="solver-clock">
          当前求解已用 {formatSeconds(stageElapsed)}
          {solveLimitSeconds === null ? "" : ` · 本次上限 ${formatSeconds(solveLimitSeconds)}`}
        </p>
      )}

      <ol className="stage-list" aria-label="任务阶段">
        {job.stages.map((stage) => (
          <li key={`${stage.attempt}-${stage.sequence}`}>
            <span className={`stage-mark stage-mark--${stage.status.toLowerCase()}`} aria-hidden="true">
              {stage.status === "SUCCEEDED" ? "✓" : stage.status === "RUNNING" ? "•" : "!"}
            </span>
            <span>
              <strong>{stageLabel(stage.stage)}</strong>
              <small>
                {formatLocalTime(stage.started_at_utc)}
                {stage.elapsed_seconds === null ? "" : ` · ${formatSeconds(stage.elapsed_seconds)}`}
              </small>
            </span>
          </li>
        ))}
      </ol>

      <div className="job-meta">
        <span>任务 {shortId(job.job_id)}</span>
        <span>关联标识 {shortId(job.correlation_id)}</span>
      </div>
    </section>
  );
}

function terminal(status: DemoJob["status"]): boolean {
  return ["SUCCEEDED", "FAILED", "INTERRUPTED", "CANCELLED"].includes(status);
}
