---
doc_id: TASK-P1-10
title: Synthetic Generator Canonical Records
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [10, 37, 38, 39, 40, 41, 42, 43, 73, 74, 104]
last_reviewed: 2026-08-19
---

# TASK-P1-10 — Synthetic Generator Canonical Records

Requirement IDs: REQ-001, REQ-003, REQ-009, REQ-011, REQ-012

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02, TASK-P1-05, TASK-P1-06, TASK-P1-07

Goal: 实现七层 deterministic Synthetic Generator，使 versioned FactoryProfile/ScenarioSpec/seed 生成非空 canonical Import v2 records与 manifest/hash；Generator仍只输出 Standard Import，不得直接构造 Snapshot、Problem或Solver对象。

Inputs: FactoryProfile/ScenarioSpec contracts、canonical Import v2、unit/normalization/data-validation contracts、ADR-0001/0009、existing seed/canonical-json primitives。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `backend/app/simulation/generators/contracts.py`、`backend/app/simulation/generators/determinism.py`、`backend/app/simulation/generators/package_contract.py`、`backend/app/simulation/generators/topology.py`、`backend/app/simulation/generators/routing.py`、`backend/app/simulation/generators/orders.py`、`backend/app/simulation/generators/calendars.py`、`backend/app/simulation/generators/materials.py`、`backend/app/simulation/generators/execution_states.py`、`backend/app/simulation/generators/locks.py`、`backend/app/simulation/generators/package_generator.py`、`backend/app/simulation/generators/__init__.py`、`fixtures/synthetic/SIM-P1-INGRESS-001/factory-profile.json`、`fixtures/synthetic/SIM-P1-INGRESS-001/scenario-spec.json`、`fixtures/synthetic/SIM-P1-INGRESS-001/calculation-note.md`、`backend/tests/simulation/test_p1_synthetic_generator.py`、生成但不提交的 `build/traceability/TASK-P1-10-report.json` 与 `build/validation/TASK-P1-10-generator.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: P0 deterministic/infeasible fixtures、canonical/Scenario Schemas、Adapter/Staging/Normalization/DataValidation行为、Snapshot/Problem、Simulation execution/baseline/benchmark、API、Solver、Production config。

Implementation steps: 每层只消费 immutable GenerationContext和命名 child seed；Profile提供全部 range/distribution，不在代码硬编码生产/通用默认；生成 topology/routing/orders/calendars/material/execution/locks records并由 package layer稳定合并；先产 source-shaped Standard Import输入再走公开 normalization/validation边界，不调用 Snapshot/Problem；manifest记录 versions/seed/generated_at，hash只覆盖 canonical package；Production target和unsupported capability显式拒绝；创建一个小型 versioned P1 synthetic regression asset并登记实际新 assumptions（如需要）。

Outputs: seven-layer generators、non-empty Standard Import v2 package、replay manifest/hash与 synthetic regression asset。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/simulation/README.md`、`docs/simulation/factory-profile.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/synthetic-generator-and-determinism.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/performance-gates.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-10-synthetic-generator-records.md`。

Documentation impact rationale: Generator从 empty protocol升级为非空 versioned data producer，改变 Scenario/Profile/seed/hash与 common-ingress风险证据。

Change-impact matrix rows reviewed: `IMPACT-SIM-GENERATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/003/009/011/012、NFR-DET/TRC/ISO、ENG-ARCH/ERR/VER → TASK-P1-10 → TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION → versioned generator/source package/manifest/hash/fixture artifacts。

Schema changes: none；严格消费已发布 Profile/Scenario/Import contracts。Generator语义变化提升 generator/asset version，不借 schema set掩盖。

Migration: none；P0 empty/manual fixture artifacts只读，不迁移或覆盖。

Error behavior: invalid range/seed/version、unknown/duplicate/unsupported capability、Production target、生成后 normalization/data validation失败都结构化拒绝；不得删记录或改变约束使场景通过。

Tests: `TEST-SCENARIO-REPLAY`、`TEST-SIM-ISOLATION`；same input bytes/hash、layer call-order independence、seed/profile/generator version sensitivity、non-empty collection/reference validity、Production/unsupported rejection、no Planning/Solver import。

Benchmark impact: regression asset只验证 correctness/replay，不是 XS生产容量或 Benchmark baseline；不运行 Solver。

Simulation scenarios: 新建 `SIM-P1-INGRESS-001` 小型 synthetic regression asset；所有定量值必须在 Profile/Scenario与 SIM_ASSUMPTION register明确，不能成为 Production default。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/simulation/generators backend/tests/simulation/test_p1_synthetic_generator.py`；`uv run pyright backend/app/simulation/generators backend/tests/simulation/test_p1_synthetic_generator.py`；`uv run pytest -q backend/tests/simulation/test_p1_synthetic_generator.py backend/tests/simulation/test_simulation_contracts.py`；`uv run pytest -q backend/tests/simulation/test_p1_synthetic_generator.py -k no_planning_or_solver_import`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P1-10-generator.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-10-synthetic-generator-records.md --check-diff --report build/traceability/TASK-P1-10-report.json`；`git diff --check`；`uv build`。

Artifacts: Profile/Scenario asset、generated Import/manifest/hash report、tests、traceability report。

Completion conditions: same Scenario/Profile/generator/seed产生相同 non-empty Import bytes/hash；所有七层有独立测试与命名 seed；输出通过 normalization/data validation且无 Snapshot/Problem/Solver shortcut；isolation/docs/trace/governance PASS。

Explicitly excluded: Execution Simulator、Benchmark/Reference Scheduler、Snapshot/Problem direct construction、Solver、真实工厂分布或生产容量声明。

PROD_OPEN: OPEN-003/004/011/012/013/015 保持 OPEN；synthetic asset不能关闭任何生产问题。

SIM_ASSUMPTIONS: 复用 SIM-ASSUMPTION-001/002/004；新增定量分布前必须先登记稳定 ID并绑定 asset version。

Rollback: 保留旧 generator/asset/hash；失败修复发布新 version，禁止覆盖或重写已提交 replay artifact。

## Completion evidence

执行时填写 generator/profile/scenario versions、seed/hash、collection counts、tests、changed paths、assumption与文档结果。
