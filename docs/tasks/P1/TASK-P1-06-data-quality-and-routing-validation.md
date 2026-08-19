---
doc_id: TASK-P1-06
title: Data Quality and Routing Validation
status: in_progress
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

Diff base: 75d761332204ec779477ba7242c98517cce1b68b

Files allowed to change: `schemas/rules/error-code-registry.v2.yaml`、`schemas/json/error.v3.schema.json`、`schemas/json/import-quality-report.schema.json`、`schemas/samples/import-quality-report.v1.pass.json`、`schemas/samples/import-quality-report.v1.fail.json`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`backend/app/domain/contracts.py`、`backend/app/domain/errors.py`、`backend/app/data_validation/__init__.py`、`backend/app/data_validation/contracts.py`、`backend/app/data_validation/references.py`、`backend/app/data_validation/routing.py`、`backend/app/data_validation/capabilities.py`、`backend/app/data_validation/validator.py`、`backend/tests/unit/test_data_validation.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_rule_contracts.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`pyproject.toml`、仅在 metadata/lock 确有变化时更新的 `uv.lock`、生成但不提交的 `build/traceability/TASK-P1-06-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: error-code-registry.v1/error.v1/v2、constraint formula/Validator evaluator、Adapter/Staging/Normalization语义、order expansion、Snapshot/Problem、Simulation、Solver、HTTP mapping。

Implementation steps: additive发布 error registry v2/error.v3/import-quality-report.v1并保留历史；实现 deterministic multi-error collector；DAG拓扑检查、所有 entity/reference/resource/capability/time/duration/option不变量；四个 Gate分别使用稳定 code `ROUTE_CYCLE`、`MISSING_RESOURCE`、`UNIT_CONVERSION_ERROR`、`MISSING_DURATION`；unsupported capability保持独立 category；报告顺序与 source location稳定。

Outputs: DataValidation contracts/evaluator、ImportQualityReport、四类 exact rejection evidence与版本化 error artifacts。

Documentation impact: required

Documents to update: `README.md`、`docs/current_phase.md`、`docs/contracts/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/core/glossary.md`、`docs/core/capability-matrix.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/technology-stack.md`、`docs/planning/constraint-catalog.md`、`docs/planning/schedule-validator.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-06-data-quality-and-routing-validation.md`。

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

Activation evidence（2026-08-19）：唯一依赖TASK-P1-05=`done`；启动时working tree干净且HEAD/origin/main均为`75d761332204ec779477ba7242c98517cce1b68b`，受保护`main`的该精确SHA对应GitHub Actions run `32253025753`、required `validate` job `96068205493`=`success`。启动前完整重读AGENTS、P1 Milestone、技术总规、canonical/error/capability/constraint合同、ADR-0001/0003/0005/0008/0009、相关代码/测试和治理矩阵；未发现P0/P1-05前提差异。

启动前scope review发现global schema set升版会影响既有`test_rule_contracts.py`与`test_unit_conversion_registry.py`断言，且原卡遗漏若干`IMPACT-DOMAIN/DEPENDENCY/VERSION-METADATA/PHASE/GOVERNANCE-REGISTRY`强制文档；同时Artifacts要求的ImportQualityReport pass/fail sample没有路径。上述路径已在任何P1-06业务实现前加入允许范围。不可变基线SHA-256：canonical-records.v1=`fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e`、import-package.v2=`166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56`、`error.schema.json`（Error v1）=`fcf00d95ee746814ca1b1c20d0f23c08a10e003184f0614811dec4ce8da1b53c`、error.v2=`8b6c3ff4f2eef937b5444d43e4c8da8fe63ff398302e50ce2346244745a8ff29`、error-code-registry.v1=`2b059bbfa19cf239875cf40009b8eb91dcef8d2649fa680bf1efd1af1e2d991c`、unit-conversion-registry.v1=`faa20954bcfa8d61ad1f8609f05d89baf38af278b2ba1b7890f50455c9e0e8d2`。本段仅激活并固化范围，尚未实现DataValidation，也未启动TASK-P1-07/P2。

Local implementation evidence（2026-08-19）：schema set以additive `2.2.0`发布error registry v2、Error v3与ImportQualityReport v1；Import v2 document version仍为`2.0.0`，unit registry v1仍为`2.1.0`，`pyproject.toml`未增加dependency且`uv.lock` SHA-256仍为`9f13637a7ec8f15fca91bfe9d93353327a8b3ddf01eb3238567093193132a093`。PASS sample report ID=`import-quality-fbea002cbfe06460f3006e10ddfcc0ed9ab0436e896f7a1734557c14ef550da5`、status=`PASS`、error_count=`0`；FAIL sample report ID=`import-quality-2e957d46dcd4746a63058d2e616d800dc6e7cf579b58d3a918ecca341f135d6e`、status=`FAIL`、error_count=`7`，其中包含exact `ROUTE_CYCLE/MISSING_RESOURCE/UNIT_CONVERSION_ERROR/MISSING_DURATION`且均为`DATA_ERROR`。新registry/Error/report/pass/fail artifacts SHA-256依次为`4c868280a1a13d2b244c131127d7447c7dd672d743982ce4a0d340b12c62698b`、`32d6d3cd5db97f8359701f86d1b753071e691ead7e519b2072e6cf155d5222a5`、`2d41fb0afadbc0e73ba6bad60a52dcbfb34ef2e5e9602e1e1612ccc8c540f434`、`7ce681bac45b5a51bbfcef4e27e8bfce8040beeaa3eed0c6735b1428a9505711`、`cdcc08ffcb8d53daedd4deddbe1411692ffcf0a5a7980c37ad25bfc5577e03e8`。

Local acceptance（2026-08-19）：`uv sync --locked`、Task/full Ruff、Task/full Pyright、`git diff --check`和`uv build`全部exit 0；Task-focused pytest=`50 passed`，full repository pytest=`210 passed`。Full docs治理=`PASS`（124 docs、30 roots、30 trace rows、36 tests、15 open、9 sim、10 risks、22 tasks）；Task diff治理=`PASS`（63 changed paths、9 matched impact rows、0 issues），报告为ignored `build/traceability/TASK-P1-06-report.json`。实现未导入或修改Planning/ScheduleValidator/Solver，也未实施Order Expansion、Snapshot/Problem、TASK-P1-07或P2。Task仍保持`in_progress`，等待immutable implementation commit和真实GitHub provider证据后才能关闭。
