---
doc_id: DOC-CORE-002
title: 工程原则与不可破坏不变量
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [1, 2, 10, 12, 15, 23, 24, 28, 30, 59, 62, 90, 108, 111]
last_reviewed: 2026-08-19
---

# 工程原则与不可破坏不变量

## 优先级

```text
Correctness
→ Explainability
→ Reproducibility
→ Feasibility
→ Performance
→ Optimization Quality
→ Advanced Capability
→ AI
```

任何优化不得通过降低硬约束正确性、可追溯性或独立验证能力实现。

## 系统不变量

1. Simulation 数据必须通过正式 Import Contract、Normalization、Snapshot 和 PlanningProblem 链路。
2. 领域层不得依赖 OR-Tools；OR-Tools 对象只能存在于 `planning/backends/cp_sat/`。
3. Solver 与 ScheduleValidator 独立；Validator 不导入 CpSatBackend、不复用 CP-SAT Constraint Builder、不信任 Solver 状态。
4. PlanningSnapshot 和 PlanningProblem 必须 deterministic、replayable、hashable；PlanningProblem 还必须 Solver-neutral。
5. PUBLISHED ScheduleVersion 不可修改；UI 拖拽必须形成新 Draft 并经过服务端验证。
6. Production 与 Simulation 至少使用独立数据库；生产默认禁用 Simulation API。
7. AI 只能预测 duration、risk、confidence，不能改变 routing、resource compatibility、hard constraint 或 schedule state。
8. 未支持能力必须返回 `UNSUPPORTED_CAPABILITY`，不能静默忽略或用简单逻辑近似。
9. 不能删除硬约束来解决 INFEASIBLE，也不能修改断言掩盖失败。
10. `FEASIBLE`、`INFEASIBLE`、`UNKNOWN`、`MODEL_INVALID` 等状态必须保持产品语义。

## 未知事实处理

生产参数未知时：

- 登记 `PROD_OPEN`；
- 开发、仿真和 Benchmark 可以继续；
- 生产发布必须被阻止；
- 如需仿真假设，单独登记 `SIM_ASSUMPTION`；
- 不允许将仿真假设升级为生产默认值。

## 偏离规则

MUST/MUST NOT 不允许任务级绕过。偏离 SHOULD 或修改 DECIDED 边界必须通过 ADR，并说明 Requirement、Schema、Validator、Fixture、Benchmark、风险和回滚影响。
