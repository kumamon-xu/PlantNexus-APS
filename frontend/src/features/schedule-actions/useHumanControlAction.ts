import { useCallback, useRef, useState } from "react";

import { WorkspaceClientError } from "../../api/client";
import type {
  ScheduleVersion,
  WorkspaceActionResult,
  WorkspaceCommandDocument,
} from "../../api/types";
import { useAppServices } from "../../app/context";

export type HumanControlPhase =
  | "idle"
  | "pending"
  | "success"
  | "error"
  | "outcome_unknown"
  | "refreshing";

export interface HumanControlFeedback {
  phase: HumanControlPhase;
  detail: string | null;
  correlationId: string | null;
  result: WorkspaceActionResult | null;
  retryReady: boolean;
}

interface UseHumanControlActionOptions {
  refreshAuthority(): Promise<void>;
  onSuccess(result: WorkspaceActionResult): Promise<void> | void;
}

const initialFeedback: HumanControlFeedback = {
  phase: "idle",
  detail: null,
  correlationId: null,
  result: null,
  retryReady: false,
};

export function serverAllows(
  version: ScheduleVersion,
  capability: string,
): boolean {
  return version.allowed_actions.some((value) => value === capability);
}

export function useHumanControlAction({
  refreshAuthority,
  onSuccess,
}: UseHumanControlActionOptions) {
  const { client } = useAppServices();
  const [feedback, setFeedback] = useState<HumanControlFeedback>(initialFeedback);
  const retained = useRef<WorkspaceCommandDocument | null>(null);
  const inFlight = useRef(false);

  const execute = useCallback(
    async (command: WorkspaceCommandDocument) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setFeedback({
        ...initialFeedback,
        phase: "pending",
        detail: `Submitting ${command.command_type} to server authority…`,
        correlationId: command.correlation_id,
      });
      try {
        const result = await client.executeCommand(command);
        await onSuccess(result);
        retained.current = null;
        setFeedback({
          phase: "success",
          detail: `Server confirmed ${command.command_type}; authoritative state was refreshed.`,
          correlationId: result.correlationId,
          result,
          retryReady: false,
        });
      } catch (error) {
        const failure =
          error instanceof WorkspaceClientError
            ? error
            : new WorkspaceClientError(
                "contract_error",
                "Human-control response failed its contract",
                200,
                command.correlation_id,
              );
        const outcomeUnknown = failure.status === null || failure.status >= 500;
        retained.current = outcomeUnknown ? command : null;
        setFeedback({
          phase: outcomeUnknown ? "outcome_unknown" : "error",
          detail: outcomeUnknown
            ? "Outcome is unknown. Refresh server authority before retrying with the same idempotency key."
            : failure.message,
          correlationId: failure.correlationId ?? command.correlation_id,
          result: null,
          retryReady: false,
        });
      } finally {
        inFlight.current = false;
      }
    },
    [client, onSuccess],
  );

  const refreshForRetry = useCallback(async () => {
    if (retained.current === null || inFlight.current) return;
    inFlight.current = true;
    setFeedback((current) => ({
      ...current,
      phase: "refreshing",
      detail: "Refreshing authoritative state before an idempotent retry…",
    }));
    try {
      await refreshAuthority();
      setFeedback((current) => ({
        ...current,
        phase: "outcome_unknown",
        detail: "Authority refreshed. Retry will reuse the original idempotency key.",
        retryReady: true,
      }));
    } catch {
      setFeedback((current) => ({
        ...current,
        phase: "outcome_unknown",
        detail: "Authority refresh failed; retry remains blocked.",
        retryReady: false,
      }));
    } finally {
      inFlight.current = false;
    }
  }, [refreshAuthority]);

  const retry = useCallback(async () => {
    const command = retained.current;
    if (command === null || !feedback.retryReady) return;
    await execute(command);
  }, [execute, feedback.retryReady]);

  const reset = useCallback(() => {
    if (inFlight.current) return;
    retained.current = null;
    setFeedback(initialFeedback);
  }, []);

  return {
    feedback,
    execute,
    refreshForRetry,
    retry,
    reset,
    pending: feedback.phase === "pending" || feedback.phase === "refreshing",
  };
}
