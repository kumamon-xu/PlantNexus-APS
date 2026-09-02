---
doc_id: TASK-DEMO-03
title: Urgent Order Ingress and Dynamic Replanning
status: completed
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-02
---

# TASK-DEMO-03 — Urgent Order Ingress and Dynamic Replanning

Task family: demo-exclusive

Depends on: TASK-DEMO-01, TASK-DEMO-02

Start gate: 用户要求依据既有 Demo 设计继续实施，并已明确该工作不属于 P7 任务链。TASK-DEMO-02 已形成 durable active run、current `PUBLISHED` Simulation 基线、真实 initial-plan artifact 与 fail-closed Demo API。

Goal: 完成 D09～D10 的后端闭环：把业务化 `UrgentOrderCommand v1` 转换为只新增一个 demand 的标准导入候选和精确 `URGENT_DEMAND_RECEIVED`，经正式 event authority、projection checkpoint、Snapshot、ReplanRequest、六轮动态重排、独立 Validator、真实 before/after KPI 与 ChangeReport，形成 schedule-version.v2 `DRAFT`，同时保持 current `PUBLISHED` 基线不变。

Non-goals: 本任务不实现 D11 统一展示 DTO、D13～D16 前端与 E2E，不自动批准或发布重排 DRAFT，不开放 Production authority，不改变产品默认入口、正式 Schema、ADR 或根仓库代码。

Inputs: TASK-DEMO-01/02 交付物；demo/docs/02-cnc-data-design.md、03-architecture-and-api.md、05-benchmark-and-acceptance.md；根仓库现有标准 ingress、urgent candidate validator、ExecutionEvent authority/repository、fact projection/checkpoint、Snapshot/ReplanRequest factory、ReplanApplicationService、CP-SAT replan strategy、独立 Validator、KPI 与 ChangeReport 机制，均只读消费。

Diff base: fd9ce328a180a8b1f0baa1a0fe870a8d39e0d200

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 定义严格命令与白名单路线展开；在任何写入前校验 active run/current PUBLISHED/expected base/horizon；构造完整标准 import candidate 并证明既有规范记录 byte-for-byte 不变；运行 mapping、normalization、Data Validation 与 urgent candidate validator；以正式 repository 提交 staging、精确事件与 checkpoint；建立新 immutable Snapshot 和严格 ReplanRequest；实现真实 candidate KPI-capturing strategy adapter；调用现有 ReplanApplicationService；交叉核对 schedule/report/validation/KPI/ChangeReport lineage；以 durable job 暴露 first apply、exact replay 与失败恢复。

Outputs: demo/backend/plantnexus_demo 下的 urgent ingress、dynamic replan orchestration、job/API 扩展，Demo-local tests、scripted urgent fixture、runtime evidence、任务上下文与 machine report，以及更新后的 Demo 实施状态。

Documentation impact: required

Documents to update: demo/docs/README.md、demo/docs/TASKS.md、demo/docs/IMPLEMENTATION-STATUS.md、本任务卡。

Schema changes: none；正式 JSON Schema 冻结。`route_template_id`、`note` 和原始 Demo command 只能进入 Demo audit/artifact，不能进入 execution-event.v1 或 ReplanRequest 正式 payload。

Migration: none expected；优先复用 TASK-DEMO-02 已建立的 per-run root migrations 与 Demo artifact/audit 表。若需要新 Demo-local 表，必须保持 additive、可重放且不改变正式 migration。

Dependency changes: none。

ADR impact: none；任何无法由 accepted ADR-0013/0014 支持的语义必须停止并记录断点，不得放宽正式 validator 或 contract。

State-machine impact: 只通过现有服务形成 v2 `DRAFT`；current Publication 和 v1 `PUBLISHED` 基线不得变化。Job 状态仍是 Demo-local orchestration state。

Error behavior: stale run/base、非 current PUBLISHED、越界时间/数量/模板、旧记录 mutation、非法 event/request、projection gap、UNKNOWN 无 candidate、INFEASIBLE、Validator/KPI/ChangeReport/lineage 不一致和持久化失败均 fail closed；terminal no-candidate 不创建 DRAFT。

Tests: command strictness/timezone/horizon；route expansion/duration；candidate additive-only 与 mutation rejection；event exact schema/no Demo fields/authority/position；first apply/exact replay/conflict/stale before write；projection checkpoint and snapshot lineage；ReplanRequest validation；completed/running/hard/freeze preservation；real KPI adapter；v2 DRAFT/current PUBLISHED unchanged；ChangeReport universe/validation；no-candidate no DRAFT；HTTP job/auth smoke；Demo-only scope。

Test IDs: DEMO-URGENT-001～012, DEMO-REPLAN-001～015, DEMO-API-006～009

Benchmark impact: 本任务先以 smoke 完成错误路径和契约集成，再至少运行一次固定 Showcase scripted urgent chain；单次证据仅为 early scale evidence，不升级为 p95 或 SLA。

