---
doc_id: DOC-PLAN-007
title: Reference Scheduler 基线
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [51, 52, 53, 54]
last_reviewed: 2026-08-21
---

# Reference Scheduler 基线

Reference Scheduler 是非生产启发式，用于 Benchmark、Regression 和 Sanity Check，不能作为绕过 GlobalCpSatStrategy 的生产 fallback。

## 最小算法集合

- FCFS；
- EDD；
- SPT；
- Priority + EDD；
- Greedy Earliest Available Machine。

每个算法必须使用相同 PlanningProblem、Constraint/Validator 和 KPI 口径，不能为基线简化输入或忽略硬约束。

## 比较

每个 Scenario 同时可运行 Reference Scheduler 与 GlobalCpSatStrategy，比较 feasibility、weighted tardiness、makespan 和 runtime。若 CP-SAT 明显劣于简单 heuristic，产生 `BENCHMARK_WARNING` 并进入诊断，不能通过隐藏基线结果解决。

## 限制

Reference Scheduler 不证明最优；完整候选必须由 Validator 确认。若启发式无法构造完整候选，应返回明确失败并丢弃内部部分状态，不能把未经 Validator 的部分 schedule 暴露为结果，也不能把启发式失败解释为 Problem infeasible。

TASK-P0-05 的 ScenarioManifest v1 提供未来 baseline 比较所需的 Scenario/Profile/Generator/seed/dataset hash 引用。Empty Import package 没有 operation/resource，不可运行 FCFS/EDD 等，也不能形成 REQ-015 或 TEST-REFERENCE-SCHEDULER evidence。

## TASK-P2-10 deterministic baseline implementation

[`simulation.baselines`](../../backend/app/simulation/baselines/reference_schedulers.py)现以`reference-scheduler-contracts.v1`、`reference-scheduler-policy.v1`和五个独立algorithm ID实现全部最小集合。FCFS按release/demand/operation，EDD按due/release/demand/operation，SPT按minimum duration/due/operation，Priority+EDD按negative priority/due/release/demand/operation选择ready operation；前四者按earliest end/start/duration/resource选择设备，Greedy Earliest Available Machine按earliest end/start/duration/resource/operation全局选择。所有key均为稳定全序，不读取随机源或隐式默认值。

五算法消费未改写的PlanningProblem v2，在共享hard-feasibility helper中处理C-001～C-011要求的候选资源、capacity-1、precedence min/max、calendar、release/material、RUNNING、HARD lock、conditional transport、duration与horizon。每次成功必须输出全部active operation且由新建`ProblemScheduleValidator`得到PASS；失败只返回`HEURISTIC_FAILURE`并丢弃内部partial state，不得升级为`INFEASIBLE`证明。Invalid Problem与Validator rejection另以`INVALID_PROBLEM`/`VALIDATION_FAILED`区分。

`reference-scheduler-report.v1`在七个P2-09 Problem上形成35个完整candidate、35次fresh Validator PASS与35次deterministic replay，并以5个blocked-calendar case证明失败零candidate。报告同口径给出priority-weighted tardiness seconds、从horizon origin计算的makespan seconds与单次runtime；所有结果均`non_production=true`、`optimality_claim=NONE`。Global Strategy比较、warning、XS/S/M与threshold仍由TASK-P2-12形成，不能把本报告称为Benchmark baseline或生产fallback。
