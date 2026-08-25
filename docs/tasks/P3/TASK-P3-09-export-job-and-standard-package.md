---
doc_id: TASK-P3-09
title: ExportJob and Standard Export Package
status: in_progress
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [34, 65, 66, 67, 77, 78, 94]
last_reviewed: 2026-08-25
---

# TASK-P3-09 — ExportJob and Standard Export Package

Task batch role: phase-plan-member

Requirement IDs: REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-03, TASK-P3-04, TASK-P3-08

Start gate: 依赖均`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；P2 internal package fingerprints冻结，P3 package/status/target合同已形成。

Goal: 实现durable ExportJob CREATED→EXPORTING→EXPORTED/FAILED/CANCELLED/retry，生成绑定ScheduleVersion/validation/approval/publication/audit的标准JSON/CSV/XLSX成果包，确保manifest-last、幂等、重试与Publish副作用分离。

Non-goals: 不向真实MES/ERP传输，不把Export成功当Publish，不形成Production adapter/Runbook，不修改schedule，不实现HTTP/UI。

Inputs: P2 package/KPI/SolverReport、P3 ScheduleVersion/ExportJob contracts/repositories、generic Job primitives、ADR-0002/0007/0009及TASK-P3-01 accepted Workspace ADR。

Diff base: b9c0b1694448a4ec348b0b02107926f6213560c9

Files allowed to change: `.github/workflows/ci.yml`、`pyproject.toml`、`schemas/data_dictionary.yaml`、`schemas/json/export-manifest.v2.schema.json`、`schemas/json/export-job.v2.schema.json`、`schemas/samples/export-manifest.v2.synthetic.json`、`schemas/samples/export-job.v2.synthetic.json`、`backend/app/__init__.py`、`backend/app/domain/__init__.py`、`backend/app/domain/workspace_contracts.py`、`backend/app/domain/workspace_contract_check.py`、`backend/app/domain/workspace.py`、`backend/app/domain/export_job.py`、`backend/app/application/__init__.py`、`backend/app/application/export_jobs.py`、`backend/app/application/export_job_check.py`、`backend/app/infrastructure/workspace_persistence.py`、`backend/app/infrastructure/export_job_repository.py`、`backend/app/exporters/__init__.py`、`backend/app/exporters/standard_package.py`、`backend/app/jobs/__init__.py`、`backend/app/jobs/export_job.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/contract/test_rule_contracts.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`backend/tests/contract/test_p3_workspace_contracts.py`、`backend/tests/contract/test_p3_export_contracts.py`、`backend/tests/unit/test_standard_export_package.py`、`backend/tests/integration/test_export_jobs.py`、`backend/tests/security/test_export_authorization.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`逐字列出的文档；这是用户批准Schema缺口扩卡后、任何Schema或业务代码修改前冻结的精确allow-list。全仓首轮581 PASS/12同源失败后，新增的两个路径仅允许把既有v1 query builder与P3-02冻结测试显式绑定`WORKSPACE_V1_SCHEMA_SET_VERSION=2.6.0`。既有四个metadata contract与P3-02冻结检查只允许更新current set认知；历史document const、Schema/sample bytes与报告任务语义禁止改写。

Files forbidden to change: external adapter/network、migration、dependency pins/`uv.lock`（复用locked openpyxl）、既有Schema/sample bytes（尤其`export-manifest.v1`/`export-job.v1`）、publication state service、Solver/Validator/P2 package历史bytes、API/Frontend、P4。

Implementation steps: request hash/target/allowed state precheck；claim/lease/heartbeat/attempt/retry/cancel；标准payload+XLSX生成；hash/count/lineage/audit；atomic storage/manifest-last；exact replay/conflict/partial cleanup/crash recovery；确保无publish call。

Outputs: business ExportJob worker boundary、standard package、machine report。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P3-planning-workspace.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-09-export-job-and-standard-package.md`、`docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/export-package.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/planning-workspace-api.md`、`docs/domain/domain-model.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/error-model.md`、`docs/core/glossary.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/benchmark-regression.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`。

Documentation impact rationale: 首次业务ExportJob、标准包/XLSX、retry/storage/audit与Publish分离需要合同、状态、运维和追踪闭环。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-EXPORT`、`IMPACT-JOBS`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/009→TASK-P3-09→TEST-EXPORT-JOB-001/TEST-OUTPUT/TEST-IDEMPOTENCY/TEST-AUDIT-TRAIL-001→package/job report。

