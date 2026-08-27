import { Typography } from "antd";

import { stateForError } from "../app/state";
import { useScheduleVersion } from "../app/useScheduleVersion";
import { ScheduleVersionPanel } from "../components/ScheduleVersionPanel";
import { WorkspaceStatePanel } from "../components/WorkspaceStatePanel";
import { useLocale } from "../i18n/locale";

const { Paragraph, Title } = Typography;

export function ValidationPage() {
  const { locale, t } = useLocale();
  const { scheduleVersionId, query } = useScheduleVersion();
  if (scheduleVersionId === null || scheduleVersionId.length === 0) {
    return (
      <WorkspaceStatePanel
        state="contract_error"
        detail={t("validation.identityRequired")}
      />
    );
  }
  if (query.isPending) return <WorkspaceStatePanel state="loading" />;
  if (query.error !== null) {
    return <WorkspaceStatePanel {...stateForError(query.error, locale)} />;
  }
  if (query.data === undefined) return <WorkspaceStatePanel state="contract_error" />;
  return (
    <article className="workspace-page">
      <Title level={2}>{t("validation.title")}</Title>
      <Paragraph type="secondary">
        {t("validation.description")}
      </Paragraph>
      <ScheduleVersionPanel version={query.data} />
      <pre className="payload-cell validation-document">
        {JSON.stringify(query.data.validation, null, 2)}
      </pre>
    </article>
  );
}
