---
doc_id: DOC-PLAN-001
title: SolverBackend 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24, 29, 57, 93, 102]
last_reviewed: 2026-08-21
---

# SolverBackend 合同

## P4 planned replan backend impact

TASK-P4-07在P4-04/05/06完成后才可添加replan solve orchestration，输入必须是版本化Problem/Policy/Limits及base schedule projection，输出必须honest status、分层objective与deterministic report；随后独立Validator决定可接受性。现有CP-SAT Backend、OR-Tools pin、limits、seed/workers及P2 benchmark contract不变。

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

## TASK-P2-02 protocol and report contract

`app.planning.contracts.SolverBackend`现以Protocol固定Problem v2、PlanningPolicy v1、SolveLimits v1到PlanningSolution v1的solver-neutral调用边界，但没有任何实现实例。Policy/Limits/Solution/Report均为JSON-compatible TypedDict与pure validation；source/dependency扫描禁止CpModel、IntervalVar、OR-Tools、ORM、FastAPI和later-layer imports。

SolverReport v1保存exact backend/solver name+version、按name有序参数、Problem/Policy/Limits/Solution引用、七种status的唯一PlanningRun/error outcome、OBJ-001 stage、model build/first feasible/solve/validation/total timing、variables/constraints/optional intervals、memory与完整version/code-commit provenance。`CONTRACT_SAMPLE`报告使用not-installed solver、零模型规模和UNKNOWN，只证明字段合同；P2-03才可安装Backend依赖并产生真实`SOLVER_RUN`，且不得绕过P2-04独立Validator。

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

## TASK-P2-03 CP-SAT foundation

ADR-0011固定`ortools==9.15.6755`和`cp-sat-backend.v1`。Canonical `SolverBackend` Protocol继续保持Problem v2 + PlanningPolicy v1 + SolveLimits v1 → PlanningSolution v1；neutral re-export不含native类型。OR-Tools、CpModel与CpSolver只存在于`planning/backends/cp_sat/`，返回的identity、parameter、status和smoke evidence均为JSON-compatible值。

Native `UNKNOWN/MODEL_INVALID/FEASIBLE/INFEASIBLE/OPTIMAL`显式映射同名合同状态；adapter cancellation映射CANCELLED，version/native-status/adapter failure映射稳定FAILED错误。未知native code不猜测；identity version drift和invalid parameters fail closed，detail经过固定sanitized message。

Empty/model-invalid smoke分别验证native调用与MODEL_INVALID路径，但两者都不产生candidate且不评估业务可行性。真实`solve()`故意以`MODEL_BUILDER_NOT_IMPLEMENTED`停止，C-001～C-011、OBJ-001、Strategy、formal Validator、Golden/Scenario和Benchmark仍由P2-04～12形成。

## TASK-P2-05 core solve activation

上一段的永久拒绝边界仅是TASK-P2-03历史状态；当前`solve()`已由TASK-P2-05接入C-001/003/004/010/011 bounded core model。它构造master/optional intervals、exact-one candidate、candidate-specific duration、capacity-1 NoOverlap和horizon域，并把任何完整native candidate交给TASK-P2-04 formal Validator复验。

纯可行模型没有objective，native OPTIMAL必须映射为业务FEASIBLE；Validator FAIL则丢弃assignments并映射FAILED。zero option、overflow或任何需要P2-06/07约束的非空事实在model build前稳定拒绝为MODEL_INVALID边界；INFEASIBLE与MODEL_INVALID不得互换。P2-03 empty/model-invalid smoke仍保持`business_feasibility=NOT_EVALUATED`，与当前业务core solve分开。

## TASK-P2-06 temporal solve activation

Current `solve()`在core模型上组合C-002/005/006/009：signed exact rounding、inclusive min/max lag、historical anchors、calendar fixed intervals、release/material gates及按option presence条件化的cross-workshop transport。需要这些约束的合法Problem现在进入模型；sub-second/overflow与仍未实现的RUNNING/lock在build前返回MODEL_INVALID。

Certified native INFEASIBLE才映射业务INFEASIBLE；time/limit导致的UNKNOWN保持UNKNOWN。模型仍无objective，native OPTIMAL降级为FEASIBLE；完整candidate必须通过formal Validator，否则丢弃assignments并返回FAILED。Strategy、C-007/008、Benchmark和Production入口未形成。

## TASK-P2-07 execution fact and lock Backend

