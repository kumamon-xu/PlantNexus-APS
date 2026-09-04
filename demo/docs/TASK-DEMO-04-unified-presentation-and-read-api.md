---
doc_id: TASK-DEMO-04
title: Unified Schedule Presentation and Read API
status: completed
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-02
---

# TASK-DEMO-04 — Unified Schedule Presentation and Read API

Task family: demo-exclusive

Depends on: TASK-DEMO-01, TASK-DEMO-02, TASK-DEMO-03

Start gate: 用户要求继续依据 Demo 设计实施，并已明确整个工作属于 Demo 专属任务族而非 P7。TASK-DEMO-03 已形成 current schedule-version.v1 `PUBLISHED`、schedule-version.v2 `DRAFT`、规范 artifact、真实 KPI、fresh Validation 和 ChangeReport，可作为统一只读模型的输入。

Goal: 完成 D11 和 D12 剩余只读查询边界：定义严格、版本化、不可发布的 `DemoFactoryView v1`、`DemoScheduleView v1` 与 `DemoComparisonView v1`；分别适配 schedule-version.v1/v2 和相应 artifact；提供 `/factory`、`/versions/{version_id}`、`/comparisons/{request_id}`，支持 610+ 工序的服务端筛选、稳定排序、分页与时间窗口，并以 ETag、active run 和 correlation headers 供后续前端消费。

Non-goals: 本任务不实现 D13～D16 React 页面、甘特图渲染、浏览器 E2E/视觉/可访问性，不改变正式 ScheduleVersion/KPI/Validation/ChangeReport Schema，不提供 publish/approve/cancel/retry，不开放多次不同加急插单或 Production authority。

Inputs: `demo/docs/03-architecture-and-api.md` 第 9～10 节、`05-benchmark-and-acceptance.md` B5/Gate E 数据部分、`TASKS.md` D11/D12；TASK-DEMO-01～03 的 Demo-local durable runtime 与 artifacts；根仓库 schedule-version.v1/v2、KPI、Validation、ChangeReport 契约和只读 repository，均只读消费。

Diff base: b0cc126522e3916d72b438e7f237851a36b51a3d

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 先冻结三个 strict response contracts 和稳定枚举；建立 artifact/fingerprint/lineage reader；从规范 factory assets、canonical batch、Snapshot、Problem、ScheduleVersion、SolverReport、Validation、KPI 和 ChangeReport 投影统一模型；统一 UTC 与 factory local time；从 KPI 投影订单交付，从 Problem/Snapshot 投影设备层级、日历/维护/状态/锁定，从 assignments 计算有明确公式与 evidence 的计划负荷；以 ChangeReport 作为变更分类唯一 authority；实现稳定 sort/filter/page/time-window；接入授权后的 GET API、ETag/If-None-Match、active-run/correlation headers；增加 B5 runtime evidence 与 machine gate。

Outputs: `demo/backend/plantnexus_demo/presentation.py`、Demo-local response contracts/schema、API/composition/export 扩展、presentation/API tests、Showcase B5 evidence、上下文 manifest、machine report 和更新后的 Demo 文档。

Documentation impact: required

Documents to update: `demo/docs/README.md`、`demo/docs/TASKS.md`、`demo/docs/IMPLEMENTATION-STATUS.md`、`demo/docs/03-architecture-and-api.md`、本任务卡。

Traceability updates: D11；D12 的 factory/version/comparison read surface；Gate E 数据部分；B5 服务端构建与 JSON size evidence。

Schema changes: 正式 schema none。Demo-local contract 必须 strict、versioned、`additionalProperties=false` 等价；`publishable` 固定 false，不得被客户端输入覆盖。

Migration: none expected；全部读取现有 Demo control/run databases 与 artifact store。

Dependency changes: none。

ADR impact: none；展示模型不是新的 planning authority，不得反向写入正式模型。

State-machine impact: none；读取不得批准、发布、切换 current、生成新排程或改变 job/run。

Error behavior: 未初始化、错 run/scope、版本或 request 不存在、artifact 缺失、kind/version/ID/fingerprint/lineage mismatch、非法 filter/page/window、ChangeReport classification/universe 不一致均 fail closed；不存在资源不伪造成空成功；内部路径、token 和原始异常不得进入响应。

Tests: strict contract/unknown fields；factory hierarchy/calendar/maintenance/counts；v1/v2 schedule parity and timezone；order KPI provenance；resource-load formula；stable sort/filter/page/window；comparison classification exactness and default changed+added；artifact/fingerprint/lineage mutation；ETag 200/304；wrong token/capability/scope/run/not-found；read-only state invariant；610+ Showcase B5 size/time。

Test IDs: DEMO-PRESENT-001～018, DEMO-API-010～016

Benchmark impact: 新增 B5 单次 Showcase early evidence，记录 v1/v2/comparison 构建耗时、canonical JSON bytes、返回条目数和环境；本任务不形成浏览器首屏、warmup + 5、p95、RSS 或 SLA 结论。

Simulation scenarios: CNC-DEMO-SHOWCASE / seed 20260902 / TASK-DEMO-03 scripted urgent fixture / SIMULATION only。

Acceptance commands: Demo-local context manifest；`uv run pytest demo/tests -q`；Ruff/Pyright；B5 presentation runtime evidence；`git diff --check -- demo`；protected-root hash 与 demo-only scope check。

