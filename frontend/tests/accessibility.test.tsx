import { render } from "@testing-library/react";
import axe from "axe-core";
import { MemoryRouter } from "react-router-dom";

import { parseGanttSegments } from "../src/api/contracts";
import { ScheduleVersionPanel } from "../src/components/ScheduleVersionPanel";
import { WorkspaceStatePanel } from "../src/components/WorkspaceStatePanel";
import { GanttTimeline } from "../src/features/gantt/GanttTimeline";
import { ganttPayload, testScheduleVersion, workspaceResponse } from "./fixtures";

describe("P3-11 accessibility foundation", () => {
  it("has no axe violations in the authority and error primitives", async () => {
    const { container } = render(
      <main>
        <ScheduleVersionPanel version={testScheduleVersion} />
        <WorkspaceStatePanel state="authorization_denied" />
      </main>,
    );
    const result = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});

describe("P3-12 visualization accessibility", () => {
  it("has no axe violations in the Gantt/table alternative", async () => {
    const response = await workspaceResponse("GANTT", {
      payloads: [ganttPayload(0), ganttPayload(1)],
      scheduleVersion: testScheduleVersion,
    });
    const { container } = render(
      <MemoryRouter>
        <main>
          <GanttTimeline
            segments={parseGanttSegments(response)}
            grouping="factory"
            scheduleVersionId={testScheduleVersion.schedule_version_id}
            zoom={1}
            selection={{ operationId: null, orderId: null, resourceId: null }}
            onSelect={() => undefined}
          />
        </main>
      </MemoryRouter>,
    );
    const result = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});
