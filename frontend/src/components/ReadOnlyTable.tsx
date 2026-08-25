import { Table, Typography, type TableColumnsType } from "antd";

import type { WorkspacePayloadItem } from "../api/types";

const { Text } = Typography;

const columns: TableColumnsType<WorkspacePayloadItem> = [
  {
    title: "Item ID",
    dataIndex: "item_id",
    key: "item_id",
    width: 260,
    render: (value: string) => <Text copyable>{value}</Text>,
  },
  {
    title: "Type",
    dataIndex: "item_type",
    key: "item_type",
    width: 180,
  },
  {
    title: "Authoritative payload",
    dataIndex: "payload",
    key: "payload",
    width: 720,
    render: (value: WorkspacePayloadItem["payload"]) => (
      <pre className="payload-cell">{JSON.stringify(value, null, 2)}</pre>
    ),
  },
];

export function ReadOnlyTable({ items }: { items: WorkspacePayloadItem[] }) {
  return (
    <Table<WorkspacePayloadItem>
      aria-label="Authoritative read-only workspace items"
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
