---
doc_id: TASK-P1-11
title: Common Ingress Pipeline and P1 Gate Evidence
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [0, 9, 10, 23, 24, 63, 65, 66, 73, 74, 93]
last_reviewed: 2026-08-19
---

# TASK-P1-11 — Common Ingress Pipeline and P1 Gate Evidence

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009, REQ-011, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, ENG-ARCH-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-03～TASK-P1-10

Goal: 用单一 application pipeline编排 Adapter/Synthetic source → Raw Staging → Normalization → Data Validation → Order Expansion → PlanningSnapshot → PlanningProblem，并生成可供 P1 Exit Gate审计的 deterministic machine report和 CI artifact。

Inputs: TASK-P1-03～10 的 versioned contracts/implementations、`SIM-P1-INGRESS-001`、P1 Gate exact rejection cases、phase-aware CI。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `backend/app/application/__init__.py`、`backend/app/application/import_pipeline.py`、`backend/app/application/p1_gate_report.py`、`backend/tests/integration/test_p1_common_ingress.py`、`backend/tests/contract/test_p1_exit_rejections.py`、`backend/tests/simulation/test_p1_pipeline_replay.py`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`、生成但不提交的 `build/validation/TASK-P1-11-p1-pipeline.json`、`build/validation/TASK-P1-11-rule-contracts.json`、`build/validation/TASK-P1-11-simulation-contracts.json`、`build/validation/TASK-P1-11-golden.json`、`build/validation/TASK-P1-11-validator-mutations.json`、`build/validation/TASK-P1-11-engineering.json` 与 `build/traceability/TASK-P1-11-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: 下游各模块的业务语义、Schema/registry、P0/P1 fixtures、database migrations、API/product endpoints、Solver/Strategy/Validator、P2、测试期望弱化或绕过 staging/normalization。

Implementation steps: application service只调用公开 protocols并传递 immutable artifacts/versions；ReferenceFileAdapter和Synthetic Generator从 staging后使用同一函数链；两次运行同 Scenario+seed并对比 import bytes/hash、snapshot bytes/hash、problem bytes/hash；四个 rejection fixture走相同入口并核对 exact code；报告记录 versions/entity counts/source/synthetic/code commit与边界；CI执行全部 P0/P1回归、machine report、governance、build和 artifact upload，不声称 Solver/Production。

Outputs: common-ingress application service、`p1-data-pipeline-report.v1`、E2E/negative/CI evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/planning-problem.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/domain/error-model.md`、`docs/operations/README.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/simulation/synthetic-generator-and-determinism.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-11-common-ingress-pipeline-and-gate-evidence.md`。

Documentation impact rationale: 首次形成跨模块产品链路、phase machine report与 CI gate，必须同步端到端、双通道、错误、隔离、质量和追踪事实。

Change-impact matrix rows reviewed: `IMPACT-APPLICATION`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/002/003/009/011/012及列出的 NFR/ENG → TASK-P1-11 → TEST-P1-COMMON-INGRESS/TEST-SCENARIO-REPLAY/TEST-SNAPSHOT-REPLAY-001/TEST-PROBLEM-REPLAY-001/TEST-DATA-QUALITY-001 → machine report、CI artifact；明确无 Solver/production evidence。

Schema changes: none。

Migration: none；使用既有 staging/snapshot migrations，E2E test在隔离 test DB执行。

Error behavior: 任一 stage失败立即形成所属结构化报告并停止下游；route cycle/missing resource/unit error/missing duration exact code不被 application包装成 SYSTEM_ERROR；partial writes transactionally回滚。

Tests: `TEST-P1-COMMON-INGRESS`、`TEST-SCENARIO-REPLAY`、`TEST-SNAPSHOT-REPLAY-001`、`TEST-PROBLEM-REPLAY-001`、`TEST-DATA-QUALITY-001`、`TEST-SIM-ISOLATION`；两种 source parity、two-run hashes、四负例、partial failure/idempotency、provenance完整与 no-shortcut scan。

Benchmark impact: 报告可记录每 stage elapsed/entity counts但不是 Solver Benchmark或生产 SLA；OPEN-012保持 OPEN。

Simulation scenarios: `SIM-P1-INGRESS-001` 完整走正式链；Production target/DB交叉显式拒绝。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/integration backend/tests/property backend/tests/simulation backend/tests/golden backend/tests/validation`；`uv run python -m app.application.p1_gate_report --root . --scenario fixtures/synthetic/SIM-P1-INGRESS-001 --repeat 2 --report build/validation/TASK-P1-11-p1-pipeline.json`；`uv run pytest -q backend/tests/contract/test_p1_exit_rejections.py`；`uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P1-11-rule-contracts.json`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P1-11-simulation-contracts.json`；`uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P1-11-golden.json`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P1-11-validator-mutations.json`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P1-11-engineering.json`；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-11-common-ingress-pipeline-and-gate-evidence.md --check-diff --report build/traceability/TASK-P1-11-report.json`；`git diff --check`；`uv build`。

Artifacts: `p1-data-pipeline-report.v1`、pytest/migration/no-shortcut结果、CI uploaded artifact、traceability report。

Completion conditions: Adapter与Synthetic从 staging后调用同一实现链；same scenario+seed的 import/snapshot/problem bytes与hash均相同；四拒绝 exact；partial failure/isolation/idempotency通过；CI/full/diff/build PASS且无 Solver/P2。

Explicitly excluded: 产品 API/Worker调度、CpSatBackend/Solver/Validator、ScheduleVersion/Export、Production deployment/readiness、P2。

PROD_OPEN: OPEN-001～015 均不关闭；Reference/Synthetic E2E不是生产接口验收。

SIM_ASSUMPTIONS: 只使用 versioned/registered P1 Scenario assumptions，不向 Production policy传播。

Rollback: application orchestration可回退但不得绕过任何 stage；machine/CI失败历史保留，旧 Snapshot/Problem hash不重写。

## Completion evidence

执行时填写完整 chain versions/hashes、negative codes、DB/CI/provider层级、changed paths、命令结果和文档/追踪结论。
