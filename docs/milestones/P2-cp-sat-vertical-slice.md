---
doc_id: MILESTONE-P2
title: P2 — CP-SAT Vertical Slice
status: active
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [75, 76]
last_reviewed: 2026-08-20
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
| 5 | TASK-P2-05 | C-001/003/004/010/011 core model | P2-03/04 | `in_progress` |
| 6 | TASK-P2-06 | C-002/005/006/009 temporal/calendar/material | P2-05 | `planned` |
| 7 | TASK-P2-07 | C-007/008 execution facts/HARD lock | P2-06 | `planned` |
| 8 | TASK-P2-08 | OBJ-001 Delivery与GlobalCpSatStrategy | P2-02/05/06/07 | `planned` |
| 9 | TASK-P2-09 | Golden/scenario/property/mutation integration | P2-04～08 | `planned` |
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

TASK-P2-00～04均已闭环为`done`。P2-03以clean/provider-verified Diff base `f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`启动，依赖变更前接受ADR-0011；implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的required run `32346208046` / job `96355386111` / artifact `9398128763`均success。P2-03只形成exact Solver dependency与Backend engineering foundation，P2-04形成formal independent Validator；业务constraint/OBJ-001/Benchmark仍未实现，P2保持`active`且不进入P3。

P2-02已形成global schema set`2.4.0`、PlanningPolicy/SolveLimits/PlanningSolution/SolverReport v1、七种status与pure fingerprint/precheck/CI report。P2-03未修改这些合同字节；empty/model-invalid smoke不构成业务可行性或candidate。用户已授权TASK-P2-04，它以clean/provider-verified `4c66dce3b919a53816005c4aebf4983db19a6108`启动并固定P0/P2合同与fixture hashes；P2-05～14仍为`planned`且未获启动授权。

P2-04的授权范围仅包含formal independent Validator及其机器证据。它已逐项独立重算C-001～C-011、忽略solver status的可信声明并保持Backend/OR-Tools/expected artifact隔离；P2-05 core model、OBJ-001、Benchmark和P3均不在本次范围。

本地实现已形成`formal-schedule-validator-report.v1`：6/6 checks、13个mutation、11个C-ID、14个hard violations及6个duration/order examples均PASS，且Problem/Solution/Validation Schema、P0 fixture/evaluator、`uv.lock`和Backend保持不变。Implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的exact run `32350068318` / required job `96367085099` / artifact `9399519368`成功并复现同一SHA的formal与38-path/6-row/0-issue治理报告，故TASK-P2-04=`done`。用户已明确授权TASK-P2-05；它以clean/provider-verified `c75f7a0e96b7591ffa9220d0de942f8841283093`为不可变Diff base，仅启动C-001/003/004/010/011 core model与对应证据。P2-06～14继续`planned`且未获授权。

TASK-P2-05本地实现已形成five-C-ID core model、candidate-specific duration、unary NoOverlap、horizon、complete mapping、formal Validator gate、tiny exhaustive oracle和真实telemetry；64 focused、360 full、Ruff/Pyright、core/formal机器报告、49-path/6-row治理、compose/build/immutable均PASS。Milestone仍为P2 active，Task等待exact provider闭环；OBJ-001与C-002/005～009仍未形成，P2-06不自动启动。
