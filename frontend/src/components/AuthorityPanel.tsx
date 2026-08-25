import { Descriptions, Tag, Typography } from "antd";

import type {
  ScheduleLineage,
  VersionReference,
  WorkspaceHttpResponse,
} from "../api/types";

const { Text } = Typography;

function lineageFingerprints(lineage: ScheduleLineage | null): string {
  if (lineage === null) return "not schedule-scoped";
  return [
    lineage.snapshot.fingerprint,
    lineage.problem.fingerprint,
    lineage.planning_solution.fingerprint,
    lineage.validation_report.fingerprint,
    lineage.kpi.fingerprint,
    lineage.solver_report.fingerprint,
  ].join(" · ");
}

export function AuthorityPanel({ response }: { response: WorkspaceHttpResponse }) {
  const result = response.document.result;
  if (result === null) return null;
  const authority: VersionReference | null = result.authoritative_schedule_version;
  return (
    <section aria-label="Server authority and lineage">
      <Descriptions bordered size="small" column={1}>
        <Descriptions.Item label="Authority">
          <Tag color="green">server application</Tag>
          <Text code>{response.document.data_plane}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="ScheduleVersion">
          {authority === null
            ? "workspace scope"
            : `${authority.schedule_version_id} · ${authority.state}`}
        </Descriptions.Item>
        <Descriptions.Item label="Content fingerprint">
          <Text copyable>{authority?.content_fingerprint ?? "not schedule-scoped"}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Source / collection">
          <Text copyable>
            {response.source_fingerprint ?? "missing"} ·{" "}
            {response.collection_fingerprint ?? "missing"}
          </Text>
        </Descriptions.Item>
        <Descriptions.Item label="Lineage fingerprints">
          <Text className="fingerprint-wrap">{lineageFingerprints(result.lineage)}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Generated at (raw UTC)">
          <time dateTime={result.generated_at_utc}>{result.generated_at_utc}</time>
        </Descriptions.Item>
        <Descriptions.Item label="Correlation ID">
          <Text copyable>{response.correlation_id}</Text>
        </Descriptions.Item>
      </Descriptions>
    </section>
  );
}
