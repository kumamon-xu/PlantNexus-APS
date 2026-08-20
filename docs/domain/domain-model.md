---
doc_id: DOC-DOM-001
title: APS 领域模型
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [17, 18, 19, 20, 21, 22]
last_reviewed: 2026-08-20
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
- `backend/app/domain/errors.py` 固定七类 product category、19 个当前 code 及唯一映射；
- `backend/app/domain/capabilities.py` 固定 20 个 capability declaration 与显式拒绝 precheck；
- `backend/app/domain/state_machines/contracts.py` 固定三套 state enum、42 个允许 pair 与终态；
- `backend/app/snapshots/contracts.py` 与 `backend/app/planning/problem/contracts.py` 分别承载 Snapshot/Problem 顶层类型；
- `backend/app/domain/validation.py` 只拒绝 skeleton 内的非法引用、UTC、interval、duration 和 lag range。

`error.v1`/`validation-report.v1` pure types 保留；新增显式 V2 types，不通过 alias 静默升级。规则/状态/capability 类型不依赖 ORM、FastAPI、Celery、Pydantic 或 OR-Tools，也不展开订单、不构建 Snapshot/Problem、不计算 hash、不执行排程、不评估候选 schedule 或执行业务状态动作。后续业务字段必须从权威合同进入并按 Schema versioning 升版，不能把 rule example 当默认值。

## P0 Simulation contract boundary

`simulation/profiles/contracts.py` 和 `simulation/scenarios/contracts.py` 只承载 synthetic-only Profile/Scenario/Manifest 的 JSON-compatible types、version/seed/range/provenance/isolation precheck；`simulation/generators/**` 只定义七层 Protocol、命名 seed、canonical JSON/SHA-256 与空 Standard Import v1 package。它们不新增 Production Factory/Order/Routing 实体，不成为 ERP/MES/WMS/CAM 权威，不导入 PlanningProblem/Solver，也不把 Schema sample 视为领域事实或正式 Fixture。

## TASK-P1-02 canonical type boundary

`canonical-records.v1`现在机器化固定Factory→Resource、Product→Routing、DemandOrder→ProductionOrder→explicit ProductionLot、execution facts与operation locks；所有引用使用稳定canonical ID，每条记录保留source system/version/record ID。`backend/app/domain/canonical_records.py`提供对应JSON-compatible `TypedDict`和pure semantic precheck，检查ID唯一、引用lineage、explicit unit、UTC、duration/lag/interval及synthetic provenance。

Snapshot v2额外固定derived OperationInstance/precedence edge与candidate级duration/source copy shape，但order expansion行为仍由TASK-P1-07实现，Snapshot builder/hash/persistence仍由TASK-P1-08实现。当前代码不检查Routing DAG或capability可用性、不生成lot/instance、不补duration、不导入ORM/API/Solver；这些边界不能因types存在而改写为已实现。

## TASK-P1-05 normalization boundary

`app.normalization`把Raw Staging transport row按显式MappingProfile转换为16个canonical collection中的记录，自动注入稳定source reference并生成Import v2 bytes/hash。Profile字段集由canonical-records.v1 required/optional properties的contract test逐项对齐；必填字段不能标为optional，`source`不能由payload伪造。

该层只负责字段值规范化和deterministic serialization。它不验证跨记录引用是否存在、不判断Routing DAG/capability、execution state组合或calendar range，不生成Lot/OperationInstance，也不构建Snapshot/Problem。上述语义仍分别属于TASK-P1-06/07/08/09。

## TASK-P1-06 data-quality type boundary

`domain/contracts.py`新增Error v3 rich detail与ImportQualityReport v1的JSON-compatible types；`domain/errors.py`保留原`ProductErrorCode`/v1 mapping，同时以独立`ProductErrorCodeV2`/mapping additive登记四项P1 DATA_ERROR。历史19项类型和consumer没有alias或重解释。

`app.data_validation`在Canonical Records之上形成best-effort multi-error evaluator，按source identity而非数组位置报告结构、lineage、DAG、resource/capability、time/duration/unit/fact/lock问题。它不修改canonical records、不创建OperationInstance、不依赖ORM/API/Planning/OR-Tools，也不是P0/P2 candidate ScheduleValidator。

## TASK-P1-07 production expansion boundary

`domain/production.py`现固定`order-expansion.v1`、derived ID算法、JSON-compatible expansion provenance/result和module-local rejection；`normalization/order_expansion.py`消费已验证Import/PASS report，按每个显式ProductionLot复制其RoutingVersion的全部operation与edge。OperationInstance ID由`version + lot ID + routing operation ID`派生，precedence ID由`version + lot ID + routing edge ID`派生，输出按ID稳定排序并保留可回链到全部canonical source record的外键。

该pure service不拥有Production lot sizing、duration calculation、material authority或resource selection。它复制明确candidate duration/source、release/material gate、RUNNING/COMPLETED fact引用和locks；COMPLETED实例留在事实输出，未来Problem过滤仍属TASK-P1-09。Expansion artifact/hash不是PlanningSnapshot/hash；TASK-P1-07把持久化与immutability交给TASK-P1-08，并由下节记录当前已形成的Snapshot value boundary，Solver仍不存在。

## TASK-P1-08 PlanningSnapshot value boundary

`app.snapshots`现在把PlanningSnapshot v2实现为canonical bytes驱动的frozen value：外部只能取得新document copy，不能通过共享dict改写事实；self ID/hash由versioned semantic projection确定性派生。Builder消费Canonical Import、matching quality PASS和Order Expansion，不拥有字段权威、lot/duration推断或未来Problem过滤。

Snapshot repository protocol只暴露put/exact replay与按ID/hash读取；SQLAlchemy adapter属于Infrastructure并永久绑定单一data plane。Snapshot事实变化必须构建新identity，不存在Domain update/delete。COMPLETED/RUNNING继续作为cutoff事实保存；哪些实例进入未来PlanningProblem仍由TASK-P1-09决定，当前未创建Solver模型或ScheduleVersion。

## TASK-P2-01 PlanningProblem v2 domain projection

`app.planning.problem`新增独立JSON-compatible v2 types，而不修改canonical entities或Snapshot v2。DeliveryDemand把DemandOrder due/source与外部显式priority/source投影到future Problem；Resource投影保留Factory→Workshop→ProductionLine→ResourceGroup拓扑、calendar、capabilities与primary `capacity=1`；active OperationInstance增加DemandOrder和business capability引用。

COMPLETED OperationInstance本体继续留在Snapshot事实层且不进入future operation set。只有作为active successor前驱时，Problem v2创建sourced HistoricalCompletionAnchor并保留edge/lag；OperationLock按Snapshot引用与cutoff活动性投影。上述都是immutable input facts，不是Schedule、Solver variable、ORM/API DTO或P3 business state。
