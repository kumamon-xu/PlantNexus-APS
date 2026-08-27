---
doc_id: TASK-P4-12
title: Dynamic Replanning HTTP API
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-12 — Dynamic Replanning HTTP API

Task batch role: phase-plan-member

Requirement IDs: REQ-006, REQ-007, REQ-008, REQ-009, REQ-013

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P4-02, TASK-P4-03, TASK-P4-04, TASK-P4-08, TASK-P4-11

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-12另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 通过thin、server-authoritative HTTP/OpenAPI暴露ExecutionEvent append/query、ReplanRequest create/cancel/retry/query/result与ChangeReport read，严格绑定idempotency、correlation、plane/capability/state。

Non-goals: 不在router重算事实/Validator/OBJ-002、不提供Simulator控制或external publish、不选择真实Production identity。

Inputs: P4 machine contracts/application/read models与P3 API composition/auth/error baseline。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `backend/app/api/**`、composition ports、限定contract/integration/security tests、OpenAPI/machine CI及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、domain/application semantics、Solver/Simulator、Frontend、external adapter/deployment、P5+

Implementation steps: 冻结operation IDs/payload/header/status；pre-lookup authorization/default-deny；thin delegation；same-key replay/conflict/unknown outcome；sanitized error/correlation/OpenAPI fingerprint；Production flag negative。

Outputs: versioned P4 HTTP surface与`p4-replanning-api-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/contracts/planning-workspace-api.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/authorization-and-audit.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/governance/prod-open-register.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md`、`docs/tasks/P4/TASK-P4-12-dynamic-replanning-http-api.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-API`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/008/009/013→P4 API→TEST-REPLAN-API-001、TEST-REPLAN、TEST-EXECUTION-EVENT-CONTRACT-001、TEST-IDEMPOTENCY、TEST-ERROR-MAPPING-001、TEST-AUDIT-TRAIL-001→API report。

Contract impact: required HTTP/OpenAPI transport；只映射P4-02 machine carriers与application errors/states，不改变domain authority或创建第二套payload。

Schema changes: none；HTTP consumes P4-02 carrier，OpenAPI versioned independently。

Migration: none。

Dependency changes: none。

ADR impact: none；新gateway/session/external endpoint需新ADR。

State-machine impact: 只委托application批准的transitions；router不推进状态。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-REPLAN-API-001、TEST-REPLAN、TEST-IDEMPOTENCY、TEST-ERROR-MAPPING-001、TEST-AUDIT-TRAIL-001、TEST-SIM-ISOLATION、TEST-OBS-001。

Test IDs: TEST-REPLAN-API-001, TEST-REPLAN, TEST-IDEMPOTENCY, TEST-ERROR-MAPPING-001, TEST-AUDIT-TRAIL-001

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: API synthetic fixtures only；Simulator scenario endpoints explicitly excluded。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-12-dynamic-replanning-http-api.md --check-diff --report build/traceability/TASK-P4-12-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-replanning-api-report.v1`、OpenAPI fingerprint、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 所有operation/negative/error/auth/idempotency/correlation/delegation checks PASS；server authority/no calculation；Production default-deny；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: API只在隔离环境启用，不形成真实gateway/identity/event source、external MES/ERP、deployment、UAT或capacity/SLA。

P5 boundary: API不得暴露P5 route、field、action或capability advertisement。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 移除P4 route registration并保留application/storage历史；P3 API不变。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
