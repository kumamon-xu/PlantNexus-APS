---
doc_id: TASK-P2-03
title: OR-Tools and SolverBackend Foundation
status: in_progress
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

Start gate: TASK-P2-02=`done`且exact closure已复核；用户于2026-08-20明确授权执行本Task；solver contracts/status固定；ADR-0011须在dependency变更前accepted；启动时`main=origin/main`、working tree clean，并记录lock/contract baseline与immutable Diff base。

Goal: exact-pin OR-Tools并建立SolverBackend protocol、CP-SAT adapter边界、status/version/parameter映射和空模型诊断骨架，不实现C-001～C-011业务约束。

Inputs: Problem/Policy/Limits/Solution contracts、ADR-0002/0003/0004、SolverBackend contract、dependency/security policy。

Diff base: f73f8c90af94d3c9b05ecc10b6c999594a3b7d66

Files allowed to change: 下列精确路径及`Documents to update`中的全部明确文档。

- dependency/CI compatibility: `pyproject.toml`、`uv.lock`、`.github/workflows/ci.yml`、`backend/app/infrastructure/contract_check.py`、`backend/app/planning/policy/contract_check.py`；
- Backend foundation: `backend/app/planning/backends/__init__.py`、`backend/app/planning/backends/contracts.py`、`backend/app/planning/backends/cp_sat/__init__.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/status.py`、`backend/app/planning/backends/cp_sat/contract_check.py`；
- bounded tests: `backend/tests/unit/test_solver_backend_contract.py`、`backend/tests/contract/test_planning_machine_contracts.py`、`backend/tests/integration/test_ci_contract.py`；
- every exact path listed in `Documents to update` below.

Files forbidden to change: `backend/app/planning/contracts.py`、`backend/app/planning/policy/contracts.py`及Problem/Policy/Solution/Report Schema/sample/语义；constraint builders、Strategy/objective、Validator evaluator、fixtures/benchmarks/export、DB/migration/API/Worker/P3；上列allow-list之外的任何路径。

Implementation steps: 接受exact solver ADR；更新direct dependency/lock/CI assertion；建立protocol与cp_sat namespace isolation；映射status/parameters/version/timing；验证domain/problem无OR-Tools import、serialization无Solver对象；构造仅工程性的empty/model-invalid smoke test。

Outputs: pinned solver dependency、backend protocol/adapter skeleton、status/version report与dependency replay evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/adr/ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md`、`docs/adr/README.md`、`docs/architecture/technology-stack.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/domain/kpi-contract.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/operations/security.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、本Task卡。

Documentation impact rationale: 首次Solver依赖与Backend边界影响技术栈、版本、供应链、CI和后续所有模型/benchmark证据。

Change-impact matrix rows reviewed: `IMPACT-POLICY`、`IMPACT-BACKEND`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/009→TASK-P2-03→TEST-CONTRACT-001/TEST-SOLVER-UPGRADE→dependency lock/backend smoke artifacts；约束和feasibility保持PLANNED。

Schema changes: none；消费P2-02合同，不修改schema set。

Migration: none。

Dependency changes: required；接受`ortools==9.15.6755` exact runtime pin并由`uv.lock`锁定全部transitive版本/wheel hashes；启动`uv.lock` SHA-256=`7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd`；记录Windows/local与Linux/provider平台、版本和安全审查；禁止floating range、beta或未锁定wheel。

ADR impact: required；`ADR-0011`在dependency变更前accepted，选择OR-Tools`9.15.6755`、wheel install、namespace isolation及upgrade/replay Gate；保持OR-Tools只存在于cp_sat backend。

Error behavior: import/version mismatch、MODEL_INVALID、unsupported platform或adapter异常使用稳定错误/status，sanitized detail；不把空模型smoke结果冒充业务可行性。

Tests: TEST-CONTRACT-001、TEST-SOLVER-UPGRADE；exact dependency/lock、namespace scans、status mapping、parameter capture、empty/model-invalid smoke与serialization isolation。

