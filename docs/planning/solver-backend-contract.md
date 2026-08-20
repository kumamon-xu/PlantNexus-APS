---
doc_id: DOC-PLAN-001
title: SolverBackend 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24, 29, 57, 93, 102]
last_reviewed: 2026-08-20
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

TASK-P0-05 的 Generator protocols 明确终止于 Standard Import package，不导入 PlanningProblem 或 SolverBackend。ScenarioSpec `expected_behavior` 只是未来运行的允许结果合同；Schema sample 中的 FEASIBLE/OPTIMAL 不是 Solver evidence。无 Backend/dependency/parameter/version 变化，因此不触发 Solver upgrade replay。

## TASK-P0-08 dependency and worker review

新增 FastAPI/DB/Redis/Celery/logging/trace runtime pins 不含 OR-Tools，`uv.lock` 与 integration tests 明确检查 solver-free dependency graph。Celery `worker` 目前不注册 Planning/Solver task；JobRecord 也不包含 PlanningProblem 或 OR-Tools object。没有 Backend、CpModel、IntervalVar、Solver status/parameter/report 或 performance artifact，因此不触发 Solver upgrade ADR/replay，P2 首次 Solver gate 保持原要求。

## TASK-P1-02 contract boundary review

Canonical records、Import v2与Snapshot v2均为JSON-compatible machine合同/pure types，不导入`planning.backends`或OR-Tools。Snapshot v2的OperationInstance/resource option payload保留未来PlanningProblem builder所需的candidate级seconds/source version，但本Task不构建Problem、tick、CpModel、SolverBackend、PlanningSolution或status。Solver-neutral边界未改变，OR-Tools upgrade/Benchmark replay Gate不触发。

## TASK-P1-04 dependency boundary review

`openpyxl==3.1.5`、`defusedxml==0.7.1`和transitive `et-xmlfile==2.0.0`只用于XLSX transport parsing；lock中仍无OR-Tools。Reference Adapter输出opaque Raw Staging rows，不构建canonical Import、PlanningProblem、tick、CpModel、SolverBackend、PlanningSolution或status，且`importers`不导入`app.planning`。

因此本Task不触发Solver upgrade/ADR/Golden/Scenario/Benchmark Gate。未来Backend不能直接读取CSV/XLSX或绕过Normalization/DataValidation/Snapshot/Problem builder。

## TASK-P1-05 dependency boundary review

Schema metadata提升到`2.1.0`但runtime dependency和`uv.lock`图不变，仍无OR-Tools。`app.normalization`输出Import v2 JSON bytes/hash，不构建PlanningProblem/tick/CpModel/IntervalVar/SolverBackend/PlanningSolution/status，并以source scan禁止`app.planning`/OR-Tools import。

因此Solver upgrade/ADR/Golden/Scenario/Benchmark Gate不触发。未来Backend只能消费TASK-P1-09的solver-neutral PlanningProblem，不能直接读取Normalization result来跳过Data Validation、Expansion与Snapshot。

## TASK-P1-06 dependency boundary review

Schema set提升到`2.2.0`只新增Error/ImportQualityReport/Data Validation；runtime dependency和`uv.lock`图不变且仍无OR-Tools。Evaluator终止于PASS/FAIL report，不构建OperationInstance、PlanningProblem/tick/CpModel/IntervalVar/SolverBackend/PlanningSolution/status，也以source scan禁止Planning/Solver/ScheduleValidator import。

因此本Task不触发Solver upgrade、ADR、Golden/Scenario或Benchmark replay。未来Backend仍只能消费TASK-P1-09的Problem，并且上游必须已有与同一Import绑定的PASS quality report；Backend不得把FAIL输入解释为INFEASIBLE或尝试“修复”。

## TASK-P1-07 solver-neutral expansion review

`domain.production`与`normalization.order_expansion`只使用JSON-compatible TypedDict/dataclass和标准库，输出OperationInstance/edge facts供未来Snapshot/Problem consumer使用；source scan与全仓回归继续证明无`app.planning`、OR-Tools、CpModel或IntervalVar。COMPLETED实例保留在事实输出，TASK-P1-09才负责从未来Problem排除；Backend不得直接读取Import或Expansion来绕过Snapshot/Problem builder。

新增Hypothesis/sortedcontainers仅为dev/property test lock，不是Solver dependency。没有Backend/version/status/parameter、PlanningProblem hash、model build或BenchmarkReport，因此Solver upgrade/replay Gate不触发；P2首个baseline必须记录`order-expansion.v1`及实际instance/edge/candidate counts。

## TASK-P1-09 executable Problem boundary

`app.planning.problem`现已形成`planning-problem-builder.v1`、`planning-problem-hash-projection.v1`、canonical bytes及immutable value；source scan与dependency lock继续证明没有OR-Tools、CpModel、IntervalVar、ORM、API或Infrastructure import。Builder调用既有pure Problem precheck并检查active DAG，但不会创建decision variable、Backend、solution/status/report或执行Solver。

未来Backend必须消费已通过`verify_problem`的canonical Problem，而不能直接读取Snapshot/Import/Expansion；其版本/参数仍须单独进入SolverReport和Benchmark。当前`planning-problem.v1`对active lock与completed-to-active historical lag表达不足时builder会在solve前拒绝，Backend不得静默忽略或将其映射为INFEASIBLE。本Task未改Solver protocol、依赖、升级策略或Benchmark baseline。

## TASK-P2-01 v2 Backend handoff boundary

P2 Backend的未来输入版本现固定为通过`verify_problem_v2`的immutable `planning-problem.v2`，其中due/priority、complete primary Resources、active locks和historical anchors均进入versioned hash projection。Backend不得继续以v1缺口为由读取Snapshot旁路补字段，也不得忽略v2 required fact或把contract rejection映射为INFEASIBLE。

P2-01没有创建Backend/Strategy protocol实现、Solver status、variables/constraints、OR-Tools依赖或参数。v1仍是Application默认builder，v2为version-specific opt-in；真正consumer切换及Policy/Limits/Solution合同必须等待P2-02，OR-Tools必须等待P2-03和独立ADR。
