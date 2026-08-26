import { useMemo, useRef, useState, type DragEvent, type UIEvent } from "react";
import { Link } from "react-router-dom";

import type { GanttSegment } from "../../api/types";

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

function groupLabel(segment: GanttSegment, grouping: GanttGrouping): string {
  if (grouping === "factory") return segment.factory_id ?? "Unspecified factory";
  if (grouping === "workshop") return segment.workshop_id ?? "Unspecified workshop";
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
    <section aria-label={`${grouping} Gantt projection`}>
      <p className="gantt-instructions">
        Visual rows are windowed. Open the accessible table for keyboard selection,
        exact raw UTC instants and Order/Operation links.
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
                <span className="gantt-row-label">{groupLabel(segment, grouping)}</span>
                <div
                  className={`gantt-segment${editable ? " is-editable" : ""}`}
                  data-operation-id={segment.operation_id}
                  data-editable={editable ? "true" : "false"}
                  draggable={editable}
                  onDragStart={(event) => beginDrag(event, segment)}
                  onDragEnd={(event) => finishDrag(event, segment)}
                  onClick={() => onSelect(segment)}
                  style={{ left, width }}
                  title={`${segment.operation_id} · ${segment.start_at_utc} → ${segment.end_at_utc}${editable ? " · drag proposes a bounded move" : ""}`}
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
        <summary>Accessible table view ({segments.length} operations)</summary>
        <div className="table-scroll">
          <table>
            <caption>
              Server-provided Gantt facts; select an operation for accessible manual
              controls or follow its related records.
            </caption>
            <thead>
              <tr>
                <th scope="col">Group</th>
                <th scope="col">Operation</th>
                <th scope="col">Order</th>
                <th scope="col">Resource</th>
                <th scope="col">Start UTC</th>
                <th scope="col">End UTC</th>
                <th scope="col">Status</th>
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
                    <td>{groupLabel(segment, grouping)}</td>
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
                      <time dateTime={segment.start_at_utc}>{segment.start_at_utc}</time>
                    </td>
                    <td>
                      <time dateTime={segment.end_at_utc}>{segment.end_at_utc}</time>
                    </td>
                    <td>
                      {isHighlighted ? "Selected or linked" : "Not selected"}{" "}
                      <Link to={`/operations?${search}`}>Operation record</Link>
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