Schema changes: 用户批准处理启动审查发现的机器合同缺口。Global set从`2.6.0` additive提升为`2.7.0`，新增非互换`export-manifest.v2`与`export-job.v2`；v2 manifest固定P3标准JSON/CSV/XLSX、ScheduleVersion/publication/ExportJob/audit lineage与deferred P4边界，v2 Job只引用v2 manifest。`export-manifest.v1`、`export-job.v1`及全部P2/P3-02历史Schema/sample/URN/bytes逐字保留，consumer显式选择版本，禁止alias/`latest`/私有字段漂移。

Migration: none；消费P3-03 ExportJob repository。

Dependency changes: none；复用locked `openpyxl==3.1.5`，runtime/dev pins及`uv.lock`必须零差异。`pyproject.toml`只允许schema-set metadata从`2.6.0`更新为`2.7.0`；依赖行仍强制review。

ADR impact: implement ADR-0002/0007/0009及TASK-P3-01 accepted Workspace ADR；外部storage/MES adapter/topology新决定必须另建ADR。

State-machine impact: 实现ExportJob既有pairs；EXPORTED/CANCELLED终态，FAILED仅显式retry；任何Job状态不得改变ScheduleVersion publication。

Error behavior: invalid state/target/plane、stale/tamper、idempotency conflict、I/O/crash/cancel生成稳定错误；部分包不暴露成功manifest；retry不double publish。

Tests: TEST-EXPORT-JOB-001、TEST-OUTPUT、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-SIM-ISOLATION；JSON/CSV/XLSX、hash/count/lineage、lease/retry/cancel/crash/partial cleanup/no-publish。

Benchmark impact: 记录包bytes/rows/generation/memory用于development，OPEN-012仍OPEN。

Simulation scenarios: 使用P2/P3 synthetic ScheduleVersion；包显式synthetic/非Production target。

Acceptance commands: 定向contract/integration/job tests与export CLI；full tests/Ruff/Pyright/locked sync；full/diff docs治理；`git diff --check`；P2 package/dependency/external network禁止diff。

Artifacts: 标准包、manifest fingerprints、ExportJob/retry/audit report、Task/provider evidence。

Provider evidence: exact implementation/closure required validate/artifact；下载检查package/job report、Task exact SHA/Impact/checks/issues、artifact expiry/digest。

Completion conditions: 所有必需文件/manifest原子、JSON/CSV/XLSX可验证、ExportJob幂等可重试、无double publish、失败不暴露部分成功；provider/docs闭环；无外部Production adapter。

Failure handling: 任何文件/manifest/storage/job失败保持FAILED/CANCELLED并可审计重试，不手工标EXPORTED；停止API/UI后继。

Explicitly excluded: MES/ERP adapter、Production file transfer、publish state变更、HTTP/Frontend、P4 ChangeReport。

PROD_OPEN: OPEN-002/010/012/015保持OPEN；standard package不定义真实接口/角色/SLA/字段authority。

SIM_ASSUMPTIONS: 复用既有synthetic facts；包规模值不外推Production。

Rollback: 终态job/artifact/audit不删除；代码回退保持可下载历史包和manifest，新格式使用新version。

## Local implementation evidence

Implementation candidate已形成2份新Schema/2份sample、12 payload（manifest另计）与4-sheet安全XLSX、durable lifecycle/audit/worker和required `export_job_check`。全仓首轮为581 PASS/12同源v1-builder常量失败，已通过显式`WORKSPACE_V1_SCHEMA_SET_VERSION=2.6.0`修正且12项定向复验PASS。最终focused 16、full 594、Ruff、全量Pyright、locked sync、27份machine reports、P2 Gate 11/11、XS benchmark 8/8、Compose、build、full/diff docs治理、`git diff --check`及冻结/禁止范围全部PASS；machine=`p3-export-job-report.v1`、8/8、`issues=[]`。Exact implementation provider未完成前Task保持`in_progress`。
