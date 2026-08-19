---
doc_id: TASK-P1-02
title: Canonical Import Contracts
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [15, 16, 17, 18, 19, 20, 23, 73, 74, 91, 103]
last_reviewed: 2026-08-19
---

# TASK-P1-02 — Canonical Import Contracts

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-01

Goal: 在不猜 ERP/MES/WMS/CAM 字段映射的前提下，发布严格、版本化的 APS canonical record、Standard Import v2 和 PlanningSnapshot v2 机器合同，为后续 staging、normalization、expansion 与 hash builder 提供唯一数据语义。

Inputs: `docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/domain/domain-model.md`、`docs/architecture/data-authority.md`、ADR-0007/0008/0009、现有 schema set `1.2.0`。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `schemas/json/canonical-records.v1.schema.json`、`schemas/json/import-package.v2.schema.json`、`schemas/json/planning-snapshot.v2.schema.json`、`schemas/samples/import-package.v2.synthetic.json`、`schemas/samples/planning-snapshot.v2.synthetic.json`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`backend/app/domain/__init__.py`、`backend/app/domain/contracts.py`、`backend/app/domain/canonical_records.py`、`backend/tests/contract/test_schema_contracts.py`、`pyproject.toml`、仅在 metadata/lock 确有变化时更新的 `uv.lock`、生成但不提交的 `build/traceability/TASK-P1-02-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: `schemas/json/import-package.schema.json`、`schemas/json/planning-snapshot.schema.json`、其他已发布 v1/v2 artifact、数据库/migrations、Adapter、staging、normalization、data validation、Snapshot/Problem builder、Simulation generator、API、Solver。

Implementation steps: 定义 Factory/Workshop/Line/Resource/Calendar、Product/Routing/Operation/Precedence/ResourceOption、Demand/ProductionOrder/Lot、execution facts/locks 的 canonical collections与稳定引用；必需时间显式 offset并规范目标 UTC、duration/unit/source version字段无默认值；新增 v2 envelope 与 v2 Snapshot payload/provenance，保留 v1 artifact；发布 schema set major compatibility说明、positive/negative/round-trip samples和 pure JSON-compatible types。

Outputs: canonical-records.v1、import-package.v2、planning-snapshot.v2、data dictionary、pure types 与 contract evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/core/glossary.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/adr/README.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-02-canonical-import-contracts.md`。

Documentation impact rationale: 新 canonical 字段、document version、schema set compatibility 与 Snapshot payload 会成为所有 P1 producer/consumer 的合同基线。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/002/003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-02 → TEST-CONTRACT-001 → v2 Schemas/data dictionary/pure types；实现类证据继续标记 `PLANNED`。

Schema changes: set-level major release；保留所有 `1.2.0` artifact，新增 canonical-records.v1、import-package.v2、planning-snapshot.v2；明确 backward/forward incompatibility与拒绝旧 consumer规则。

Migration: 无数据库 consumer；v1 fixture/history 保留只读，后续 Adapter 必须显式产出 v2，禁止 alias 或覆盖 v1。

Error behavior: 缺少必需 ID/source/version/unit/duration、未知字段、非法 synthetic provenance、非法 UTC/引用形状在 Schema/pure precheck 层明确拒绝；不补默认值。

Tests: `TEST-CONTRACT-001`；Draft 2020-12 meta、positive/negative、v1/v2 isolation、unknown/default、reference shape、UTC/unit/duration、Production/Synthetic 条件、round-trip 和 dictionary coverage。

Benchmark impact: 尚无 Solver；contract/hash 语义变化登记为 P1 replay 输入，不生成性能结论。

Simulation scenarios: samples 必须 synthetic；不修改或冒充正式 `SIM-MINIMAL-001`，不创建分布 Generator。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/domain backend/tests/contract`；`uv run pyright backend/app/domain backend/tests/contract`；`uv run pytest -q backend/tests/unit backend/tests/contract`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-02-canonical-import-contracts.md --check-diff --report build/traceability/TASK-P1-02-report.json`；`git diff --check`；`uv build`。

Artifacts: versioned Schemas、data dictionary、synthetic samples、contract-test result、traceability report。

Completion conditions: v1 artifacts逐字保留；v2 canonical collections满足领域/权威边界且无隐式生产默认值；Schema set/version metadata一致；正反/round-trip tests与提交前后治理均 PASS；Adapter/pipeline仍未实现。

Explicitly excluded: 真实源字段 mapping、Production Adapter、staging/normalization/validation/expansion/builder、API、ORM、Solver、关闭 OPEN-002/013/015。

PROD_OPEN: OPEN-001/002/003/004/007/008/009/013/014/015 均只引用不关闭。

SIM_ASSUMPTIONS: 只使用已登记 synthetic sample 边界；不得把 sample 数值提升为 Profile 或生产事实。

Rollback: 已发布 v2 不原地覆盖；失败时停止 consumer 开发并保留 v1，可发布修正版新版本而非改写历史。

## Completion evidence

执行时填写真实版本、兼容分类、changed paths、测试结果、hash/replay 边界和文档审查。
