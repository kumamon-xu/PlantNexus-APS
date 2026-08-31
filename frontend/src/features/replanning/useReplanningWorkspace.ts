import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { ContractViolation } from "../../api/contracts";
import type { RuntimeConfig } from "../../api/runtime";
import { useAppServices } from "../../app/context";
import { ReplanningClientError, type DynamicReplanningClient } from "./client";
import {
  buildChangeReportQuery,
  buildReplanAttemptAction,
  buildRequestQuery,
  buildResultQuery,
  buildTimelineQuery,
} from "./query";
import type {
  ReplanActionRequest,
  ReplanAttemptAction,
  ReplanningWorkspaceIdentity,
  ReplanningWorkspaceProjection,
} from "./types";

export type ReplanActionPhase =
  | "idle"
  | "submitting"
  | "confirmed"
  | "outcome_unknown"
  | "refreshing"
  | "retry_ready"
  | "resolved_by_refresh"
  | "failed";

export interface ReplanActionFeedback {
  phase: ReplanActionPhase;
  action: ReplanAttemptAction | null;
  message: string | null;
  correlationId: string | null;
}

const idleFeedback: ReplanActionFeedback = {
  phase: "idle",
  action: null,
  message: null,
  correlationId: null,
};

export async function loadReplanningWorkspace(
  client: DynamicReplanningClient,
  runtime: RuntimeConfig,
  identity: ReplanningWorkspaceIdentity,
): Promise<ReplanningWorkspaceProjection> {
  const [timelineQuery, requestQuery, resultQuery] = await Promise.all([
    buildTimelineQuery(runtime, identity),
    buildRequestQuery(runtime, identity),
    buildResultQuery(runtime, identity),
  ]);
  const [timeline, request, result] = await Promise.all([
    client.listExecutionEvents(timelineQuery),
    client.getReplanRequest(requestQuery),
    client.getReplanResult(resultQuery),
  ]);
  if (
    request.attempt.attempt_id !== identity.attemptId ||
    request.attempt.attempt_id !== result.attempt_id ||
    request.attempt.attempt_number !== result.attempt_number ||
    request.attempt.planning_run_id !== result.planning_run_id ||
    request.attempt.state !== result.planning_run_state
  ) {
    throw new ContractViolation(
      "replanning_workspace.attempt",
      "request and result projections disagree",
    );
  }
  let report = null;
  if (result.change_report !== null) {
    const reportQuery = await buildChangeReportQuery(
      runtime,
      identity,
      result.change_report.report_id,
      result.change_report.report_fingerprint,
    );
    report = await client.getChangeReport(reportQuery);
    if (
      report.report.new_schedule_version.schedule_version_id !==
        result.new_schedule_version?.schedule_version_id ||
      report.report.new_schedule_version.content_fingerprint !==
        result.new_schedule_version?.content_fingerprint
    ) {
      throw new ContractViolation(
        "replanning_workspace.change_report",
        "report and result ScheduleVersion lineage disagree",
      );
    }
  }
  return { timeline, request, result, report };
}

