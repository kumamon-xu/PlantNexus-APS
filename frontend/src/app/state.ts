import { WorkspaceClientError } from "../api/client";
import type { WorkspaceUiState } from "../api/types";

export function stateForError(error: unknown): {
  state: WorkspaceUiState;
  detail: string;
} {
  if (error instanceof WorkspaceClientError) {
    const suffix = error.correlationId
      ? ` Correlation: ${error.correlationId}`
      : "";
    return { state: error.kind, detail: `${error.message}${suffix}` };
  }
  return {
    state: "contract_error",
    detail: "The read-only consumer rejected an unexpected error shape.",
  };
}
