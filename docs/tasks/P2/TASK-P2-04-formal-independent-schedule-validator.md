---
doc_id: TASK-P2-04
title: Formal Independent ScheduleValidator
status: in_progress
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

Start gate: Problem v2与Solution/Validation contracts固定；TASK-P2-01/02=`done`；用户于2026-08-20明确授权执行本Task；启动时`main=origin/main`、working tree clean，并固定positive base hashes、独立性规则、provider evidence和Diff base。

Goal: 实现直接消费正式PlanningProblem与candidate PlanningSolution的独立ScheduleValidator，完整判定C-001～C-011并输出稳定ValidationReport/Error。

Inputs: Problem v2、PlanningSolution、constraint-rule-sheet.v1、validation-report.v2、ADR-0005/0008、P0 positive/mutation assets。

Diff base: 4c66dce3b919a53816005c4aebf4983db19a6108

Files allowed to change: `backend/app/planning/validation/problem_schedule_validator.py`、`backend/app/planning/validation/problem_validator_check.py`、`backend/app/planning/validation/__init__.py`、`backend/tests/validation/test_problem_schedule_validator.py`、`backend/tests/validation/test_schedule_validator_mutations.py`、`backend/tests/property/test_schedule_validator_properties.py`、`backend/tests/integration/test_ci_contract.py`、`.github/workflows/ci.yml`及`Documents to update`；若需新Schema/fixture路径先修订卡片。

Files forbidden to change: `backend/app/planning/backends/**`、CP-SAT constraint builder、Solver status trust、P0 immutable fixture bytes/expected artifacts、Strategy/objective、Export/Benchmark/P3。

Implementation steps: 建立正式candidate materializer；按结构/duration/time/operation/edge/resource/lock/fact顺序独立检查；保留exact C-ID和stable ordering；迁移P0 mutation到正式合同且保持公式分离；增加property与backend import scan；生成machine report。

Outputs: formal validator、C-001～C-011 positive/negative/property证据、validation/error report与independence report。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/planning/schedule-validator.md`、`docs/planning/constraint-catalog.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/domain/error-model.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: Validator从fixture-local升级为正式Problem/Solution evaluator，是P2 correctness和所有后继Task的独立接受门。

