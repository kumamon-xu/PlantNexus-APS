---
doc_id: DOC-PLAN-001
title: SolverBackend 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24, 29, 57, 93, 102]
last_reviewed: 2026-08-19
---

# SolverBackend 合同

```python
class SolverBackend(Protocol):
    def solve(
        self,
        problem: PlanningProblem,
        policy: PlanningPolicy,
        limits: SolveLimits,
    ) -> PlanningSolution:
        ...
```

## 边界

- Domain、PlanningProblem 和协议不依赖 OR-Tools。
- OR-Tools 对象只存在于 `planning/backends/cp_sat/`。
- Backend 不批准、不发布计划，也不代替 ScheduleValidator。
- Backend 不从数据库或 API Controller 隐式读取业务事实；全部求解输入来自显式合同。

## 输出

PlanningSolution 至少包含状态、assignments、目标阶段结果、best bound/gap、build/first-feasible/solve timing、模型规模、内存、参数、Solver exact version 和诊断。

## 状态

`OPTIMAL`、`FEASIBLE`、`INFEASIBLE`、`UNKNOWN`、`MODEL_INVALID`、`CANCELLED`、`FAILED` 保持原义。UNKNOWN 映射 `NO_SOLUTION_WITHIN_LIMIT`，不能伪装成无解。

## 升级

Backend/OR-Tools 升级必须经过 ADR、dependency lock、Golden/Scenario replay、Benchmark comparison 和状态合同测试。显著正确性或性能退化阻止发布，除非有批准 ADR。

## P0-03 boundary

`planning-problem.v1` JSON Schema 与 `PlanningProblemDocument` pure type 已形成，满足可序列化、Solver-neutral、无 OR-Tools 类型的输入骨架。Problem builder、PlanningPolicy、SolveLimits、PlanningSolution、Strategy 和任何 Backend 均未实现；没有 Solver status、model size 或 performance artifact。P2 首次实现必须在固定 Scenario Set 上回放本合同并补齐 benchmark evidence。
