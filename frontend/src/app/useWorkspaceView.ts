import { useQuery } from "@tanstack/react-query";

import { buildWorkspaceQuery, type WorkspaceQueryFilters } from "../api/query";
import type { ScheduleVersion, WorkspaceView } from "../api/types";
import { useAppServices } from "./context";

export interface ScheduleWorkspaceViewOptions {
  filters?: Partial<WorkspaceQueryFilters>;
  pageSize?: number;
  enabled?: boolean;
}

export function useScheduleWorkspaceView(
  view: WorkspaceView,
  version: ScheduleVersion | undefined,
  options: ScheduleWorkspaceViewOptions = {},
) {
  const { client, runtime } = useAppServices();
  const filterKey = JSON.stringify(options.filters ?? {});
  return useQuery({
    queryKey: [
      "schedule-workspace",
      view,
      version?.schedule_version_id ?? "ABSENT",
      version?.state ?? "ABSENT",
      version?.content_fingerprint ?? "ABSENT",
      options.pageSize ?? 500,
      filterKey,
    ],
    queryFn: async () => {
      if (version === undefined) throw new Error("ScheduleVersion authority is absent");
      const query = await buildWorkspaceQuery({
        authority: runtime,
        view,
        scheduleVersion: version,
        pageSize: options.pageSize ?? 500,
        filters: options.filters,
      });
      return client.queryWorkspace(query, view);
    },
    enabled: (options.enabled ?? true) && version !== undefined,
    retry: false,
    staleTime: 0,
  });
}
