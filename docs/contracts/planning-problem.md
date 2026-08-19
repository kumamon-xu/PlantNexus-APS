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
  "snapshot_id": "canonical-id",
  "problem_builder_version": "...",
  "problem_hash": "...",
  "tick_seconds": 60,
  "horizon_start_utc": "...",
  "horizon_end_utc": "...",
  "resource_ids": [],
  "operation_instances": [],
  "precedence_edges": [],
  "resource_unavailable_intervals": [],
  "required_capabilities": []
}
```

[`planning-problem.schema.json`](../../schemas/json/planning-problem.schema.json) 已表达 candidate options、NOT_STARTED/RUNNING execution facts、min/max/transport lag、resource unavailable intervals、provenance 和 capability declarations。HARD/SOFT lock、due/priority 和完整 Resource 事实仍由后续合同 Task 在不改变 ADR-0003 边界的前提下升版补充。

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

P0 纯类型位于 `backend/app/planning/problem/contracts.py`；`backend/app/domain/validation.py` 只做 ID 引用、UTC interval、duration 和 lag range 的最小 precheck，不实现 C-001～C-011 或 Solver。PlanningProblem builder/hash、DAG 检查、Constraint rule sheet、Golden/Scenario replay 和 Benchmark 仍为 `PLANNED`。本次首次 skeleton 由既有 ADR-0003 覆盖，没有新增架构决定。
