---
doc_id: DOC-PLAN-005
title: 独立 ScheduleValidator 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [30, 31, 50, 75, 86, 87]
last_reviewed: 2026-08-19
---

# 独立 ScheduleValidator 合同

## 独立性

Validator 必须：

- 不导入 CpSatBackend；
- 不复用 CP-SAT constraint builder；
- 不信任 Solver status；
- 使用 PlanningProblem、candidate schedule 和独立规则判定；
- 检查 C-001～C-011。

可以共享稳定领域类型、时间换算和 Schema parser，但任何会让 Solver 与 Validator 产生同源逻辑缺陷的共享均禁止。

## 输出

```text
validation_passed
hard_violation_count
violations[]:
  constraint_id
  severity
  entity_ids
  observed_value
  expected_rule
  message
```

进入 READY_FOR_REVIEW 必须 `validation_passed=true` 且 `hard_violation_count=0`。

P0 当前机器输出合同为 [`validation-report.v2`](../../schemas/json/validation-report.v2.schema.json)：状态字段使用 `PASS/FAIL`，`hard_violation_count` 为非负整数，violation 只接受 C-001～C-011、`severity=HARD`、非空 entity IDs、observed value、expected rule 和 message。PASS 必须 count=0 且无 violations；FAIL 必须至少一个 hard violation。Emitter/consumer 还必须保证 count 与实际 hard violations 一致，不能依赖 JSON Schema 表达跨数组计数等式。

TASK-P0-07 同时固定 FAIL 到 [`error.v2`](../../schemas/json/error.v2.schema.json) 的映射：`VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED`，每个 detail 保留 constraint/entity/observed/expected/source；PASS 返回无 Error。该映射不是 HTTP contract。

## Mutation Set

至少人工构造并拒绝：machine overlap、wrong resource、wrong duration、wrong precedence、calendar overlap、lock movement、material early start、cross-workshop lag violation、missing operation、duplicate operation。P0 固定资产为 [`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/calculation-note.md)：13 个声明式 case 还覆盖 completed/running facts 与 horizon overflow，C-001～C-011 均有负例。

## 验证顺序建议

先检查结构完整性与引用，再检查 duration/time domain，然后按 Operation/Edge/Resource/Lock/Execution 分类检查。验证结果应尽可能收集多个独立违反，而不是遇到第一条即只返回通用错误。

## 变更门

新增 Constraint 时必须同时更新 Validator 合同、正/反 Fixture、Mutation test、Property test 和 Benchmark 影响，不允许“Solver 先支持、Validator 后补”。

## P0-04 contract boundary

TASK-P0-04 形成 [`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) 和 completeness CLI。它只检查 C-001～C-018 metadata、code/category/capability/state registry 一致性，并显式扫描 validation contract package 不导入 backend/OR-Tools。它没有 `validate_schedule`、不读取 candidate schedule，也不构成 ADR-0005 的完整 Validator implementation。

TEST-RULE-SHEET-001/TEST-ERROR-MAPPING-001/TEST-CAPABILITY-001/TEST-STATE-TRANSITION-001 是 P0 contract evidence；它们本身不是 TEST-VALIDATOR-MUTATION。

TASK-P0-05 的 rule-sheet 代码变更只允许 additive schema set `1.2.0`，不修改任何 rule、violation、import scan 或候选 schedule 行为；P0-04 tests 全量回归。Scenario expected behavior/manifest 不是 Validator output，empty Import package 不能作为 C-001～C-011 PASS。

## P0-06 positive Golden boundary

`SIM-MINIMAL-001@1.0.0` 提供人工 schedule 与 fixture-local `golden-validation.v1` expected checks；[`test_sim_minimal_001.py`](../../backend/tests/golden/test_sim_minimal_001.py) 从 Import/Schedule 直接复算所有 applicable C-ID，并确认 hard violation count 期望为 0。replay loader 只检查 artifact/provenance/hash，明确不评估 C-ID，且两者均不导入 Planning backend/OR-Tools。

这证明一个已知正例可独立手算；TASK-P0-07 保持原目录只读，并把该正例作为 evaluator 的 PASS 输入。它仍不是正式 PlanningProblem/candidate schema 或 Solver integration。

## P0-07 fixture-local evaluator

[`schedule_validator.py`](../../backend/app/planning/validation/schedule_validator.py) 直接消费 `sim-minimal-records.v1` 与 `golden-schedule.v1`，从 Import facts 和 candidate assignments 复算 C-001～C-011。它只共享稳定 UTC/tick/domain output types，不导入 planning backend、OR-Tools 或 constraint builder；不读取 Rule Sheet formula、mutation suite 或 expected outcome。Rule Sheet YAML 只在测试/CLI 中交叉核对 violation metadata。

[`mutation_check.py`](../../backend/app/planning/validation/mutation_check.py) 以无公式的声明式操作在内存副本上构造 mutation，验证：positive Golden PASS、13 个 negative case FAIL、15 个 hard violations 的 exact report/error、两份 v2 Schema、deterministic replay、Rule Sheet metadata、全部 C-ID 与 required mutation coverage。生成的 `validator-mutation-report.v1` 为 ignored build evidence。

这是 ADR-0005 的 P0 correctness slice，但明确不是 P2 production/performance completion：fixture-local vocabulary 尚未替换为正式 PlanningProblem/candidate contract，未做 Solver comparison、规模/耗时/内存 Benchmark、API/persistence 或 READY_FOR_REVIEW 状态集成。TEST-PROPERTY 和 P2 全链路 Validator 仍 `PLANNED`。