Simulation scenarios: CNC-DEMO-SHOWCASE / seed 20260902 / scripted urgent fixture v1 / SIMULATION only。

Acceptance commands: Demo-local context manifest；`uv run pytest demo/tests -q`；受影响 Ruff/Pyright；Showcase urgent runtime evidence；`git diff --check -- demo`；protected-root hash 与 demo-only scope check。

Artifacts: demo/build/validation/task-context-manifest-demo-03.json、demo/build/validation/runtime-evidence-demo-03.json、demo/build/validation/task-machine-report-demo-03.json；`demo/runtime/**` 为可删除本地产物且不入 Git。

Provider evidence: 本地 Demo 交付，不提交、不 push、不注册 P7；所有 authority 与发布均为 Simulation local。

Completion conditions: D09/D10 验收项通过；stale base 在任何写入前失败；同 key 精确重放不重复 demand/event/request/attempt/version；既有规范记录 byte-for-byte 不变；route_template_id 不进入正式事件；new Snapshot/ReplanRequest/event range lineage 一致；fresh Validator 与 ChangeReport validation PASS；completed/running/hard/freeze 逐项保留；新版本为 v2 DRAFT且 current PUBLISHED 不变；demo 外受保护文件 hash 不变。

Completion evidence:

- 实现：`demo/backend/plantnexus_demo/urgent.py` 提供严格命令、DST/offset/horizon 校验、当前四个批准路线模板展开与 additive-only Standard Import candidate；`generator.py` 暴露从记录重建标准 batch 的复用边界。
- 编排：`demo/backend/plantnexus_demo/replanning.py` 通过正式 event authority/repository、projection checkpoint、Snapshot/ReplanRequest factory 和 `ReplanApplicationService` 形成 v2 `DRAFT`；after KPI 来自真实 candidate，ChangeReport 与 fresh Validator 均由正式服务校验。
- Durable/API：`jobs.py`、`api.py`、`composition.py` 增加 `URGENT_REPLAN` job、`POST /api/demo/v1/urgent-orders`、真实十阶段进度与 `DRAFT_COMPARISON_READY` 状态；manual cancel/retry 仍 fail closed。
- Tests：`uv run pytest demo/tests -q` 为 31 passed；Ruff PASS；Pyright 0 errors；`git diff --check -- demo` PASS。新增测试覆盖旧记录规范字节不变、事件无 Demo-only 字段、DST/offset/horizon、stale base 写前失败、formal exact replay、lineage 单例、锁定/冻结证据、v2 `DRAFT`、ChangeReport universe 和 current Publication 不变。
- Showcase：`runtime-evidence-demo-03.json` 为 PASS；132 单 current `PUBLISHED` 基线上新增 5 道工序，urgent job 约 24.16 秒返回 `FEASIBLE` 且 Validator `PASS`；ChangeReport 为 5 `ADDED`、23 `CHANGED`、557 `UNCHANGED`；event/checkpoint/request/request-event/attempt/result 各 1，schedule versions 共 2；formal replay 未增加第二套 lineage。
- Governance：上下文与最终机器门禁分别记录于 `task-context-manifest-demo-03.json` 和 `task-machine-report-demo-03.json`；protected-root hashes 与 demo-only scope 由同一门禁复核。所有数据和 authority 保持 SIMULATION，P7 状态未改变。

Known limitations: 当前每个 deterministic run 只接受一个不同的加急事件；同命令可精确重放，第二个不同插单以 `BASELINE_STATE_CONFLICT` fail closed。根 projector 会携带基线前历史 completed facts，而比较 universe 仅含基线 active assignments；Demo 保留 Snapshot 历史 tuple 原字节，通过单 worker 调用范围内的兼容 adapter 只收窄 effective-lock completed comparison view。该边界不修改正式 projector/Validator，后续应以正式依赖注入或统一 universe 语义替代。D11 presentation DTO、剩余查询 API 和前端不在本任务完成范围内。

Failure handling: 保留失败 job 的稳定 error code、阶段证据和最后已提交的 PUBLISHED 基线；若 event 已提交但后续失败，exact replay 必须从已持久化 lineage 恢复而不是重复追加；不删除 append-only event/request/attempt/version 记录。

Explicitly excluded: P7 全部任务与状态、D11～D18、Production、真实客户数据、外部身份、部署、SLA 和自动发布重排版本。

Simulation assumptions: 沿用固定 factory timezone、900 秒 freeze、priority 1/4/12、300 秒 tick、单 solver worker、30 秒 replan solve limit 与 scripted urgent fixture；这些值仅属于 Simulation。

Rollback: 停止 Demo runner，删除本任务新增的 demo 实现/测试/报告与 `demo/runtime` 本地产物，恢复 Demo 文档到 TASK-DEMO-02 状态；不触碰根仓库文件、P7 task/phase 或其他用户差异。