Benchmark impact: 触发首次版本baseline要求，但本Task无业务模型；记录NOT_APPLICABLE而非零runtime，实际baseline由P2-12。

Simulation scenarios: none。

Acceptance commands: `uv lock --check`；`uv sync --locked`；`uv run pytest -q backend/tests/unit/test_solver_backend_contract.py backend/tests/contract/test_planning_machine_contracts.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python -m app.planning.backends.cp_sat.contract_check --root . --report build/validation/TASK-P2-03-solver-backend-foundation.json`；`uv run python -m app.planning.policy.contract_check --root . --report build/validation/TASK-P2-02-planning-machine-contracts.json`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P0-08-engineering.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-03-ortools-backend-foundation.md --check-diff --report build/traceability/TASK-P2-03-report.json`；`docker compose --env-file .env.example config --quiet`；`uv build`；`git diff --check`。

Artifacts: accepted ADR、dependency/lock fingerprints、`solver-backend-foundation-report.v1`、Task `traceability-report.v1`。

Provider evidence: provider=`GitHub Actions`、repository=`kumamon-xu/PlantNexus-APS`、branch=`main`、workflow=`PlantNexus repository gates`；用`gh run view <run-id> --repo kumamon-xu/PlantNexus-APS`与GitHub REST查询exact SHA。Required `validate`必须在clean Linux runner完成locked install、tests/build并上传Task/backend artifacts；记录immutable SHA、run/attempt/event/job/steps、artifact ID/name/size/digest/expiry、solver version及branch required-check=`validate`。

Completion conditions: exact dependency和ADR闭环；Backend边界/状态/版本可测；上层无OR-Tools泄漏；local/provider PASS；没有业务constraint/strategy结果。

Explicitly excluded: C-001～C-011、OBJ-001、candidate schedule、benchmark baseline、Solver Worker/DB/API、P3。

PROD_OPEN: OPEN-011/012保持OPEN；本Task不承诺solver limit、capacity或SLA。

SIM_ASSUMPTIONS: none。

Rollback: 回退dependency/lock和backend namespace；保留ADR为rejected/superseded历史，不重写；若后继已消费则先回退consumer并重跑全部replay。

## Activation evidence

2026-08-20用户明确授权执行TASK-P2-03。启动复核时working tree clean，`main=origin/main=f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`；P2-02 implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`为HEAD祖先，closure run `32342949743`、required `validate` job `96345556588`和artifact `9396984310`均为`completed/success`且artifact未过期，required context仍为`validate`。

启动冻结SHA-256：`pyproject.toml=8b43a21525089655fbc0505f8ded44ab0e512092dc84f4837dcff23700be0d53`、`uv.lock=7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd`、`app.planning.contracts=d5f7a7e49e4f83e1da011da113f93a80c7f6bc7b1dc3814df374c5dfaefae630`、`policy.contracts=eff050db6a337866631a7e27d0dd00f29c4d48dce913e819a17687feec01d89c`；四份P2-02 Schema分别为`62624424...1bda`、`8caff522...1d95`、`4344468e...df4`、`64feacd0...b2a`，本Task禁止修改这些合同字节。

官方PyPI与Google release资料确认`9.15.6755`是启动日最新稳定版，并提供CPython 3.12 Windows x86-64、manylinux x86-64/aarch64和macOS wheels；`v10.0 Beta`不进入本Task。官方GitHub repository-level security advisories查询为空；release已知Python wrapper问题包括`status_name()`调用异常，因此foundation使用显式enum/name映射而不依赖该API。上述审查不等于持续漏洞监控或Production安全认证。

Scope review在任何dependency/Backend修改前补入新ADR、machine report CLI、P2-02/P0 historical report兼容更新、contract test、workflow，以及POLICY/INFRA/PHASE等Impact Rule要求的强制文档。Problem/Policy/Solution/Report合同语义、Schema/sample、C-ID、Strategy/objective、Validator、fixture/benchmark/export、DB/API/Worker/P3全部保持禁止。
