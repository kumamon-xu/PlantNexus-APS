---
doc_id: TASK-P1-12
title: P1 Exit Gate Audit
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [73, 74, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-19
---

# TASK-P1-12 — P1 Exit Gate Audit

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009, REQ-011, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-01～TASK-P1-11

Goal: 独立复核全部 P1 Task范围、证据和总规 §74 Gate，形成有日期、不可变 commit、真实命令结果与边界声明的 P1 Exit Gate audit/report manifest；本 Task无权进入 P2。

Inputs: TASK-P1-01～11 Completion evidence、P1 machine reports、Schema/migration/hash vectors、CI/provider artifacts、P0 superseding audit。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `docs/milestones/P1-exit-gate-audit-report.md`、`docs/milestones/P1-exit-gate-evidence-manifest.json`、生成但不提交的 `build/validation/TASK-P1-12-p1-pipeline.json`、`build/validation/TASK-P1-12-rule-contracts.json`、`build/validation/TASK-P1-12-simulation-contracts.json`、`build/validation/TASK-P1-12-golden.json`、`build/validation/TASK-P1-12-validator-mutations.json`、`build/validation/TASK-P1-12-engineering.json`、`build/traceability/TASK-P1-12-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: `backend/**`、`schemas/**`、`fixtures/**`、`scripts/**`、`.github/**`、`infra/**`、`pyproject.toml`、`uv.lock`、migrations、test assertions、任何 remediation、P2 Task/implementation、Solver/OR-Tools、Production state。

Implementation steps: 固定 audit commit/range；逐 Task复核 allowed scope/completion evidence；重跑 full P0+P1 build/test/migration/machine/governance gates；至少两次独立 replay same Scenario+seed并核对 import package bytes/hash、snapshot hash、problem hash；重跑 route cycle/missing resource/unit error/missing duration exact rejection；核验 CSV/Excel/formal adapter、Raw Staging、Normalization、Expansion、Snapshot immutability与 common ingress；查询实际 CI provider/run/artifact/required-check（只在执行时授权可用时）；忠实给出 READY/NOT_READY与 gaps，失败不在 audit内修复。

Outputs: `P1-exit-gate-audit-report.md`、`P1-exit-gate-evidence-manifest.json`、Gate decision、gap list与 P2 transition recommendation。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/milestones/P1-exit-gate-audit-report.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-12-p1-exit-gate-audit.md`、`docs/contracts/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/planning-problem.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/simulation/synthetic-generator-and-determinism.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`。

Documentation impact rationale: Exit Gate汇总分散实现证据并决定 P1 readiness、gaps和是否可请求进入 P2，必须同步 Milestone、Phase、质量、合同和追踪边界。

Change-impact matrix rows reviewed: `IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: 全部 P1 roots → TASK-P1-01～12 → 相关 Test IDs/machine reports/CI artifacts → P1 audit report/manifest；分别记录 formed evidence与 P2/Production `PLANNED`，任何 gap建立新的有界 P1 remediation Task。

Schema changes: none；只审计已发布版本、兼容与 hash replay。

Migration: none；只重跑并核验 P1 staging/snapshot migrations，不修改 revision。

Error behavior: 任一必需 Gate非 PASS则 overall `NOT_READY`；无法运行写 `NOT_RUN`，证据不一致写 `FAIL`/gap；audit Task可因诚实完整而 done，但 Milestone不得伪装 READY。

Tests: 全部 P0/P1 registered tests；重点 `TEST-P1-COMMON-INGRESS`、`TEST-SCENARIO-REPLAY`、`TEST-SNAPSHOT-REPLAY-001`、`TEST-PROBLEM-REPLAY-001`、`TEST-DATA-QUALITY-001`、`TEST-IMPORT-ADAPTER-001`、`TEST-IMPORT-STAGING-001`、`TEST-ORDER-EXPANSION-001`。

Benchmark impact: P1无 Solver benchmark gate；只审计 pipeline build/replay诊断且不关闭 OPEN-012或声称生产容量。

Simulation scenarios: 重放 versioned `SIM-P1-INGRESS-001`至少两次；确认 Production target rejection和 assumptions/provenance完整。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/integration backend/tests/property backend/tests/simulation backend/tests/golden backend/tests/validation`；`uv run pytest -q backend/tests/integration/test_migrations_and_infrastructure.py backend/tests/contract/test_p1_exit_rejections.py`；`uv run python -m app.application.p1_gate_report --root . --scenario fixtures/synthetic/SIM-P1-INGRESS-001 --repeat 2 --report build/validation/TASK-P1-12-p1-pipeline.json`；`uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P1-12-rule-contracts.json`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P1-12-simulation-contracts.json`；`uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P1-12-golden.json`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P1-12-validator-mutations.json`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P1-12-engineering.json`；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-12-p1-exit-gate-audit.md --check-diff --report build/traceability/TASK-P1-12-report.json`；`git diff --check`；`uv build`；provider查询只在执行时获得外部授权后进行，并将实际命令、run/job/artifact/required-check结果写入 evidence manifest。

Artifacts: audit report、machine manifest、two-run hashes、negative reports、migration/build/governance/CI evidence与 gap records。

Completion conditions: audit范围完整且命令结果真实；只有全部 §74 Gate、P1 deliverables、repository build/governance/CI prerequisites有可核验证据时才给 `READY`；否则给 `NOT_READY`和 remediation；current phase保持 P1且不创建/执行 P2 Task。

Explicitly excluded: 在 audit内修代码/Schema/test、自动进入 P2、关闭 PROD_OPEN、Solver/Benchmark/Production readiness声明。

PROD_OPEN: OPEN-001～015 必须保持有权威证据的真实状态；P1 Gate不要求关闭全部且不得用 synthetic evidence关闭。

SIM_ASSUMPTIONS: 审计全部 active IDs与资产引用；不得用于 Production结论。

Rollback: Audit是历史记录，不覆盖失败为 PASS；事实错误用更正/superseding audit，失败时保留 P1 active并创建有界 remediation。

## Completion evidence

执行时填写 audit date/attestation、Diff base/HEAD、全部 Gate表、命令退出码、artifact hashes/provider facts、gaps和最终 recommendation。
