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

## TASK-P4-09 deterministic producer

Execution Simulator core现在是`execution-event.v1`的producer、P4-04 `ingest_event`的consumer。它先把PUBLISHED base、versioned Scenario/Profile/Generator/Simulator、seed、virtual clock与event schedule绑定为run fingerprint，再按`(offset_seconds, named-child-seed rank, event_key)`生成连续source positions、deterministic occurred/received UTC、exact entity refs及content-derived event ID/fingerprint。完整prefix先经P4-04 strict validator；任一invalid payload/time/reference/source会在首个ingress call前拒绝。

Simulator不创建ReplanRequest、不投影事实、不调用Solver/Replan、不写ScheduleVersion。Checkpoint只保存run fingerprint、last emitted position和prefix fingerprint；existing manifest的fact checkpoint必须由下游显式提供。五类连续场景仍归TASK-P4-10。

## TASK-P4-04 ingestion and projection consumer

P4-04实现全部11个既有ExecutionEvent type的strict Simulation runtime消费：root/payload exact fields、canonical fingerprint/event ID、authority/scope/stream、source position、UTC/provenance与entity refs先验证，再按完整连续prefix投影。Ingress事务只写ledger+`EXECUTION_EVENT_APPENDED` audit；projection事务只写new immutable PlanningSnapshot、CAS checkpoint与`PROJECTION_CHECKPOINT_COMMITTED` audit。Exact replay返回既有identity；different content、gap/late、terminal regression、invalid ref、stale base、cross-plane或写入失败均fail closed。

本Task不创建ReplanRequest，也不解析其freeze、Policy/Limits、Solver、Validator、ChangeReport或new ScheduleVersion字段。Urgent Demand event只携带identity/quantity/due/priority source，canonical demand/order/lot必须由完整Standard Import链产生；private canonical/Snapshot injection不构成合法输入。Implementation `47f55b41e370aa9d24fd9c987cff4663672c3ee8` / artifact `9644190441`已把该runtime consumer evidence升级为`PROVIDER_VERIFIED`。


## TASK-P4-03 durable consumer

P4-03现建立Simulation-only durable consumer：ExecutionEvent按`event_id`和authority/stream/position双重唯一约束append，exact bytes replay返回同记录，不同content冲突；projection checkpoint只可通过position+revision CAS前进；ReplanRequest必须在同plane找到完整有序ledger events与匹配fact checkpoint后才能append。Request不新增state，attempt/result只引用既有PlanningRun attempt与terminal state；ChangeReport、SolverReport、ValidationReport和new ScheduleVersion只保存version/id/fingerprint引用，内容生成与应用仍由P4-06/07/08负责。

所有写primitive提供caller-owned transaction入口，允许ledger+audit或checkpoint+request+audit原子提交/回滚。P4-03没有event endpoint、事实投影、Solver/Simulator、publish/export、external delivery或Production authority。

## TASK-P4-02 machine carriers

`execution-event.v1`现把Simulation plane/environment/factory/scope、authority/source stream、单调position、occurred/received UTC、entity refs、typed payload、correlation、synthetic provenance与canonical fingerprint编码为strict carrier。`received_at_utc`只记录接收观察，不参与event identity；authority、ordering和payload语义参与fingerprint。同identity不同fingerprint、position gap/倒退、authority/scope/plane漂移均fail closed。

`replan-request.v1`现绑定immutable PUBLISHED base Version、base/new Snapshot与Problem、ordered event stream/fact checkpoint、reason set、半开resolved freeze区间、effective locks、Policy/Limits及request fingerprint。Request没有业务state；sample只证明合同与lineage，不投影事实、不创建Snapshot、不调用Solver，也不创建new ScheduleVersion。Durable transaction、projection与application仍分别属于P4-03、04、08。

## TASK-P4-01 accepted contract baseline

