---
doc_id: DOC-CONTRACT-006
title: ExecutionEvent 与 ReplanRequest 合同
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [35, 47, 48, 49, 50, 64, 66, 79, 80]
last_reviewed: 2026-08-27
---

# ExecutionEvent 与 ReplanRequest 合同

## P4 planning ownership

本页现作为TASK-P4-01的主要人类合同输入；事件authority/order/idempotency、事实投影、ReplanRequest生命周期、freeze window、base/new lineage及ChangeReport连接必须先由planned Event/Fact/Replan ADR与Freeze/Stability/ChangeReport ADR决定，再由TASK-P4-02形成机器合同。TASK-P4-03/04分别拥有durable transaction与ingestion/fact projection；本次阶段规划没有形成任何event endpoint、repository、state transition或真实MES来源。

## V1 ExecutionEvent 类型

`OPERATION_STARTED`、`OPERATION_COMPLETED`、`OPERATION_DELAYED`、`MACHINE_DOWN`、`MACHINE_RECOVERED`、`MATERIAL_DELAYED`、`URGENT_ORDER_CREATED`、`LOCK_CREATED`、`LOCK_RELEASED`。

每个事件至少需要 stable event ID、event type、occurred_at、received_at、source、source version、entity refs、payload version 和 idempotency key。事件重复接收不得造成重复事实或重复 Replan。

## ReplanRequest

```text
base_schedule_version_id
new_snapshot_id
replan_reason
freeze_window
```

请求必须指向不可变 base version 和 new snapshot；请求创建、取消、重试和结果版本均可审计。

## 事实保护

新的计划必须保持 completed operation、running resource、HARD_LOCK；对 SOFT_LOCK 记录变化成本，并生成 ChangeReport。Execution Simulator 使用同一 Event 合同，simulation source 必须显式标识。
