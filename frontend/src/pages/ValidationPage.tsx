import { Typography } from "antd";

import { stateForError } from "../app/state";
import { useScheduleVersion } from "../app/useScheduleVersion";
import { ScheduleVersionPanel } from "../components/ScheduleVersionPanel";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";

const { Paragraph, Title } = Typography;

export function ValidationPage() {
  const { scheduleVersionId, query } = useScheduleVersion();
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    return (
      <WorkspaceStatePanel
        state="contract_error"
        detail="Validation requires ?schedule_version_id=<immutable-id>."
      />
    );
  }
  if (query.isPending) return <WorkspaceStatePanel state="loading" />;
  if (query.error !== null) {
    return <WorkspaceStatePanel {...stateForError(query.error)} />;
  }
  if (query.data === undefined) return <WorkspaceStatePanel state="contract_error" />;
  return (
    <article className="workspace-page">
      <Title level={2}>Validation</Title>
      <Paragraph type="secondary">
        Formal Validator evidence is rendered verbatim from the authoritative
        ScheduleVersion. The browser does not validate the schedule.
      </Paragraph>
      <ScheduleVersionPanel version={query.data} />
      <pre className="payload-cell validation-document">
        {JSON.stringify(query.data.validation, null, 2)}
      </pre>
    </article>
  );
}