[ADR-0013](../adr/ADR-0013-execution-event-authority-fact-projection-replan-lineage.md)、[ADR-0014](../adr/ADR-0014-freeze-window-stability-change-report.md)和[ADR-0015](../adr/ADR-0015-deterministic-execution-simulator-common-path.md)现已在任何P4 Schema/migration/code前固定事件authority/order/idempotency、事实投影、ReplanRequest、freeze/OBJ-002/ChangeReport及Simulator共同路径。TASK-P4-02才可发布机器字段/URN/version，TASK-P4-03/04/08分别拥有durable transaction、ingestion/projection与new DRAFT应用；本Task没有event endpoint、repository、业务实现或真实MES来源。

## V1 ExecutionEvent 类型

`OPERATION_STARTED`、`OPERATION_COMPLETED`、`MACHINE_UNAVAILABLE`、`MACHINE_RECOVERED`、`MATERIAL_READY`、`MATERIAL_DELAYED`、`PROCESSING_DURATION_CHANGED`、`PROCESSING_REMAINING_CHANGED`、`URGENT_DEMAND_RECEIVED`、`LOCK_CREATED`、`LOCK_RELEASED`。

每个事件至少需要stable event identity、event type、business `occurred_at`、transport `received_at`、data plane/environment/factory scope、authority source stream/version、单调source position、entity refs、payload version、canonical fingerprint、correlation和conditional synthetic provenance。`received_at`不参与业务顺序或identity。

同scope/identity与同fingerprint只重放原logical result；不同fingerprint为conflict。position gap只保留可审计接收记录并阻断projection，late position不得改写历史事实。P4只支持一个authority stream/事实scope；多writer merge需要新ADR。Production authority尚未形成，因此默认拒绝；Simulation test authority必须显式`production_binding=false`。

Ingress只append ledger/audit；连续event或确定性batch的projection在另一原子事务中提交append-only fact revision、new immutable Snapshot、ReplanRequest、checkpoint/result和audit references。任一错误不得留下partial fact/Snapshot/Request；event不能直接修改ScheduleVersion、Problem或Solver参数。

## ReplanRequest

```text
base_schedule_version_id + content_fingerprint
base_snapshot_id
new_snapshot_id
ordered event/fact references
replan_reason
freeze policy/version + resolved half-open window
planning policy / solve limits references
request fingerprint + plane/scope/correlation
```

请求必须指向不可变base PUBLISHED Version和new Snapshot，并由完整内容确定identity。一个request对应一个明确projection batch；coalescing/debounce必须版本化且无隐式默认。ReplanRequest不拥有独立状态机：每次solve attempt复用PlanningRun状态机，request/result/audit以append-only references连接。Retry不得伪造成request self-transition。

## 事实保护

新的计划必须保持completed/running事实、显式HARD_LOCK和freeze-derived effective HARD lock；冲突fail closed。SOFT_LOCK与非冻结旧计划只通过ADR-0014的整数OBJ-002向量计价。Candidate必须经fresh independent Validator，随后在同一result transaction写new DRAFT、完整ChangeReport、request result和audit；base PUBLISHED不改且不自动approve/publish/export。

Execution Simulator只输出同一Event合同并通过同一ingress/application路径。其virtual clock、seed、simulator/scenario/profile versions、source positions和stream hash必须可重放；不得直接写fact/Snapshot/Version。具体值留给versioned SIM_ASSUMPTION，不能成为Production默认。

## Schema、state、migration与error边界

当前schema set仍为`2.7.0`，本Task不创建Schema。TASK-P4-02必须以additive新document发布ExecutionEvent、ReplanRequest、ChangeReport和必要Simulator carrier，保留P2/P3 bytes并提供strict/no-default/offline refs/fingerprint/negative interchange。TASK-P4-03才可建立ledger/fact/request/checkpoint/result persistence；DDL不得反向发明默认语义。

PlanningRun、ScheduleVersion、ExportJob既有state/pair全部不变；ReplanRequest和Simulator checkpoint均不是业务状态机。未知version/type/authority、duplicate conflict、gap/late、stale base、cross-plane、missing provenance、Validator/report failure均无成功副作用；UNKNOWN继续不等于INFEASIBLE。P4 Test ID仍为`PLANNED`，本合同本身不是行为证据。