export function useReplanningWorkspace(identity: ReplanningWorkspaceIdentity | null) {
  const { dynamicReplanningClient, runtime } = useAppServices();
  const [feedback, setFeedback] = useState<ReplanActionFeedback>(idleFeedback);
  const retained = useRef<ReplanActionRequest | null>(null);
  const inFlight = useRef(false);
  const enabled = identity !== null && dynamicReplanningClient !== undefined;
  const query = useQuery({
    queryKey: [
      "p4-replanning-workspace",
      identity?.planningScopeId,
      identity?.authorityId,
      identity?.streamId,
      identity?.streamVersion,
      identity?.fromPosition,
      identity?.throughPosition,
      identity?.requestId,
      identity?.requestFingerprint,
      identity?.attemptId,
    ],
    enabled,
    queryFn: () => {
      if (identity === null || dynamicReplanningClient === undefined) {
        throw new TypeError("P4 dynamic replanning client is unavailable");
      }
      return loadReplanningWorkspace(dynamicReplanningClient, runtime, identity);
    },
    retry: false,
    refetchOnWindowFocus: false,
  });

  const submit = async (actionRequest: ReplanActionRequest, retry: boolean) => {
    if (dynamicReplanningClient === undefined || inFlight.current) return;
    inFlight.current = true;
    setFeedback({
      phase: "submitting",
      action: actionRequest.document.action,
      message: retry ? "retrying exact retained request" : null,
      correlationId: actionRequest.document.correlation_id,
    });
    try {
      await dynamicReplanningClient.executeAttemptAction(actionRequest);
      retained.current = null;
      await query.refetch();
      setFeedback({
        phase: "confirmed",
        action: actionRequest.document.action,
        message: null,
        correlationId: actionRequest.document.correlation_id,
      });
    } catch (error) {
      if (error instanceof ReplanningClientError && error.outcomeUnknown) {
        retained.current = actionRequest;
        setFeedback({
          phase: "outcome_unknown",
          action: actionRequest.document.action,
          message: error.message,
          correlationId: error.correlationId,
        });
      } else {
        retained.current = null;
        setFeedback({
          phase: "failed",
          action: actionRequest.document.action,
          message: error instanceof Error ? error.message : "replan action failed",
          correlationId:
            error instanceof ReplanningClientError ? error.correlationId : null,
        });
      }
    } finally {
      inFlight.current = false;
    }
  };

  const execute = async (action: ReplanAttemptAction, reason: string) => {
    if (
      identity === null ||
      query.data === undefined ||
      dynamicReplanningClient === undefined ||
      inFlight.current
    ) {
      return;
    }
    try {
      const actionRequest = await buildReplanAttemptAction(runtime, {
        action,
        requestId: identity.requestId,
        requestFingerprint: identity.requestFingerprint,
        attempt: query.data.request.attempt,
        planningScopeId: identity.planningScopeId,
        reason,
      });
      await submit(actionRequest, false);
    } catch (error) {
      setFeedback({
        phase: "failed",
        action,
        message: error instanceof Error ? error.message : "replan action contract failed",
        correlationId: null,
      });
    }
  };

  const refreshAuthority = async () => {
    const actionRequest = retained.current;
    if (actionRequest === null || inFlight.current) return;
    setFeedback({
      phase: "refreshing",
      action: actionRequest.document.action,
      message: null,
      correlationId: actionRequest.document.correlation_id,
    });
    const refreshed = await query.refetch();
    if (refreshed.error !== null || refreshed.data === undefined) {
      setFeedback({
        phase: "outcome_unknown",
        action: actionRequest.document.action,
        message: "authoritative refresh failed; retry remains blocked",
        correlationId: actionRequest.document.correlation_id,
      });
      return;
    }
    const attempt = refreshed.data.request.attempt;
    const unchanged =
      attempt.attempt_id === actionRequest.document.expected_attempt_id &&
      attempt.attempt_number === actionRequest.document.expected_attempt_number &&
      attempt.state === actionRequest.document.expected_planning_run_state &&
      attempt.allowed_actions.includes(actionRequest.document.action);
    if (unchanged) {
      setFeedback({
        phase: "retry_ready",
        action: actionRequest.document.action,
        message: null,
        correlationId: actionRequest.document.correlation_id,
      });
    } else {
      retained.current = null;
      setFeedback({
        phase: "resolved_by_refresh",
        action: actionRequest.document.action,
        message: null,
        correlationId: actionRequest.document.correlation_id,
      });
    }
  };

  const retrySameRequest = async () => {
    if (feedback.phase !== "retry_ready" || retained.current === null) return;
    await submit(retained.current, true);
  };

  return {
    query,
    configured: dynamicReplanningClient !== undefined,
    feedback,
    execute,
    refreshAuthority,
    retrySameRequest,
    resetFeedback: () => setFeedback(idleFeedback),
  };
}
