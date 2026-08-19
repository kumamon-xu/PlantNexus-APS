---
doc_id: DOC-DOM-002
title: OperationInstance 与候选资源语义
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [19, 20, 21, 25, 26]
last_reviewed: 2026-08-19
---

# OperationInstance 与候选资源语义

## OperationInstance

OperationInstance 是某个订单/批次中可排程工序的实例化对象。它必须与来源 DemandOrder、ProductionOrder、ProductionLot、RoutingVersion 和 RoutingOperation 保持可追溯关联。

至少需要表达：

- 稳定 ID、业务引用和状态；
- release time、material ready time；
- precedence edge 与 min/max/transport lag；
- candidate resource options；
- COMPLETED/RUNNING 的实际事实；
- HARD_LOCK/SOFT_LOCK；
- 优先级、交期和目标所需数据。

## OperationResourceOption

每个候选资源选项至少包含：

```text
resource_id
setup_seconds
cycle_seconds_per_unit
final_duration_seconds
duration_source
source_version
```

`final_duration_seconds` 是候选资源级字段。同一 OperationInstance 在不同设备上速度不同，必须形成不同的 duration；禁止先选择统一时长再忽略设备差异。

P0 `planning-problem.v1` skeleton 对每个未完成实例要求 `operation_id`、`status`、`release_at_utc`、`material_ready_at_utc` 和至少一个 `resource_options`。每个 option 明确要求上述六个字段，所有 duration 为整数秒且 `final_duration_seconds > 0`。RUNNING 额外要求 `actual_start_at_utc`、`assigned_resource_id` 和正整数 `remaining_seconds`；COMPLETED 不进入 Problem，因此不在 status enum 中。

## Solver 表达

候选资源 `r` 对应 `presence[i,r]` 和 optional interval，并满足：

```text
sum(presence[i,*]) == 1
end - start == selected_option.final_duration_ticks
```

OperationInstance 没有合法候选资源时必须在 Precheck/Data Validation 中拒绝，不能生成空选择或随机分配。

## Duration 来源

来源必须版本化。未来 AI DurationPrediction 只能提供候选 duration/risk/confidence；低置信度回退规则取决于 OPEN-014，不能在 P0 猜测。

P0 semantic precheck 会拒绝不存在的 candidate/assigned resource，但不实现 resource capability、routing expansion、DAG 或 C-001～C-011 判定；这些仍由 P1/P0-04/07 后续证据完成。
