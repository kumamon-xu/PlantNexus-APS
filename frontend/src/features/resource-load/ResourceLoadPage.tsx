import { Alert, Button, Flex, Typography } from "antd";
import { Link, useSearchParams } from "react-router-dom";

import { parseResourceLoads } from "../../api/contracts";
import type { ResourceLoad, WorkspaceUiState } from "../../api/types";
import { stateForError } from "../../app/state";
import { useScheduleVersion } from "../../app/useScheduleVersion";
import { useScheduleWorkspaceView } from "../../app/useWorkspaceView";
import { AuthorityPanel } from "../../components/AuthorityPanel";
import { WorkspaceStatePanel } from "../../components/WorkspaceStatePanel";

const { Paragraph, Title } = Typography;

export function ResourceLoadPage() {
  const [search] = useSearchParams();
  const resourceId = search.get("resource_id")?.trim() ?? "";
  const { scheduleVersionId, query: versionQuery } = useScheduleVersion();
  const version = versionQuery.data;
  const loadQuery = useScheduleWorkspaceView("RESOURCE_LOAD", version, {
    filters: { resource_ids: resourceId.length === 0 ? [] : [resourceId] },
    pageSize: 500,
  });

  let state: WorkspaceUiState = "loading";
  let detail: string | undefined;
  let loads: ResourceLoad[] = [];
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    state = "contract_error";
    detail = "Resource Load requires ?schedule_version_id=<immutable-id>.";
  } else if (versionQuery.error !== null) {
    ({ state, detail } = stateForError(versionQuery.error));
  } else if (loadQuery.error !== null) {
    ({ state, detail } = stateForError(loadQuery.error));
  } else if (loadQuery.data !== undefined) {
    const result = loadQuery.data.document.result;
    if (result === null) {
      state = "contract_error";
      detail = "The Resource Load RESULT carrier has no result body.";
    } else if (result.freshness !== "FRESH") {
      state = "stale";
      detail = `Server freshness is ${result.freshness}; refresh the Version precondition.`;
    } else if (!result.found || loadQuery.data.items.length === 0) {
      state = "empty";
    } else {
      try {
        loads = parseResourceLoads(loadQuery.data);
        state = "ready";
      } catch (error) {
        state = "contract_error";
        detail = error instanceof Error ? error.message : "Resource Load contract failed.";
      }
    }
  }
  const result = loadQuery.data?.document.result ?? null;

  return (
    <article className="workspace-page visualization-page">
      <Flex justify="space-between" align="flex-start" gap="middle" wrap>
        <div>
          <Title level={2}>Resource Load</Title>
          <Paragraph type="secondary">
            Planning-horizon load facts are server-provided. Busy time, availability and
            utilization are displayed without client-side capacity calculations.
          </Paragraph>
        </div>
        <Button
          onClick={() => void loadQuery.refetch()}
          disabled={version === undefined || loadQuery.isFetching}
        >
          Refresh read
        </Button>
      </Flex>
      {resourceId.length > 0 && (
        <Alert type="info" showIcon title={`Server resource filter: ${resourceId}`} />
      )}
      <WorkspaceStatePanel
        state={state}
        detail={detail}
        emptyKind={result?.found === false ? "missing" : "collection"}
      />
      {loadQuery.data !== undefined && state !== "contract_error" && (
        <div className="workspace-results">
          <AuthorityPanel response={loadQuery.data} />
          {result !== null && result.observed_count > loadQuery.data.items.length && (
            <Alert
              type="warning"
              showIcon
              title={`Server reports ${result.observed_count} rows; this bounded page contains ${loadQuery.data.items.length}.`}
            />
          )}
          {state === "ready" && version !== undefined && (
            <div className="table-scroll">
              <table className="resource-load-table">
                <caption>Server Resource Load facts for the immutable ScheduleVersion</caption>
                <thead>
                  <tr>
                    <th scope="col">Resource</th>
                    <th scope="col">Planning horizon UTC</th>
                    <th scope="col">Assignments</th>
                    <th scope="col">Busy seconds</th>
                    <th scope="col">Available seconds</th>
                    <th scope="col">Utilization</th>
                    <th scope="col">Related Gantt</th>
                  </tr>
                </thead>
                <tbody>
                  {loads.map((load) => (
                    <tr key={load.item_id}>
                      <td>{load.resource_code}<br /><code>{load.resource_id}</code></td>
                      <td>
                        <time dateTime={load.start_at_utc}>{load.start_at_utc}</time>
                        <br />to<br />
                        <time dateTime={load.end_at_utc}>{load.end_at_utc}</time>
                      </td>
                      <td>{load.assignment_count}</td>
                      <td>{load.planned_busy_seconds}</td>
                      <td>{load.available_seconds}</td>
                      <td>
                        <progress max={1} value={Math.min(load.utilization, 1)}>
                          {load.utilization}
                        </progress>
                        <output>{load.utilization}</output>
                      </td>
                      <td>
                        <Link
                          to={`/planning/versions/${encodeURIComponent(version.schedule_version_id)}/gantt/machines?resource_id=${encodeURIComponent(load.resource_id)}`}
                        >
                          Machine Gantt
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </article>
  );
}
