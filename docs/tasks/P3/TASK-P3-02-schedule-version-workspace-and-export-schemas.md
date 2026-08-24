---
doc_id: TASK-P3-02
title: ScheduleVersion Workspace and Export Schemas
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 35, 65, 66, 67, 69, 77, 78, 94]
last_reviewed: 2026-08-24
---

# TASK-P3-02 — ScheduleVersion Workspace and Export Schemas

Task batch role: phase-plan-member

Requirement IDs: REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-HUM-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-01

Start gate: TASK-P3-01=`done`且其accepted Workspace ADR、页面/API/permission矩阵由exact provider验证；用户明确授权；clean synchronized main；启动时记录immutable 40字符Diff base并冻结schema set `2.5.0`及P2 artifact fingerprints。

Goal: 发布ScheduleVersion、workspace query/command、comparison、audit event、publication result与ExportJob的严格版本化机器合同和synthetic samples，为持久化/API/Frontend提供单一Schema来源。

Non-goals: 不建表、不实现状态迁移/API/UI/Worker，不更改既有state pair，不产生可发布业务计划。

Inputs: TASK-P3-01合同/accepted Workspace ADR、PlanningSolution/Validation/KPI/ExportManifest、state-machines.v1、Error registry、ADR-0007/0009。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `schemas/json/schedule-version.schema.json`、`schemas/json/workspace-query.schema.json`、`schemas/json/workspace-command.schema.json`、`schemas/json/schedule-version-comparison.schema.json`、`schemas/json/audit-event.schema.json`、`schemas/json/publication-result.schema.json`、`schemas/json/export-job.schema.json`、对应`schemas/samples/*.synthetic.json`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`pyproject.toml`、`backend/app/domain/contracts.py`、`backend/app/domain/state_machines/contracts.py`、`backend/app/planning/contracts.py`、限定contract tests及`Documents to update`；激活前须把实际新增文件逐字固定。

Files forbidden to change: `backend/app/infrastructure/**`、`backend/app/application/**`、`backend/app/api/**`、`backend/app/jobs/**`、`backend/app/exporters/**`、`frontend/**`、migrations、Solver/Validator实现、`.github/workflows/**`（除非激活前扩卡批准machine contract step）、`uv.lock`、P2 Schema/sample历史bytes、P4 contracts/implementation。

Implementation steps: 版本/URN/strict registry设计；定义immutable IDs、状态、actor/reason/audit、idempotency/target、lineage/hash、synthetic conditional、query pagination与command envelope；发布positive/negative/round-trip/fingerprint tests；提升global schema set并保留旧文档版本。

Outputs: additive P3 schema release、samples/data dictionary、pure contracts/prechecks、schema contract report。

Documentation impact: required

Documents to update: `docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、三份state-machine文档、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/data-authority.md`、`docs/architecture/technology-stack.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance registry/trace/impact/inventory必审文档、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 新外部机器合同、global schema set、状态/错误/provenance/consumer兼容性同时变化。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-PLANNING-CONTRACTS`、`IMPACT-STATE`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/009→TASK-P3-02→TEST-CONTRACT-001/TEST-WORKSPACE-CONTRACT-001/TEST-STATE-TRANSITION-001→Schema fingerprints/report；只把合同slice标记formed。

Schema changes: required；additive global release，旧P2 document versions/bytes/URN不变；跨文档`$ref`、unknown-field/no-default、v1/non-interchangeability、canonical fingerprint必须测试。

Migration: none；Schema不等于DB，持久化留给TASK-P3-03。

Dependency changes: none expected；`pyproject.toml`只允许schema metadata，`uv.lock`必须零差异；如需新库停止并拆分/扩卡。

ADR impact: implement TASK-P3-01 accepted Workspace ADR；若字段导致state/publish语义改变，停止并提交new/superseding ADR后再继续。

State-machine impact: enum/pair集合必须与state-machines.v1完全一致；本Task只形成document carriers，不能将allowed pair写成已持久化行为。

Error behavior: strict contract/version/reference/data-plane/idempotency/actor字段错误在consumer副作用前拒绝；不映射INFEASIBLE，不泄漏raw actor credential。

Tests: TEST-CONTRACT-001、TEST-WORKSPACE-CONTRACT-001、TEST-STATE-TRANSITION-001、TEST-ERROR-MAPPING-001；覆盖Schema meta/round-trip/negative/compatibility/hash与Production/Synthetic conditional。

Benchmark impact: 只记录payload size/count；不形成UI、DB或Production性能阈值。

Simulation scenarios: synthetic samples只验证合同形状，不能替代Scenario/状态行为或Production authority。

Acceptance commands: `uv run pytest -q backend/tests/contract`；P3 schema contract machine CLI（在激活前固定模块/报告路径）；`uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；full/diff docs治理；`git diff --check`；按Diff base核验`uv.lock`及P2 Schema/sample零变化。

Artifacts: Schema/sample fingerprints、registry/round-trip report、Task report、provider artifact。

Provider evidence: exact implementation/closure SHA各自required `validate`和artifact；检查Task、schema report、Impact rows/checks/issues及所有`code_commit`一致。

Completion conditions: 所有P3机器合同严格、版本化、互引可离线解析；P2 bytes保留；非法组合fail closed；文档/追踪/provider闭环；无DB/API/UI/Worker行为。

Failure handling: 兼容、URN、状态或authority冲突即保留失败报告并停止TASK-P3-03；禁止放宽additionalProperties/required字段绕过。

Explicitly excluded: persistence/migration、ScheduleVersion行为、HTTP、Frontend、Export worker、外部publish、P4。

PROD_OPEN: OPEN-002/010/015保持OPEN；Schema表达显式来源/actor/target，不提供真实值或角色。

SIM_ASSUMPTIONS: samples显式synthetic；不新增定量assumption，必要时先登记。

Rollback: consumer采用前可回退additive release；一旦消费必须新版本/迁移，禁止覆盖已发布Schema或P2 bytes。
