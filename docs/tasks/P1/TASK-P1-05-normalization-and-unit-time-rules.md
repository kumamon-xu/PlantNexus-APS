---
doc_id: TASK-P1-05
title: Normalization and Unit Time Rules
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [15, 16, 20, 22, 73, 74, 90, 103]
last_reviewed: 2026-08-19
---

# TASK-P1-05 — Normalization and Unit/Time Rules

Requirement IDs: REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02, TASK-P1-03, TASK-P1-04

Goal: 将 staged source rows 通过显式、版本化规则确定性转换为 canonical Import v2，统一 ID、UTC、整数秒与稳定排序；未知或缺失单位/时区/字段必须拒绝，绝不使用生产默认值。

Inputs: canonical schemas/data dictionary、ReferenceFileAdapter staged rows、ADR-0008、OPEN-001/013/015。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `schemas/rules/unit-conversion-registry.v1.yaml`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`backend/app/normalization/__init__.py`、`backend/app/normalization/contracts.py`、`backend/app/normalization/ids.py`、`backend/app/normalization/time.py`、`backend/app/normalization/units.py`、`backend/app/normalization/normalizer.py`、`backend/tests/unit/test_normalization.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`pyproject.toml`、仅在 metadata/lock 确有变化时更新的 `uv.lock`、生成但不提交的 `build/traceability/TASK-P1-05-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: source Adapter/Raw Staging migration、data validation/order expansion、Snapshot/Problem、Simulation、API、Solver、任何隐式 Production mapping/default。

Implementation steps: 发布 unit-conversion-registry.v1与 compatibility规则；显式 mapping profile将 source field映射为 canonical field，来源冲突拒绝；timestamp必须携带 offset并转 UTC Z，duration/unit以整数算术转秒且拒绝浮点歧义；canonical ID与collection/record排序稳定；生成 canonical Import v2 source/rule provenance与 bytes，但本 Task不做跨实体业务校验。

Outputs: versioned normalization rules、pure normalization modules、canonical Import v2 producer与 unit/contract evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/governance/prod-open-register.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/documentation-consistency-checks.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-05-normalization-and-unit-time-rules.md`。

Documentation impact rationale: unit/time/ID转换与 canonical serialization 是 P1 correctness/hash 语义，且直接受生产开放问题和 Schema versioning约束。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/009、NFR-DET/TRC、ENG-ERR/VER → TASK-P1-05 → TEST-NORMALIZATION-001/TEST-CONTRACT-001 → unit registry、canonical bytes与 tests。

Schema changes: schema set additive release，新增 unit-conversion-registry.v1；不改写 import-package.v2/canonical-records.v1；规则语义变化须发布新 registry version并回放 hashes。

Migration: 无数据库迁移；旧 staged rows必须显式选择 mapping/unit rule version，禁止按“latest”静默重解释。

Error behavior: unknown/missing/ambiguous unit、overflow/non-integral second、missing/naive/invalid timezone、duplicate canonical ID、conflicting authority和 unmapped required field明确返回 DATA_ERROR及 source location。

Tests: `TEST-NORMALIZATION-001`、`TEST-CONTRACT-001`；秒/分/时显式转换、UTC offset/DST边界、ID稳定性、排序/round-trip、unit error/missing duration、mapping version变化、same staged input replay。

Benchmark impact: 只采集测试数据 normalization records/sec作为非门禁诊断；不设生产阈值、不运行 Solver benchmark。

Simulation scenarios: 使用 explicit synthetic source values验证同入口；Simulation Config不得注入 Production default。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/normalization backend/tests/unit/test_normalization.py backend/tests/contract/test_unit_conversion_registry.py`；`uv run pyright backend/app/normalization backend/tests/unit/test_normalization.py backend/tests/contract/test_unit_conversion_registry.py`；`uv run pytest -q backend/tests/unit/test_normalization.py backend/tests/contract/test_unit_conversion_registry.py backend/tests/contract/test_schema_contracts.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-05-normalization-and-unit-time-rules.md --check-diff --report build/traceability/TASK-P1-05-report.json`；`git diff --check`；`uv build`。

Artifacts: unit registry、canonical Import samples/replay result、traceability report。

Completion conditions: 同 staged input + mapping/unit rule version产生 byte-identical canonical Import；unit error与 missing duration exact rejection通过；无隐式 default/float rounding；versions/docs/traceability与提交前后 governance均 PASS。

Explicitly excluded: 生产 unit policy closure、跨实体 DAG/reference validation、order expansion、Snapshot/Problem、API、Solver。

PROD_OPEN: OPEN-001/002/013/015 保持 OPEN；只实现显式规则，不批准默认单位或字段权威。

SIM_ASSUMPTIONS: synthetic sample单位/时区必须显式且只属于测试资产。

Rollback: 保留旧 rule version与 hash evidence；consumer回退时显式选择旧版本，禁止覆盖或重解释历史 canonical package。

## Completion evidence

执行时填写 registry/schema set版本、hash before/after、正反测试、changed paths、文档和治理结果。
