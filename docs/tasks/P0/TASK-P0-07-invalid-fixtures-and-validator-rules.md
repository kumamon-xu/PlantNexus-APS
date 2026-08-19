---
doc_id: TASK-P0-07
title: Invalid Fixtures and Validator Rules
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [30, 31, 71, 72, 86]
last_reviewed: 2026-08-19
---

# TASK-P0-07 — Invalid Fixtures and Validator Rules

Requirement IDs: REQ-005

NFR / ENG IDs: NFR-COR-001, ENG-VAL-001, ENG-ERR-001

Depends on: TASK-P0-04, TASK-P0-06

Goal: 基于 Golden Schedule 创建至少三个明确非法 Fixture，并用独立 Rule Sheet 证明能够定位相应 Constraint。

Inputs: SIM-MINIMAL-001、Constraint Catalog、ValidationReport/Error schemas。

Diff base: 14fe1efcb085902ac6b0f7d8dd73b4c3b14c511d

Files allowed to change: `/backend/app/planning/validation/__init__.py`、新增 `/backend/app/planning/validation/schedule_validator.py`、新增 `/backend/app/planning/validation/mutation_check.py`、新增 `/backend/tests/validation/test_schedule_validator_mutations.py`、新增 `/fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/mutation-suite.json`、新增 `/fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/expected-outcomes.json`、新增 `/fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/coverage-matrix.json`、新增 `/fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/calculation-note.md`、生成但不提交的 `/build/validation/TASK-P0-07-rule-contracts.json`、`/build/validation/TASK-P0-07-validator-mutations.json`、`/build/traceability/TASK-P0-07-report.json`，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: `/schemas/**`、`/backend/app/domain/**`、`/backend/app/planning/backends/**`、`/backend/app/planning/problem/**`、`/backend/app/simulation/**`、`/backend/tests/contract/**`、`/backend/tests/golden/**`、`/backend/tests/simulation/**`、`/backend/tests/unit/**`、`/fixtures/deterministic/**`、除 `/fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/**` 外的其他 `/fixtures/**`、`/pyproject.toml`、`/uv.lock`、CpModel、IntervalVar、任何 Solver 或修改 Golden 正例以掩盖问题。若 ValidationReport/Error Schema、领域合同或 PlanningProblem 必须变化才能完成，则停止本 Task 并先修订边界，不在本 Task 内顺手修改。

Implementation steps: 实现只消费 `SIM-MINIMAL-001` fixture-local `sim-minimal-records.v1` 与 `golden-schedule.v1` 的独立结构化 evaluator，不把它声明为 P2 production-performance Validator；直接复算 C-001～C-011，且不读取 expected outcome 自证、不导入 Solver/backend；以与 evaluator 分离的声明式 mutation materializer 注入 missing/duplicate operation、wrong resource、machine overlap、calendar overlap、material early start、completed/running fact、hard lock movement、max lag、cross-workshop transport lag、wrong duration、horizon overflow；固定每个 case 的 `validation-report.v2` 和 `error.v2` expected outcome、完整 required-mutation/C-ID coverage matrix、deterministic ordering 和 machine-check CLI。

Outputs: illegal fixtures、expected validation reports、Rule Sheet PASS report。

Documentation impact: required

Documents to update: `/docs/current_phase.md`、`/docs/domain/error-model.md`、`/docs/planning/schedule-validator.md`、`/docs/planning/constraint-catalog.md`、`/docs/quality/validator-mutation-tests.md`、`/docs/quality/fixtures-and-golden-tests.md`、`/docs/quality/property-tests.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/quality/ci-gates-and-definition-of-done.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/adr/ADR-0005-independent-schedule-validator.md`、`/docs/milestones/README.md`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: 非法 Fixture 会固定 Validator 对各 C-ID 的错误定位、报告字段和测试覆盖。

