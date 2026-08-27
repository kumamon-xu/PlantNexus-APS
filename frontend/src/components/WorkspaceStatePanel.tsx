import { Alert, Empty, Skeleton } from "antd";

import type { WorkspaceUiState } from "../api/types";
import type { TranslationKey } from "../i18n/dictionaries/en-US";
import { useLocale } from "../i18n/locale";

const stateCopy: Record<
  Exclude<WorkspaceUiState, "loading" | "empty" | "ready">,
  { title: TranslationKey; description: TranslationKey; type: "error" | "warning" }
> = {
  stale: { title: "state.staleTitle", description: "state.staleDescription", type: "warning" },
  authorization_denied: { title: "state.authorizationTitle", description: "state.authorizationDescription", type: "error" },
  contract_error: { title: "state.contractTitle", description: "state.contractDescription", type: "error" },
  server_error: { title: "state.serverTitle", description: "state.serverDescription", type: "error" },
};

export interface WorkspaceStatePanelProps {
  state: WorkspaceUiState;
  detail?: string;
  emptyKind?: "missing" | "collection";
}

export function WorkspaceStatePanel({
  state,
  detail,
  emptyKind = "collection",
}: WorkspaceStatePanelProps) {
  const { t } = useLocale();
  if (state === "loading") {
    return (
      <div role="status" aria-label={t("state.loadingAria")}>
        <Skeleton active />
      </div>
    );
  }
  if (state === "empty") {
    const missing = emptyKind === "missing";
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <span>
            <strong>{missing ? t("state.resourceNotFound") : t("state.noMatchingItems")}</strong>
            <br />
            {missing
              ? t("state.foundFalse")
              : t("state.foundEmpty")}
          </span>
        }
      />
    );
  }
  if (state === "ready") return null;
  const copy = stateCopy[state];
  return (
    <Alert
      showIcon
      type={copy.type}
      title={t(copy.title)}
      description={detail ?? t(copy.description)}
      role="alert"
    />
  );
}
