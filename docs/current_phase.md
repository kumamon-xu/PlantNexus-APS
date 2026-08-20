---
doc_id: DOC-PHASE-CURRENT
title: 当前阶段
status: living
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [73, 74, 75, 76, 110, 111]
last_reviewed: 2026-08-20
---

# 当前阶段：P2 — CP-SAT Vertical Slice

## 阶段授权与证据

用户于2026-08-20明确批准P1→P2 phase transition，并授权先进行P2 Task规划。切换前已重新核验：TASK-P1-01～12全部`done`；[P1 Exit Gate audit](milestones/P1-exit-gate-audit-report.md)与[machine manifest](milestones/P1-exit-gate-evidence-manifest.json)给出overall=`READY`、blocking gaps为空；audit implementation `a5d7e4a68dc12d48e36cb692500f59446f8097b4`是规划基线`098c44059856e3203d95d046fea44894b5cf414b`的祖先。

GitHub上audit implementation的push run `32326616525` / required `validate` job `96299073525` / artifact `9391591718`均success；规划基线自身的run `32327121469` / job `96300506550` / artifact `9391753870`也精确绑定`098c44059856e3203d95d046fea44894b5cf414b`并success。规划启动时`main=origin/main`且working tree clean，因此前提一致，阶段切换成立。

P1 Milestone现为`completed`，P2 Milestone为`active`。这只授权P2范围内的Task规划与后续逐Task实现，不表示Solver、Validator、Benchmark、Export或Production能力已经形成。

## 当前目标

建立唯一受支持的P2纵向链：

```text
PlanningSnapshot
→ PlanningProblem v2
→ PlanningPolicy + SolveLimits
→ GlobalCpSatStrategy + CpSatBackend
→ PlanningSolution
→ independent ScheduleValidator
→ KPI + SolverReport + internal Export package
→ Reference Scheduler / BenchmarkRunner
```

只实现C-001～C-011与OBJ-001；Gate覆盖Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock和XS/S/M，并记录model size、build、first feasible、objective、bound、gap、memory、Validator与Snapshot→Export证据。

## 当前Task与启动边界

