---
doc_id: TASK-P4-11
title: ChangeReport Read Model and Export Integration
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-11 — ChangeReport Read Model and Export Integration

Task batch role: phase-plan-member

Requirement IDs: REQ-006, REQ-007, REQ-008, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-06, TASK-P4-08

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-11另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 形成versioned ChangeReport/replan lineage只读模型，并把完整ChangeReport以deterministic、manifest-bound、internal Simulation方式纳入标准成果包。

Non-goals: 不自动publish/export、不外发MES/ERP/object storage、不创建API/UI、不改变approval authority或ExportJob state pair。

Inputs: P4 Replan result/ChangeReport、P3 read model与standard package/export job。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: domain/application read projections、planning reporting、exporter有界集成、unit/contract/integration/security tests、machine CI及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、Replan solver/orchestration、Simulator/scenarios、API/UI、external target、Production readiness、P5+

Implementation steps: 定义stable query/filter/lineage；验证base/new hashes与report completeness；扩展P4-approved export carrier consumer；canonical JSON/CSV/XLSX/manifest binding；replay/tamper/partial cleanup/default-deny。

Outputs: ChangeReport read model、P4 standard package integration与`p4-change-report-output-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/contracts/export-package.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/schedule-version.md`、`docs/architecture/provenance-and-versioning.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/traceability-matrix.md`、`docs/tasks/P4/TASK-P4-11-change-report-read-model-and-export-integration.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-REPORTING`、`IMPACT-EXPORT`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/008/009→ChangeReport read/export→TEST-CHANGE-REPORT-001、TEST-OUTPUT、TEST-EXPORT-JOB-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001→output report。

Contract impact: consumer-only；实现P4-02 ChangeReport/export carrier与P3 deterministic package/manifest合同，历史package profiles逐字冻结。

Schema changes: none；消费P4-02 approved export/ChangeReport versions，旧v1/v2 bytes冻结。

Migration: none；复用P3 ExportJob storage。

Dependency changes: none；XLSX/Frontend locks冻结。

ADR impact: none；遵循ADR-0012 publish/export separation和TASK-P4-01 accepted Freeze/Stability/ChangeReport ADR。

State-machine impact: 只执行既有ExportJob pair；ChangeReport读取不推进ScheduleVersion或ReplanRequest。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-CHANGE-REPORT-001、TEST-OUTPUT、TEST-EXPORT-JOB-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-SIM-ISOLATION。

Test IDs: TEST-CHANGE-REPORT-001, TEST-OUTPUT, TEST-EXPORT-JOB-001, TEST-IDEMPOTENCY, TEST-AUDIT-TRAIL-001

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 使用P4-10前可用fixed ChangeReport fixtures；连续场景由P4-14复核。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-11-change-report-read-model-and-export-integration.md --check-diff --report build/traceability/TASK-P4-11-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-change-report-output-report.v1`、deterministic package fingerprints、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: read/export lineage、完整性、determinism、tamper/failure/idempotency全PASS；仅internal Simulation；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: internal Simulation成果包不形成external publish/storage、真实approval authority、deployment、UAT或capacity/SLA。

P5 boundary: ChangeReport/export不得包含未实现P5 capability结果或占位成功payload。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 停用P4 output profile；保留P3 profiles和已生成artifact历史，不删除ExportJob/audit。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
