import { useQuery } from "@tanstack/react-query";
import { Button, Flex, Space, Typography } from "antd";
import { useState } from "react";

import { buildWorkspaceQuery } from "../api/query";
import type { WorkspaceUiState, WorkspaceView } from "../api/types";
import { useAppServices } from "../app/context";
import { stateForError } from "../app/state";
import { useScheduleVersion } from "../app/useScheduleVersion";
import { AuthorityPanel } from "../components/AuthorityPanel";
import { ReadOnlyTable } from "../components/ReadOnlyTable";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";
import { labelBusinessValue } from "../i18n/business-labels";
import { useLocale } from "../i18n/locale";

const { Paragraph, Title } = Typography;

export interface WorkspaceCollectionPageProps {
  title?: string;
  view: WorkspaceView;
  scheduleScoped?: boolean;
}

export function WorkspaceCollectionPage({
  title,
  view,
  scheduleScoped = false,
}: WorkspaceCollectionPageProps) {
  const { client, runtime } = useAppServices();
  const { locale, t } = useLocale();
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const cursor = cursorStack.at(-1) ?? null;
  const { scheduleVersionId, query: versionQuery } = useScheduleVersion();
  const version = scheduleScoped ? versionQuery.data : undefined;
  const queryEnabled = !scheduleScoped || version !== undefined;
  const workspaceQuery = useQuery({
    queryKey: [
      "workspace",
      view,
      version?.schedule_version_id ?? "WORKSPACE",
      version?.state ?? "WORKSPACE",
      version?.content_fingerprint ?? "WORKSPACE",
      cursor,
    ],
    queryFn: async () => {
      const query = await buildWorkspaceQuery({
        authority: runtime,
        view,
        scheduleVersion: version,
        cursor,
      });
      return client.queryWorkspace(query, view);
    },
    enabled: queryEnabled,
    retry: false,
    staleTime: 0,
  });

  let state: WorkspaceUiState = "loading";
  let detail: string | undefined;
  if (scheduleScoped && (scheduleVersionId === null || scheduleVersionId.length === 0)) {
    state = "contract_error";
    detail =
      t("collection.identityRequired");
  } else if (scheduleScoped && versionQuery.error !== null) {
    ({ state, detail } = stateForError(versionQuery.error, locale));
  } else if (workspaceQuery.error !== null) {
    ({ state, detail } = stateForError(workspaceQuery.error, locale));
  } else if (workspaceQuery.data !== undefined) {
    const result = workspaceQuery.data.document.result;
    if (result === null) {
      state = "contract_error";
      detail = t("collection.resultMissing");
    } else if (result.freshness !== "FRESH") {
      state = "stale";
      detail = t("collection.stale", { freshness: result.freshness });
    } else if (!result.found || workspaceQuery.data.items.length === 0) {
      state = "empty";
    } else {
      state = "ready";
    }
  }

  const result = workspaceQuery.data?.document.result ?? null;
  const emptyKind = result?.found === false ? "missing" : "collection";
  const viewLabel = labelBusinessValue("workspaceView", view, locale);

  return (
    <article className="workspace-page">
      <Flex justify="space-between" align="flex-start" gap="middle" wrap>
        <div>
          <Title level={2}>{viewLabel.known ? viewLabel.label : title ?? viewLabel.label}</Title>
          <Paragraph type="secondary">
            {t("collection.description")}
          </Paragraph>
        </div>
        <Space>
          <Button
            onClick={() => void workspaceQuery.refetch()}
            disabled={!queryEnabled || workspaceQuery.isFetching}
          >
            {t("common.refreshRead")}
          </Button>
          <Button
            onClick={() => setCursorStack((values) => values.slice(0, -1))}
            disabled={cursorStack.length === 1 || workspaceQuery.isFetching}
          >
            {t("common.previousPage")}
          </Button>
          <Button
            onClick={() => {
              if (result?.next_cursor !== null && result?.next_cursor !== undefined) {
                setCursorStack((values) => [...values, result.next_cursor]);
              }
            }}
            disabled={result?.next_cursor == null || workspaceQuery.isFetching}
          >
            {t("common.nextPage")}
          </Button>
        </Space>
      </Flex>

      <WorkspaceStatePanel state={state} detail={detail} emptyKind={emptyKind} />
      {workspaceQuery.data !== undefined && state !== "contract_error" && (
        <Space orientation="vertical" size="large" className="workspace-results">
          <AuthorityPanel response={workspaceQuery.data} />
          {state === "ready" && <ReadOnlyTable items={workspaceQuery.data.items} />}
        </Space>
      )}
    </article>
  );
}
