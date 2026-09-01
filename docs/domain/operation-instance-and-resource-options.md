---
doc_id: DOC-DOM-002
title: OperationInstance 与候选资源语义
status: baseline
spec_version: 0.3.0
phase: P0-P6
normative: true
source_sections: [19, 20, 21, 25, 26]
last_reviewed: 2026-09-01
---

# OperationInstance 与候选资源语义

## P6-06 local runtime authority boundary

Runtime request必须把factory/operation/resource option/resource identity与独立的`seconds/duration_source/source_version/source_record_id/source_record_fingerprint`标准工时authority一起传入。Provider验证FeatureRecord中同一option的`standard_duration_seconds`及source引用逐字匹配，但从不把FeatureRecord自身当作标准工时的唯一authority，也不回写`OperationResourceOption.final_duration_seconds`。

只有exact model/Gate/policy/feature全部通过且confidence≥`9/10`时，独立Prediction carrier可选择model p50；否则carrier选择请求中的exact standard duration。标准工时缺失、非正、来源无效或无法绑定同option时不允许“fallback的fallback”，而是fail closed。当前carrier未进入PlanningProblem，RUNNING remaining、COMPLETED actual及全部candidate/resource语义保持不变。

## P6-03 dataset consumption boundary

Dataset builder只读取source record中已版本化的operation/resource-option/resource ID以及decision cutoff前可用的`standard_duration_seconds`；它不改写`OperationResourceOption`或为缺失option补值。输出FeatureRecord保持同一operation/resource option/resource精确关联，label provenance另指向明确completed Simulation execution record。

标准工时值即使与显式actual label相等也仍是feature/authority evidence而非label来源。RUNNING/INTERRUPTED事实不被转换为普通completed label，dataset不计算remaining/freeze、不改变actual fact优先级，也不进入PlanningProblem。P6-04+若消费manifest必须使用其不可变ID/fingerprint，而不能回写本文件定义的owner对象。

## P6 duration candidate and fallback boundary

ADR-0016确认本文件既有`final_duration_seconds`、`duration_source`与`source_version`仍是每个resource option的标准工时authority。未来DurationPrediction只能以独立、versioned、可审计carrier提供候选；不得原地改写option、合并不同resource的duration或把候选写回历史Snapshot/Problem。Consumer遇到缺失、invalid、低置信度、版本不兼容、未批准、drift或provenance不全时必须选择同一option的标准工时。

COMPLETED的actual resource/time和RUNNING的权威remaining/freeze事实优先于prediction。标准工时本身缺失、无效或冲突时，该option继续由Data Validation fail closed，模型不能成为fallback的fallback。TASK-P6-01尚未发布Prediction Schema或改变任何existing carrier。

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

## TASK-P1-02 v2 contract

`canonical-records.v1`要求每个`routing_resource_option`显式提供routing operation/resource引用、quantity unit、setup/cycle/final seconds、duration source及其version；`final_duration_seconds > 0`，不含default。`planning-snapshot.v2`的expanded option用`source_version`保留该duration source version，并由pure precheck验证所有candidate字段与canonical option逐项一致。

Snapshot v2的OperationInstance显式引用DemandOrder、ProductionOrder、ProductionLot、RoutingVersion和RoutingOperation，并要求status、quantity/unit、due/release/material UTC、required capabilities、至少一个candidate与lock IDs；RUNNING/COMPLETED必须引用execution fact，NOT_STARTED禁止该引用。Schema/precheck只固定形状和copy不变量；stable ID算法、DAG expansion、completed过滤、capability/data-quality判定与future Problem投影仍分别属于TASK-P1-06/07/09。

## TASK-P1-06 candidate-input gate

Data Validation在Expansion前要求每个RoutingOperation至少一条显式`routing_resource_option`；option的resource必须存在，operation/resource logical pair唯一，setup/cycle为非负整数秒、final duration为正整数秒，且duration source/version非空。缺少duration字段或provenance返回`MISSING_DURATION`，非法数值返回`INVALID_DURATION`，不得补guess或统一工时。

普通设备required capability必须由至少一个候选Resource完整满足；无option、orphan resource或零capability-eligible option返回`MISSING_RESOURCE`。ExecutionFact/OperationLock resource还必须属于其routing operation的显式option。该Gate不选择资源、不计算实例duration、不做C-003/C-010 schedule判定；TASK-P1-07仍负责确定性实例展开。

## TASK-P1-07 expansion semantics

`order-expansion.v1`为每个显式`ProductionLot × RoutingOperation`生成且只生成一个OperationInstance；多lot只有在source已明确给出时才产生，不执行自动拆分/合并。实例复制DemandOrder/ProductionOrder/Lot/RoutingVersion/RoutingOperation IDs、lot quantity/unit、due/release/material UTC与required capabilities。每个candidate按`routing_resource_option_id`排序并逐字段复制resource、setup/cycle/final seconds、duration source及`duration_source_version → source_version`，不按lot quantity重新推算duration。

实例ID的versioned lineage为`[lot_id, routing_operation_id]`，edge ID为`[lot_id, routing_precedence_edge_id]`；canonical JSON SHA-256使输入collection顺序不影响输出。branch/merge、cross-workshop transport lag与max lag只按Routing DAG逐lot复制，不被线性化。RUNNING/COMPLETED绑定唯一fact，NOT_STARTED无fact；locks按同一lot/operation lineage复制。缺candidate/duration或请求SPLIT_MERGE明确失败，不选择资源、不生成Snapshot/Problem。

## TASK-P1-09 future Problem projection

Problem builder以Snapshot `operation_instance_id → operation_id`逐字保留active实例身份、release/material gate和全部candidate六字段；不按quantity重算setup/cycle/final duration。Candidate按resource/duration/source稳定排序，权威`final_duration_seconds`保持整数秒，ceiling tick只用于horizon完整性检查。Data Validation已验证的CUTTING等业务capability通过candidate eligibility体现；Problem顶层只声明platform capability，不混用两类词汇。

RUNNING通过`execution_fact_id`解析actual start、assigned resource和remaining seconds，历史start保留但未来occupancy从horizon start计算。COMPLETED实例不进入未来Problem；两端均completed的edge排除，completed-active edge因v1无法保留historical lag而明确unsupported。Active operation的lock若与horizon相交也明确unsupported；历史/horizon外lock不改变当前Problem。本Task不选择candidate、不改变fact、也不实现C-007/C-008 candidate ScheduleValidator。

## TASK-P2-01 v2 operation and resource facts

Problem v2的active OperationInstance保留`demand_order_id`与`required_capabilities`，candidate option六字段和ceiling-tick horizon检查仍沿用v1确定性语义。完整Resource fact不再只是一组ID：每项必须包含code/type/status、Factory/Workshop/Line/Group IDs、calendar、capabilities和整数`capacity=1`。Builder仍不选择candidate或重算duration；capacity=1只为后续C-003提供primary unary input，不代表C-012 secondary capacity。

Completed实例只在其为active successor的前驱时以HistoricalCompletionAnchor表达，不重新成为可排程OperationInstance。v2 Schema、semantic precheck与hash验证active/anchor集合互斥、candidate/resource引用完整、RUNNING assigned resource属于candidate。Solver、presence变量、NoOverlap和C-010仍由后续Task实现。
