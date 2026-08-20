---
doc_id: DOC-CONTRACT-005
title: PlanningSolution 与 ScheduleVersion 合同
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [29, 30, 32, 33, 67, 78]
last_reviewed: 2026-08-19
---

# PlanningSolution 与 ScheduleVersion 合同

PlanningSolution 是 SolverBackend 的候选输出，应包含 Solver 状态、operation assignments、objective/bound/gap、diagnostics 和 provenance。它不代表已经验证、批准或发布。

## Operation assignment

每个被排 Operation 至少给出 operation ID、selected resource、start/end tick 和可还原 UTC 时间、duration、lock/execution references。不得只返回展示用 Gantt 坐标。

## 从 Solution 到 Version

```text
PlanningSolution
→ independent validation
→ validation report PASS
→ DRAFT ScheduleVersion
→ READY_FOR_REVIEW
```

如果验证失败，PlanningRun 进入 VALIDATION_FAILED，不得生成可评审版本。

## ScheduleVersion

ScheduleVersion 必须引用 source PlanningRun、Snapshot、Problem、base version（若 Replan）、validation report、KPI、ChangeReport 和 audit。版本内容在 PUBLISHED 后不可变。

只有 APPROVED version 可以发布。所有编辑、拒绝后修订和 Replan 产生新 version ID。

## P0 state contract boundary

[`state-transition.v1`](../../schemas/json/state-transition.schema.json) 只验证 machine/state 名称；[`state-machines.v1`](../../schemas/rules/state-machines.v1.yaml) 与纯状态枚举共同固定允许 pair、终态、guard/evidence 文本。`DRAFT → PUBLISHED` 即使字段名称合法也必须由 transition table 拒绝为 `INVALID_STATE_TRANSITION`。

这些 artifact 不持久化状态、不执行审批/发布、不解决 OPEN-010 权限角色。P3 实现必须保留 ADR-0007 的新版本/不可变语义，并把 actor、reason、audit、idempotency 等 guard evidence 落为真实记录。

## TASK-P2-02 PlanningSolution v1 boundary

[`planning-solution.v1`](../../schemas/json/planning-solution.schema.json)固定Problem v2、Policy v1和Limits v1引用，assignment按operation ID唯一有序，保存resource、start/end tick、由horizon/tick精确还原的UTC、权威duration seconds以及lock/execution fact IDs。`duration_ticks=ceil(duration_seconds/tick_seconds)`；非candidate状态禁止assignments。

P2只允许一个OBJ-001 stage。由于weighted tardiness与bound均为非负整数，`relative_gap=(objective_value-best_bound)/max(1, objective_value)`且范围为`[0,1]`；bound不得大于minimization candidate objective。OPTIMAL还要求objective等于best bound且gap为0；FEASIBLE要求objective/bound/gap存在但不冒充最优；UNKNOWN不得携带candidate objective/gap；INFEASIBLE/MODEL_INVALID/CANCELLED/FAILED均不得携带objective/bound/gap。Stage solve time不得超过显式stage budget，所有非candidate结果必须提供sanitized diagnostics。

本合同是candidate carrier，不是独立ScheduleValidator结果。只有未来`SOLVER_RUN`且通过独立ValidationReport的candidate才能进入后续ScheduleVersion流程；本Task发布的UNKNOWN `CONTRACT_SAMPLE`没有candidate，也不创建DRAFT、READY_FOR_REVIEW或任何P3状态。

## TASK-P2-04 Validator consumption

正式Validator现直接消费`planning-solution.v1`的Problem reference与assignments，并逐项对照权威PlanningProblem v2；Policy/Limits/objective/declared solver status不参与schedule validity。Schema-valid positive vector先通过`validate_planning_solution`，随后由独立Evaluator重算C-001～C-011；status矛盾测试故意绕过machine-contract precheck，只用于证明Validator不把status当oracle，不能作为可持久化PlanningSolution。

Assignment的tick/seconds/UTC在formal边界重新核对。NOT_STARTED duration来自selected option；RUNNING future occupancy与`duration_seconds`来自Problem的`remaining_seconds`。Validation FAIL映射Error v2，不创建或迁移ScheduleVersion，也不改变四份P2-02 Schema/sample bytes、global schema set或canonical fingerprint规则。

## TASK-P2-05 core candidate mapping

完整native candidate被映射为每operation恰一条assignment，保存selected resource的原始seconds、ceiling ticks及由horizon start还原的UTC；只有formal Validator PASS时才保留assignments。INFEASIBLE/UNKNOWN/MODEL_INVALID/FAILED等非candidate状态必须输出空assignments，不能泄漏部分解。

PlanningSolution v1要求的OBJ-001 stage在本Task只承载post-solve measurement：状态为FEASIBLE、best bound为通用0、gap按已测值计算，并以`CORE_FEASIBILITY_ONLY_*_OBJECTIVE_NOT_OPTIMIZED`明确未运行目标搜索。Schema、ScheduleVersion迁移与publishability均不变；所有candidate只作为测试artifact。
