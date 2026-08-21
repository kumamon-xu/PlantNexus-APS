---
doc_id: TASK-P2-06
title: CP-SAT Temporal Calendar and Material Model
status: in_progress
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [25, 26, 27, 30, 75]
last_reviewed: 2026-08-21
---

# TASK-P2-06 — CP-SAT Temporal Calendar and Material Model

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-05

Start gate: TASK-P2-05 core model=`done`且formal Validator PASS；用户于2026-08-21明确授权执行本Task；启动时`main=origin/main`、working tree clean，固定tick/rounding、calendar half-open及lag seconds规则，记录即时Diff base并核验依赖Task的exact provider evidence。

Goal: 实现C-002/C-005/C-006/C-009的precedence min/max lag、calendar unavailable intervals、release/material gate与cross-workshop transport，不静默放宽秒/tick边界。

Inputs: core CP-SAT model、Problem v2 edges/calendars/gates、ADR-0008、formal Validator、Golden lag/calendar/material facts。

Diff base: c55aa294977a6cafad85741f425d46cd36e9af1a

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/planning/backends/cp_sat/__init__.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/contract_check.py`、`backend/app/planning/backends/cp_sat/core_constraints.py`、`backend/app/planning/backends/cp_sat/model.py`、`backend/app/planning/backends/cp_sat/solution_mapper.py`、`backend/app/planning/backends/cp_sat/temporal_constraints.py`、`backend/app/planning/backends/cp_sat/temporal_model_check.py`、`backend/tests/integration/test_ci_contract.py`、`backend/tests/property/test_cp_sat_temporal_properties.py`、`backend/tests/unit/test_cp_sat_core_model.py`、`backend/tests/unit/test_cp_sat_temporal_model.py`、`backend/tests/unit/test_solver_backend_contract.py`及`Documents to update`；上述兼容、机器证据与CI exact路径已在进入`in_progress`时冻结，其他路径必须先修订卡片。

Files forbidden to change: contracts/schema、formal Validator formulas、Problem builder/hash、fact/lock/objective/Strategy、dependency/lock、P0 immutable assets、Reference/Export/Benchmark/P3。

Implementation steps: 统一UTC seconds→ticks边界；建min/max lag上下界；transport独立叠加；固定unavailable intervals进入NoOverlap；release/material gate；覆盖inclusive/max-lag和fragmented calendar；Solver结果交独立Validator与tiny brute force。

Outputs: temporal constraint builder、C-002/005/006/009正反/property证据、timing/model delta report。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/domain/kpi-contract.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/planning/constraint-catalog.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/objective-policy.md`、`docs/planning/schedule-validator.md`、`docs/quality/property-tests.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: lag/tick/calendar/gate实现决定可行域边界，必须与独立秒级Validator和Golden一致。

Change-impact matrix rows reviewed: `IMPACT-BACKEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012→TASK-P2-06→C-002/005/006/009→TEST-MAX-LAG/CALENDAR/MATERIAL/CROSS-WORKSHOP/PROPERTY→solver+validator reports。

Schema changes: none。

Migration: none。

Dependency changes: none；solver lock固定。

ADR impact: none if implementing ADR-0008 and catalog formulas exactly；任何rounding、calendar或lag语义偏差需superseding ADR并停止。

Error behavior: invalid/overflow tick或unsupported calendar在build前拒绝；max-lag不可省略；无解返回INFEASIBLE only with certified status，limit未知仍UNKNOWN。

Tests: TEST-MAX-LAG、TEST-CALENDAR、TEST-MATERIAL、TEST-CROSS-WORKSHOP、TEST-PROPERTY、TEST-VALIDATOR-MUTATION；覆盖exact boundary、碎片calendar、min+transport组合、non-integral seconds和infeasible cases。

Benchmark impact: 记录constraint/interval增量和真实build/solve telemetry；不定义Production阈值。

