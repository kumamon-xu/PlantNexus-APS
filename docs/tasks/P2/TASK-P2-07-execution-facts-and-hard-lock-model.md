---
doc_id: TASK-P2-07
title: Execution Facts and Hard Lock Model
status: done
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [25, 26, 30, 35, 50, 75]
last_reviewed: 2026-08-21
---

# TASK-P2-07 — Execution Facts and Hard Lock Model

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-06

Start gate: TASK-P2-06=`done`；用户于2026-08-21明确授权执行本Task；启动时`main=origin/main`、working tree clean，Problem v2 RUNNING/COMPLETED anchor与lock字段已验证；固定execution/lock facts、不可变Diff base及依赖Task的exact provider evidence。

Goal: 实现C-007/C-008：COMPLETED排除但历史lag有效，RUNNING资源/实际开始/剩余未来占用固定，HARD lock resource/start/end不可移动；SOFT lock仅保留供未来稳定性且不作为硬约束。

Inputs: Problem v2 facts/locks、CP-SAT core/temporal model、formal Validator、ADR-0007、C-007/008 rule sheet。

Diff base: 33cc3282ead23a4cc1bb214190191e116b095119

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/planning/backends/cp_sat/__init__.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/contract_check.py`、`backend/app/planning/backends/cp_sat/core_constraints.py`、`backend/app/planning/backends/cp_sat/core_model_check.py`、`backend/app/planning/backends/cp_sat/fact_lock_constraints.py`、`backend/app/planning/backends/cp_sat/fact_lock_model_check.py`、`backend/app/planning/backends/cp_sat/model.py`、`backend/app/planning/backends/cp_sat/solution_mapper.py`、`backend/tests/integration/test_ci_contract.py`、`backend/tests/property/test_cp_sat_core_properties.py`、`backend/tests/property/test_cp_sat_fact_lock_properties.py`、`backend/tests/unit/test_cp_sat_core_model.py`、`backend/tests/unit/test_cp_sat_fact_lock_model.py`、`backend/tests/unit/test_solver_backend_contract.py`及`Documents to update`；上述兼容、机器证据与CI exact路径已在进入`in_progress`时冻结，其他路径必须先修订卡片。

Files forbidden to change: Problem/Policy/Solution schema、formal Validator formulas、Problem builder/hash、constraint rule sheet、dependency/lock、SOFT lock objective、dynamic Replan、ExecutionSimulator、P0 asset bytes、Export/Benchmark implementation、P3。

Implementation steps: 固定RUNNING master/assignment/remaining interval；应用historical anchors；排除COMPLETED未来assignment；固定HARD lock三要素及一致性；保留SOFT metadata不硬化；构造lock/no-resource/horizon infeasible；Validator和property交叉。

Outputs: fact/lock constraint builder、C-007/008正反/property/infeasibility证据及model report。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/kpi-contract.md`、`docs/planning/constraint-catalog.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/objective-policy.md`、`docs/planning/schedule-validator.md`、`docs/planning/replanning.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: execution facts和HARD lock是事实保护边界，错误实现会产生不可接受计划并影响未来Replan。

Change-impact matrix rows reviewed: `IMPACT-BACKEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012→TASK-P2-07→C-007/008→TEST-RUNNING/INF-LOCK/PROPERTY/VALIDATOR-MUTATION→fact-lock solver/validator artifacts。

Schema changes: none；消费Problem v2。

Migration: none。

Dependency changes: none。

ADR impact: implements ADR-0007；若允许移动RUNNING/HARD lock或把SOFT变hard必须停止并新建superseding ADR。

Error behavior: fact/lock自相矛盾在model build前明确拒绝；真实不可行返回INFEASIBLE；不得静默降级lock为hint或重新选择RUNNING资源。

Tests: TEST-RUNNING、TEST-INF-LOCK、TEST-PROPERTY、TEST-VALIDATOR-MUTATION；覆盖completed-active lag、running occupancy、hard start/end/resource、soft non-hard、conflicts和deterministic replay。

Benchmark impact: 记录fixed interval/constraint counts与solver telemetry；不运行动态Replan或稳定性benchmark。

