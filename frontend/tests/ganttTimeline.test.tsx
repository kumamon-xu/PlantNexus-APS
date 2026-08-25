import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { parseGanttSegments } from "../src/api/contracts";
import { GanttTimeline } from "../src/features/gantt/GanttTimeline";
import { ganttPayload, testScheduleVersion, workspaceResponse } from "./fixtures";

describe("virtualized accessible Gantt", () => {
  it("windows a 120-row synthetic projection and preserves the full table fallback", async () => {
    const syntheticSegmentCount = 120;
    const response = await workspaceResponse("GANTT", {
      payloads: Array.from({ length: syntheticSegmentCount }, (_, index) =>
        ganttPayload(index),
      ),
      scheduleVersion: testScheduleVersion,
    });
    const segments = parseGanttSegments(response);
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <GanttTimeline
          segments={segments}
          grouping="machine"
          scheduleVersionId={testScheduleVersion.schedule_version_id}
          zoom={1}
          selection={{ operationId: null, orderId: null, resourceId: null }}
          onSelect={onSelect}
        />
      </MemoryRouter>,
    );

    const viewport = screen.getByTestId("gantt-viewport");
    expect(viewport).toHaveAttribute("data-total-row-count", "120");
    expect(Number(viewport.getAttribute("data-rendered-row-count"))).toBeLessThanOrEqual(24);
    expect(viewport.querySelectorAll(".gantt-row").length).toBeLessThanOrEqual(24);

    fireEvent.click(screen.getByText("Accessible table view (120 operations)"));
    fireEvent.click(screen.getByRole("button", { name: "operation-test-120" }));
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ operation_id: "operation-test-120" }),
    );
    expect(screen.getAllByRole("link", { name: "Operation record" })).toHaveLength(120);
  });
});
