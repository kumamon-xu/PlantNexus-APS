import { useMemo, useRef, useState, type DragEvent, type UIEvent } from "react";
import { Link } from "react-router-dom";

import type { GanttSegment } from "../../api/types";
import { formatUtc } from "../../i18n/formatters";
import { useLocale } from "../../i18n/locale";

export type GanttGrouping = "factory" | "workshop" | "machine";

interface GanttSelection {
  operationId: string | null;
  orderId: string | null;
  resourceId: string | null;
}

export interface GanttTimelineProps {
  segments: GanttSegment[];
  grouping: GanttGrouping;
  scheduleVersionId: string;
  zoom: number;
  selection: GanttSelection;
  editable?: boolean;
  onSelect(segment: GanttSegment): void;
  onMoveIntent?(segment: GanttSegment, offsetSeconds: number): void;
}

const rowHeight = 48;
const viewportHeight = 384;
const overscan = 4;
const labelWidth = 240;

function groupLabel(
  segment: GanttSegment,
  grouping: GanttGrouping,
  unspecifiedFactory: string,
  unspecifiedWorkshop: string,
): string {
  if (grouping === "factory") return segment.factory_id ?? unspecifiedFactory;
  if (grouping === "workshop") return segment.workshop_id ?? unspecifiedWorkshop;
  return `${segment.resource_code} · ${segment.resource_id}`;
}

function highlighted(segment: GanttSegment, selection: GanttSelection): boolean {
  if (selection.operationId !== null) {
    return segment.operation_id === selection.operationId;
  }
  if (selection.orderId !== null && segment.order_id === selection.orderId) return true;
  return selection.resourceId !== null && segment.resource_id === selection.resourceId;
}

