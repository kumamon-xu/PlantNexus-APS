---
doc_id: TASK-P1-01
title: P1 Phase Governance and CI Handoff
status: ready
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [6, 58, 73, 74, 98, 99, 100, 101]
last_reviewed: 2026-08-19
---

# TASK-P1-01 — P1 Phase Governance and CI Handoff

Requirement IDs: REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-PER-001, ENG-ARCH-001, ENG-VER-001

Depends on: TASK-P0-10；用户于 2026-08-19 明确授权进入 P1

Goal: 将文档治理和 CI 从 P0-10 的一次性 handoff 收敛为可识别当前 Phase 与当前变更 Task 的 P1 基线，使后续 P1 Task 能在不改业务代码的情况下得到 full/diff governance 与 provider evidence。

Inputs: `docs/current_phase.md`、`docs/tasks/README.md`、`docs/quality/documentation-consistency-checks.md`、`.github/workflows/ci.yml`、P0 successful provider evidence。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA；当前 `ready` 状态不得预填移动引用

Files allowed to change: `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`、生成但不提交的 `build/traceability/TASK-P1-01-report.json` 与 `build/validation/TASK-P1-01-ci-contract.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: `backend/app/domain/**`、`backend/app/importers/**`、`backend/app/normalization/**`、`backend/app/data_validation/**`、`backend/app/snapshots/**`、`backend/app/planning/**`、`backend/app/simulation/**`、`schemas/**`、`fixtures/**`、`pyproject.toml`、`uv.lock`、任何 P1 数据实现、Solver 或 Production 配置。

Implementation steps: 固定 phase-aware Task policy（历史 Phase 只保留 terminal Task、未来 Phase 禁止详细卡）；让 Task range/changed-task discovery 不再硬编码 P0；CI 保留 full governance、全部 P0 回归、构建和 artifact upload，并对本次 P1 Task 执行 immutable diff check；integration/unit tests 覆盖 current/historical/future phase、短范围依赖和 stale P0 handoff 拒绝；任何 provider push/branch 变更须另有执行时授权。

Outputs: current-phase-aware governance validator、不会遗留 P0-10 task range 的 P1 CI contract、机器报告与更新后的治理说明。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/governance/document-control.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/operations/README.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md`。

Documentation impact rationale: 治理 validator、Task phase policy 与 CI provider gate 的行为和使用命令都会改变，必须同步 Agent、质量、追踪和阶段文档。

Change-impact matrix rows reviewed: `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-009/NFR-TRC-001/NFR-PER-001/ENG-ARCH-001/ENG-VER-001 → TASK-P1-01 → TEST-TRACEABILITY-VALIDATOR/TEST-PHASE-GOVERNANCE-001 → phase-aware report、workflow contract 与 provider artifact；不把治理 PASS 写成 P1 数据能力证据。

Schema changes: none。

Migration: none。

Error behavior: current phase 无效、未来 Phase Task、历史非 terminal Task、Task phase/path/ID 不一致、stale P0 command 或遗漏 diff gate均必须返回非零；不得自由文本 skip。

Tests: `TEST-TRACEABILITY-VALIDATOR`、`TEST-PHASE-GOVERNANCE-001`；覆盖 P0 terminal history + P1 current cards、P2 future rejection、跨 Phase 依赖、changed-task CI 和 artifact handoff。

Benchmark impact: 仅保留既有 conditional hook；无 Solver、无 BenchmarkReport、无性能承诺。

Simulation scenarios: 只重放既有 P0 Simulation/Golden/Mutation gates，不修改 Scenario 或 Fixture。

Acceptance commands: `uv sync --locked`；`uv run ruff check scripts/check_docs.py backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run pyright scripts/check_docs.py backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md --check-diff --report build/traceability/TASK-P1-01-report.json`；`git diff --check`；`uv build`。

Artifacts: `traceability-report.v1`、CI contract test result、workflow evidence artifact；provider run ID/URL 仅在实际执行并授权后记录。

Completion conditions: phase-aware unit/integration negative paths全部通过；CI 不再引用 P0-10 immutable range且不削弱既有 gates；本 Task 提交前后 diff governance均 PASS；真实 provider 结果如未获授权必须记为 `NOT_RUN` 而非 PASS；没有业务代码变更。

Explicitly excluded: P1 Schema/Adapter/Staging/Normalization/Snapshot/Problem/Generator 实现、CI gate 弱化、P2、OR-Tools、Production deployment。

PROD_OPEN: OPEN-001～015 均不关闭；CI/provider 信息不是生产业务权威。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～009 不新增、不修改、不用于生产结论。

Rollback: 恢复到最后一个能识别当前 Phase 且通过 full/diff governance 的版本；不得恢复 stale P0 task handoff，provider 历史不得删除。

## Completion evidence

执行时填写真实 changed paths、Diff base/HEAD、测试/报告/provider 结果和文档影响；当前不得预填 PASS。