Artifacts: `demo/build/validation/task-context-manifest-demo-04.json`、`runtime-evidence-demo-04.json`、`task-machine-report-demo-04.json`；`demo/runtime/**` 仍为可删除本地产物且不入 Git。

Provider evidence: 本地 Demo 交付，不提交、不 push、不注册 P7；所有读取与 authority 保持 Simulation local。

Completion conditions: 三个 contract strict validation PASS；v1/v2 使用同一 Schedule DTO 且相同 assignment 的 UTC/local 时间一致；Factory 层级/日历/维护与 approved assets 一致；KPI 只从规范 artifact 投影；ChangeReport classification/universe 逐项一致且默认结果同时包含 `CHANGED` 与 `ADDED`；filter/sort/page/window 在 610+ 数据上确定；所有 DTO `publishable=false` 且标明 SIMULATION/DRAFT；artifact mutation fail closed；GET API 权限、ETag/304、错误映射与 read-only state invariant PASS；Demo-only scope 与 protected-root hashes PASS。

Completion evidence:

- Contracts/adapter：`demo/backend/plantnexus_demo/presentation.py` 定义三个 strict、frozen、versioned response contract 和规范化 query contract；v1/v2 Schedule 共用一个 DTO，所有 nested object 均 `extra=forbid`，所有 boundary 固定 `SIMULATION`、`production_authority=false`、`publishable=false`。
- Authority/lineage：presentation 逐项读取并校验 Snapshot、Problem、Solution/ScheduleVersion、SolverReport、Validation、KPI 和 ChangeReport 的 document version、artifact ID、fingerprint 与 lineage；v2 comparison 先通过正式 `ChangeReportQueryService`，变更分类及 universe 不在浏览器或 Demo adapter 重算。篡改 KPI artifact 的 mutation test fail closed。
- Factory/schedule/comparison：Factory 投影 approved hierarchy、calendar gaps、maintenance；Schedule 投影 orders、resource loads、execution facts 和 assignments；Comparison 投影 before/after、operation delta、delivery delta、稳定性与受影响订单。UTC 是筛选 authority，`Asia/Shanghai` local time 成对返回；窗口为半开区间。
- Query/API：`GET /api/demo/v1/factory`、`GET /api/demo/v1/versions/{version_id}`、`GET /api/demo/v1/comparisons/{request_id}` 已接入 Simulation 授权；支持稳定 filter/sort、offset/limit（最大 500）、ETag/If-None-Match 304、`X-Correlation-Id` 与 `X-Demo-Active-Run`。未知/重复/非法 query、not-found、缺 capability 和错 schedule scope 均有稳定 fail-closed 结果。
- Tests：`uv run pytest demo/tests -q` 为 36 passed；Ruff PASS；Pyright 0 errors；`git diff --check -- demo` PASS。OpenAPI 包含三个读取路径，三个顶层 response schema 均为 `additionalProperties=false`；读取前后 run/story/publication/database state invariant PASS。
- Showcase B5：`runtime-evidence-demo-04.json` 为 PASS。v1 `PUBLISHED` 为 132 单/580 assignments，v2 `DRAFT` 为 133 单/585 assignments，二者 Validator 均 PASS；分页分别为 500+80 和 500+85。Comparison universe 为 585 = 558 `UNCHANGED` + 22 `CHANGED` + 5 `ADDED`，默认结果同时含 `CHANGED` 与 `ADDED`，重复 query fingerprint 一致。
- Early performance：同一次 Showcase 中 Factory、v1 首页、v2 首页、默认比较、全量比较首页构建分别约 0.317/0.383/0.562/0.898/0.930 秒；这是当前开发机单次同进程证据，没有浏览器、warmup + 5、p95 或 RSS，不构成 SLA。
- Governance：上下文与最终机器门禁记录于 `task-context-manifest-demo-04.json` 和 `task-machine-report-demo-04.json`；protected-root hashes 与 Demo-only scope 由同一门禁复核。正式 schema、默认产品入口、P7 状态和 current Publication 均未改变。

Known limitations: OpenAPI 提供严格 response schema，但当前手工 query parser 的筛选参数说明以本文和架构文档为准，后续前端必须使用既定枚举；本任务未测浏览器序列化/绘制成本。单次 650～715 KiB 的 500 条 payload 表明前端必须消费分页/窗口，不应一次加载全部甘特数据。manual retry/cancel 与连续第二个不同加急事件仍 fail closed；均未被本任务包装成可用能力。

Failure handling: presentation 构建或查询失败只返回稳定 Demo error code 和 correlation id，不改变 active run、Publication、ScheduleVersion、artifact 或 command lineage；缺失或冲突证据不能降级为部分权威视图。

Explicitly excluded: P7 全部任务与状态、正式 contracts/schemas、D13～D18 UI/E2E/发布、Production、真实客户数据、外部 identity、自动批准/发布、浏览器 KPI 重算、SLA。

Simulation assumptions: factory timezone `Asia/Shanghai`、300 秒 tick、Showcase 10 天 horizon 和 approved synthetic assets；本地时间只作展示，权威比较和筛选使用 UTC。

Rollback: 删除 TASK-DEMO-04 新增的 Demo presentation/contract/test/report，恢复 Demo API 与文档到 TASK-DEMO-03 状态；不触碰根仓库文件、P7 task/phase 或其他用户差异。