Simulation scenarios: versioned Running/Hard Lock correctness scenarios；不注入事件流。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_cp_sat_core_model.py backend/tests/unit/test_cp_sat_fact_lock_model.py backend/tests/unit/test_solver_backend_contract.py backend/tests/property/test_cp_sat_core_properties.py backend/tests/property/test_cp_sat_fact_lock_properties.py backend/tests/golden backend/tests/validation backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python -m app.planning.backends.cp_sat.contract_check --root . --report build/validation/TASK-P2-03-solver-backend-foundation.json`；`uv run python -m app.planning.backends.cp_sat.core_model_check --root . --report build/validation/TASK-P2-05-cp-sat-core-model.json`；`uv run python -m app.planning.backends.cp_sat.temporal_model_check --root . --report build/validation/TASK-P2-06-cp-sat-temporal-model.json`；`uv run python -m app.planning.backends.cp_sat.fact_lock_model_check --root . --report build/validation/TASK-P2-07-cp-sat-fact-lock-model.json`；`uv run python -m app.planning.validation.problem_validator_check --root . --report build/validation/TASK-P2-04-formal-schedule-validator.json`；`docker compose --env-file .env.example config --quiet`；`uv build`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-07-execution-facts-and-hard-lock-model.md --check-diff --report build/traceability/TASK-P2-07-report.json`；`git diff --check`；并复核本Task禁止路径相对Diff base无变化。

Artifacts: fact-lock model/validator/property report、infeasibility cases、Task report。

Provider evidence: exact SHA required `validate`成功，artifact含C-007/008 evidence和Task report，记录run/job/steps/digest。

Completion conditions: C-007/008全部事实保护在Solver与Validator独立PASS；冲突负例明确；SOFT boundary保持；local/provider/docs/trace闭环。

Explicitly excluded: OBJ-002 stability、ExecutionSimulator、event/replan、approval/publish、P3/P4。

PROD_OPEN: OPEN-005/007保持OPEN；freeze policy和事实authority不猜。

SIM_ASSUMPTIONS: Running/lock比例和值只属于versioned scenarios。

Rollback: 回退fact-lock builder并禁止使用缺少C-007/008的Backend生成可接受结果；保留冲突/失败证据。

Activation evidence: 2026-08-21启动复核确认`main=origin/main=33cc3282ead23a4cc1bb214190191e116b095119`且working tree clean；该SHA的GitHub push run `32432843343`、required `validate` job/check `96627943272`（app `15368`）、artifact `9429703054`均success，artifact digest=`sha256:de371e743b27881ea7901e1252a2c3465256d797e54736e95cf225e05eef065c`、expiry=`2026-11-19T00:29:15Z`，且temporal/core/formal/Task报告绑定同一SHA。P2-06 implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`是本Diff base的祖先。

Scope review: P2-06的`core_constraints.py`仍显式拒绝本Task必须消费的RUNNING/lock事实，`model.py`仍按option duration建模，`solution_mapper.py`未映射RUNNING remaining或lock references；历史core测试锁定旧拒绝。正式provider evidence还要求新增machine report并接入workflow/integration contract，foundation current boundary与Backend诊断也必须同步。上述路径因此在任何业务代码修改前补入允许范围；Problem/Policy/Solution Schema、formal Validator、Problem builder/hash、constraint-rule-sheet、OR-Tools pin与`uv.lock`保持不可变。

Local implementation evidence: C-007/C-008已由独立fact/lock builder与现有core/temporal model组合形成；COMPLETED只保留historical anchor，RUNNING固定资源并从horizon start占用ceil-rounded remaining interval，HARD固定resource/start/end，SOFT仅保留metadata/reference。Focused suite=`93 passed`，full repository=`382 passed`，Ruff/Pyright为0问题；foundation/core/formal machine reports各6/6、temporal/fact-lock各7/7 PASS，fact-lock counts为2个C-ID、4 candidate、3 certified INFEASIBLE、4 precheck、2 Validator mutation及6 tiny oracle。Full治理为142 docs/30 roots/36 Test IDs/15 OPEN/10 SIM/11 risks/37 Tasks；Task diff为54 paths、6 matched Impact Rules、19 checks、0 issues，Compose、build、`git diff --check`与禁止路径复核均PASS。Exact implementation SHA的required `validate`与artifact尚未形成，因此本Task继续`in_progress`，P2-08未启动。

Provider closure: implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`已直接push `main`。GitHub push run `32435395744`、required `validate` job/check `96635463577`（GitHub Actions app `15368`）均`completed/success`，包括新增fact-lock step在内的全部步骤成功。Artifact `9430579117`=`plantnexus-ci-evidence-32435395744`，`expired=false`、expiry=`2026-11-19T01:11:01Z`、digest=`sha256:a6b6ff7413b8010a8012ddd351a2a194b89b1a13cdf71c6dada5d6afa53a44ab`；foundation/core/formal报告各6/6、temporal/fact-lock各7/7且全部绑定同一SHA，fact-lock counts与本地一致，Task report绑定同一SHA/Diff base并为54 committed/0 working paths、6 rows、19 checks、0 issues。Completion conditions全部满足，Task=`done`；P2保持`active`，P2-08～14仍为`planned`且未获启动授权，不进入P3。