Change-impact matrix rows reviewed: `IMPACT-VALIDATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: REQ-005、NFR-COR-001、ENG-VAL-001、ENG-ERR-001 → C-001～C-011 fixture-local evaluator → TASK-P0-07 → TEST-VALIDATOR-MUTATION → versioned mutation suite、`validation-report.v2` / `error.v2` expected outcomes、coverage matrix 和 machine reports；明确 TASK-P0-06 positive Golden 保持只读且 PASS，P2 production Validator、PlanningProblem/Solver comparison 继续 `PLANNED`。

Schema changes: none。现有 `validation-report.v2` 与 `error.v2` 足够；若发现缺口则停止并先修订任务边界，而不是在本 Task 内改 Schema。

Migration: 无。

Error behavior: 每个错误返回明确 constraint_id/entity/observed/expected；不能只返回 false。

Tests: positive Golden remains PASS；每个 mutation FAIL 且 exact constraint/entity/observed/expected/report/error 定位正确；C-001～C-011 与总规要求的 mutation 类别 coverage 无缺口；相同输入输出稳定；Validator 不导入 planning backend 或 OR-Tools。

Benchmark impact: 无。

Simulation scenarios: SIM-MINIMAL-001 mutations。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation`；`uv run pyright backend/app backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation`；`uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-07-rule-contracts.json`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-07-validator-mutations.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-07-invalid-fixtures-and-validator-rules.md --check-diff --report build/traceability/TASK-P0-07-report.json`；`git diff --exit-code 14fe1efcb085902ac6b0f7d8dd73b4c3b14c511d -- schemas backend/app/domain backend/app/planning/backends backend/app/planning/problem backend/app/simulation backend/tests/contract backend/tests/golden backend/tests/simulation backend/tests/unit fixtures/deterministic pyproject.toml uv.lock`；`git diff --check`；`uv build`。

Artifacts: versioned invalid mutation suite、expected `validation-report.v2` / `error.v2` outcomes、C-ID/required-mutation coverage matrix、`validator-mutation-report.v1` 和 Rule Sheet contract report（后两者为 ignored build evidence）。

Explicitly excluded: 完整 P2 ScheduleValidator 性能实现、Solver comparison。

PROD_OPEN: 无关闭。

SIM_ASSUMPTIONS: Mutation 不是业务场景事实。

Rollback: 移除新增 mutation version，不修改原始 Golden。

## Completion evidence

Completed at: `2026-08-19T13:28:42+08:00`

### Delivered artifacts

- 独立 evaluator：[`schedule_validator.py`](../../../backend/app/planning/validation/schedule_validator.py) 只消费 fixture-local `sim-minimal-records.v1` / `golden-schedule.v1`，从问题事实和 candidate 直接复算 C-001～C-011，稳定排序并输出 `validation-report.v2`；FAIL 逐 violation 映射 `error.v2` 的 `VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED`，PASS 不生成 Error。它不导入 planning backend、OR-Tools 或 Solver，不读取 Rule Sheet formula、mutation suite、Golden expected checks 或 committed expected outcomes。
- Mutation runner：[`mutation_check.py`](../../../backend/app/planning/validation/mutation_check.py) 以与 evaluator 分离且不含约束公式的 remove/duplicate/replace/append 操作构造 fresh deep copies；CLI 检查 positive/negative exact outcome、两个 v2 JSON Schema、deterministic replay、Rule Sheet violation metadata、coverage 和 dependency boundary，生成 ignored `build/validation/TASK-P0-07-validator-mutations.json`（`validator-mutation-report.v1`）。
- 非法 Fixture：[`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/calculation-note.md) 固定 13 个 versioned mutation case、exact reports/errors 与 coverage matrix。positive base hash 保持 `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`；13 cases 全部 FAIL，共 15 hard violations；duplicate operation 明确同时定位 C-001/C-003/C-004，其余 12 cases 各隔离到一个目标 C-ID；C-001～C-011 和 13 required mutation classes 均无 uncovered entry。
- 测试：[`test_schedule_validator_mutations.py`](../../../backend/tests/validation/test_schedule_validator_mutations.py) 形成 18 项 TEST-VALIDATOR-MUTATION 及 CALENDAR/MATERIAL/RUNNING/LOCK/MAX-LAG/CROSS-WORKSHOP/HORIZON/NO-RESOURCE P0 slice，包含手写 case→C-ID、关键秒/tick 算术、Schema、exact Error、base immutability、formula separation、metadata/coverage、malformed envelope 与 backend/OR-Tools dependency checks。原始 [`SIM-MINIMAL-001`](../../../fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md) 和 5 项 Golden tests 未修改且全量回归 PASS。
- 边界：这只是 ADR-0005 的 P0 fixture-local correctness slice，不声明 P1 canonical/PlanningProblem/candidate contract、P2 production/performance Validator、Solver comparison、Property/Benchmark、API/persistence 或 READY_FOR_REVIEW 状态集成。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/checked 17 packages，lock 无漂移。 |
| `uv run ruff check backend/app backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation` | 0 | PASS；`All checks passed!`。 |
| `uv run pyright backend/app backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation` | 0 | PASS；0 errors、0 warnings、0 informations。 |
| `uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation` | 0 | PASS；64 passed（8 governance unit + 23 contract + 10 simulation + 5 Golden + 18 Validator）。 |
| `uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-07-rule-contracts.json` | 0 | PASS；11 active、7 deferred、20 capabilities、19 error codes、3 machines/27 states/42 transitions。 |
| `uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-07-validator-mutations.json` | 0 | PASS；positive count 0；13 negative cases、11 constraints、13 classes、15 hard violations、0 issues。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；107 docs、30 roots/trace rows、27 Test IDs、15 OPEN、9 SIM assumptions、10 risks、9 Tasks。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-07-invalid-fixtures-and-validator-rules.md --check-diff --report build/traceability/TASK-P0-07-report.json` | 0 | PASS；32 paths、6 impact rows、19 required review docs/19 actually changed、0 missing refs/issues。 |
| `git diff --exit-code 14fe1efcb085902ac6b0f7d8dd73b4c3b14c511d -- schemas backend/app/domain backend/app/planning/backends backend/app/planning/problem backend/app/simulation backend/tests/contract backend/tests/golden backend/tests/simulation backend/tests/unit fixtures/deterministic pyproject.toml uv.lock` | 0 | PASS；Schema、Domain、Problem、Backend、Simulation、既有 tests/Golden、dependencies/version metadata 均未改动。 |
| `git diff --check` | 0 | PASS；无 whitespace error，仅输出 Windows LF→CRLF working-copy 提示。 |
| `uv build` | 0 | PASS；成功构建 sdist 与 wheel。 |

### Documentation impact and traceability

Documentation impact: `required`。实际 diff 为 32 paths：3 个 validation Python files、1 个 Validator test file、4 个 infeasible fixture artifacts、24 份 Markdown。机器矩阵命中 `IMPACT-VALIDATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`；19 份 required review documents 全部实际更新，Task Card 另列的 current phase、Error model、CI gate、ADR-0005 与本卡也同步更新，无“已审查但未修改”项。

Traceability updates:

- REQ-005 / NFR-COR-001 → C-001～C-011 Rule Sheet + positive Golden → TASK-P0-07 → TEST-VALIDATOR-MUTATION → versioned mutation suite / exact `validation-report.v2` / `error.v2` / coverage matrix / machine report；P2 production/performance evidence继续 `PLANNED`。
- ENG-VAL-001 → independent evaluator + formula-free materializer + expected-artifact separation + validation package backend/OR-Tools scan；ENG-ERR-001 → registered FAIL category/code 和逐 violation detail/schema evidence。
- TEST-CALENDAR/MATERIAL/RUNNING/INF-LOCK/MAX-LAG/CROSS-WORKSHOP/INF-HORIZON/INF-NO-RESOURCE 获得 P0 negative slice；TEST-PROPERTY、Solver infeasibility/integration 和 Benchmark 继续 `PLANNED`。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`，没有 closure record；mutation 数值不是生产权威。SIM_ASSUMPTIONS: 未新增/修改，SIM-ASSUMPTION-001～009 全部保持 `ACTIVE`；刻意非法的 gate/lag/horizon/lock/fact 值不是新假设。Risks: RISK-003/004 早期控制增强，但 fixture-local evidence 不足以关闭风险，RISK-001～010 全部保持 `MONITORED`。

Schema changes: none；`validation-report.v2` / `error.v2` 足够且已用锁定 Draft 2020-12 validator 验证。Migration: none；无 DB、consumer 或历史 run。Benchmark impact: none；未创建 Solver、未测 runtime/gap/memory/model size，不修改 Benchmark baseline。ADR: 落实 ADR-0005，Decision 未改变，不新增 ADR。

Diff base 与验收时 Git HEAD 均为 `14fe1efcb085902ac6b0f7d8dd73b4c3b14c511d`；报告 source counts 为 committed range 0、working tree 32。本 Task 未提交用户工作树。Rollback 在其他 Task 消费前可删除整个 mutation bundle、两个 evaluator/runner files、validation test、`__init__` exports 和对应文档追踪；一旦被 P1/P2 artifact 引用，必须发布新 mutation suite version/expected hashes，禁止覆盖 `SIM-MINIMAL-001-MUTATIONS@1.0.0`。原始 Golden 从未修改。TASK-P0-08 保持 `planned`，本 Task 未自动进入下一任务。
