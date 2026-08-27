import { Table, Typography, type TableColumnsType } from "antd";
import { useMemo } from "react";

import type { WorkspacePayloadItem } from "../api/types";
import { useLocale } from "../i18n/locale";

const { Text } = Typography;

export function ReadOnlyTable({ items }: { items: WorkspacePayloadItem[] }) {
  const { t } = useLocale();
  const columns = useMemo<TableColumnsType<WorkspacePayloadItem>>(
    () => [
      {
        title: t("table.itemId"),
        dataIndex: "item_id",
        key: "item_id",
        width: 260,
        render: (value: string) => <Text copyable>{value}</Text>,
      },
      {
        title: t("table.type"),
        dataIndex: "item_type",
        key: "item_type",
        width: 180,
      },
      {
        title: t("table.authoritativePayload"),
        dataIndex: "payload",
        key: "payload",
        width: 720,
        render: (value: WorkspacePayloadItem["payload"]) => (
          <pre className="payload-cell">{JSON.stringify(value, null, 2)}</pre>
        ),
      },
    ],
    [t],
  );
  return (
    <Table<WorkspacePayloadItem>
      aria-label={t("table.readOnlyAria")}
      rowKey="item_id"
      columns={columns}
      dataSource={items}
      pagination={false}
      virtual
      scroll={{ x: 1160, y: 520 }}
      size="small"
    />
  );
}