Current `solve()`在core/temporal模型上组合C-007/C-008：RUNNING option interval统一改用权威remaining seconds并固定resource/start/end；HARD lock增加exact resource/start/end equality；SOFT lock只进入assignment metadata。完成历史继续只以anchor参与temporal constraints。

Precheck区分HARD grid/权威duration/多lock/RUNNING tuple自冲突的MODEL_INVALID，与calendar、capacity-1 overlap或horizon冲突的certified INFEASIBLE。完整candidate稳定回写lock IDs并强制formal Validator PASS；Validator FAIL仍丢弃assignments。模型无objective，native OPTIMAL降级为FEASIBLE，UNKNOWN不升级。Global Strategy、OBJ-001搜索、dynamic Replan、Benchmark和Production入口未形成。

## TASK-P2-08 OBJ-001 backend path

Backend新增`solve_delivery_with_evidence`供Global Strategy：在既有完整C-001～C-011模型上加入每Demand active-operation最大completion、exact tardiness seconds与priority integer sum并Minimize；int64溢出在search前拒绝。历史`solve_with_evidence`继续保留feasibility-only诊断语义，不能作为可接受策略入口。

Objective路径如实保留native OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN；最佳bound从native carrier保守转换为整数，OPTIMAL强制value=bound/gap=0。所有candidate仍经formal independent Validator；失败转FAILED且清空assignments。Global Strategy报告exact parameters、timing/model/memory/provenance；Schema、Protocol signature、Backend/OR-Tools version、C-ID、Validator、dependency均未改变。

## TASK-P2-11 report freeze boundary

`app.planning.reporting.freeze_solver_report`不调用Backend或重写测量值；它验证PlanningSolution/SolverReport/ValidationReport合同、`SOLVER_RUN` evidence kind、candidate status、PASS validation、Problem/Policy/Limits/status/stage/diagnostics/solution fingerprint完全一致，并按Global Strategy identity projection重新计算report ID。通过后只返回canonical bytes/fingerprint和planning run ID。

KPI与Export consumer必须使用这份已冻结的真实report，不得用P2-02 `CONTRACT_SAMPLE`、伪造timing或跨run report补齐package。Backend/Strategy/Validator代码、OR-Tools exact pin、parameters/status mapping和`uv.lock`均未改变；报告冻结不是BenchmarkRunner或PlanningRun persistence。

## TASK-P2-12 Benchmark consumption

BenchmarkRunner只通过`GlobalCpSatStrategy`/solver-neutral documents消费Backend；每次run使用显式Simulation Policy、single worker、seed和profile wall limit，并从真实SolverReport读取exact solver identity/parameters、status、model build/first feasible/solve/validation/total、model counts、objective/bound/gap及Python peak memory。它不导入OR-Tools native types、不调用constraint builder或改写telemetry。

Backend/Strategy/Validator/Problem、C-ID/OBJ-001与dependency/lock零变化。XS/S/M观测是development synthetic evidence，不能成为默认SolveLimits、Worker capacity或Production SLA。

## TASK-P2-14 Exit audit

locked sync与运行时检查确认OR-Tools exact version仍为`9.15.6755`，ADR-0011 accepted且`pyproject.toml`/`uv.lock`相对Diff base无变化。两次Gate与独立XS/S/M重放保存status、model/build/first/solve/validation/total、objective/bound/gap、memory及Validator；全部PASS。该证据只关闭P2 Synthetic Solver Gate，不建立Production worker capacity、SLA或升级批准。
## TASK-P3-02 frozen Solver boundary

Workspace carrier release不修改PlanningProblem/Policy/Limits/Solution/SolverReport Schema、CP-SAT backend、OBJ-001或formal Validator。ScheduleVersion只通过exact artifact reference与assignment `$ref`消费P2 validated output；纯precheck不导入或调用Backend/Validator。Solver UNKNOWN继续映射`NO_SOLUTION_WITHIN_LIMIT`且无candidate，不能创建Version。`uv.lock`与OR-Tools pin保持不变；OBJ-002及动态planning仍在后续阶段边界外。

P3-09只复制已经由P2 Validator PASS冻结的PlanningSolution/Validation/KPI/SolverReport bytes，重新核对ScheduleVersion assignment与solution fingerprint，不执行solve或重新认证candidate。ExportJob retry绝不重新运行Solver；OBJ-002/003、ChangeReport和P4 replan仍未实现。