Simulation scenarios: SIM-MINIMAL-001 derived formal case + versioned cross/calendar/material cases；asset变化升version。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_cp_sat_core_model.py backend/tests/unit/test_cp_sat_temporal_model.py backend/tests/unit/test_solver_backend_contract.py backend/tests/property/test_cp_sat_core_properties.py backend/tests/property/test_cp_sat_temporal_properties.py backend/tests/golden backend/tests/validation backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python -m app.planning.backends.cp_sat.contract_check --root . --report build/validation/TASK-P2-03-solver-backend-foundation.json`；`uv run python -m app.planning.backends.cp_sat.core_model_check --root . --report build/validation/TASK-P2-05-cp-sat-core-model.json`；`uv run python -m app.planning.backends.cp_sat.temporal_model_check --root . --report build/validation/TASK-P2-06-cp-sat-temporal-model.json`；`uv run python -m app.planning.validation.problem_validator_check --root . --report build/validation/TASK-P2-04-formal-schedule-validator.json`；`docker compose --env-file .env.example config --quiet`；`uv build`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-06-cp-sat-temporal-calendar-material-model.md --check-diff --report build/traceability/TASK-P2-06-report.json`；`git diff --check`；并复核本Task禁止路径相对Diff base无变化。

Artifacts: temporal-model/validator/property report、model delta和Task report。

Provider evidence: exact SHA required `validate`/all steps success，artifact包含temporal evidence与Task report并记录digest/expiry。

Completion conditions: 四个C-ID solver+Validator一致；边界/负例/property PASS；telemetry、docs、trace和provider闭环；facts/locks/objective仍未形成。

Explicitly excluded: C-007/008、OBJ-001、dynamic Replan、setup/buffer/preemption、P3。

PROD_OPEN: OPEN-004/009/010/011/012保持OPEN；transport/calendar Production来源不猜。

SIM_ASSUMPTIONS: calendar/material/transport值仅versioned synthetic。

Rollback: 独立撤销temporal builder并回到P2-05 core；保留失败case/report，禁止通过删掉max-lag或calendar让测试变绿。

Activation evidence: 2026-08-21启动复核确认`main=origin/main=c55aa294977a6cafad85741f425d46cd36e9af1a`且working tree clean；该SHA的GitHub push run `32354521904`、required `validate` job `96380738933`、artifact `9401134902`均success，artifact digest=`sha256:03f304162e1d862ecc320cf592a27ca1c41282cbcc9ea7c060718bcc69842fe9`且core/formal/Task报告绑定同一SHA。P2-05 implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`是本Diff base的祖先。

Scope review: P2-05的`core_constraints.py`仍会拒绝本Task必须消费的precedence/calendar/gate事实，历史core测试锁定该拒绝；`backend.py`/`solution_mapper.py`/foundation contract需同步真实current boundary，新增provider temporal report还必须接入workflow与integration contract。上述路径因此在任何业务代码修改前补入允许范围；Problem/Policy/Solution Schema、formal Validator、Problem builder/hash、constraint-rule-sheet、OR-Tools pin与`uv.lock`保持不可变。

Implementation evidence: `temporal_constraints.py`实现signed exact ceil/floor、calendar grid projection/merge、precedence/historical anchor、release/material gates与option-conditional transport；`model.py`在resource NoOverlap前组合temporal bindings，Backend/mapper/contract surface同步P2-06真实边界。`temporal_model_check.py`冻结合同/Builder/Validator/rule/lock fingerprints并输出7项机器检查；workflow与integration contract上传/验证该报告。

Local acceptance: focused `87 passed`、full repository `367 passed`、Ruff/Pyright均0；foundation/core/formal/temporal报告分别6/6、6/6、6/6、7/7。Temporal counts为4 implemented C-ID、5 positive candidate、3 certified infeasible、2 precheck、4 independent Validator mutation与8 tiny oracle cases；治理为142 docs、53 paths/6 rows/19 checks/0 issues，Compose、`uv build`、`git diff --check`及禁止路径diff均PASS。Exact provider结果仍待implementation SHA；在此之前Task保持`in_progress`。
