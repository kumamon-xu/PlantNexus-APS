---
doc_id: TASK-DEMO-06
title: Chinese Schedule Workspace and Capacity View
status: completed
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-02
---

# TASK-DEMO-06 — Chinese Schedule Workspace and Capacity View

Task family: demo-exclusive

Depends on: TASK-DEMO-04, TASK-DEMO-05

Start gate: 用户要求继续实施。TASK-DEMO-05 machine report 为 `PASS`，中文故事壳已能恢复 current `PUBLISHED` 基线；TASK-DEMO-04 已提供 strict、immutable 的 Factory/Schedule presentation API，可作为 D14 唯一展示数据源。

Goal: 完成 D14：在 `demo/frontend` 的中文故事首页中增加初始排产工作区，提供订单风险表、订单联动的工厂/车间/设备甘特图、班次/非工作时间/维护与任务状态语义、计划负荷和瓶颈排序、Solver/Validator/KPI 证据，以及面向 580+ assignments 的有界时间窗和分页消费。

Non-goals: 本任务不实现 D15 加急表单、动态重排触发或前后版本比较，不实现 D16 完整失败注入/重启/视觉基线矩阵，不修改 root `frontend/**`、默认产品入口、正式 schema、状态机、排产算法、publication 生命周期或 P7；不把计划负荷称为设备实际利用率、OEE 或生产容量。

Inputs: `demo/docs/04-ux-and-demo-script.md` 第 2.3、3～5、7.2 节；`demo/docs/05-benchmark-and-acceptance.md` 第 5.5、6.4、9 Gate E 与 10 节；`demo/docs/TASKS.md` D14；TASK-DEMO-04 presentation contract/reader/API/tests；TASK-DEMO-05 frontend consumer/client/story shell/tests；固定 Showcase/Smoke ScenarioManifest 与现有 Demo API。

Diff base: b0cc126522e3916d72b438e7f237851a36b51a3d

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 冻结 Factory/Schedule 完整 TypeScript consumer types 和 fail-closed guards；扩展同源 client 的分页与筛选 query；建立 ScheduleWorkspace 状态和按需加载；实现中文工作区导航、订单风险表、行选择联动、层级资源筛选、可横向滚动的时间窗甘特与等价明细表；绘制工作日历、维护、completed/running/planned、hard/soft/freeze 的文字/图形双编码；按服务端 busy/available 数据展示计划负荷并排序；提供 KPI/Validator/Solver 证据；为 Showcase 使用每页不超过 200 条和可选时间窗，避免一次渲染 580+ 甘特节点；补单元/组件测试、真实浏览器 Showcase smoke、布局/节点数/控制台证据和机器门禁。

Outputs: 扩展后的 `demo/frontend/**`；D14 consumer/controller/components/tests；更新后的中文 UX/运行文档；`TASK-DEMO-06` context、frontend workspace evidence、screenshots 与 machine report。

Documentation impact: required

Documents to update: `demo/docs/README.md`、`demo/docs/TASKS.md`、`demo/docs/IMPLEMENTATION-STATUS.md`、`demo/docs/04-ux-and-demo-script.md`、`demo/docs/05-benchmark-and-acceptance.md`、本任务卡。

Traceability updates: D14；Gate E 的初始排产展示子集；B5 的浏览器节点/首屏 early evidence；中文 UI 约束。

Schema changes: formal schema none。前端只消费 TASK-DEMO-04 已有 DTO；unknown field 可忽略但全部必需字段、枚举、authority/boundary、分页一致性、时间区间和 lineage 必须 fail closed。不得在前端推导或替代 ChangeReport/KPI authority。

Migration: none。

Dependency changes: none expected。沿用 TASK-DEMO-05 已锁定 React/Vite/Vitest/Testing Library/TypeScript/ESLint，不修改根 package 或 lockfile。

ADR impact: none。

State-machine impact: none。工作区是只读 consumer；任何筛选、分页、展开、选中和时间窗变化都不得写入 Demo run、ScheduleVersion 或 Publication。

Error behavior: Factory/Schedule 网络、契约、scope、stale active run、分页和 query 失败显示中文安全提示；保留最后成功的故事页，不显示部分可信甘特；空筛选显示明确空态；未知 task/calendar/lock 枚举阻断相应工作区；不显示 raw backend message 或 token。

Tests: 完整 Factory/Schedule guard 与 malformed mutations；query 编码和 same-origin credentials；分页汇总/去重/上限；订单风险排序与筛选；订单→甘特联动；车间/设备筛选；时间窗裁剪与刻度；维护/非工作/状态/锁/冻结双编码；等价表格；计划负荷排序和非 OEE 文案；OPTIMAL/FEASIBLE 中文诚实文案；loading/empty/error/recovery；Showcase 132/580/24 真实浏览器 smoke；1440×900 与 1024×768 无页面级横向滚动。

