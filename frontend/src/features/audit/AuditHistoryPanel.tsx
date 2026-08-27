import { Alert, Card, Typography } from "antd";
import { Link } from "react-router-dom";

import type { ScheduleVersion } from "../../api/types";
import { useLocale } from "../../i18n/locale";

const { Paragraph } = Typography;

export function AuditHistoryPanel({ version }: { version: ScheduleVersion }) {
  const { t } = useLocale();
  const search = new URLSearchParams({
    schedule_version_id: version.schedule_version_id,
  });
  return (
    <Card title={t("audit.title")} className="control-card">
      <Alert
        type="info"
        showIcon
        title={t("audit.immutable")}
      />
      <Paragraph>
        {t("audit.description")}
      </Paragraph>
      <Link to={`/audit?${search}`}>{t("audit.open")}</Link>
    </Card>
  );
}
