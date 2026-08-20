---
doc_id: DOC-QUAL-003
title: Validator Mutation Test 规范
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [30, 31, 86]
last_reviewed: 2026-08-20
---

# Validator Mutation Test 规范

Mutation Test 从一个已知合法计划出发，单次或受控组合地注入错误，证明 Validator 不依赖 Solver 的自我声明。

| Mutation | 期望 Constraint |
|---|---|
| missing operation / duplicate operation | C-001 |
| wrong resource / multiple selection | C-003 |
| machine overlap | C-004 |
| calendar overlap | C-005 |
| material/release early start | C-006 |
| completed/running fact change | C-007 |
| HARD_LOCK movement | C-008 |
| wrong precedence / max lag | C-002 |
| cross-workshop lag violation | C-009 |
| wrong duration | C-010 |
| horizon overflow/truncation | C-011 |

每个断言至少验证 `validation_passed=false`、正确 `constraint_id`、相关 entity IDs、observed 和 expected。只返回通用 `VALIDATION_FAILED` 而无细节不算通过。

Mutation 生成逻辑不得复用 Validator 的判断公式，以免测试与实现同源。

## P0-04 rule baseline

P0-04 已发布 `constraint-rule-sheet.v1` 与 `validation-report.v2`，固定每个 active C-ID 的 input/formula/example/violation/Test ID，并由 TEST-RULE-SHEET-001 验证元数据完整性。该测试不注入 schedule mutation，不把规则表自检误称为 Validator PASS。

TASK-P0-07 已从 SIM-MINIMAL-001 Golden Schedule 独立构造 [`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/calculation-note.md)。[`mutation-suite.json`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/mutation-suite.json) 用 remove/duplicate/replace/append 等声明式操作构造 13 个 case；materializer 不含 constraint ID、Rule Sheet metadata 或 duration/lag 判断公式。C-012～C-018 仍属于 capability precheck rejection，不伪装成 schedule violation。

TASK-P0-05 的 TEST-SIM-ISOLATION 只验证 Production target 与 capability declaration precheck，不注入 candidate schedule mutation。Schema samples/empty Import 不是合法 Golden Schedule，因此没有提前形成 TEST-VALIDATOR-MUTATION；TASK-P0-07 边界不变。

TASK-P0-06 已形成不可覆盖的 `SIM-MINIMAL-001@1.0.0` positive baseline，并在 test-local 代码中直接复算 C-001～C-011；C-007/C-008 因本版本没有 execution facts/locks 明确 N/A。TASK-P0-07 保持该目录/hash 不变，并由不同 mutation construction 路径证明结构化 rejection。

## P0-07 executable evidence

[`expected-outcomes.json`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/expected-outcomes.json) 固定 positive PASS 与每个 negative case 的 exact `validation-report.v2` / `error.v2`。13 个 case 共 15 个 hard violations：duplicate operation 同时违反 C-001、C-003、C-004，其余 12 个 case 各产生一个目标 C-ID。每条 violation 均包含 constraint、unique entity IDs、observed value、Rule Sheet expected rule 和 message；Error 映射保留相同诊断信息。

[`coverage-matrix.json`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/coverage-matrix.json) 对 C-001～C-011 和 missing/duplicate/wrong-resource/overlap/calendar/material/completed/running/lock/max-lag/transport/duration/horizon 13 类 mutation 全量列举，两个 uncovered 数组均为空。[`test_schedule_validator_mutations.py`](../../backend/tests/validation/test_schedule_validator_mutations.py) 独立手写 case→C-ID 与关键秒/tick 算术；[`mutation_check.py`](../../backend/app/planning/validation/mutation_check.py) 再检查 exact artifacts、v2 Schema、determinism、metadata、coverage 和 backend/OR-Tools dependency boundary。

这形成 TEST-VALIDATOR-MUTATION 的 P0 fixture-local correctness evidence。随机生成/shrinking、正式 PlanningProblem/candidate contract、Solver result comparison、规模/性能 Benchmark 和 P2 production Validator 仍 `PLANNED`。

## TASK-P1-06 non-overlap review

TASK-P1-06的negative inputs从canonical Import sample复制后只注入route cycle、orphan/duplicate、resource/capability、unit/duration、calendar/lag/fact/lock错误，输出ImportQualityReport/Error v3。它们不是从合法candidate Schedule产生的C-ID mutation，未读取或改写`SIM-MINIMAL-001-MUTATIONS`、expected outcomes、P0 evaluator或ValidationReport v2。

因此本Task只形成TEST-DATA-QUALITY-001/TEST-INF-NO-RESOURCE/TEST-CAPABILITY-001的input-gate evidence，不能把四个exact data error写成TEST-VALIDATOR-MUTATION新增coverage。P0 positive fixture/hash和13-case mutation资产保持不变；P2 production/performance边界继续`PLANNED`。

## TASK-P1-10 non-overlap review

Generator tests注入unknown lock resource以证明生成后Data Validation FAIL会被结构化拒绝，并用wrong unit-registry version证明Normalization失败；这些是source/canonical input gate负例，不是candidate Schedule mutation或C-001～C-011 evaluator evidence。P0 `SIM-MINIMAL-001-MUTATIONS@1.0.0`及13-case expected artifacts保持只读，TEST-VALIDATOR-MUTATION coverage不变。

生成的RUNNING fact/lock只证明canonical reference/resource-option自洽，不证明未来Solver保持事实或lock约束。P2 independent Validator/Solver comparison继续`PLANNED`。

## TASK-P2-04 formal contract mutation evidence

P2-04保留`SIM-MINIMAL-001@1.0.0`与`SIM-MINIMAL-001-MUTATIONS@1.0.0`全部历史bytes，不改写P0 exact outcomes。新的机器检查在内存中构造一个valid `planning-problem.v2`与schema-valid `planning-solution.v1` correctness vector，再通过只做remove/duplicate/field replacement/explicit interval replacement的materializer产生13类负例；materializer不读取`FORMAL_RULE_METADATA`、expected report或Validator判断结果。

Formal cases为missing、duplicate、wrong resource、machine overlap、calendar overlap、material early、completed rescheduled、running moved、hard lock moved、max/min precedence lag、cross-workshop transport lag、wrong duration和horizon overflow。它们产生14个hard violations：duplicate同时命中C-001/C-003，其余case各精确命中一个目标C-ID；C-001～C-011全集覆盖，重复执行报告字节语义相同。每个FAIL同时通过`validation-report.v2`和`error.v2` Schema，Error保持constraint/entity/observed/expected/source detail。

[`test_problem_schedule_validator.py`](../../backend/tests/validation/test_problem_schedule_validator.py) 固定case→exact C-ID、positive/status-independence、malformed/reference、RUNNING remainder、Schema/error与source AST边界；历史[`test_schedule_validator_mutations.py`](../../backend/tests/validation/test_schedule_validator_mutations.py)继续原样重放P0 13 cases/15 violations。Formal machine report不把历史expected outcome当决策输入，也不构成Solver comparison、性能或Production证据。
