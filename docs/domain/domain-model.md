---
doc_id: DOC-DOM-001
title: APS 领域模型
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [17, 18, 19, 20, 21, 22]
last_reviewed: 2026-08-19
---

# APS 领域模型

## 工厂结构

```text
Factory
└─ Workshop
   └─ ProductionLine
      └─ ResourceGroup
         └─ Resource
```

Resource 至少具有稳定 ID/code、type、status、group、calendar 和 capabilities。V1 只对 Capacity=1 的主设备建立互斥约束；Secondary Capacity 属于明确未支持能力。

## 工艺结构

```text
Product
└─ RoutingVersion
   ├─ RoutingOperation[]
   ├─ RoutingPrecedenceEdge[]
   └─ RoutingResourceOption[]
```

Routing 必须是 DAG，支持串行、并行、汇合和跨车间关系。`sequence_no` 可以用于显示，但不能代替 precedence edge 表达工艺语义。

## 订单到排程实例

```text
DemandOrder
→ ProductionOrder
→ ProductionLot
→ OperationInstance
```

Solver 排的是 `OperationInstance`，不是 `RoutingOperation`。每个未完成实例引用明确的工艺版本、前后关系、候选资源、持续时间来源、release/material gates、执行状态和锁定状态。

## 核心聚合边界

- PlanningSnapshot 聚合某个 cutoff 的版本化计划事实，只读且不可变。
- PlanningProblem 是从 Snapshot 和 rule version 构建的求解输入，不承担持久化实体职责。
- PlanningSolution 是候选解；Validator 通过后才能形成可评审 ScheduleVersion。
- PlanningRun 记录计算生命周期；ScheduleVersion 记录业务计划生命周期；ExportJob 记录导出生命周期。

## 不变量

- 每个 RoutingVersion 无环；
- 每个 OperationInstance 的候选 Resource 必须存在且具备所需 capability；
- 不同 Resource 可以产生不同 duration；
- COMPLETED 不进入未来排程；RUNNING 保留历史事实和未来剩余占用；
- 任何 unsupported capability 在 Problem 构建前或明确预检阶段被识别。

## P0 executable type boundary

- `backend/app/domain/types.py` 提供 canonical ID、严格 UTC、integer duration 和 tick ceiling 的纯标准库值语义；
- `backend/app/domain/contracts.py` 提供 Import/KPI/Error/ValidationReport 的 JSON-compatible `TypedDict` skeleton；
- `backend/app/snapshots/contracts.py` 与 `backend/app/planning/problem/contracts.py` 分别承载 Snapshot/Problem 顶层类型；
- `backend/app/domain/validation.py` 只拒绝 skeleton 内的非法引用、UTC、interval、duration 和 lag range。

这些类型不依赖 ORM、FastAPI、Celery、Pydantic 或 OR-Tools，也不展开订单、不构建 Snapshot/Problem、不计算 hash、不执行排程。后续业务字段必须从权威合同进入并按 Schema versioning 升版，不能把 sample 值当默认值。
