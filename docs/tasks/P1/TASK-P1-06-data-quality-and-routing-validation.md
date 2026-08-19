---
doc_id: TASK-P1-06
title: Data Quality and Routing Validation
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [8, 18, 20, 22, 27, 73, 74, 91]
last_reviewed: 2026-08-19
---

# TASK-P1-06 — Data Quality and Routing Validation

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-05

Goal: 对 canonical Import v2 执行独立于 Solver 的结构、引用、DAG、resource option、duration、capability与时间区间校验，并以稳定、可排序的 ImportQualityReport 明确拒绝 P1 Gate 的四类错误。

Inputs: canonical Import v2、capability registry、constraint input语义、error model、P1 Gate rejection list。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `schemas/rules/error-code-registry.v2.yaml`、`schemas/json/error.v3.schema.json`、`schemas/json/import-quality-report.schema.json`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`backend/app/domain/contracts.py`、`backend/app/domain/errors.py`、`backend/app/data_validation/__init__.py`、`backend/app/data_validation/contracts.py`、`backend/app/data_validation/references.py`、`backend/app/data_validation/routing.py`、`backend/app/data_validation/capabilities.py`、`backend/app/data_validation/validator.py`、`backend/tests/unit/test_data_validation.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/contract/test_schema_contracts.py`、`pyproject.toml`、仅在 metadata/lock 确有变化时更新的 `uv.lock`、生成但不提交的 `build/traceability/TASK-P1-06-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: error-code-registry.v1/error.v1/v2、constraint formula/Validator evaluator、Adapter/Staging/Normalization语义、order expansion、Snapshot/Problem、Simulation、Solver、HTTP mapping。

Implementation steps: additive发布 error registry v2/error.v3/import-quality-report.v1并保留历史；实现 deterministic multi-error collector；DAG拓扑检查、所有 entity/reference/resource/capability/time/duration/option不变量；四个 Gate分别使用稳定 code `ROUTE_CYCLE`、`MISSING_RESOURCE`、`UNIT_CONVERSION_ERROR`、`MISSING_DURATION`；unsupported capability保持独立 category；报告顺序与 source location稳定。

Outputs: DataValidation contracts/evaluator、ImportQualityReport、四类 exact rejection evidence与版本化 error artifacts。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/core/capability-matrix.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/planning/constraint-catalog.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-06-data-quality-and-routing-validation.md`。

Documentation impact rationale: 新错误版本、数据质量报告和 DAG/reference/capability行为直接决定 P1 Gate及下游可接受输入。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/002/003/009、NFR-COR/DET/TRC、ENG-ERR/VER → TASK-P1-06 → TEST-DATA-QUALITY-001/TEST-INF-NO-RESOURCE/TEST-CAPABILITY-001 → exact reports/error artifacts；不写成 ScheduleValidator或Solver证据。

Schema changes: schema set additive release；新增 error-code-registry.v2、error.v3、import-quality-report.v1，保留 v1/v2 consumers并明确不互换。

Migration: 无数据库 migration；历史 Error/Report artifact不改写，新 consumer显式选择 v3/v1。

Error behavior: route cycle/missing resource/unit error/missing duration必须分别以 exact code和 DATA_ERROR拒绝；unsupported capability保持 `UNSUPPORTED_CAPABILITY`；错误包含 entity/field/observed/expected/source location/action，不统一为 SYSTEM_ERROR。

Tests: `TEST-DATA-QUALITY-001`、`TEST-INF-NO-RESOURCE`、`TEST-CAPABILITY-001`；正例、四个 Gate负例、orphan/duplicate/self-edge/cycle、invalid option/calendar/lag、multi-error ordering、Schema round-trip和 deterministic replay。

Benchmark impact: DAG/reference checks记录小型 synthetic规模诊断；不设 SLA，不实现 Solver/Benchmark。

Simulation scenarios: 负例由 canonical test builder生成，不覆盖 P0 fixture；unsupported scenario保持明确拒绝。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/domain backend/app/data_validation backend/tests/unit/test_data_validation.py backend/tests/contract`；`uv run pyright backend/app/domain backend/app/data_validation backend/tests/unit/test_data_validation.py backend/tests/contract`；`uv run pytest -q backend/tests/unit/test_data_validation.py backend/tests/contract/test_import_validation.py backend/tests/contract/test_schema_contracts.py backend/tests/contract/test_rule_contracts.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-06-data-quality-and-routing-validation.md --check-diff --report build/traceability/TASK-P1-06-report.json`；`git diff --check`；`uv build`。

Artifacts: error registry/schema、ImportQualityReport schema/sample、positive/negative reports、traceability report。

Completion conditions: 四个 Exit Gate错误exact code/category/source evidence全部通过；合法 canonical package零 error；报告 deterministic且历史 error artifacts保留；无 Solver/Validator同源逻辑；docs/trace/governance PASS。

Explicitly excluded: C-001～C-011 candidate schedule validation、infeasibility proof、HTTP status、order expansion、Snapshot/Problem、Solver。

PROD_OPEN: OPEN-002/004/007/009/013/014/015 保持 OPEN；校验输入事实而不决定生产值。

SIM_ASSUMPTIONS: 负例只属于测试，不新增生产规则或通用 Profile参数。

Rollback: consumer可显式回到旧 error version，但不得绕过新增 P1 input validation；发现语义错误时发布新 registry/report version。

## Completion evidence

执行时填写每个 error case、artifact version/hash、changed paths、测试结果、文档与边界审查。