`TASK-P2-00 — P2 Phase Transition and Task Planning Governance`、`TASK-P2-01 — PlanningProblem v2 Contract Gap Closure`与`TASK-P2-02 — Planning Machine Contracts and Status`均已闭环为`done`。P2-02 implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`的GitHub push run `32342489997`、required `validate` job `96344226221`与artifact `9396828326`均精确绑定该SHA并为success；closure HEAD `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`的run `32342949743` / job `96345556588` / artifact `9396984310`也成功并作为P2-03 Diff base。

用户于2026-08-20明确授权执行`TASK-P2-03 — OR-Tools and SolverBackend Foundation`；该Task以clean、provider-verified `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`启动，并在依赖变更前接受ADR-0011。现已由implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的GitHub run `32346208046` / required job `96355386111` / artifact `9398128763`闭环为`done`。Problem/Policy/Solution/Report合同字节和语义保持只读。

P2-02把global schema set additive提升到`2.4.0`，新增四个互相离线解析的v1 document contract，并以`CONTRACT_SAMPLE`/`SOLVER_RUN`显式区分shape样例与真实运行。该发布样例的`not-installed`是P2-02历史shape证据，不随P2-03安装依赖而改写。用户于2026-08-20明确授权执行TASK-P2-04；该Task以clean/provider-verified `4c66dce3b919a53816005c4aebf4983db19a6108`启动，现由implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的run `32350068318` / required job `96367085099` / artifact `9399519368`闭环为`done`。TASK-P2-00～04现均`done`；用户已明确授权TASK-P2-05，它以clean/provider-verified `c75f7a0e96b7591ffa9220d0de942f8841283093`为Diff base并处于`in_progress`。P2-06～14未获授权。

## 当前允许

- 按已授权Task在P2范围内演进solver-neutral Problem/Policy/Limits/Solution/Report合同；
- exact pin OR-Tools并保持其只存在于CP-SAT Backend；
- 逐项实现C-001～C-011、OBJ-001、formal independent Validator、Reference Schedulers、internal Export与BenchmarkRunner；
- 使用versioned Simulation Policy/Profile/Scenario运行correctness与XS/S/M；
- 每个Task完成本地验收后，在用户本次授权边界内提交并直接push当前`main`，再核验exact required `validate`和artifact。

## 当前禁止

- 未经用户另行明确授权启动任何P2-06～14实现；TASK-P2-05仅按已冻结的core model范围执行；
- 修改Task允许范围外文件、预填PASS/provider evidence或跳过独立Validator；
- 实现C-012～C-018、OBJ-002 Stability、动态Replan、ExecutionSimulator、P3 Workspace/审批/发布状态；
- 把UNKNOWN写成INFEASIBLE、FEASIBLE写成OPTIMAL，或以hint代替Execution Fact/HARD lock；
- 猜测Production权重、calendar/transport/default solve limits、性能阈值或真实system authority；
- 将synthetic correctness/XS/S/M结果外推为Production SLA、容量或readiness。

## 阶段完成条件

- Problem/Policy/Limits/Solution/Report版本化合同与solver/backend隔离成立；
- C-001～C-011与OBJ-001由CP-SAT实现且formal independent Validator全部PASS；
- Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock、Property/Mutation与Reference Scheduler证据形成；
- Snapshot→Export internal package闭环，报告/hash/版本一致；
- XS/S/M报告包含全部Gate字段且有provider artifact，不形成Production承诺；
- TASK-P2-01～13全部`done`后，最后执行TASK-P2-14 Exit Gate Audit；只有audit=`READY`且用户再次明确批准，才允许请求进入P3。

Task全部完成或audit READY都不自动切换P3；失败时保持P2并建立有界remediation Task。

## TASK-P2-03 执行结果

`ortools==9.15.6755`、`cp-sat-backend.v1`、七状态adapter、SolveLimits参数映射、namespace/serialization隔离与6-check machine report已形成；本地39 focused、319 full、Ruff/Pyright、P2-02/P0历史兼容、Compose和build均PASS。Provider artifact精确复现Linux/x86_64、6/6 foundation及50 paths/9 rows/0 issues，因此TASK-P2-03=`done`。

该foundation没有business model builder，真实`solve()`以稳定MODEL_INVALID边界停止；empty model的OPTIMAL不表示PlanningProblem可行。P2-05～14仍未授权，current phase保持P2且不进入P3。

## TASK-P2-04 启动边界

TASK-P2-04以`4c66dce3b919a53816005c4aebf4983db19a6108`为不可变Diff base，复用且不修改Problem v2、PlanningSolution、ValidationReport/Error v2与constraint-rule-sheet v1。正式Validator必须独立重算C-001～C-011，不能导入Backend/OR-Tools、复用CP-SAT constraint builder、读取expected outcome决定结果或信任solver status。P0 fixture-local evaluator与全部历史asset bytes保持只读；P2-05 core model、OBJ-001、Benchmark、DB/API/Worker和P3仍未启动。

## TASK-P2-04 执行结果

正式`ProblemScheduleValidator`现直接消费Problem v2与candidate PlanningSolution，按稳定顺序独立判定C-001～C-011，并把失败映射为`validation-report.v2`与`error.v2`。本地machine report为6/6 PASS，覆盖13个声明式mutation、11个C-ID、14个hard violations、一个positive/status-contradiction replay和6个duration/order examples；AST证据确认无Backend/OR-Tools/expected outcome决策依赖。

本地指定suite=`59 passed`、full=`343 passed`，Ruff/Pyright、历史machine compatibility、Compose、build与38-path/6-row/0-issue治理均PASS。Exact implementation provider artifact内formal report绑定同一SHA并为6/6 PASS，Task report为38 committed/0 working paths、19 checks、0 issues；因此TASK-P2-04=`done`。

## TASK-P2-05 启动边界

用户于2026-08-20明确授权执行TASK-P2-05。启动复核确认`main=origin/main=c75f7a0e96b7591ffa9220d0de942f8841283093`、working tree clean，且该SHA的GitHub run `32350571302` / required job `96368639237` / artifact `9399702868`精确成功。Problem/Solution/Policy/Limits Schema、constraint-rule-sheet v1、formal Validator、Planning contracts、Problem builder/hash、OR-Tools exact pin与`uv.lock`均作为不可变启动基线。

本Task只建模C-001/003/004/010/011，必须在build前拒绝任何需要C-002/005～009的非空事实，并用formal independent Validator复验candidate。不实现OBJ-001搜索目标、Strategy、Benchmark threshold、DB/API/Worker或P3；纯可行模型的native OPTIMAL不能升格为业务最优声明。P2-06及以后仍为`planned`且未获授权，current phase继续为P2。

## TASK-P2-05 本地实现状态

Core builder现使用master/optional intervals、exact-one candidate、candidate-specific duration、capacity-1 NoOverlap和horizon域；Backend把完整candidate映射为诚实FEASIBLE并强制formal Validator PASS，zero/overflow与P2-06/07非空事实在build前fail closed。模型不含objective，OBJ-001 stage仅为post-solve measurement。

本地验收：focused `64 passed`、full repository `360 passed`、Ruff/Pyright 0、`cp-sat-core-model-report.v1` 6/6、formal report 6/6、治理142 docs且Task diff 49 paths/6 rows/19 checks/0 issues、compose/build/immutable diff PASS。Task在exact implementation GitHub required `validate`和artifact核验前继续`in_progress`；P2-06～14仍未授权。
