import { Alert, Card, Typography } from "antd";
import { Link } from "react-router-dom";

import type { ScheduleVersion } from "../../api/types";

const { Paragraph } = Typography;

export function AuditHistoryPanel({ version }: { version: ScheduleVersion }) {
  const search = new URLSearchParams({
    schedule_version_id: version.schedule_version_id,
  });
  return (
    <Card title="Audit and immutable history" className="control-card">
      <Alert
        type="info"
        showIcon
        title="The browser cannot rewrite audit or published history."
      />
      <Paragraph>
        Review server-projected command, decision, publication and export events with
        their correlation and actor references.
      </Paragraph>
      <Link to={`/audit?${search}`}>Open audit history</Link>
    </Card>
  );
}
