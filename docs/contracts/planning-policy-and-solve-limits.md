---
doc_id: DOC-CONTRACT-004
title: PlanningPolicy 与 SolveLimits 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 28, 29, 35, 57, 96]
last_reviewed: 2026-08-19
---

# PlanningPolicy 与 SolveLimits 合同

## TASK-P4-05 versioned Simulation freeze policy

唯一已实现policy为`POLICY-P4-SIM-DYNAMIC-FREEZE-001@1.0.0`，内含`FREEZE-POLICY-P4-SIM-001@1.0.0`与显式source `SIM-P4-FREEZE-001`；窗口为900正整数秒，anchor只取verified new Snapshot `cutoff_at_utc`，区间固定为half-open `[cutoff, cutoff+900s)`。任何不同policy bytes、Production plane、缺失source/version或非整秒anchor都在solve前拒绝；OPEN-005继续阻止Production默认。SolveLimits、OBJ-002执行和Solver策略未由本Task修改。

## TASK-P4-02 PlanningPolicy v2 carrier

`planning-policy.v2`是与v1不可互换的Simulation carrier，显式引用policy source/revision/fingerprint和freeze policy，并把目标固定为exact lexicographic `OBJ-001 delivery → OBJ-002 stability → OBJ-003 makespan`。OBJ-002依次最小化SOFT lock violations、changed existing operations、resource changes与absolute start shift seconds；禁止加权和、隐式priority或Production默认。SolveLimits继续复用v1 exact reference，本Task不改变其字段、默认或执行行为。

## TASK-P4-01 policy decision

ADR-0014固定freeze policy必须显式versioned，以new Snapshot cutoff解析half-open interval并保存source/fingerprint；缺少approved Production policy时拒绝，不采用0或仓库样例默认。OBJ-002在Delivery等价后以`soft lock violations → changed existing operations → resource changes → absolute start shift seconds`的非负整数向量逐层优化，Makespan仅在完整Stability相等后tie-break。

TASK-P4-02必须以additive新document/version表达freeze、objective stages与exact references；P4-06/07才可计算/求解。当前PlanningPolicy v1、SolveLimits v1、OBJ-001、OR-Tools pin与Production limits/SLA完全不变，未形成Production freeze、priority或capacity默认值。

## PlanningPolicy

PlanningPolicy 描述业务允许的计划策略，例如目标层级、交期权重来源、Replan 稳定性、freeze/lock 语义。V1 目标按词典序执行：Delivery → Stability（Replan）→ Makespan。

Policy 不得包含随意混合的 `0.6/0.3/0.1` 权重，不得允许关闭硬约束。未确认的业务优先级/冻结窗口分别引用 OPEN-006/005。

## SolveLimits

SolveLimits 描述计算预算，例如 wall time、worker/resource limit 和允许的求解参数。它可以终止搜索，但不能改变业务事实、候选设备、duration 或 Constraint。

## 可追溯性

每次运行必须记录 Policy version、limits、Solver exact version 和完整参数。相同 Problem/Policy/Limits 不保证相同 Gantt 排序，但必须满足相同合同和可重放诊断。

## 状态语义

Limits 到期且 Solver 不能给出认证结论时返回 UNKNOWN，并映射 `NO_SOLUTION_WITHIN_LIMIT`。有已认证可行解时可以返回 FEASIBLE，但不得描述为最优。

## TASK-P2-02 machine contract

[`planning-policy.v1`](../../schemas/json/planning-policy.schema.json)要求`schema_set_version=2.4.0`、显式`SIMULATION/PRODUCTION` data plane、policy ID/revision/source、`canonical-json.v1`、`constraint-rule-sheet.v1`和`objective-policy.v1`。P2 slice的硬约束列表必须按C-001～C-011完整有序出现，且只允许一个`OBJ-001/WEIGHTED_TARDINESS/MINIMIZE` stage；硬约束不能由policy关闭，OBJ-002/003不能提前混入。

[`solve-limits.v1`](../../schemas/json/solve-limits.schema.json)要求limits ID/revision/source与显式`max_wall_time_seconds`、`max_workers`、`random_seed`。Schema不含`default`；仓库sample的30秒/1 worker/seed只属于`SIMULATION`合同样例，不是Production默认、SLA或推荐参数。Solution和Report必须逐值复制这三个limit并引用完整Policy/Limits canonical fingerprint，任何缺失、类型漂移或来源不一致均在执行边界拒绝。

四份sample通过稳定URN离线解析；pure validation进一步固定跨文档fingerprint、OBJ-001和limit budget一致性。它们的`CONTRACT_SAMPLE`标识明确说明没有Solver执行，不能用于声明可行性、最优性或性能。

## TASK-P2-03 CP-SAT parameter mapping

Adapter精确映射`max_wall_time_seconds→max_time_in_seconds`、`max_workers→num_search_workers`、`random_seed→random_seed`，并固定Backend-owned `log_search_progress=false`。参数报告按name稳定排序并记录`SOLVE_LIMITS`或`BACKEND`来源；不读取环境、不补默认值、不改变P2-02 sample或fingerprint。

本Task只验证参数可写入native solver。`CpSatBackend.solve()`尚无业务model builder，因此不会把Policy内C-ID/OBJ-001转成约束或目标，也不会生成`SOLVER_RUN` PlanningSolution/SolverReport。

## TASK-P2-08 executable Simulation policy

仓库现批准唯一`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`：data plane=`SIMULATION`、C-001～C-011完整有序、单一OBJ-001 stage，source=`plantnexus-synthetic-policy@1.0.0`。Strategy要求Problem的每个priority weight使用同一versioned synthetic source；任意Production data plane、policy drift或priority source drift均在Backend调用前显式拒绝。OPEN-006/011/012继续阻断Production。

`simulation_solve_limits`要求调用方逐项提供ID/revision/source record、wall time、workers和seed，不提供默认值。Backend继续精确映射native参数；SolverReport同时记录合同字段名与native映射名并按name排序。Policy/Limits Schema/version/fingerprint算法未改变，OBJ-002/003仍不允许进入stage。

## TASK-P2-14 Exit audit

独立Gate与四类exit rejection确认唯一Simulation OBJ-001 Policy、显式SolveLimits来源、native参数映射及UNKNOWN/no-candidate边界均PASS；`INVALID_SOLVE_LIMITS`与Production policy拒绝继续fail-closed。合同字节、默认值政策、dependency与ADR均无变化；OPEN-006/011/012继续阻止把本次READY外推为Production权重、limits或SLA。
