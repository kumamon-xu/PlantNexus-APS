import { useCallback, useEffect, useRef, useState } from "react";

import type { DemoApi } from "../api/client";
import { DemoContractError } from "../api/contracts";
import type {
  DemoFactoryView,
  DemoScheduleView,
  ScheduleQueryInput,
} from "../api/types";
import { noticeFor, type UiNotice } from "../domain/copy";

const HOUR_MS = 3_600_000;
export const DEMO_SCHEDULE_PAGE_LIMIT = 160;
export const DEMO_DEFAULT_WINDOW_HOURS = 72;
export const DEMO_HISTORY_HOURS = 6;

export function initialWorkspaceQuery(
  factory: DemoFactoryView,
): ScheduleQueryInput {
  const horizonStart = Date.parse(factory.horizon_start.utc);
  const horizonEnd = Date.parse(factory.horizon_end.utc);
  const start = horizonStart - DEMO_HISTORY_HOURS * HOUR_MS;
  const end = Math.min(
    horizonEnd,
    start + DEMO_DEFAULT_WINDOW_HOURS * HOUR_MS,
  );
  return {
    start_at_utc: new Date(start).toISOString(),
    end_at_utc: new Date(end).toISOString(),
    sort: "ORDER_START_ASC",
    offset: 0,
    limit: DEMO_SCHEDULE_PAGE_LIMIT,
  };
}

function assertWorkspaceScope(
  factory: DemoFactoryView,
  schedule: DemoScheduleView,
  expectedRunId: string,
  expectedVersionId: string,
): void {
  if (
    factory.run_id !== expectedRunId ||
    schedule.run_id !== expectedRunId ||
    factory.scenario_id !== schedule.scenario_id ||
    schedule.version.schedule_version_id !== expectedVersionId ||
    factory.factory.timezone !== schedule.timezone
  ) {
    throw new DemoContractError("schedule.workspace.scope");
  }
}

export interface ScheduleWorkspaceController {
  readonly factory: DemoFactoryView | null;
  readonly schedule: DemoScheduleView | null;
  readonly loading: boolean;
  readonly refreshing: boolean;
  readonly notice: UiNotice | null;
  readonly lastLoadedAt: number | null;
  readonly loadSchedule: (query: ScheduleQueryInput) => Promise<void>;
  readonly refresh: () => Promise<void>;
  readonly dismissNotice: () => void;
}

export function useScheduleWorkspace(
  api: DemoApi,
  expectedRunId: string,
  expectedVersionId: string,
): ScheduleWorkspaceController {
  const [factory, setFactory] = useState<DemoFactoryView | null>(null);
  const [schedule, setSchedule] = useState<DemoScheduleView | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [notice, setNotice] = useState<UiNotice | null>(null);
  const [lastLoadedAt, setLastLoadedAt] = useState<number | null>(null);
  const sequence = useRef(0);
  const factoryRef = useRef<DemoFactoryView | null>(null);
  const scheduleRef = useRef<DemoScheduleView | null>(null);

  const loadInitial = useCallback(async () => {
    const requestSequence = ++sequence.current;
    try {
      const nextFactory = await api.getFactory();
      const nextSchedule = await api.getSchedulePage(
        expectedVersionId,
        initialWorkspaceQuery(nextFactory),
      );
      assertWorkspaceScope(
        nextFactory,
        nextSchedule,
        expectedRunId,
        expectedVersionId,
      );
      if (requestSequence !== sequence.current) return;
      factoryRef.current = nextFactory;
      scheduleRef.current = nextSchedule;
      setFactory(nextFactory);
      setSchedule(nextSchedule);
      setLastLoadedAt(Date.now());
    } catch (error) {
      if (requestSequence === sequence.current) setNotice(noticeFor(error));
    } finally {
      if (requestSequence === sequence.current) setLoading(false);
    }
  }, [api, expectedRunId, expectedVersionId]);

  useEffect(() => {
    factoryRef.current = null;
    scheduleRef.current = null;
    const timer = window.setTimeout(() => void loadInitial(), 0);
    return () => {
      window.clearTimeout(timer);
      sequence.current += 1;
    };
  }, [loadInitial]);

  const loadSchedule = useCallback(
    async (query: ScheduleQueryInput) => {
      const currentFactory = factoryRef.current;
      if (currentFactory === null) return;
      const requestSequence = ++sequence.current;
      setRefreshing(true);
      setNotice(null);
      try {
        const nextSchedule = await api.getSchedulePage(expectedVersionId, query);
        assertWorkspaceScope(
          currentFactory,
          nextSchedule,
          expectedRunId,
          expectedVersionId,
        );
        if (requestSequence !== sequence.current) return;
        scheduleRef.current = nextSchedule;
        setSchedule(nextSchedule);
        setLastLoadedAt(Date.now());
      } catch (error) {
        if (requestSequence === sequence.current) setNotice(noticeFor(error));
      } finally {
        if (requestSequence === sequence.current) setRefreshing(false);
      }
    },
    [api, expectedRunId, expectedVersionId],
  );

  const refresh = useCallback(async () => {
    if (factoryRef.current === null || scheduleRef.current === null) {
      setRefreshing(true);
      setNotice(null);
      await loadInitial();
      setRefreshing(false);
      return;
    }
    const requestSequence = ++sequence.current;
    setRefreshing(true);
    setNotice(null);
    try {
      const [nextFactory, nextSchedule] = await Promise.all([
        api.getFactory(),
        api.getSchedulePage(expectedVersionId, scheduleRef.current.query),
      ]);
      assertWorkspaceScope(
        nextFactory,
        nextSchedule,
        expectedRunId,
        expectedVersionId,
      );
      if (requestSequence !== sequence.current) return;
      factoryRef.current = nextFactory;
      scheduleRef.current = nextSchedule;
      setFactory(nextFactory);
      setSchedule(nextSchedule);
      setLastLoadedAt(Date.now());
    } catch (error) {
      if (requestSequence === sequence.current) setNotice(noticeFor(error));
    } finally {
      if (requestSequence === sequence.current) setRefreshing(false);
    }
  }, [api, expectedRunId, expectedVersionId, loadInitial]);

  return {
    factory,
    schedule,
    loading,
    refreshing,
    notice,
    lastLoadedAt,
    loadSchedule,
    refresh,
    dismissNotice: () => setNotice(null),
  };
}
