---
doc_id: MILESTONE-P2
title: P2 — CP-SAT Vertical Slice
status: active
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [75, 76]
last_reviewed: 2026-08-21
---

# P2 — CP-SAT Vertical Slice

## Authorization

P1 Exit Gate=`READY`且blocking gaps为空；用户于2026-08-20明确批准P1→P2并授权先进行P2 Task规划。P1现为`completed`，P2为当前`active` Milestone。该授权不自动启动任何P2业务Task，也不授权P3或Production release。

## Outcome

实现PlanningProblem、Policy、Limits、Solution、GlobalCpSatStrategy、CpSatBackend、ScheduleValidator、Reference Scheduler和BenchmarkRunner；只支持C-001～C-011与OBJ-001。Snapshot→Export仅形成内部、不可发布的标准成果包闭环。

## Ordered Task plan

| Order | Task | Outcome | Depends on | Current state |
|---:|---|---|---|---|
| 0 | TASK-P2-00 | Phase transition、完整Task规划与batch CI治理 | TASK-P1-12 | `done` |
| 1 | TASK-P2-01 | PlanningProblem v2合同缺口闭环 | P2-00 | `done` |
| 2 | TASK-P2-02 | Policy/Limits/Solution/SolverReport/status机器合同 | P2-01 | `done` |
| 3 | TASK-P2-03 | OR-Tools exact pin与Backend foundation | P2-02 | `done` |
| 4 | TASK-P2-04 | 正式Problem/Solution独立ScheduleValidator | P2-01/02 | `done` |
| 5 | TASK-P2-05 | C-001/003/004/010/011 core model | P2-03/04 | `done` |
| 6 | TASK-P2-06 | C-002/005/006/009 temporal/calendar/material | P2-05 | `done` |
| 7 | TASK-P2-07 | C-007/008 execution facts/HARD lock | P2-06 | `done` |
| 8 | TASK-P2-08 | OBJ-001 Delivery与GlobalCpSatStrategy | P2-02/05/06/07 | `done` |
| 9 | TASK-P2-09 | Golden/scenario/property/mutation integration | P2-04～08 | `done` |
| 10 | TASK-P2-10 | 五个Reference Schedulers | P2-01/02/04 | `planned` |
| 11 | TASK-P2-11 | KPI/SolverReport/internal Export closure | P2-08/09 | `planned` |
| 12 | TASK-P2-12 | BenchmarkRunner与XS/S/M profiles | P2-08～11 | `planned` |
| 13 | TASK-P2-13 | 完整vertical-slice Gate report与CI evidence | P2-01～12 | `planned` |
| 14 | TASK-P2-14 | P2 Exit Gate Audit | P2-01～13 | `planned` |

## Dependency graph

```text
P2-00 → P2-01 → P2-02 ─┬→ P2-03 ─┐
                        └→ P2-04 ─┴→ P2-05 → P2-06 → P2-07 → P2-08 → P2-09
                             └──────────────────────────────→ P2-10
P2-08 + P2-09 → P2-11
P2-08 + P2-09 + P2-10 + P2-11 → P2-12
P2-01～12 → P2-13 → P2-14
```

P2-03与P2-04在合同固定后可并行准备，但P2-05必须同时等待Backend foundation与formal Validator。P2-10不依赖CP-SAT实现，可在P2-04后独立完成；P2-12必须使用相同Problem/Validator/KPI比较所有策略。

## Exit Gate

必须运行Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running Operation、Hard Lock和XS/S/M；记录Problem/model规模、build、first feasible、solve、objective、bound、gap、memory、Solver/Policy exact versions与Validator结果，并完成Snapshot→Export闭环。

所有required scenario必须走正式Import/Snapshot/Problem和同一Validator/KPI；Reference Scheduler不得简化输入。功能测试通过不是充分条件；correctness failure不能被性能抵消。

## Boundaries

