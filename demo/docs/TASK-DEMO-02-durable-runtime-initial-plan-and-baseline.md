---
doc_id: TASK-DEMO-02
title: Durable Demo Runtime, Initial Plan, and Simulation Baseline
status: done
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-02
---

# TASK-DEMO-02 — Durable Demo Runtime, Initial Plan, and Simulation Baseline

Task family: demo-exclusive

Depends on: TASK-DEMO-01

Start gate: 用户要求依据既有 Demo 设计继续实施，并已明确该工作不属于 P7 任务链。TASK-DEMO-01 的固定 CNC 数据、标准 ingress、Solver/Validator 规模门与 Demo-only scope 证据均已通过。

Goal: 完成 D05～D08 的后端闭环：独立 SQLite 组合根、fail-closed Simulation 本地授权、跨刷新可恢复的 run/job/artifact/reset 基础、真实初始排产形成 `READY_FOR_REVIEW`，以及经现有批准/发布生命周期显式激活为 current `PUBLISHED` 仿真基线。

Non-goals: 本任务不实现 D09/D10 加急事实导入与动态重排，不实现 D11～D16 展示 DTO/完整 API/前端/E2E，不改变产品默认入口，不声称 Production capacity 或 SLA。

Inputs: TASK-DEMO-01 交付物；demo/docs/03-architecture-and-api.md；根仓库现有 Alembic migrations、Raw Staging/Snapshot/ScheduleVersion/Audit/Publication repositories、GlobalCpSatStrategy、独立 Validator、KPI、ValidatedSolutionToScheduleVersionService、ApprovalDecisionService、PublicationService、FastAPI create_app 与授权合同，均只读消费。

Diff base: fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 建立 Demo runtime path guard 与 control.db；实现 run/job/stage/idempotency/authorization-audit persistence；每次 reset 新建 per-run SQLite 并执行现有 Alembic 与 Demo 辅助迁移；以原子 active-run CAS 切换且失败保留旧 run；实现本地 token provider；实现 InitialPlanningOrchestrator 并持久化规范 artifact；调用现有 lifecycle 形成 READY；实现显式 BaselineActivationService，经现有 APPROVE/PUBLISH 服务写入 current Publication；用独立 create_app 组合根挂载最小 Demo router；覆盖重放、stale、失败恢复和授权边界。

Outputs: demo/backend/plantnexus_demo 下的 persistence/security/orchestration/composition/API 实现，Demo-local tests、启动脚本、任务上下文与 machine report，以及更新后的 Demo 实施状态。

Documentation impact: required

Documents to update: demo/docs/README.md、demo/docs/TASKS.md、demo/docs/IMPLEMENTATION-STATUS.md、本任务卡。

Schema changes: none；正式 JSON Schema 不变。Demo control/run 辅助表使用 Demo-local migration version，不能替代正式 repository。

Migration: required；每个 run 先执行根 Alembic `head`，随后建立 `demo_artifacts`、`demo_scenario_manifest`、`demo_command_audit`。control.db 使用独立 Demo-local schema。

Dependency changes: none；复用根项目锁定的 FastAPI、SQLAlchemy、Alembic、OR-Tools 与测试环境。

ADR impact: none；若现有正式生命周期或状态机无法支持 Simulation 基线，应停止并记录契约断点，不修改根 ADR/Schema。

State-machine impact: 只通过现有服务执行 `DRAFT → READY_FOR_REVIEW → APPROVED → PUBLISHED`；Demo 不直接更新 schedule state 字段。Job 状态为 Demo-local orchestration state，不改变 P0 PlanningRun 状态机。

Error behavior: 所有路径逃逸、无 token/错 token/错 capability/Production、stale run、active-job conflict、同 key 异内容、迁移/生成/求解/Validator/持久化失败均 fail closed；UNKNOWN 无 candidate 映射为 `SOLVER_NO_CANDIDATE`，不得伪装 INFEASIBLE 或成功。

