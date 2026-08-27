import { WorkspaceClientError } from "../api/client";
import type { WorkspaceUiState } from "../api/types";
import { translate } from "../i18n/locale";
import { fallbackLocale, type AppLocale } from "../i18n/types";

export function stateForError(error: unknown, locale: AppLocale = fallbackLocale): {
  state: WorkspaceUiState;
  detail: string;
} {
  if (error instanceof WorkspaceClientError) {
    const suffix = error.correlationId
      ? ` ${translate(locale, "common.correlation", { value: error.correlationId })}`
      : "";
    return { state: error.kind, detail: `${error.message}${suffix}` };
  }
  return {
    state: "contract_error",
    detail: translate(locale, "error.unexpectedConsumer"),
  };
}
