---
doc_id: TASK-P4-08
title: Replan Application and ScheduleVersion Lineage
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-08 — Replan Application and ScheduleVersion Lineage

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-007, REQ-008, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-HUM-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P4-03, TASK-P4-04, TASK-P4-05, TASK-P4-06, TASK-P4-07

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-08另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 编排ReplanRequest从PUBLISHED base、新Snapshot、freeze policy到Problem/lexicographic Solver/fresh Validator/ChangeReport/new immutable DRAFT ScheduleVersion的完整事务、幂等和audit lineage。

Non-goals: 不自动approve/publish/export、不修改base PUBLISHED、不允许Production authority fallback、不提供HTTP/UI/Simulator。

Inputs: P4-03 repositories、P4-04 Snapshot、P4-05 freeze、P4-06 report、P4-07 solver及P3 ScheduleVersion lifecycle。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: domain/application Replan orchestration、composition/machine command、限定unit/contract/integration/security tests、CI evidence及命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: Schema/migration/dependency、Solver formulas、Simulator/scenarios、API/UI、P3 approval/publication/export behavior、external side effect、P5+

Implementation steps: auth/plane/state/precondition→idempotency→Problem build→solve→fresh validate/report→atomic new DRAFT/result/audit；replay/conflict/cancel/failure/rollback/concurrency；base immutability。

Outputs: dynamic Replan application service与`p4-replan-application-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/replanning.md`、`docs/contracts/authorization-and-audit.md`、`docs/operations/observability-and-audit.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md`、`docs/tasks/P4/TASK-P4-08-replan-application-and-schedule-version-lineage.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/007/008/009→Replan service→TEST-REPLAN、TEST-CHANGE-REPORT-001、TEST-P4-PERSISTENCE-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-STATE-TRANSITION-001→report。

Contract impact: consumer-only；严格编排P4-02 Replan/Version/ChangeReport与P3 immutable ScheduleVersion/state/audit contracts，不增加私有command或transition。

Schema changes: none；消费P4-02。

Migration: none；消费P4-03。

Dependency changes: none。

ADR impact: none；实现TASK-P4-01 accepted Event/Fact/Replan与Freeze/Stability/ChangeReport ADR，并遵循ADR-0012不可变/人工控制边界。

State-machine impact: 执行P4-01批准的ReplanRequest transition；新ScheduleVersion仅DRAFT，后续仍走P3 review/approval/publish。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-REPLAN、TEST-CHANGE-REPORT-001、TEST-P4-PERSISTENCE-001、TEST-IDEMPOTENCY、TEST-AUDIT-TRAIL-001、TEST-STATE-TRANSITION-001、TEST-SIM-ISOLATION。

Test IDs: TEST-REPLAN, TEST-CHANGE-REPORT-001, TEST-P4-PERSISTENCE-001, TEST-IDEMPOTENCY, TEST-AUDIT-TRAIL-001, TEST-STATE-TRANSITION-001

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 固定synthetic request正负/并发；不连续推进仿真时钟。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-08-replan-application-and-schedule-version-lineage.md --check-diff --report build/traceability/TASK-P4-08-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-replan-application-report.v1`、transaction/lineage manifest、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 完整成功/拒绝/幂等/rollback/concurrency链可重放；base与P3 history不可变；new DRAFT未越权发布；exact provider闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: new DRAFT不构成真实approval/publish authority、external dispatch、deployment、UAT或capacity/SLA。

P5 boundary: application service不得分派或近似任何P5 advanced capability。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 关闭Replan command入口；保留事件、请求、结果、Version与audit，失败通过新请求/补偿event处理。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