Tests: runtime path traversal；迁移与新 run 自检；reset failure preserves active；job exact replay/conflict/mutex/recovery；token/capability/scope/Production denial；initial smoke/showcase candidate + fresh Validator + artifact + READY lifecycle；mutated validation blocks version；activation preconditions/confirmation/exact replay/approved-resume/current reference；HTTP bootstrap/state/job/auth smoke；demo-only scope。

Test IDs: DEMO-RUNTIME-001～010, DEMO-AUTH-001～006, DEMO-PLAN-001～008, DEMO-BASELINE-001～008, DEMO-API-001～005

Benchmark impact: 复用 TASK-DEMO-01 的初排 scale evidence；本任务的集成测试可使用 smoke，关闭前至少运行一次 showcase runtime chain。不会把单次结果升级为稳定 benchmark。

Simulation scenarios: CNC-DEMO-SHOWCASE / seed 20260902 / SIMULATION only。

Acceptance commands: Demo-local context manifest；`uv run pytest demo/tests -q`；受影响 Ruff/Pyright；showcase runtime evidence script；`git diff --check -- demo`；protected-root hash 与 demo-only scope check。

Artifacts: demo/build/validation/task-context-manifest-demo-02.json、demo/build/validation/task-machine-report-demo-02.json、Demo runtime integration evidence；`demo/runtime/**` 为本地可删除产物且不入 Git。

Provider evidence: 本地 Demo 交付，不提交、不 push、不注册 P7；本地 token provider 明确不是 Production authority。

Completion conditions: D05～D08 验收项在本任务范围内通过；产品默认 app 保持 fail-closed；reset 失败不替换 active run；初排只有 candidate + fresh Validator PASS 才形成 READY；激活必须显式确认且 current Publication 精确指向 PUBLISHED；同 key 精确重放；demo 外受保护文件 hash 不变。

Completion evidence:

- `demo/build/validation/runtime-evidence-demo-02.json`：Showcase 132 单 / 580 active operations，reset、initial plan 和 activation 全链路 `PASS`；初排 `OPTIMAL`、fresh Validator `PASS`、7 类规范 artifact 完整。
- 初始版本由 `ValidatedSolutionToScheduleVersionService.create_reviewable` 形成 `READY_FOR_REVIEW` / state revision 1；显式激活经现有 `ApprovalDecisionService` 与 `PublicationService` 形成 current `PUBLISHED` / state revision 3，Publication reference 与 schedule id/fingerprint 精确一致。
- reset 与 initial-plan durable job 均记录 10 个真实阶段；同 key 成功后返回同一 job/result，activation 同 key 返回同一 publication 结果。
- `uv run pytest demo/tests -q`：28 passed；Ruff 与 Pyright 均为 0 issue。
- 失败注入证明切换前失败保留旧 active run；遗留 RUNNING job 恢复为 `INTERRUPTED`；路径逃逸、active-job mutex、stale/idempotency conflict、错 token/capability/scope 与 Production 均 fail closed。
- 独立 Demo app 已注入真实 P3 handlers 和 P4 append/read persistence facade；D09/D10 之前不存在的 replan cancel/retry 执行仍显式 `SERVICE_UNAVAILABLE`，没有伪造 handler。
- `demo/runtime/**` 被忽略；默认产品 `backend/app/api/app.py` 未修改且仍为 unavailable/fail-closed composition。

Failure handling: 保留失败 job 的稳定 error code 与阶段证据；允许从 APPROVED 恢复发布；不得删除旧 active run 或清空核心 append-only 表。需要根代码/Schema/依赖变化时停止并请求新范围。

Explicitly excluded: P7 全部任务与状态、D09～D18、外部认证、Production、真实客户数据、部署和 SLA。

Simulation assumptions: 沿用 TASK-DEMO-01 已冻结的 profile、资产 digest、300 秒 tick、单 solver worker 和明确 solve limit。

Rollback: 停止 Demo runner，删除本任务新增的 demo 实现/测试/报告与 `demo/runtime` 本地产物，恢复 Demo 文档到 TASK-DEMO-01 状态；不触碰根仓库文件或其他任务差异。
