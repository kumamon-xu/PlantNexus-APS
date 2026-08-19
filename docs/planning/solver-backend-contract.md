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

## P0-04 rule/error boundary

`constraint-rule-sheet.v1` 将 C-001～C-011 validator formula 与 C-012～C-018 rejection metadata 固定下来，但没有新增 Backend、constraint builder 或 solver dependency。`UNSUPPORTED_CAPABILITY` precheck 在 model construction 前拒绝明确未支持/延迟声明；它不得由 Backend 静默忽略。

PlanningRun 的 MODEL_INVALID/INFEASIBLE/NO_SOLUTION_WITHIN_LIMIT 与 error.v2 映射保持原义；P0 没有 Solver status artifact。Rule-sheet completeness module 不导入 `planning.backends`/OR-Tools，也不是 ADR-0005 ScheduleValidator evaluator。