Test IDs: DEMO-FE-019～052, DEMO-BROWSER-004～009

Benchmark impact: 记录一次 Showcase 前端 early evidence，包括 API payload、工作区加载耗时、渲染 assignment 数、DOM 节点数和目标宽度；不是 warmup + 5/p95、独立 RSS、目标演示机或 Production SLA。主甘特首屏必须有界，不把 580 assignments 全部同时挂载为可视节点。

Simulation scenarios: CNC-DEMO-SHOWCASE current `PUBLISHED` 初排为主；Smoke fixture 用于单元/快速浏览器回归；均为固定 seed 20260902、合成数据和 `Asia/Shanghai`。

Acceptance commands: TASK-DEMO-06 context manifest；`npm ci`；frontend lint/typecheck/test/build；Python Demo regression、Ruff、Pyright；真实 Chromium Showcase workspace smoke；frontend workspace evidence；`git diff --check -- demo`；protected-root hash 与 demo-only scope check。

Artifacts: `demo/build/validation/task-context-manifest-demo-06.json`、`frontend-evidence-demo-06.json`、`browser-workspace-observation-demo-06.json`、`task-machine-report-demo-06.json`；截图放 `demo/build/validation/screenshots/`；node_modules/dist/runtime/Playwright session 不入 Git。

Provider evidence: local Demo-only。浏览器只连接 127.0.0.1 的 Vite proxy 与 Demo backend；不部署、不提交、不 push、不注册或恢复 P7。

Completion conditions: 所有新增业务界面和信息默认中文；BASELINE_PUBLISHED 可打开订单/甘特/负荷/校验四个视图；Showcase 精确显示 132 单、580 assignments、24 设备；订单筛选和行选择可联动甘特；工厂/车间/设备层级可切换；日历、维护、completed/running/planned、hard/soft/freeze 均有非颜色标识和等价表格；计划负荷从服务端口径展示并明确非 OEE；单次请求 `limit<=200` 且甘特 DOM assignment 节点有界；1440×900 和 1024×768 无页面级横向滚动；刷新与筛选不产生写请求；front/Python/scope/protected-root gates 全 PASS。

Completion evidence: `demo/frontend` production build、ESLint、TypeScript 和 5 files / 26 tests 均 PASS；Python Demo regression 为 36 passed，Ruff、Pyright 与 `git diff --check -- demo` 均 PASS。真实 Chromium 连接固定 Showcase current `PUBLISHED` 基线，中文四视图精确显示 132 单、580 assignments、24 设备；默认 72 小时查询匹配 546 道并只挂载 160 个 assignment 节点，包含 30 completed、12 running、4 hard lock、8 soft lock、24 freeze、120 非工作时段块和 2 个当前窗口维护块，总 DOM 1,173。订单 `demand-order-cnc-036` 搜索为 1 条并以 GET 聚焦 5 道工序；计划负荷 24 行且非 OEE 口径明确；求解器为 `OPTIMAL`、独立 Validator `PASS`、0 hard violations。1440×900 与 1024×768 页面级无横向滚动，console 0 error / 0 warning；`frontend-evidence-demo-06.json` 30/30 assertions、5/5 screenshots PASS，protected-root hashes 与 Demo-only scope 由 `task-machine-report-demo-06.json` 复核。浏览器耗时只是一轮 early evidence，不是 warmup + 5/p95、目标机、独立 RSS 或 Production SLA。

Failure handling: 工作区失败不改变故事主状态和 current baseline；分页或契约任一页失败即丢弃本次聚合结果；网络恢复只重放 GET；筛选/选中恢复到合法默认值；若 Showcase 不能在有界节点内清晰呈现，则先降低首屏窗口/页长而不改变场景计数。

Explicitly excluded: P7、Production、真实客户数据、D15 urgent command/comparison、D16 完整 E2E、安全审计和 WCAG closure、自动发布、根 frontend、正式 schema/migration、OEE/实际利用率/容量承诺、500+ 同屏 DOM 条目。

Simulation assumptions: 中文 `zh-CN`、时区 `Asia/Shanghai`、默认 Showcase、列表页长 100～200、甘特默认显示 24～72 小时时间窗并可切换、只读单 active schedule、计划负荷采用服务端 presentation 口径。

Rollback: 删除 TASK-DEMO-06 新增的 D14 frontend modules/tests/evidence/screenshots，恢复 TASK-DEMO-05 故事页与 Demo 文档/校验器；不触碰 backend 规范数据、root frontend、P7 或用户其他差异。
