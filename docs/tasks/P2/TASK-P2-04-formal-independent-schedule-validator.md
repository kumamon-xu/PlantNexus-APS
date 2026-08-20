---
doc_id: TASK-P2-04
title: Formal Independent ScheduleValidator
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [30, 31, 50, 75, 86, 87]
last_reviewed: 2026-08-20
---

# TASK-P2-04 — Formal Independent ScheduleValidator

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-01, TASK-P2-02

Start gate: Problem v2与Solution/Validation contracts固定；TASK-P2-01/02=`done`；启动前固定positive base hashes、独立性规则和Diff base。

Goal: 实现直接消费正式PlanningProblem与candidate PlanningSolution的独立ScheduleValidator，完整判定C-001～C-011并输出稳定ValidationReport/Error。

Inputs: Problem v2、PlanningSolution、constraint-rule-sheet.v1、validation-report.v2、ADR-0005/0008、P0 positive/mutation assets。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/planning/validation/problem_schedule_validator.py`、`backend/app/planning/validation/__init__.py`、`backend/tests/validation/test_problem_schedule_validator.py`、`backend/tests/validation/test_schedule_validator_mutations.py`、`backend/tests/property/test_schedule_validator_properties.py`及`Documents to update`；若需新Schema/fixture路径先修订卡片。

Files forbidden to change: `backend/app/planning/backends/**`、CP-SAT constraint builder、Solver status trust、P0 immutable fixture bytes/expected artifacts、Strategy/objective、Export/Benchmark/P3。

Implementation steps: 建立正式candidate materializer；按结构/duration/time/operation/edge/resource/lock/fact顺序独立检查；保留exact C-ID和stable ordering；迁移P0 mutation到正式合同且保持公式分离；增加property与backend import scan；生成machine report。

Outputs: formal validator、C-001～C-011 positive/negative/property证据、validation/error report与independence report。

Documentation impact: required

Documents to update: `docs/planning/schedule-validator.md`、`docs/planning/constraint-catalog.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/domain/error-model.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: Validator从fixture-local升级为正式Problem/Solution evaluator，是P2 correctness和所有后继Task的独立接受门。

Change-impact matrix rows reviewed: `IMPACT-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-04→TEST-VALIDATOR-MUTATION/TEST-PROPERTY及C-specific Test IDs→formal validation artifacts；与Backend路径显式隔离。

Schema changes: none expected；复用P2-02 Solution与validation-report.v2；若字段不足先做兼容评审并修订Task/Schema version。

Migration: none。

Dependency changes: none；Validator禁止OR-Tools import。

ADR impact: implements ADR-0005；如需共享constraint logic或改变C语义必须停止并提出superseding ADR。

Error behavior: malformed candidate、缺失/重复/非法reference生成稳定validation failure；每个hard violation携带C-ID/实体/observed/expected；Validator异常不得吞掉或信任Solver status。

Tests: TEST-VALIDATOR-MUTATION、TEST-PROPERTY、TEST-CALENDAR、TEST-MATERIAL、TEST-RUNNING、TEST-CROSS-WORKSHOP、TEST-MAX-LAG、TEST-INF-LOCK/NO-RESOURCE/HORIZON；positive replay、13+ mutations、ordering、schema/error、dependency scan。

Benchmark impact: correctness先行；只记录validator runtime诊断，不设Production threshold；P2-12纳入XS/S/M。

Simulation scenarios: 正式Problem/Solution化SIM-MINIMAL-001及声明式负例；不改历史asset bytes，必要时新增versioned derived fixture。

Acceptance commands: `uv run pytest -q backend/tests/validation backend/tests/property/test_schedule_validator_properties.py backend/tests/golden`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P2-04-validator.json`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-04-formal-independent-schedule-validator.md --check-diff --report build/traceability/TASK-P2-04-report.json`；`git diff --check`。

Artifacts: formal validation/mutation/property/independence reports和Task report。

Provider evidence: exact SHA required `validate`成功；artifact包含validator machine report和Task report，核验job steps/digest/expiry/required context。

Completion conditions: 正式合同上全部C-001～C-011正反路径可复验；独立性扫描PASS；报告确定且schema-valid；local/provider/docs/trace闭环；无Solver实现修改。

Explicitly excluded: CP-SAT建模、objective、Solver结果批准、state persistence/API、P3。

PROD_OPEN: OPEN-004/005/007/009/010不关闭；Validator只判断显式输入事实。

SIM_ASSUMPTIONS: mutation/positive assets保持synthetic/correctness边界，不形成性能或Production证据。

Rollback: 保留fixture-local evaluator与历史报告；formal validator尚无consumer时可回退，已有consumer后以版本化adapter撤销，禁止让Backend替代Validator。