Change-impact matrix rows reviewed: `IMPACT-VALIDATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-04→TEST-VALIDATOR-MUTATION/TEST-PROPERTY及C-specific Test IDs→formal validation artifacts；与Backend路径显式隔离。

Schema changes: none expected；复用P2-02 Solution与validation-report.v2；若字段不足先做兼容评审并修订Task/Schema version。

Migration: none。

Dependency changes: none；Validator禁止OR-Tools import。

ADR impact: implements ADR-0005；如需共享constraint logic或改变C语义必须停止并提出superseding ADR。

Error behavior: malformed candidate、缺失/重复/非法reference生成稳定validation failure；每个hard violation携带C-ID/实体/observed/expected；Validator异常不得吞掉或信任Solver status。

Tests: TEST-VALIDATOR-MUTATION、TEST-PROPERTY、TEST-CALENDAR、TEST-MATERIAL、TEST-RUNNING、TEST-CROSS-WORKSHOP、TEST-MAX-LAG、TEST-INF-LOCK/NO-RESOURCE/HORIZON；positive replay、13+ mutations、ordering、schema/error、dependency scan。

Benchmark impact: correctness先行；只记录validator runtime诊断，不设Production threshold；P2-12纳入XS/S/M。

Simulation scenarios: 正式Problem/Solution化SIM-MINIMAL-001及声明式负例；不改历史asset bytes，必要时新增versioned derived fixture。

Acceptance commands: `uv sync --locked`；`uv run pytest -q backend/tests/validation backend/tests/property/test_schedule_validator_properties.py backend/tests/golden backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run python -m app.planning.validation.problem_validator_check --root . --report build/validation/TASK-P2-04-formal-schedule-validator.json`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-07-validator-mutations.json`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-04-formal-independent-schedule-validator.md --check-diff --report build/traceability/TASK-P2-04-report.json`；`docker compose --env-file .env.example config --quiet`；`uv build`；`git diff --exit-code 4c66dce3b919a53816005c4aebf4983db19a6108 -- uv.lock schemas fixtures backend/app/planning/backends`（仅允许本Task新增的`backend/app/planning/validation/**`出现在该检查之外，最终以显式path hash/source scan复核）；`git diff --check`。

Artifacts: formal validation/mutation/property/independence reports和Task report。

Provider evidence: exact SHA required `validate`成功；artifact包含validator machine report和Task report，核验job steps/digest/expiry/required context。

Completion conditions: 正式合同上全部C-001～C-011正反路径可复验；独立性扫描PASS；报告确定且schema-valid；local/provider/docs/trace闭环；无Solver实现修改。

Explicitly excluded: CP-SAT建模、objective、Solver结果批准、state persistence/API、P3。

PROD_OPEN: OPEN-004/005/007/009/010不关闭；Validator只判断显式输入事实。

SIM_ASSUMPTIONS: mutation/positive assets保持synthetic/correctness边界，不形成性能或Production证据。

Rollback: 保留fixture-local evaluator与历史报告；formal validator尚无consumer时可回退，已有consumer后以版本化adapter撤销，禁止让Backend替代Validator。

## Activation evidence

2026-08-20用户明确授权执行TASK-P2-04。启动复核时working tree clean，`main=origin/main=4c66dce3b919a53816005c4aebf4983db19a6108`；TASK-P2-01 implementation `c64284685f37ef0d03eacade5699076146653333`与TASK-P2-02 implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`均为HEAD祖先且对应Task=`done`。该HEAD的GitHub push run `32346604989`、required `validate` job `96356577126`均`completed/success`；artifact `9398269688`=`plantnexus-ci-evidence-32346604989`，digest=`sha256:d805fbc175cffc3e6397eb162d974e3a59921ff1d1f61b8e8661d0f35572d332`、`expired=false`、expires=`2026-11-18T07:59:37Z`，required context=`validate`/GitHub Actions app ID `15368`。

不可变positive/mutation基线固定为：SIM-MINIMAL-001 import package SHA-256=`6299921cb58866fba8c66a7f8c6adfb47c3de50122d49fde4c20014e7bf0c112`、Golden schedule=`44885e64f477167e08f3146e02546d43780ce5c0fa5db26d82b8b268a2005d5a`、expected validation=`28ecb8cf41fd376f04e916e3c3bea6a026ecb393202257fce8eff2a38a012f9b`；mutation suite=`27914614496f2784f9d3a339a58814b2c0344b864592569b33949e8e22f8c51a`、expected outcomes=`d3a9a16236c39aed55badd0aff46e85d48d78fc5d01be9ffd7c7af8c55069086`、coverage matrix=`a00138aeb672bd18f06d413a84a9e65193536ff4a6767a29df8f0fc52fc46327`。Problem v2/Solution/Validation Schema、rule sheet与`uv.lock`分别固定为`e6e4a984…87c8`、`4344468e…df4`、`1da63e93…353`、`83fc3663…f1e2`、`8b13617f…7a82`；历史fixture evaluator与runner固定为`2b7369d9…8cd2`、`9843bbdd…7dd`且本Task只读。

独立性边界固定为：正式Validator只消费solver-neutral Problem v2与PlanningSolution JSON，不导入`app.planning.backends`、`ortools`、`CpModel`或任何backend constraint builder，不读取expected outcome决定结果，也不信任`solver_status`作为schedule PASS；每个C-ID由Problem/Solution事实独立重算。Scope review在实现前增加独立machine CLI、CI workflow和integration contract路径；不新增Schema/fixture/dependency/ADR，也不修改P0历史bytes。

## Implementation candidate evidence

本地实现已形成`ProblemScheduleValidator`、函数入口、ValidationReport→Error映射与`formal-schedule-validator-report.v1` CLI。正式positive vector为PASS；13个声明式mutation覆盖C-001～C-011并产生14个exact hard violations；6个duration/order examples及三组fixed-seed Hypothesis properties通过。把candidate声明状态改为FAILED并删除run outcome/objective metadata后报告保持完全相同；AST/source evidence确认无Backend、OR-Tools、P0 evaluator/runner、expected outcome或`solver_status`决策依赖。

Task卡Acceptance Commands已在格式化后的工作树执行：`uv sync --locked` PASS；指定validation/property/golden/CI integration suite=`59 passed`；full repository suite=`343 passed`；formal machine=`6/6 PASS`、13 mutations/11 constraints/14 violations/6 examples；历史P0 mutation=`13 cases/11 constraints/13 classes/15 violations PASS`；P2-02=`5/5`、P2-03=`6/6`、P0-08=`6/6`兼容报告PASS；Ruff PASS；Pyright=`0 errors, 0 warnings`；Compose config、`uv build`、版本断言、`git diff --check`均PASS。

Full文档治理为142 docs/30 roots/36 Test IDs/15 OPEN/10 SIM assumptions/11 risks/37 Tasks；Task diff报告为38 paths、6 matched Impact Rules、19 checks、0 issues，Diff base保持`4c66dce3b919a53816005c4aebf4983db19a6108`。`uv.lock`、`schemas/**`、`fixtures/**`与`backend/app/planning/backends/**`相对Diff base无差异；`docs/tasks/TASK_TEMPLATE.md`经review确认既有字段足够，故保持字节不变。

以上仍是implementation candidate本地证据。Implementation SHA及其exact GitHub required `validate`、job、artifact内容/digest/expiry尚待commit/push后核验；在这些provider证据形成前Task保持`in_progress`，不得启动P2-05。
