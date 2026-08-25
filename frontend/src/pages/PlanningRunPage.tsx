import { useQuery } from "@tanstack/react-query";
import { Typography } from "antd";
import { useParams } from "react-router-dom";

import { useAppServices } from "../app/context";
import { stateForError } from "../app/state";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";

const { Paragraph, Title } = Typography;

export function PlanningRunPage() {
  const { client } = useAppServices();
  const { planning_run_id: planningRunId } = useParams<{
    planning_run_id: string;
  }>();
  const query = useQuery({
    queryKey: ["planning-run", planningRunId],
    queryFn: () => client.getPlanningRun(planningRunId ?? ""),
    enabled: planningRunId !== undefined && planningRunId.length > 0,
    retry: false,
  });
  if (planningRunId === undefined || planningRunId.length === 0) {
    return <WorkspaceStatePanel state="contract_error" detail="PlanningRun identity is required." />;
  }
  if (query.isPending) return <WorkspaceStatePanel state="loading" />;
  if (query.error !== null) return <WorkspaceStatePanel {...stateForError(query.error)} />;
  if (query.data === undefined) return <WorkspaceStatePanel state="contract_error" />;
  return (
    <article className="workspace-page">
      <Title level={2}>PlanningRun detail</Title>
      <Paragraph type="secondary">
        Versioned server summary. No run, solve, cancel or publish control is present.
      </Paragraph>
      <pre className="payload-cell">{JSON.stringify(query.data, null, 2)}</pre>
    </article>
  );
}
