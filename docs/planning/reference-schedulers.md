---
doc_id: DOC-PLAN-007
title: Reference Scheduler 基线
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [51, 52, 53, 54]
last_reviewed: 2026-08-19
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

Reference Scheduler 不证明最优；若无法满足所有硬约束，应返回明确失败并由 Validator 确认，不能输出随机或部分 schedule 冒充结果。
