import { useMemo, useState } from "react";

import type { ScheduleOrder } from "../../api/types";
import { formatNumber } from "../../domain/copy";
import {
  filterAndSortOrders,
  formatDurationSeconds,
  formatWorkspaceTime,
  priorityLabels,
  quantityUnitLabel,
  type OrderFilters,
} from "../../domain/scheduleWorkspace";

const ORDER_PAGE_SIZE = 12;

interface OrdersWorkspaceViewProps {
  readonly orders: readonly ScheduleOrder[];
  readonly selectedOrderId: string | null;
  readonly onFocusOrder: (order: ScheduleOrder) => void;
}

export function OrdersWorkspaceView({
  orders,
  selectedOrderId,
  onFocusOrder,
}: OrdersWorkspaceViewProps) {
  const [filters, setFilters] = useState<OrderFilters>({
    search: "",
    priority: "ALL",
    risk: "ALL",
  });
  const [pageIndex, setPageIndex] = useState(0);
  const filtered = useMemo(
    () => filterAndSortOrders(orders, filters),
    [filters, orders],
  );
  const pageCount = Math.max(1, Math.ceil(filtered.length / ORDER_PAGE_SIZE));
  const safePageIndex = Math.min(pageIndex, pageCount - 1);
  const visibleOrders = filtered.slice(
    safePageIndex * ORDER_PAGE_SIZE,
    (safePageIndex + 1) * ORDER_PAGE_SIZE,
  );

  const updateFilters = (patch: Partial<OrderFilters>) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPageIndex(0);
  };

  return (
    <section aria-labelledby="orders-view-title">
      <div className="workspace-view-heading">
        <div>
          <p className="eyebrow">交付风险</p>
          <h3 id="orders-view-title">订单按风险、优先级与交期排序</h3>
          <p>选择订单后自动切换到甘特，并通过只读查询聚焦该订单全部工序。</p>
        </div>
        <span className="result-count">匹配 {formatNumber(filtered.length)} / {formatNumber(orders.length)} 单</span>
      </div>

      <div className="order-filters" aria-label="订单筛选">
        <label>
          <span>搜索订单或产品</span>
          <input
            type="search"
            value={filters.search}
            placeholder="例如 CNC-001"
            onChange={(event) => updateFilters({ search: event.target.value })}
          />
        </label>
        <label>
          <span>订单等级</span>
          <select
            value={filters.priority}
            onChange={(event) =>
              updateFilters({
                priority: event.target.value as OrderFilters["priority"],
              })
            }
          >
            <option value="ALL">全部等级</option>
            <option value="URGENT">加急</option>
            <option value="KEY">重点</option>
            <option value="NORMAL">普通</option>
          </select>
        </label>
        <label>
          <span>交付状态</span>
          <select
            value={filters.risk}
            onChange={(event) =>
              updateFilters({ risk: event.target.value as OrderFilters["risk"] })
            }
          >
            <option value="ALL">全部状态</option>
            <option value="LATE">仅延期风险</option>
            <option value="RUNNING">正在加工</option>
          </select>
        </label>
      </div>

      <div className="data-table-scroll">
        <table className="orders-table">
          <caption className="sr-only">当前排程订单、交期与工序进展</caption>
          <thead>
            <tr>
              <th scope="col">订单 / 产品</th>
              <th scope="col">等级</th>
              <th scope="col">数量</th>
              <th scope="col">物料到齐</th>
              <th scope="col">承诺交期</th>
              <th scope="col">工序进展</th>
              <th scope="col">预计完工</th>
              <th scope="col">交付判断</th>
              <th scope="col"><span className="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            {visibleOrders.map((order) => (
              <tr
                key={order.demand_order_id}
                className={selectedOrderId === order.demand_order_id ? "is-selected" : undefined}
              >
                <th scope="row">
                  <strong>{order.order_code}</strong>
                  <small>{order.product_code}</small>
                </th>
                <td>
                  <span className={`priority-tag priority-tag--${order.priority_class.toLowerCase()}`}>
                    {priorityLabels[order.priority_class]}
                  </span>
                </td>
                <td>{formatNumber(order.quantity)} {quantityUnitLabel(order.quantity_unit)}</td>
                <td>{formatWorkspaceTime(order.material_ready_at.utc)}</td>
                <td>{formatWorkspaceTime(order.due_at.utc)}</td>
                <td>
                  <strong>{order.completed_operation_count} 完成 · {order.running_operation_count} 加工中</strong>
                  <small>{order.scheduled_operation_count} 道待排 / 共 {order.operation_count} 道</small>
                </td>
                <td>{formatWorkspaceTime(order.completion_at.utc)}</td>
                <td>
                  <span className={`delivery-tag ${order.on_time ? "is-on-time" : "is-late"}`}>
                    {order.on_time
                      ? "按期"
                      : `延期 ${formatDurationSeconds(order.tardiness_seconds)}`}
                  </span>
                </td>
                <td>
                  <button
                    className="table-link"
                    type="button"
                    aria-label={`在甘特中查看订单 ${order.order_code}`}
                    onClick={() => onFocusOrder(order)}
                  >
                    查看甘特
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {visibleOrders.length === 0 && (
        <div className="workspace-empty">
          <strong>没有符合条件的订单</strong>
          <p>调整搜索、订单等级或交付状态即可恢复列表。</p>
        </div>
      )}

      <nav className="table-pagination" aria-label="订单分页">
        <span>第 {safePageIndex + 1} / {pageCount} 页 · 每页最多 {ORDER_PAGE_SIZE} 单</span>
        <div>
          <button
            className="button button--small button--quiet"
            type="button"
            disabled={safePageIndex === 0}
            onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
          >
            上一页
          </button>
          <button
            className="button button--small button--quiet"
            type="button"
            disabled={safePageIndex >= pageCount - 1}
            onClick={() => setPageIndex((current) => Math.min(pageCount - 1, current + 1))}
          >
            下一页
          </button>
        </div>
      </nav>
    </section>
  );
}
