import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DemoClientError, type DemoApi } from "../api/client";
import { DemoContractError } from "../api/contracts";
import type {
  BaselineActivationRequest,
  DemoBootstrap,
  DemoJob,
  DemoScheduleSummary,
  UrgentOrderCommand,
  UrgentOrderInput,
} from "../api/types";
import { noticeFor, type UiNotice } from "../domain/copy";
import { CommandIdentityStore } from "./commandIdentity";

export type ConfirmationKind = "RESET" | "ACTIVATE" | null;

export interface DemoStoryOptions {
  readonly pollIntervalMs?: number;
  readonly profile?: "smoke" | "showcase";
  readonly commandStore?: CommandIdentityStore;
}

export interface DemoStoryController {
  readonly bootstrap: DemoBootstrap | null;
  readonly schedule: DemoScheduleSummary | null;
  readonly job: DemoJob | null;
  readonly connecting: boolean;
  readonly submitting: boolean;
  readonly pollingJobId: string | null;
  readonly notice: UiNotice | null;
  readonly confirmation: ConfirmationKind;
  readonly lastSyncedAt: number | null;
  readonly isBusy: boolean;
  readonly pendingUrgentOrder: UrgentOrderCommand | null;
  reconnect(): Promise<void>;
  refresh(): Promise<void>;
  requestReset(): void;
  startInitialPlan(): Promise<void>;
  requestActivation(): void;
  submitUrgentOrder(input: UrgentOrderInput): Promise<boolean>;
  confirmAction(): Promise<void>;
  cancelConfirmation(): void;
  dismissNotice(): void;
}

const terminalStatuses = new Set([
  "SUCCEEDED",
  "FAILED",
  "INTERRUPTED",
  "CANCELLED",
]);

function activeJobId(bootstrap: DemoBootstrap): string | null {
  if (typeof bootstrap.active_job === "string") return bootstrap.active_job;
  return bootstrap.active_job?.job_id ?? null;
}

function pendingJobMatches(
  bootstrap: DemoBootstrap,
  job: ReturnType<CommandIdentityStore["pendingJob"]>,
): boolean {
  if (job === null) return false;
  if (job.job_kind === "RESET") {
    return bootstrap.run === null || bootstrap.run.run_id === job.run_id;
  }
  return bootstrap.run !== null && bootstrap.run.run_id === job.run_id;
}

function jobFailure(job: DemoJob): DemoClientError {
  return new DemoClientError(
    job.error_code ?? "JOB_EXECUTION_FAILED",
    "job",
    job.correlation_id,
    null,
  );
}

