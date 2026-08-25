import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import { useAppServices } from "./context";

export function useScheduleVersionId(): string | null {
  const params = useParams<{ schedule_version_id?: string }>();
  const [search] = useSearchParams();
  return params.schedule_version_id ?? search.get("schedule_version_id");
}

export function useScheduleVersion() {
  const { client } = useAppServices();
  const scheduleVersionId = useScheduleVersionId();
  const query = useQuery({
    queryKey: ["schedule-version", scheduleVersionId],
    queryFn: () => client.getScheduleVersion(scheduleVersionId ?? ""),
    enabled: scheduleVersionId !== null && scheduleVersionId.length > 0,
    staleTime: 0,
    retry: false,
  });
  return { scheduleVersionId, query };
}
