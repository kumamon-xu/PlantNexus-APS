import { Descriptions, Tag, Typography } from "antd";

import type { ScheduleVersion } from "../api/types";

const { Text, Title } = Typography;

export function ScheduleVersionPanel({ version }: { version: ScheduleVersion }) {
  return (
    <section aria-label="Authoritative ScheduleVersion">
      <Title level={3}>ScheduleVersion</Title>
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="Identity">
          <Text copyable>{version.schedule_version_id}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="State">
          <Tag color="green">{version.state}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Revision">{version.revision}</Descriptions.Item>
        <Descriptions.Item label="Plane / environment">
          {version.data_plane} / {version.environment}
        </Descriptions.Item>
        <Descriptions.Item label="Parent">
          {version.parent_schedule_version?.schedule_version_id ?? "none"}
        </Descriptions.Item>
        <Descriptions.Item label="Content fingerprint">
          <Text copyable>{version.content_fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Snapshot fingerprint">
          <Text copyable>{version.lineage.snapshot.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Problem fingerprint">
          <Text copyable>{version.lineage.problem.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Solution fingerprint">
          <Text copyable>{version.lineage.planning_solution.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Validation fingerprint">
          <Text copyable>{version.lineage.validation_report.fingerprint}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Created at (raw UTC)">
          <time dateTime={version.created_at_utc}>{version.created_at_utc}</time>
        </Descriptions.Item>
        <Descriptions.Item label="Server allowed actions">
          {version.allowed_actions.map(String).join(", ") || "none"}
        </Descriptions.Item>
      </Descriptions>
    </section>
  );
}