export function GanttTimeline({
  segments,
  grouping,
  scheduleVersionId,
  zoom,
  selection,
  editable = false,
  onSelect,
  onMoveIntent,
}: GanttTimelineProps) {
  const { locale, t } = useLocale();
  const [scrollTop, setScrollTop] = useState(0);
  const dragStartX = useRef<number | null>(null);
  const timeRange = useMemo(() => {
    const starts = segments.map((segment) => Date.parse(segment.start_at_utc));
    const ends = segments.map((segment) => Date.parse(segment.end_at_utc));
    return {
      start: Math.min(...starts),
      end: Math.max(...ends),
    };
  }, [segments]);
  const timelineWidth = Math.max(
    960,
    Math.ceil(
      (Math.max(1, timeRange.end - timeRange.start) / 3_600_000) * 96 * zoom,
    ),
  );
  const firstRow = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visibleCount = Math.ceil(viewportHeight / rowHeight) + overscan * 2;
  const visible = segments.slice(firstRow, firstRow + visibleCount);

  function onScroll(event: UIEvent<HTMLDivElement>) {
    setScrollTop(event.currentTarget.scrollTop);
  }

  function beginDrag(event: DragEvent<HTMLDivElement>, segment: GanttSegment) {
    if (!editable || !Number.isFinite(event.clientX)) {
      event.preventDefault();
      return;
    }
    dragStartX.current = event.clientX;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", segment.operation_id);
    onSelect(segment);
  }

  function finishDrag(event: DragEvent<HTMLDivElement>, segment: GanttSegment) {
    const startX = dragStartX.current;
    dragStartX.current = null;
    if (
      !editable ||
      startX === null ||
      !Number.isFinite(event.clientX) ||
      onMoveIntent === undefined
    )
      return;
    const spanSeconds = Math.max(1, timeRange.end - timeRange.start) / 1000;
    const rawOffset = ((event.clientX - startX) / timelineWidth) * spanSeconds;
    const quantized = Math.round(rawOffset / 300) * 300;
    const bounded = Math.max(-86_400, Math.min(86_400, quantized));
    if (bounded !== 0) onMoveIntent(segment, bounded);
  }

  return (
    <section aria-label={t(grouping === "factory" ? "gantt.factoryTitle" : grouping === "workshop" ? "gantt.workshopTitle" : "gantt.machineTitle")}>
      <p className="gantt-instructions">
        {t("gantt.instructions")}
      </p>
      <div
        className="gantt-viewport"
        data-testid="gantt-viewport"
        data-total-row-count={segments.length}
        data-rendered-row-count={visible.length}
        onScroll={onScroll}
      >
        <div
          className="gantt-canvas"
          style={{ height: segments.length * rowHeight, width: timelineWidth + labelWidth }}
          aria-hidden="true"
        >
          {visible.map((segment, visibleIndex) => {
            const rowIndex = firstRow + visibleIndex;
            const left =
              labelWidth +
              ((Date.parse(segment.start_at_utc) - timeRange.start) /
                (timeRange.end - timeRange.start)) *
                timelineWidth;
            const width = Math.max(
              6,
              ((Date.parse(segment.end_at_utc) - Date.parse(segment.start_at_utc)) /
                (timeRange.end - timeRange.start)) *
                timelineWidth,
            );
            const isHighlighted = highlighted(segment, selection);
            return (
              <div
                className={`gantt-row${isHighlighted ? " is-highlighted" : ""}`}
                key={segment.item_id}
                style={{ top: rowIndex * rowHeight, height: rowHeight }}
              >
                <span className="gantt-row-label">{groupLabel(segment, grouping, t("gantt.unspecifiedFactory"), t("gantt.unspecifiedWorkshop"))}</span>
                <div
                  className={`gantt-segment${editable ? " is-editable" : ""}`}
                  data-operation-id={segment.operation_id}
                  data-editable={editable ? "true" : "false"}
                  draggable={editable}
                  onDragStart={(event) => beginDrag(event, segment)}
                  onDragEnd={(event) => finishDrag(event, segment)}
                  onClick={() => onSelect(segment)}
                  style={{ left, width }}
                  title={`${segment.operation_id} · ${segment.start_at_utc} → ${segment.end_at_utc}${editable ? ` · ${t("gantt.dragTitle")}` : ""}`}
                >
                  {isHighlighted ? "● " : ""}
                  {segment.operation_id}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <details className="accessible-fallback">
        <summary>{t("gantt.tableSummary", { count: segments.length })}</summary>
        <div className="table-scroll">
          <table>
            <caption>
              {t("gantt.tableCaption")}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t("gantt.group")}</th>
                <th scope="col">{t("gantt.operation")}</th>
                <th scope="col">{t("gantt.order")}</th>
                <th scope="col">{t("gantt.resource")}</th>
                <th scope="col">{t("gantt.startUtc")}</th>
                <th scope="col">{t("gantt.endUtc")}</th>
                <th scope="col">{t("gantt.status")}</th>
              </tr>
            </thead>
            <tbody>
              {segments.map((segment) => {
                const isHighlighted = highlighted(segment, selection);
                const search = new URLSearchParams({
                  schedule_version_id: scheduleVersionId,
                  operation_id: segment.operation_id,
                });
                return (
                  <tr key={segment.item_id} className={isHighlighted ? "is-highlighted" : ""}>
                    <td>{groupLabel(segment, grouping, t("gantt.unspecifiedFactory"), t("gantt.unspecifiedWorkshop"))}</td>
                    <td>
                      <button type="button" onClick={() => onSelect(segment)}>
                        {segment.operation_id}
                      </button>
                    </td>
                    <td>
                      <Link
                        to={`/planning/versions/${encodeURIComponent(scheduleVersionId)}/orders?order_id=${encodeURIComponent(segment.order_id)}`}
                      >
                        {segment.order_id}
                      </Link>
                    </td>
                    <td>
                      <Link
                        to={`/resources?schedule_version_id=${encodeURIComponent(scheduleVersionId)}&resource_id=${encodeURIComponent(segment.resource_id)}`}
                      >
                        {segment.resource_code}
                      </Link>
                    </td>
                    <td>
                      <time dateTime={segment.start_at_utc}>
                        {formatUtc(segment.start_at_utc, locale).display}
                        <code className="localized-raw">{segment.start_at_utc}</code>
                      </time>
                    </td>
                    <td>
                      <time dateTime={segment.end_at_utc}>
                        {formatUtc(segment.end_at_utc, locale).display}
                        <code className="localized-raw">{segment.end_at_utc}</code>
                      </time>
                    </td>
                    <td>
                      {isHighlighted ? t("gantt.selectedLinked") : t("gantt.notSelected")}{" "}
                      <Link to={`/operations?${search}`}>{t("gantt.operationRecord")}</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
