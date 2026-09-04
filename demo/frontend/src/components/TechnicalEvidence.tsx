import { useState } from "react";

import type { DemoBootstrap, DemoJob, DemoScheduleSummary } from "../api/types";
import { shortId } from "../domain/copy";

interface TechnicalEvidenceProps {
  readonly bootstrap: DemoBootstrap;
  readonly schedule: DemoScheduleSummary | null;
  readonly job: DemoJob | null;
}

export function TechnicalEvidence({ bootstrap, schedule, job }: TechnicalEvidenceProps) {
  const [copied, setCopied] = useState(false);
  const evidence = {
    说明: "仅包含合成数据标识、指纹、版本和稳定错误证据，不包含会话令牌。",
    运行: bootstrap.run,
    场景清单: bootstrap.scenario_manifest,
    当前排程: schedule,
    最近任务: job,
  };
  const serialized = JSON.stringify(evidence, null, 2);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(serialized);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <details className="technical-evidence">
      <summary>
        <span>
          <strong>技术证据</strong>
          <small>版本、指纹与安全诊断</small>
        </span>
        <span className="summary-action">展开查看</span>
      </summary>
      <div className="technical-evidence__body">
        <div className="evidence-strip">
          <div>
            <span>当前运行</span>
            <strong title={bootstrap.run?.run_id}>{shortId(bootstrap.run?.run_id)}</strong>
          </div>
          <div>
            <span>排程版本</span>
            <strong title={schedule?.version.schedule_version_id}>
              {shortId(schedule?.version.schedule_version_id)}
            </strong>
          </div>
          <div>
            <span>数据边界</span>
            <strong>仅限合成仿真</strong>
          </div>
        </div>
        <div className="evidence-toolbar">
          <p>完整标识默认收起；复制内容不含令牌和内部异常。</p>
          <button className="button button--small" type="button" onClick={() => void copy()}>
            {copied ? "已复制诊断摘要" : "复制诊断摘要"}
          </button>
        </div>
        <pre tabIndex={0} aria-label="技术证据 JSON">
          {serialized}
        </pre>
      </div>
    </details>
  );
}
