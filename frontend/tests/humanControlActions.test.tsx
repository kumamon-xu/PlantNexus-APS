import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import {
  WorkspaceClientError,
  type PlanningWorkspaceClient,
} from "../src/api/client";
import type { RuntimeConfig } from "../src/api/runtime";
import type {
  WorkspaceActionResult,
  WorkspaceCommandDocument,
} from "../src/api/types";
import { AppServicesProvider } from "../src/app/context";
import { GanttEditControls, ScheduleActionsPanel } from "../src/features/schedule-actions/ScheduleActionsPanel";
import { ganttPayload, syntheticDraftVersion } from "./fixtures";

const runtime: RuntimeConfig = {
  apiBaseUrl: "/api/v1",
  dataPlane: "SIMULATION",
  environment: "TEST",
  synthetic: true,
};

function resultFor(command: WorkspaceCommandDocument): WorkspaceActionResult {
  return {
    commandType: command.command_type,
    correlationId: command.correlation_id,
    auditEventId: "audit-ui-control-001",
    exactReplay: false,
    sourceVersion: {
      schedule_version_id: syntheticDraftVersion.schedule_version_id,
      state: syntheticDraftVersion.state,
      content_fingerprint: syntheticDraftVersion.content_fingerprint,
    },
    authoritativeVersion: {
      schedule_version_id: "schedule-version-sim-ui-new-001",
      state: "READY_FOR_REVIEW",
      content_fingerprint: `sha256:${"8".repeat(64)}`,
    },
    exportJob: null,
  };
}

function clientWith(
  executeCommand: PlanningWorkspaceClient["executeCommand"],
): PlanningWorkspaceClient {
  return {
    async getPlanningRun() {
      throw new Error("not used");
    },
    async getScheduleVersion() {
      return syntheticDraftVersion;
    },
    async getExportJob() {
      throw new Error("not used");
    },
    executeCommand,
    async downloadExportPackage() {
      throw new Error("not used");
    },
    async queryWorkspace() {
      throw new Error("not used");
    },
    async compareScheduleVersions() {
      throw new Error("not used");
    },
  };
}

function renderSubmit(
  executeCommand: PlanningWorkspaceClient["executeCommand"],
  refreshAuthority = vi.fn(async () => undefined),
) {
  const onActionResult = vi.fn(async () => undefined);
  render(
    <AppServicesProvider services={{ client: clientWith(executeCommand), runtime }}>
      <ScheduleActionsPanel
        version={syntheticDraftVersion}
        refreshAuthority={refreshAuthority}
        onActionResult={onActionResult}
      />
    </AppServicesProvider>,
  );
  return { onActionResult, refreshAuthority };
}

async function enterReason() {
  await userEvent.type(screen.getByLabelText("Submission reason"), "Ready for review");
}

describe("P3 human-control action state machine", () => {
  it("blocks double submit and reports success only after authoritative handling", async () => {
    let resolveCommand: ((value: WorkspaceActionResult) => void) | undefined;
    const executeCommand = vi.fn(
      (command: WorkspaceCommandDocument) =>
        new Promise<WorkspaceActionResult>((resolve) => {
          resolveCommand = resolve;
        }).then((result) => ({ ...result, correlationId: command.correlation_id })),
    );
    const { onActionResult } = renderSubmit(executeCommand);
    await enterReason();
    const submit = screen.getByRole("button", { name: "Submit for review" });
    fireEvent.click(submit);
    fireEvent.click(submit);
    await waitFor(() => expect(executeCommand).toHaveBeenCalledTimes(1));
    const command = executeCommand.mock.calls[0]?.[0];
    expect(command).toBeDefined();
    resolveCommand?.(resultFor(command!));
    await waitFor(() => expect(onActionResult).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("alert")).toHaveTextContent("Server confirmed");
  });

  it("refreshes authority and retries an unknown outcome with the exact same key", async () => {
    const seen: WorkspaceCommandDocument[] = [];
    const executeCommand = vi.fn(async (command: WorkspaceCommandDocument) => {
      seen.push(command);
      if (seen.length === 1) {
        throw new WorkspaceClientError(
          "server_error",
          "network outcome unknown",
          null,
          command.correlation_id,
        );
      }
      return { ...resultFor(command), exactReplay: true };
    });
    const refreshAuthority = vi.fn(async () => undefined);
    renderSubmit(executeCommand, refreshAuthority);
    await enterReason();
    await userEvent.click(screen.getByRole("button", { name: "Submit for review" }));
    await screen.findByText("Server outcome not assumed");
    const retry = screen.getByRole("button", { name: "Retry same request" });
    expect(retry).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Refresh authority" }));
    await waitFor(() => expect(retry).toBeEnabled());
    await userEvent.click(retry);
    await waitFor(() => expect(executeCommand).toHaveBeenCalledTimes(2));
    expect(refreshAuthority).toHaveBeenCalledTimes(1);
    expect(seen[1]?.idempotency_key).toBe(seen[0]?.idempotency_key);
    expect(seen[1]?.request_fingerprint).toBe(seen[0]?.request_fingerprint);
    expect(seen[1]?.command_id).toBe(seen[0]?.command_id);
  });

  it.each([
    [403, "authorization denied"],
    [409, "stale state"],
    [422, "validation failed"],
  ])("keeps HTTP %s failure visible and does not offer blind retry", async (status, message) => {
    renderSubmit(async (command) => {
      throw new WorkspaceClientError(
        status === 403 ? "authorization_denied" : status === 409 ? "stale" : "contract_error",
        message,
        status,
        command.correlation_id,
      );
    });
    await enterReason();
    await userEvent.click(screen.getByRole("button", { name: "Submit for review" }));
    await screen.findByText(message);
    expect(screen.queryByRole("button", { name: "Retry same request" })).toBeNull();
  });

  it("mounts no mutation buttons for a PUBLISHED Version", () => {
    const published = {
      ...syntheticDraftVersion,
      state: "PUBLISHED" as const,
      allowed_actions: ["view", "export", "audit"],
    };
    const segment = ganttPayload(0);
    render(
      <MemoryRouter>
        <AppServicesProvider services={{ client: clientWith(vi.fn()), runtime }}>
          <GanttEditControls
            version={published}
            segment={{ item_id: "gantt-1", ...segment } as never}
            refreshAuthority={async () => undefined}
            onActionResult={() => undefined}
          />
        </AppServicesProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Published history is immutable");
    expect(screen.queryByRole("button", { name: /move|assign|lock/iu })).toBeNull();
  });
});
