---
doc_id: DOC-CONTRACT-003
title: PlanningProblem 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 14, 24, 25, 26, 45, 89]
last_reviewed: 2026-08-19
---

# PlanningProblem 合同

PlanningProblem 必须可序列化、Solver-neutral、deterministic，不包含 OR-Tools 类型。

## 顶层结构

```json
{
  "problem_version": "planning-problem.v1",
  "snapshot_id": "uuid",
  "tick_seconds": 60,
  "horizon_start_utc": "...",
  "horizon_end_utc": "...",
  "operation_instances": [],
  "precedence_edges": [],
  "resource_unavailable_intervals": []
}
```

正式 Schema 还需表达 resources、candidate options、execution facts、locks、due/priority、provenance 和 capability declarations。

## 不变量

- operation/resource/edge 引用完整；
- routing/operation precedence 无环；
- NOT_STARTED Operation 有至少一个合法候选资源；
- duration 秒到 tick 的转换显式且可复算；
- max_lag 一旦存在就必须被 Solver 和 Validator 使用；
- horizon 不静默截断任务；
- unsupported capability 在 solve 前明确拒绝；
- 同 Snapshot 与 rule/problem builder version 得到同 `problem_hash`。

## 边界

PlanningProblem 不含数据库 Session、ORM Model、API DTO、CpModel、IntervalVar 或求解过程统计。修改本合同必须 ADR、problem version 更新、contract/golden/scenario replay 和 benchmark comparison。
