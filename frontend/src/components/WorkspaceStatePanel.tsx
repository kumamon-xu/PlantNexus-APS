import { Alert, Empty, Skeleton } from "antd";

import type { WorkspaceUiState } from "../api/types";

const stateCopy: Record<
  Exclude<WorkspaceUiState, "loading" | "empty" | "ready">,
  { title: string; description: string; type: "error" | "warning" }
> = {
  stale: {
    title: "ScheduleVersion changed",
    description:
      "The server rejected the cached precondition. Refresh the authoritative Version before retrying.",
    type: "warning",
  },
  authorization_denied: {
    title: "Authorization denied",
    description:
      "The server did not grant this read. No cached or synthetic value is shown as a substitute.",
    type: "error",
  },
  contract_error: {
    title: "Contract error",
    description:
      "The request or response did not satisfy the versioned Planning Workspace contract.",
    type: "error",
  },
  server_error: {
    title: "Workspace unavailable",
    description:
      "The authoritative service could not provide this view. No zero value or success state was inferred.",
    type: "error",
  },
};

export interface WorkspaceStatePanelProps {
  state: WorkspaceUiState;
  detail?: string;
  emptyKind?: "missing" | "collection";
}

export function WorkspaceStatePanel({
  state,
  detail,
  emptyKind = "collection",
}: WorkspaceStatePanelProps) {
  if (state === "loading") {
    return (
      <div role="status" aria-label="Loading authoritative workspace data">
        <Skeleton active />
      </div>
    );
  }
  if (state === "empty") {
    const missing = emptyKind === "missing";
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <span>
            <strong>{missing ? "Resource not found" : "No matching items"}</strong>
            <br />
            {missing
              ? "The server returned found=false for this immutable identity."
              : "The server returned found=true with an empty item collection."}
          </span>
        }
      />
    );
  }
  if (state === "ready") return null;
  const copy = stateCopy[state];
  return (
    <Alert
      showIcon
      type={copy.type}
      message={copy.title}
      description={detail ?? copy.description}
      role="alert"
    />
  );
}