- P2只实现C-001～C-011与OBJ-001；C-012～C-018继续explicit unsupported。
- 不实现OBJ-002 Stability、动态Replan、ExecutionSimulator、ChangeReport或P4事实事件链。
- internal Export不创建P3 Workspace、ScheduleVersion审批/发布、ExportJob持久化、API/UI或external publish。
- OPEN-006/011/012未关闭前只允许versioned Simulation policy/profile；XS/S/M不代表Production capacity/SLA。
- P2-14必须最后执行；READY不自动改变current phase或创建P3 Task。

## Current execution boundary

TASK-P2-00～09均已由local/exact provider闭环为`done`。P2-03形成exact Solver dependency与Backend engineering foundation，P2-04形成formal independent Validator，P2-05～07形成完整C-001～C-011 hard model，P2-08形成唯一OBJ-001与Global Strategy，P2-09形成七类correctness integration。P2保持`active`，P2-10～14未获授权且不进入P3。

P2-02已形成global schema set`2.4.0`、PlanningPolicy/SolveLimits/PlanningSolution/SolverReport v1、七种status与pure fingerprint/precheck/CI report。P2-03未修改这些合同字节；empty/model-invalid smoke不构成业务可行性或candidate。TASK-P2-04随后以clean/provider-verified `4c66dce3b919a53816005c4aebf4983db19a6108`启动并固定P0/P2合同与fixture hashes；TASK-P2-04～09现均已完成，P2-10～14仍为`planned`且未获启动授权。

P2-04的授权范围仅包含formal independent Validator及其机器证据。它已逐项独立重算C-001～C-011、忽略solver status的可信声明并保持Backend/OR-Tools/expected artifact隔离；P2-05 core model、OBJ-001、Benchmark和P3均不在本次范围。

本地实现已形成`formal-schedule-validator-report.v1`：6/6 checks、13个mutation、11个C-ID、14个hard violations及6个duration/order examples均PASS，且Problem/Solution/Validation Schema、P0 fixture/evaluator、`uv.lock`和Backend保持不变。Implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的exact run `32350068318` / required job `96367085099` / artifact `9399519368`成功并复现同一SHA的formal与38-path/6-row/0-issue治理报告，故TASK-P2-04=`done`。用户已明确授权TASK-P2-05；它以clean/provider-verified `c75f7a0e96b7591ffa9220d0de942f8841283093`为不可变Diff base，仅启动C-001/003/004/010/011 core model与对应证据。P2-06～14继续`planned`且未获授权。

TASK-P2-05本地实现已形成five-C-ID core model、candidate-specific duration、unary NoOverlap、horizon、complete mapping、formal Validator gate、tiny exhaustive oracle和真实telemetry；64 focused、360 full、Ruff/Pyright、core/formal机器报告、49-path/6-row治理、compose/build/immutable均PASS。下方exact provider证据已完成闭环；Milestone仍为P2 active，OBJ-001与C-002/005～009仍未形成，P2-06不自动启动。

Implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / required job `96379299455` / artifact `9400957897`均success；artifact core/formal报告绑定同一SHA并各6/6，Task report为49 committed/0 working paths、6 rows、19 checks、0 issues。因此TASK-P2-05=`done`。用户于2026-08-21明确授权TASK-P2-06；启动时`main=origin/main=c55aa294977a6cafad85741f425d46cd36e9af1a`、working tree clean，该SHA的run `32354521904` / required job `96380738933` / artifact `9401134902`均success。P2保持`active`；P2-06仅启动C-002/005/006/009与对应证据，OBJ-001、C-007/008、Benchmark、P2-07～14和P3仍未形成或未获授权。

TASK-P2-06已形成C-002/005/006/009：exact min/max lag、historical anchor、calendar half-open grid projection、release/material gates与selected-resource conditional transport，并保留independent Validator、no-objective和C-007/008 fail-closed边界。Focused=`87 passed`、full=`367 passed`、Ruff/Pyright 0、四份machine reports PASS、治理53 paths/6 rows/0 issues且compose/build/immutable均PASS。

Implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`的run `32432482739` / required job `96626844156` / artifact `9429579311`均success，artifact digest=`sha256:3d1dce2dad986669d5709d7f8cf3900287773863cdda430e791e007495d5259c`且精确复现temporal/core/formal/Task报告。因此TASK-P2-06=`done`。用户于2026-08-21明确授权TASK-P2-07；启动时`main=origin/main=33cc3282ead23a4cc1bb214190191e116b095119`且working tree clean，该SHA的run `32432843343` / required job `96627943272` / artifact `9429703054`均success。P2仍`active`；P2-07只启动C-007/008，OBJ-001、Benchmark、P2-08～14和P3仍未形成或未获授权。

TASK-P2-07本地实现已形成COMPLETED exclusion/historical anchor、RUNNING remaining/resource fixed interval、HARD exact tuple与SOFT metadata-only边界。Focused=`93 passed`、full=`382 passed`、Ruff/Pyright 0，五份历史/当前machine reports均PASS，治理54 paths/6 rows/19 checks/0 issues且Compose/build/immutable均PASS。Task仍等待exact implementation SHA的required `validate`与artifact，故保持`in_progress`；Milestone保持`active`且不启动P2-08。

Implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的run `32435395744` / required job `96635463577` / artifact `9430579117`均success，artifact digest=`sha256:a6b6ff7413b8010a8012ddd351a2a194b89b1a13cdf71c6dada5d6afa53a44ab`且精确复现fact-lock/temporal/core/formal/Task报告。因此TASK-P2-07=`done`。

用户于2026-08-21明确授权TASK-P2-08；启动基线`9c55df993b12ae0bdd3d4d38c900d601324c05d2`的run `32435755901` / required job `96636509174` / artifact `9430697910`均success且工作树clean。TASK-P2-08只接入versioned Simulation OBJ-001与Global Strategy/status/report evidence；P2 Milestone保持`active`，P2-09～14和P3不自动启动。

TASK-P2-08本地已形成explicit Simulation-only Delivery Policy/SolveLimits、priority-weighted tardiness seconds、single-call GlobalCpSatStrategy、诚实七状态/objective/bound/gap/report与mandatory formal Validator gate。Focused=`70 passed`、full=`395 passed`、Ruff/Pyright=0、objective/strategy machine=`7/7 PASS`，全部历史machine、治理52 paths/8 rows/19 checks/0 issues、Compose/build/immutable均PASS；Schema/contracts、Problem/Validator/C-ID/dependency/lock无变化。Exact provider闭环前TASK-P2-08仍为`in_progress`，Milestone保持`active`且不启动P2-09。

Implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的run `32438785162` / required job `96645152864` / artifact `9431673977`均success；artifact digest=`sha256:843c036ffa3e133a9bceee1ca3b3320ce42a790cc955f01e94acab135f8fab5d`并精确复现objective/strategy 7/7与52 committed/0 working paths、8 rows、19 checks、0 issues。因此TASK-P2-08=`done`；P2 Milestone保持`active`，P2-09～14和P3不自动启动。

用户于2026-08-21明确授权TASK-P2-09；启动基线`15c298f343a47db2a922544944ff5e02e4ca72d9`的run `32439301758` / required job `96646617379` / artifact `9431840946`均success且working tree clean。新assembler/catalog/manifest版本、七个Scenario及P0/P1 immutable asset digest已冻结；本Task只形成correctness integration，P2-10～14和P3不自动启动。

TASK-P2-09本地已形成2个手算Golden、5个feature matrix、7次正式pipeline Solver/Validator PASS、7次row-order/fresh Validator property与11个C-ID exact mutation；45 focused、427 full、machine 8/8、全部历史reports、治理58 paths/7 rows/19 checks/0 issues、Compose/build/immutable均PASS。

Implementation `20e49c92306128b47313059fabe31534814dbe3d`的run `32442651322` / required job `96656224252` / artifact `9432982306`均success；artifact digest=`sha256:c736a2f029f119850f8a0c9b40b0dbbd0898383f10ddbc798f7182ff5ec90e09`并精确复现correctness 8/8、16/16 reports及58 committed/0 working paths、7 rows、19 checks、0 issues。因此TASK-P2-09=`done`；Milestone保持`active`，P2-10～14和P3不自动启动。
