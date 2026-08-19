---
doc_id: TASK-P1-08
title: Immutable PlanningSnapshot and Hash
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [23, 40, 62, 73, 74, 101, 103]
last_reviewed: 2026-08-19
---

# TASK-P1-08 — Immutable PlanningSnapshot and Hash

Requirement IDs: REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, ENG-SOL-001, ENG-VER-001

Depends on: TASK-P1-03, TASK-P1-06, TASK-P1-07

Goal: 从已验证、已展开的 canonical facts 构建 immutable PlanningSnapshot v2，定义 canonical hash projection和 deterministic snapshot ID，并用持久化约束证明已创建 Snapshot 不可就地修改。

Inputs: PlanningSnapshot v2 Schema、canonical package/quality report/expanded operations、ADR-0007/0009、provenance rules。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `backend/app/snapshots/__init__.py`、`backend/app/snapshots/contracts.py`、`backend/app/snapshots/canonical.py`、`backend/app/snapshots/builder.py`、`backend/app/snapshots/repository.py`、`backend/app/infrastructure/snapshot_repository.py`、`backend/migrations/versions/0003_planning_snapshots.py`、`backend/tests/unit/test_snapshot_builder.py`、`backend/tests/property/test_snapshot_properties.py`、`backend/tests/integration/test_snapshot_repository.py`、`backend/tests/integration/test_migrations_and_infrastructure.py`、生成但不提交的 `build/traceability/TASK-P1-08-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: Snapshot v1/v2 Schema、Import/Adapter/Normalization/DataValidation/Expansion语义、PlanningProblem/Solver、Simulation Generator、API、ScheduleVersion/Export。

Implementation steps: canonicalize所有 Snapshot事实和 source/rule/schema/expansion versions；hash排除 self hash、随机 UUID、received/generated timestamps等噪声但包含 cutoff和业务事实；snapshot_id由 versioned digest派生；builder要求 quality PASS；repository content-addressed insert-only并拒绝 hash/content冲突或 update/delete；synthetic Snapshot必须保留 scenario/profile/generator/seed，Production不得引用 synthetic source；reversible migration与 replay/property tests。

Outputs: Snapshot builder/hash/repository、immutable migration与 deterministic replay artifacts。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/import-and-normalization.md`、`docs/domain/domain-model.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/data-authority.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-08-immutable-snapshot-and-hash.md`。

Documentation impact rationale: Snapshot hash projection、ID、immutability、persistence与 synthetic provenance 是 P1 Gate和后续所有 run的核心合同。

Change-impact matrix rows reviewed: `IMPACT-SNAPSHOT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/009、NFR-DET/TRC/ISO/REL、ENG-SOL/VER → TASK-P1-08 → TEST-SNAPSHOT-REPLAY-001/TEST-SIM-ISOLATION → hash vectors、property/repository/migration evidence。

Schema changes: none；实现已发布 planning-snapshot.v2，发现语义不足须停止并走 Schema version Task。

Migration: 新增 `0003_planning_snapshots` insert-only storage；空库/含 Snapshot upgrade-downgrade测试并记录 downgrade数据损失边界。

Error behavior: quality非 PASS、provenance缺失、hash/content冲突、mutation/update/delete、synthetic/production混用、invalid cutoff明确失败；同内容 replay返回同 identity而非复制可变记录。

Tests: `TEST-SNAPSHOT-REPLAY-001`、`TEST-SIM-ISOLATION`；hash vectors、key/order/noise变化、cutoff/rule/version变化、round-trip、immutability、repository conflict、migration与 property shrinking。

Benchmark impact: 记录 synthetic entity counts/hash/build time作为诊断；不设生产阈值、不运行 Solver。

Simulation scenarios: synthetic Snapshot保留完整 provenance；Production isolation负例必测，未建立独立 Production deployment声明。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/snapshots backend/app/infrastructure/snapshot_repository.py backend/tests/unit/test_snapshot_builder.py backend/tests/property/test_snapshot_properties.py backend/tests/integration`；`uv run pyright backend/app/snapshots backend/app/infrastructure/snapshot_repository.py backend/tests/unit/test_snapshot_builder.py backend/tests/property/test_snapshot_properties.py backend/tests/integration`；`uv run pytest -q backend/tests/unit/test_snapshot_builder.py backend/tests/property/test_snapshot_properties.py backend/tests/integration/test_snapshot_repository.py backend/tests/integration/test_migrations_and_infrastructure.py`（该 integration suite必须实际执行空库及含 Snapshot 的 upgrade/downgrade）；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-08-immutable-snapshot-and-hash.md --check-diff --report build/traceability/TASK-P1-08-report.json`；`git diff --check`；`uv build`。

Artifacts: canonical hash vectors、Snapshot/repository/migration tests、traceability report。

Completion conditions: same canonical facts/cutoff/versions得到同 snapshot bytes/hash/id；任何事实/version变化改变 hash；insert-only与 isolation负例通过；migration、docs、traceability和提交前后 governance PASS。

Explicitly excluded: PlanningProblem/Solver、mutable Snapshot correction、ScheduleVersion、API、Production release或关闭数据权威 OPEN。

PROD_OPEN: OPEN-001/002/004/007/009/015 保持 OPEN；Snapshot只固化已提供事实，不补猜。

SIM_ASSUMPTIONS: synthetic provenance引用已登记 assumptions；不得把 snapshot内容作为生产校准。

Rollback: 不改写既有 Snapshot；代码回滚保留 content-addressed记录，migration downgrade前必须确认仅开发/测试且记录数据影响。

## Completion evidence

执行时填写 hash contract/version/vectors、migration、changed paths、命令/退出码、文档与追踪结论。
