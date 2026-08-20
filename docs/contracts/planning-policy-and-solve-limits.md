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