export function useDemoStory(
  api: DemoApi,
  options: DemoStoryOptions = {},
): DemoStoryController {
  const pollIntervalMs = options.pollIntervalMs ?? 800;
  const profile = options.profile ?? "showcase";
  const commandStoreRef = useRef(
    options.commandStore ?? new CommandIdentityStore(),
  );
  const mutationInFlightRef = useRef(false);
  const [bootstrap, setBootstrap] = useState<DemoBootstrap | null>(null);
  const [schedule, setSchedule] = useState<DemoScheduleSummary | null>(null);
  const [job, setJob] = useState<DemoJob | null>(null);
  const [connecting, setConnecting] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const [notice, setNotice] = useState<UiNotice | null>(null);
  const [confirmation, setConfirmation] = useState<ConfirmationKind>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(null);
  const [pendingUrgentOrder, setPendingUrgentOrder] =
    useState<UrgentOrderCommand | null>(null);

  const hydrate = useCallback(async () => {
    const next = await api.bootstrap();
    let nextSchedule: DemoScheduleSummary | null = null;
    if (next.schedule_version !== null) {
      nextSchedule = await api.getScheduleSummary(
        next.schedule_version.schedule_version_id,
      );
      if (
        nextSchedule.run_id !== next.run?.run_id ||
        nextSchedule.version.schedule_version_id !==
          next.schedule_version.schedule_version_id ||
        nextSchedule.version.content_fingerprint !==
          next.schedule_version.content_fingerprint
      ) {
        throw new DemoContractError("bootstrap.schedule_lineage");
      }
    }
    const activeId = activeJobId(next);
    const storedPending = commandStoreRef.current.pendingJob();
    let recoveredJobId = activeId;
    if (recoveredJobId === null && pendingJobMatches(next, storedPending)) {
      recoveredJobId = storedPending?.job_id ?? null;
    } else if (storedPending !== null && !pendingJobMatches(next, storedPending)) {
      commandStoreRef.current.clearPendingJob(storedPending.job_id);
    }
    setBootstrap(next);
    setSchedule(nextSchedule);
    setPollingJobId(recoveredJobId);
    if (next.run === null || next.story_state === "DRAFT_COMPARISON_READY") {
      if (next.run !== null) commandStoreRef.current.clearUrgentOrder(next.run.run_id);
      setPendingUrgentOrder(null);
    } else {
      setPendingUrgentOrder(
        commandStoreRef.current.urgentOrder(next.run.run_id)?.request ?? null,
      );
    }
    setLastSyncedAt(Date.now());
  }, [api]);

  const reconnect = useCallback(async () => {
    setConnecting(true);
    setNotice(null);
    try {
      await api.establishSession();
      await hydrate();
    } catch (error) {
      setNotice(noticeFor(error));
    } finally {
      setConnecting(false);
    }
  }, [api, hydrate]);

  const refresh = useCallback(async () => {
    setNotice(null);
    try {
      await hydrate();
    } catch (error) {
      setNotice(noticeFor(error));
    }
  }, [hydrate]);

  useEffect(() => {
    const timer = window.setTimeout(() => void reconnect(), 0);
    return () => window.clearTimeout(timer);
  }, [reconnect]);

  useEffect(() => {
    if (pollingJobId === null) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const current = await api.getJob(pollingJobId);
        if (cancelled) return;
        setJob(current);
        if (terminalStatuses.has(current.status)) {
          commandStoreRef.current.clearPendingJob(current.job_id);
          setPollingJobId(null);
          if (current.status !== "SUCCEEDED") {
            setNotice(noticeFor(jobFailure(current)));
          }
          await hydrate();
          return;
        }
      } catch (error) {
        if (cancelled) return;
        setNotice(noticeFor(error));
        if (
          error instanceof DemoContractError ||
          (error instanceof DemoClientError && error.code === "JOB_NOT_FOUND")
        ) {
          commandStoreRef.current.clearPendingJob(pollingJobId);
          setPollingJobId(null);
          return;
        }
      }
      if (!cancelled) timer = setTimeout(() => void poll(), pollIntervalMs);
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [api, hydrate, pollIntervalMs, pollingJobId]);

  const submitJob = useCallback(
    async (operation: "reset" | "initial-plan") => {
      if (mutationInFlightRef.current) return;
      mutationInFlightRef.current = true;
      setSubmitting(true);
      setNotice(null);
      try {
        const runId = bootstrap?.run?.run_id ?? "empty";
        const key = commandStoreRef.current.getOrCreate(operation, runId);
        const accepted =
          operation === "reset"
            ? await api.reset(profile, key)
            : await api.createInitialPlan(runId, key);
        commandStoreRef.current.savePendingJob(accepted);
        setPollingJobId(accepted.job_id);
      } catch (error) {
        setNotice(noticeFor(error));
      } finally {
        mutationInFlightRef.current = false;
        setSubmitting(false);
      }
    },
    [api, bootstrap, profile],
  );

  const requestReset = useCallback(() => {
    if (bootstrap?.run === null || bootstrap === null) {
      void submitJob("reset");
      return;
    }
    setConfirmation("RESET");
  }, [bootstrap, submitJob]);

  const startInitialPlan = useCallback(async () => {
    if (bootstrap?.run === null || bootstrap?.run === undefined) {
      setNotice(noticeFor(new DemoClientError("DEMO_NOT_INITIALIZED", "run", null, 404)));
      return;
    }
    await submitJob("initial-plan");
  }, [bootstrap?.run, submitJob]);

  const requestActivation = useCallback(() => {
    if (schedule === null || bootstrap?.run === null || bootstrap?.run === undefined) {
      setNotice(noticeFor(new DemoContractError("activation.schedule")));
      return;
    }
    if (
      schedule.version.state === "APPROVED" &&
      commandStoreRef.current.activation(schedule.version.schedule_version_id) === null
    ) {
      setNotice({
        title: "无法安全恢复发布",
        detail: "页面缺少原批准操作的幂等身份，系统不会生成新的发布身份。请保留现场并查看技术证据。",
        correlationId: bootstrap.correlation_id,
      });
      return;
    }
    setConfirmation("ACTIVATE");
  }, [bootstrap, schedule]);

  const activate = useCallback(async () => {
    if (mutationInFlightRef.current) return;
    if (schedule === null || bootstrap?.run === null || bootstrap?.run === undefined) {
      setNotice(noticeFor(new DemoContractError("activation.schedule")));
      return;
    }
    const versionId = schedule.version.schedule_version_id;
    let stored = commandStoreRef.current.activation(versionId);
    if (stored === null) {
      const request: BaselineActivationRequest = {
        command_version: "cnc-demo-baseline-activation.v1",
        expected_run_id: bootstrap.run.run_id,
        schedule_version_id: versionId,
        content_fingerprint: schedule.version.content_fingerprint,
        expected_state_revision: schedule.version.revision,
        confirmation: "ACTIVATE_SIMULATION_BASELINE",
      };
      stored = {
        idempotencyKey: commandStoreRef.current.getOrCreate(
          "activate",
          versionId,
        ),
        request,
      };
      commandStoreRef.current.saveActivation(stored);
    }
    mutationInFlightRef.current = true;
    setSubmitting(true);
    setNotice(null);
    try {
      await api.activateBaseline(stored.request, stored.idempotencyKey);
      await hydrate();
      commandStoreRef.current.clearActivation(versionId);
    } catch (error) {
      setNotice(noticeFor(error));
      try {
        await hydrate();
      } catch {
        // The original sanitized action error remains the useful UI boundary.
      }
    } finally {
      mutationInFlightRef.current = false;
      setSubmitting(false);
    }
  }, [api, bootstrap, hydrate, schedule]);

  const submitUrgentOrder = useCallback(
    async (input: UrgentOrderInput): Promise<boolean> => {
      if (mutationInFlightRef.current) return false;
      const run = bootstrap?.run;
      const publication = bootstrap?.current_publication;
      if (
        bootstrap === null ||
        run === null ||
        run === undefined ||
        publication === null ||
        publication === undefined ||
        bootstrap.story_state !== "BASELINE_PUBLISHED"
      ) {
        setNotice(
          noticeFor(
            new DemoClientError("STALE_BASE_VERSION", "schedule_version", null, 409),
          ),
        );
        return false;
      }
      const request: UrgentOrderCommand = {
        command_version: "cnc-demo-urgent-order-command.v1",
        expected_run_id: run.run_id,
        expected_base_version_id: publication.schedule_version_id,
        ...input,
      };
      let stored = commandStoreRef.current.urgentOrder(run.run_id);
      if (stored === null) {
        stored = {
          idempotencyKey: commandStoreRef.current.getOrCreate(
            "urgent",
            run.run_id,
          ),
          request,
        };
        commandStoreRef.current.saveUrgentOrder(stored);
        setPendingUrgentOrder(request);
      } else if (JSON.stringify(stored.request) !== JSON.stringify(request)) {
        setNotice(
          noticeFor(
            new DemoClientError(
              "IDEMPOTENCY_CONFLICT",
              "urgent_order",
              bootstrap.correlation_id,
              409,
            ),
          ),
        );
        return false;
      }
      mutationInFlightRef.current = true;
      setSubmitting(true);
      setNotice(null);
      try {
        const accepted = await api.submitUrgentOrder(
          stored.request,
          stored.idempotencyKey,
        );
        if (accepted.job_kind !== "URGENT_REPLAN" || accepted.run_id !== run.run_id) {
          throw new DemoContractError("urgent.job_accepted.lineage");
        }
        commandStoreRef.current.savePendingJob(accepted);
        setPollingJobId(accepted.job_id);
        return true;
      } catch (error) {
        setNotice(noticeFor(error));
        return false;
      } finally {
        mutationInFlightRef.current = false;
        setSubmitting(false);
      }
    },
    [api, bootstrap],
  );

  const confirmAction = useCallback(async () => {
    const selected = confirmation;
    setConfirmation(null);
    if (selected === "RESET") await submitJob("reset");
    if (selected === "ACTIVATE") await activate();
  }, [activate, confirmation, submitJob]);

  const isBusy = connecting || submitting || pollingJobId !== null;

  return useMemo(
    () => ({
      bootstrap,
      schedule,
      job,
      connecting,
      submitting,
      pollingJobId,
      notice,
      confirmation,
      lastSyncedAt,
      isBusy,
      pendingUrgentOrder,
      reconnect,
      refresh,
      requestReset,
      startInitialPlan,
      requestActivation,
      submitUrgentOrder,
      confirmAction,
      cancelConfirmation: () => setConfirmation(null),
      dismissNotice: () => setNotice(null),
    }),
    [
      bootstrap,
      confirmation,
      connecting,
      confirmAction,
      isBusy,
      job,
      lastSyncedAt,
      notice,
      pendingUrgentOrder,
      pollingJobId,
      reconnect,
      refresh,
      requestActivation,
      requestReset,
      schedule,
      startInitialPlan,
      submitUrgentOrder,
      submitting,
    ],
  );
}
