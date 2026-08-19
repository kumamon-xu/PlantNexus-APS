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

| ID | 规则 | Solver 表达 | Validator 核心检查 | P0 Test contract |
|---|---|---|---|---|
| C-001 | 必排完整性 | 每个未完成 Operation 恰有一个资源和 interval | 缺失、重复、未排均拒绝 | TEST-RULE-SHEET-001；TEST-VALIDATOR-MUTATION planned |
| C-002 | 工艺时间关系 | `succ.start >= pred.end + min_lag`；存在 max_lag 时同时约束上界 | 以 `(succ.start-pred.end)*tick_seconds` 精确检查 min/max 秒，不用 ceil 放宽 max | TEST-RULE-SHEET-001；TEST-MAX-LAG planned |
| C-003 | 候选设备唯一选择 | `sum(presence[i,*]) == 1` | selected resource 属于候选且唯一 | TEST-RULE-SHEET-001；TEST-INF-NO-RESOURCE planned |
| C-004 | 单机互斥 | Capacity=1 Resource 使用 NoOverlap | 同资源半开 interval 不重叠 | TEST-RULE-SHEET-001；TEST-VALIDATOR-MUTATION planned |
| C-005 | 设备日历 | 不可用固定 interval 加入 NoOverlap | 非抢占任务不跨/不占不可用半开区间 | TEST-RULE-SHEET-001；TEST-CALENDAR planned |
| C-006 | Release Gate | `start >= order_release_at` 且 `start >= material_ready_at` | 从 horizon/ticks 还原 candidate UTC，对两个 gate 独立检查 | TEST-RULE-SHEET-001；TEST-MATERIAL planned |
| C-007 | Execution Facts | COMPLETED 不排；RUNNING 资源与未来剩余占用固定 | 历史、资源、remaining、future occupancy | TEST-RULE-SHEET-001；TEST-RUNNING planned |
| C-008 | Lock | HARD resource/start/end 固定；SOFT 进入稳定性目标 | HARD 不移动；SOFT 不作为 hard PASS 条件 | TEST-RULE-SHEET-001；TEST-INF-LOCK planned |
| C-009 | 跨车间衔接 | `succ.start >= pred.end + transport_lag` | 以 observed seconds 独立于 C-002 检查 transport lag | TEST-RULE-SHEET-001；TEST-CROSS-WORKSHOP planned |
| C-010 | 工时一致性 | `end-start == selected.final_duration_ticks` | `ceil(final_duration_seconds/tick_seconds)` 可复算 | TEST-RULE-SHEET-001；TEST-VALIDATOR-MUTATION planned |
| C-011 | Planning Horizon | NOT_STARTED `start>=horizon_start`、`end<=horizon_end` | 还原 UTC 后不允许截断或越界 | TEST-RULE-SHEET-001；TEST-INF-HORIZON planned |

## 共同规则

- max_lag 存在就必须实现，不能只在 Schema 存储。
- 非抢占任务不能跨 calendar unavailable interval。
- 每个候选设备使用自身 duration。
- HARD_LOCK 和 Execution Fact 不能通过 Hint 代替。
- Validator 报告至少包含 `constraint_id`、severity、entity IDs、observed、expected rule 和 message。

## Deferred/Unsupported constraints

| ID | 能力 registry key | V1 行为 |
|---|---|---|
| C-012 | SECONDARY_CAPACITY | `UNSUPPORTED_CAPABILITY` |
| C-013 | SEQUENCE_DEPENDENT_SETUP | `UNSUPPORTED_CAPABILITY` |
| C-014 | MATERIAL_COMPETITION | `UNSUPPORTED_CAPABILITY`；只支持 material_ready_at |
| C-015 | BATCH_PROCESSING | `UNSUPPORTED_CAPABILITY` |
| C-016 | SPLIT_MERGE | `UNSUPPORTED_CAPABILITY`；不猜 OPEN-008 lot policy |
| C-017 | BUFFER_CAPACITY | `UNSUPPORTED_CAPABILITY` |
| C-018 | PREEMPTIVE_OPERATION | `UNSUPPORTED_CAPABILITY`；V1 非抢占 |

## P0 验证规则表

[`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) 为 C-001～C-011 固定 input path、判定公式、positive/negative example、`VALIDATION_FAILED`/`SCHEDULE_VALIDATION_FAILED` violation shape、Test ID 与 PROD_OPEN；同时为 C-012～C-018 固定 capability key 与 explicit rejection。[`rule_sheet.py`](../../backend/app/planning/validation/rule_sheet.py) 只检查 11+7 ID、必需字段和跨 registry 一致性，不读取或评估 candidate schedule。

TASK-P0-03 的 `planning-problem.v1` 只为候选资源、min/max/transport lag、calendar unavailable interval、release/material gate、部分 RUNNING facts、horizon、duration 和 capability declaration 建立输入字段。COMPLETED execution facts、HARD/SOFT lock、cross-workshop edge identification 与 candidate assignment schema 仍需 P1/P2 合同扩展；规则表用 `contract_status` 明确这些 gap，不虚构字段已发布。OPEN-004/005/007/009/010 均未关闭。

最小 data precheck 和 rule-sheet completeness 都不是 ScheduleValidator，也不能作为任何 C-001～C-011 schedule PASS 证据。TASK-P0-07 才使用 Golden/illegal fixtures 建立真实 mutation rejection；P2 才实现完整独立 Validator。Constraint semantics 本次未改变，因此不触发 Solver benchmark，但 P2 首个 baseline 必须包含本 rule version。

TASK-P0-05 仅移除 rule completeness CLI 对全局 schema set `1.1.0` 的硬编码，仍要求 data dictionary 与 `app.SCHEMA_VERSION` 一致。C-001～C-018 YAML、formula、capability mapping、ValidationReport 和 evaluator 边界均未改变；CLI 在 additive `1.2.0` 下回归通过，不把 Scenario Schema 引入解释为 Constraint 或 Validator 实现。
