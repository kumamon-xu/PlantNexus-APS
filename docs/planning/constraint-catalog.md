---
doc_id: DOC-PLAN-003
title: V1 Constraint Catalog
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [21, 22, 25, 26, 27, 30, 31]
last_reviewed: 2026-08-19
---

# V1 Constraint Catalog

本目录是 V1 硬约束的规范索引。Solver 实现与 Validator 实现必须分别追踪这些 ID，但不得共享 CP-SAT 约束实现。

| ID | 规则 | Solver 表达 | Validator 核心检查 |
|---|---|---|---|
| C-001 | 必排完整性 | 每个未完成 Operation 恰有一个资源和 interval | 缺失、重复、未排均拒绝 |
| C-002 | 工艺时间关系 | `succ.start >= pred.end + min_lag`；存在 max_lag 时同时约束上界 | 逐 edge 检查 min/max lag |
| C-003 | 候选设备唯一选择 | `sum(presence[i,*]) == 1` | selected resource 属于候选且唯一 |
| C-004 | 单机互斥 | Capacity=1 Resource 使用 NoOverlap | 同资源 interval 不重叠 |
| C-005 | 设备日历 | 不可用固定 interval 加入 NoOverlap | 任务不跨/不占不可用区间 |
| C-006 | Release Gate | `start >= order_release_at` 且 `start >= material_ready_at` | 对两个 gate 独立检查 |
| C-007 | Execution Facts | COMPLETED 不排；RUNNING 资源与未来剩余占用固定 | 历史、资源、remaining、future occupancy |
| C-008 | Lock | HARD resource/start/end 固定；SOFT 进入稳定性目标 | HARD 不移动，SOFT 变化进入报告 |
| C-009 | 跨车间衔接 | `succ.start >= pred.end + transport_lag` | workshop edge 与 lag 来源一致 |
| C-010 | 工时一致性 | `end-start == selected.final_duration_ticks` | 选中设备的 duration 可复算 |
| C-011 | Planning Horizon | NOT_STARTED `start>=horizon_start`、`end<=horizon_end` | 不允许截断或越界 |

## 共同规则

- max_lag 存在就必须实现，不能只在 Schema 存储。
- 非抢占任务不能跨 calendar unavailable interval。
- 每个候选设备使用自身 duration。
- HARD_LOCK 和 Execution Fact 不能通过 Hint 代替。
- Validator 报告至少包含 `constraint_id`、severity、entity IDs、observed、expected rule 和 message。

## Deferred/Unsupported constraints

| ID | 能力 | V1 行为 |
|---|---|---|
| C-012 | Secondary Capacity | `UNSUPPORTED_CAPABILITY` |
| C-013 | Sequence-dependent Setup | `UNSUPPORTED_CAPABILITY` |
| C-014 | Material Balance | `UNSUPPORTED_CAPABILITY`；只支持 material_ready_at |
| C-015 | Batch Processing | `UNSUPPORTED_CAPABILITY` |
| C-016 | Split / Merge | `UNSUPPORTED_CAPABILITY` |
| C-017 | Buffer Capacity | `UNSUPPORTED_CAPABILITY` |
| C-018 | Preemption | `UNSUPPORTED_CAPABILITY` |

## P0 验证规则表

P0 不实现 Solver，但必须为 C-001～C-011 固定输入字段、判定公式、正例、反例、错误码和 Test ID。TASK-P0-04 建规则表，TASK-P0-07 用人工非法计划验证规则完整性。
