import { render } from "@testing-library/react";
import axe from "axe-core";

import { ScheduleVersionPanel } from "../src/components/ScheduleVersionPanel";
import { WorkspaceStatePanel } from "../src/components/WorkspaceStatePanel";
import { testScheduleVersion } from "./fixtures";

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
