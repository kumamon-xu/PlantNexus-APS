import { Alert, Select } from "antd";
import { useState } from "react";
import { isJsonObject } from "../../api/contracts";
import type { ScheduleVersion, WorkspaceActionResult } from "../../api/types";
import { useLocale } from "../../i18n/locale";
import { GanttEditControls } from "./ScheduleActionsPanel";

export function ManualVersionEditor({ version, refreshAuthority, onActionResult }: {
  version: ScheduleVersion;
  refreshAuthority(): Promise<void>;
  onActionResult(result: WorkspaceActionResult): Promise<void>;
}) {
  const { locale } = useLocale();
  const [selected, setSelected] = useState<string | null>(null);
  if (version.schedule_version_version !== "schedule-version.v1" || version.state !== "DRAFT") return null;
  const rows = isJsonObject(version.content) ? version.content.assignments : null;
  if (!Array.isArray(rows) || rows.some((row) => !isJsonObject(row) || ["operation_id", "resource_id", "start_at_utc", "end_at_utc"].some((key) => typeof row[key] !== "string"))) {
    return <Alert type="error" title="CONTRACT_REJECTED: schedule assignments" />;
  }
  const assignments = rows as Array<{ operation_id: string; resource_id: string; start_at_utc: string; end_at_utc: string }>;
  const segment = assignments.find((row) => row.operation_id === selected);
  return <section>
    <label>{locale === "zh-CN" ? "人工调整工序" : "Manual operation"}
      <Select virtual={false} aria-label="Manual operation" style={{ minWidth: 280 }} value={selected} onChange={setSelected} options={assignments.map((row) => ({ label: row.operation_id, value: row.operation_id }))} />
    </label>
    {segment && <GanttEditControls key={`${version.schedule_version_id}:${segment.operation_id}`} version={version} segment={segment} refreshAuthority={refreshAuthority} onActionResult={onActionResult} />}
  </section>;
}
