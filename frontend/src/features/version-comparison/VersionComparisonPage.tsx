import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Descriptions, Flex, Input, Radio, Tag, Typography } from "antd";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { parseVersionComparison } from "../../api/contracts";
import { buildWorkspaceQuery } from "../../api/query";
import type {
  OperationDelta,
  ScheduleVersionComparison,
  WorkspaceUiState,
} from "../../api/types";
import { useAppServices } from "../../app/context";
import { stateForError } from "../../app/state";
import { useScheduleVersion } from "../../app/useScheduleVersion";
import { AuthorityPanel } from "../../components/AuthorityPanel";
import { WorkspaceStatePanel } from "../../components/WorkspaceStatePanel";

const { Paragraph, Text, Title } = Typography;
type DeltaFilter = "ALL" | "CHANGED" | "UNCHANGED";

function visibleDeltas(
  deltas: OperationDelta[],
  filter: DeltaFilter,
): OperationDelta[] {
  if (filter === "ALL") return deltas;
  if (filter === "UNCHANGED") {
    return deltas.filter((delta) => delta.change_kind === "UNCHANGED");
  }
  return deltas.filter((delta) => delta.change_kind !== "UNCHANGED");
}

export function VersionComparisonPage() {
  const { client, runtime } = useAppServices();
  const [search, setSearch] = useSearchParams();
  const initialCompared = search.get("compared_schedule_version_id") ?? "";
  const [comparedDraft, setComparedDraft] = useState(initialCompared);
  const [requestedId, setRequestedId] = useState(initialCompared.trim());
  const [deltaFilter, setDeltaFilter] = useState<DeltaFilter>("CHANGED");
  const { scheduleVersionId, query: baseQuery } = useScheduleVersion();
  const baseVersion = baseQuery.data;
  const comparedQuery = useQuery({
    queryKey: ["compared-schedule-version", requestedId],
    queryFn: () => client.getScheduleVersion(requestedId),
    enabled: requestedId.length > 0,
    retry: false,
    staleTime: 0,
  });
  const comparedVersion = comparedQuery.data;
  const comparisonQuery = useQuery({
    queryKey: [
      "version-comparison",
      baseVersion?.schedule_version_id ?? "ABSENT",
      baseVersion?.state ?? "ABSENT",
      baseVersion?.content_fingerprint ?? "ABSENT",
      comparedVersion?.schedule_version_id ?? "ABSENT",
      comparedVersion?.state ?? "ABSENT",
      comparedVersion?.content_fingerprint ?? "ABSENT",
    ],
    queryFn: async () => {
      if (baseVersion === undefined || comparedVersion === undefined) {
        throw new Error("Both immutable Version preconditions are required");
      }
      const query = await buildWorkspaceQuery({
        authority: runtime,
        view: "VERSION_COMPARISON",
        scheduleVersion: baseVersion,
        pageSize: 1,
      });
      return client.compareScheduleVersions(query, comparedVersion);
    },
    enabled:
      baseVersion !== undefined &&
      comparedVersion !== undefined &&
      baseVersion.schedule_version_id !== comparedVersion.schedule_version_id,
    retry: false,
    staleTime: 0,
  });

  let state: WorkspaceUiState = "loading";
  let detail: string | undefined;
  let comparison: ScheduleVersionComparison | null = null;
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    state = "contract_error";
    detail = "Version comparison requires an immutable base ScheduleVersion route.";
  } else if (baseQuery.error !== null) {
    ({ state, detail } = stateForError(baseQuery.error));
  } else if (requestedId.length === 0) {
    state = "empty";
    detail = "Enter a distinct compared ScheduleVersion ID to start the read query.";
  } else if (baseVersion?.schedule_version_id === requestedId) {
    state = "contract_error";
    detail = "The compared ScheduleVersion must differ from the base Version.";
  } else if (comparedQuery.error !== null) {
    ({ state, detail } = stateForError(comparedQuery.error));
  } else if (comparisonQuery.error !== null) {
    ({ state, detail } = stateForError(comparisonQuery.error));
  } else if (comparisonQuery.data !== undefined) {
    const result = comparisonQuery.data.document.result;
    if (result === null) {
      state = "contract_error";
      detail = "The comparison RESULT carrier has no result body.";
    } else if (result.freshness !== "FRESH") {
      state = "stale";
      detail = `Server freshness is ${result.freshness}; reload both Version preconditions.`;
    } else if (!result.found || comparisonQuery.data.items.length === 0) {
      state = "empty";
    } else {
      try {
        comparison = parseVersionComparison(comparisonQuery.data);
        state = "ready";
      } catch (error) {
        state = "contract_error";
        detail = error instanceof Error ? error.message : "Comparison contract failed.";
      }
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = comparedDraft.trim();
    setRequestedId(next);
    const nextSearch = new URLSearchParams(search);
    if (next.length === 0) nextSearch.delete("compared_schedule_version_id");
    else nextSearch.set("compared_schedule_version_id", next);
    setSearch(nextSearch, { replace: true });
  }

  const deltas = comparison === null
    ? []
    : visibleDeltas(comparison.operation_deltas, deltaFilter);

  return (
    <article className="workspace-page visualization-page">
      <Title level={2}>ScheduleVersion comparison</Title>
      <Paragraph type="secondary">
        Two immutable server versions are compared by the existing read-query endpoint.
        Change kinds, summaries and KPI deltas are rendered as server facts.
      </Paragraph>
      <form className="comparison-form" onSubmit={submit}>
        <label htmlFor="compared-version-id">Compared ScheduleVersion ID</label>
        <Input
          id="compared-version-id"
          value={comparedDraft}
          onChange={(event) => setComparedDraft(event.target.value)}
        />
        <Button htmlType="submit" type="primary">Run read comparison</Button>
      </form>

      {requestedId.length === 0 ? (
        <Alert type="info" showIcon title={detail} />
      ) : (
        <WorkspaceStatePanel state={state} detail={detail} />
      )}

      {comparisonQuery.data !== undefined && state !== "contract_error" && (
        <div className="workspace-results">
          <AuthorityPanel response={comparisonQuery.data} />
        </div>
      )}

      {comparison !== null && state === "ready" && (
        <>
          <Descriptions bordered size="small" column={1} className="comparison-authority">
            <Descriptions.Item label="Comparison ID">
              <Text copyable>{comparison.comparison_id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Base Version">
              {comparison.base_version.schedule_version_id} · {comparison.base_version.state}
            </Descriptions.Item>
            <Descriptions.Item label="Compared Version">
              {comparison.compared_version.schedule_version_id} · {comparison.compared_version.state}
            </Descriptions.Item>
            <Descriptions.Item label="Comparison fingerprint">
              <Text copyable>{comparison.comparison_fingerprint}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Generated at raw UTC">
              <time dateTime={comparison.generated_at_utc}>{comparison.generated_at_utc}</time>
            </Descriptions.Item>
          </Descriptions>

          <Title level={3}>Server summary</Title>
          <dl className="comparison-summary">
            {Object.entries(comparison.summary).map(([name, value]) => (
              <div key={name}><dt>{name}</dt><dd>{String(value)}</dd></div>
            ))}
          </dl>

          <Title level={3}>Server KPI deltas</Title>
          <div className="table-scroll">
            <table>
              <caption>No KPI value is recalculated in the browser</caption>
              <thead><tr><th scope="col">Metric</th><th scope="col">Base</th><th scope="col">Compared</th><th scope="col">Delta</th></tr></thead>
              <tbody>
                {comparison.kpi_deltas.map((delta) => (
                  <tr key={delta.metric}><th scope="row">{delta.metric}</th><td>{delta.base_value}</td><td>{delta.compared_value}</td><td>{delta.delta}</td></tr>
                ))}
              </tbody>
            </table>
          </div>

          <Flex justify="space-between" align="center" gap="middle" wrap>
            <Title level={3}>Operation deltas</Title>
            <Radio.Group
              aria-label="Operation delta visibility"
              value={deltaFilter}
              onChange={(event) => setDeltaFilter(event.target.value as DeltaFilter)}
              options={[
                { label: "Changed", value: "CHANGED" },
                { label: "Unchanged", value: "UNCHANGED" },
                { label: "All", value: "ALL" },
              ]}
            />
          </Flex>
          <div className="table-scroll">
            <table>
              <caption>Server-classified operation changes ({deltaFilter.toLowerCase()})</caption>
              <thead>
                <tr><th scope="col">Operation</th><th scope="col">Change kind</th><th scope="col">Base resource/time</th><th scope="col">Compared resource/time</th></tr>
              </thead>
              <tbody>
                {deltas.map((delta) => (
                  <tr key={delta.operation_id}>
                    <th scope="row">{delta.operation_id}</th>
                    <td><Tag>{delta.change_kind}</Tag></td>
                    <td>{delta.base_resource_id ?? "absent"}<br />{delta.base_start_at_utc ?? "absent"}<br />{delta.base_end_at_utc ?? "absent"}</td>
                    <td>{delta.compared_resource_id ?? "absent"}<br />{delta.compared_start_at_utc ?? "absent"}<br />{delta.compared_end_at_utc ?? "absent"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Flex gap="middle" wrap>
            <Link to={`/planning/versions/${encodeURIComponent(comparison.base_version.schedule_version_id)}/gantt/factory`}>Base factory Gantt</Link>
            <Link to={`/planning/versions/${encodeURIComponent(comparison.compared_version.schedule_version_id)}/gantt/factory`}>Compared factory Gantt</Link>
          </Flex>
        </>
      )}
    </article>
  );
}
