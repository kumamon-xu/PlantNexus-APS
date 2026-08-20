---
doc_id: TASK-P2-03
title: OR-Tools and SolverBackend Foundation
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [13, 14, 24, 29, 57, 75, 93, 102]
last_reviewed: 2026-08-20
---

# TASK-P2-03 — OR-Tools and SolverBackend Foundation

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-02

Start gate: TASK-P2-02=`done`；solver contracts/status固定；先批准首次OR-Tools exact-version ADR、记录lock baseline和Diff base。

Goal: exact-pin OR-Tools并建立SolverBackend protocol、CP-SAT adapter边界、status/version/parameter映射和空模型诊断骨架，不实现C-001～C-011业务约束。

Inputs: Problem/Policy/Limits/Solution contracts、ADR-0002/0003/0004、SolverBackend contract、dependency/security policy。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `pyproject.toml`、`uv.lock`、`backend/app/planning/backends/__init__.py`、`backend/app/planning/backends/contracts.py`、`backend/app/planning/backends/cp_sat/__init__.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/status.py`、`backend/tests/unit/test_solver_backend_contract.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；ADR文件和其他新增路径进入in_progress前精确登记。

Files forbidden to change: Problem/Policy合同语义、constraint builders、Strategy/objective、Validator evaluator、fixtures/benchmarks/export、DB/API/Worker/P3。

Implementation steps: 接受exact solver ADR；更新direct dependency/lock/CI assertion；建立protocol与cp_sat namespace isolation；映射status/parameters/version/timing；验证domain/problem无OR-Tools import、serialization无Solver对象；构造仅工程性的empty/model-invalid smoke test。

Outputs: pinned solver dependency、backend protocol/adapter skeleton、status/version report与dependency replay evidence。

Documentation impact: required

Documents to update: `docs/architecture/technology-stack.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/contracts/schema-versioning.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/operations/security.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 首次Solver依赖与Backend边界影响技术栈、版本、供应链、CI和后续所有模型/benchmark证据。

Change-impact matrix rows reviewed: `IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-BACKEND`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/009→TASK-P2-03→TEST-CONTRACT-001/TEST-SOLVER-UPGRADE→dependency lock/backend smoke artifacts；约束和feasibility保持PLANNED。

Schema changes: none；消费P2-02合同，不修改schema set。

Migration: none。

Dependency changes: required；OR-Tools必须exact pin并锁定全部transitive版本，记录安装平台/版本和安全审查；禁止floating range或未锁定wheel。

ADR impact: required；首次solver/version/upgrade-replay ADR须在dependency变更前accepted，保持OR-Tools只存在于cp_sat backend。

Error behavior: import/version mismatch、MODEL_INVALID、unsupported platform或adapter异常使用稳定错误/status，sanitized detail；不把空模型smoke结果冒充业务可行性。

Tests: TEST-CONTRACT-001、TEST-SOLVER-UPGRADE；exact dependency/lock、namespace scans、status mapping、parameter capture、empty/model-invalid smoke与serialization isolation。

Benchmark impact: 触发首次版本baseline要求，但本Task无业务模型；记录NOT_APPLICABLE而非零runtime，实际baseline由P2-12。

Simulation scenarios: none。

Acceptance commands: `uv lock --check`；`uv sync --locked`；`uv run pytest -q backend/tests/unit/test_solver_backend_contract.py backend/tests/integration/test_ci_contract.py`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-03-ortools-backend-foundation.md --check-diff --report build/traceability/TASK-P2-03-report.json`；`git diff --check`。

Artifacts: accepted ADR、dependency/lock fingerprints、backend contract/status smoke report、Task report。

Provider evidence: exact SHA的required `validate`必须在clean runner完成locked install、tests/build并上传Task/status artifacts；记录solver version与artifact digest。

Completion conditions: exact dependency和ADR闭环；Backend边界/状态/版本可测；上层无OR-Tools泄漏；local/provider PASS；没有业务constraint/strategy结果。

Explicitly excluded: C-001～C-011、OBJ-001、candidate schedule、benchmark baseline、Solver Worker/DB/API、P3。

PROD_OPEN: OPEN-011/012保持OPEN；本Task不承诺solver limit、capacity或SLA。

SIM_ASSUMPTIONS: none。

Rollback: 回退dependency/lock和backend namespace；保留ADR为rejected/superseded历史，不重写；若后继已消费则先回退consumer并重跑全部replay。
