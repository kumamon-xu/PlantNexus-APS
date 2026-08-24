---
doc_id: TASK-P3-09
title: ExportJob and Standard Export Package
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [34, 65, 66, 67, 77, 78, 94]
last_reviewed: 2026-08-24
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

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/exporters/standard_package.py`、有界扩展`backend/app/exporters/package.py`、`backend/app/jobs/export_job.py`、相关`__init__.py`、限定unit/contract/integration/job tests、machine CLI及`Documents to update`；实际路径激活前固定。

Files forbidden to change: external adapter/network、Schema/migration/dependency（预计复用locked openpyxl）、publication state service、Solver/Validator/P2 package历史bytes、API/Frontend、P4。

Implementation steps: request hash/target/allowed state precheck；claim/lease/heartbeat/attempt/retry/cancel；标准payload+XLSX生成；hash/count/lineage/audit；atomic storage/manifest-last；exact replay/conflict/partial cleanup/crash recovery；确保无publish call。

Outputs: business ExportJob worker boundary、standard package、machine report。

Documentation impact: required

Documents to update: `docs/contracts/export-package.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/error-model.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/OPEN/risk/impact/inventory必审文档、本Task卡。

Documentation impact rationale: 首次业务ExportJob、标准包/XLSX、retry/storage/audit与Publish分离需要合同、状态、运维和追踪闭环。

Change-impact matrix rows reviewed: `IMPACT-EXPORT`、`IMPACT-JOBS`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/009→TASK-P3-09→TEST-EXPORT-JOB-001/TEST-OUTPUT/TEST-IDEMPOTENCY/TEST-AUDIT-TRAIL-001→package/job report。

Schema changes: none expected；消费P3-02与P2 output Schema；缺口须先版本化Schema，禁止私有字段漂移。

Migration: none；消费P3-03 ExportJob repository。

Dependency changes: none expected；复用locked openpyxl；若XLSX要求新库必须先dependency review/lock/ADR判断并扩卡。

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
