---
doc_id: TASK-DEMO-05
title: Chinese Demo Story Shell and Job Recovery
status: completed
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-02
---

# TASK-DEMO-05 — Chinese Demo Story Shell and Job Recovery

Task family: demo-exclusive

Depends on: TASK-DEMO-02, TASK-DEMO-04

Start gate: 用户要求继续实施，并明确前端界面和信息采用中文。TASK-DEMO-04 machine report 为 `PASS`，Demo API 已提供 session/bootstrap/state/job、reset/initial-plan/baseline-activation，以及 Factory/Schedule/Comparison 只读视图，可作为独立 Demo 前端的同源边界。

Goal: 完成 D13：在 `demo/frontend` 建立可运行、可构建、可测试的中文 React 单页故事壳；同源建立 HttpOnly Simulation session，恢复 active run/job/story state，显示四步流程、场景事实、真实 job 阶段与计时，并可用键盘完成初始化、自动排产和显式设为仿真基线。

Non-goals: 本任务不实现 D14 的订单表、甘特图和资源负荷，不实现 D15 加急表单/版本比较，不实现 D16 全浏览器 E2E/视觉基线/完整 WCAG 审计，不实现 manual cancel/retry，不自动批准或发布 v2 DRAFT，不修改根 `frontend/**`、默认产品入口、正式 schema 或 P7。

Inputs: `demo/docs/04-ux-and-demo-script.md` 第 1～2、5～7、9～10 节；`demo/docs/TASKS.md` D13；TASK-DEMO-04 task card、三个 presentation contract 和 Demo API；Demo session/bootstrap/state/job/reset/initial-plan/baseline-activation 现有响应；根前端 package/config 仅作只读技术基线。

Diff base: b0cc126522e3916d72b438e7f237851a36b51a3d

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 冻结前端 TypeScript API types 和 runtime guards；建立 credentials same-origin client 和一次性 session bootstrap；实现 story controller、active job polling、refresh recovery 和请求防双击；实现中文 header、Simulation/run 标识、四步 stepper、场景卡、主操作、job drawer、Solver/Validator 摘要与折叠技术证据；失败使用稳定错误码到中文文案映射且不暴露 token/原始异常；建立 responsive/keyboard/focus/contrast 基础；补 Vitest/RTL、build、lint、typecheck 和浏览器 smoke evidence。

Outputs: `demo/frontend/**` 独立 Vite/React 应用及 lockfile、前端单元/组件测试、browser smoke evidence、TASK-DEMO-05 context/machine report，以及更新后的 Demo 文档与启动说明。

Documentation impact: required

Documents to update: `demo/docs/README.md`、`demo/docs/TASKS.md`、`demo/docs/IMPLEMENTATION-STATUS.md`、`demo/docs/04-ux-and-demo-script.md`、本任务卡。

Traceability updates: D13；Gate E 的故事壳数据消费；Gate F 的 session/refresh 子集；中文 UI 约束。

Schema changes: formal schema none。前端只定义 runtime-validated consumer types，不复制或放宽后端 authority；未知 response shape 必须进入中文“响应契约不匹配”阻断态。

Migration: none。

Dependency changes: 新增 `demo/frontend/package.json` 与 lockfile，依赖固定为 React/Vite/Vitest/Testing Library/TypeScript/ESLint；不得修改根 `frontend/package.json` 或 lockfile。

ADR impact: none。

State-machine impact: none。前端只能触发现有 Demo 命令并读取状态；按钮可用性由服务端 `story_state` 派生，不创建影子生命周期。v1 基线激活仍需用户显式确认。

Error behavior: session/bootstrap/job/network/contract/authorization/stale/conflict/terminal failure 全部显示中文可操作信息和 correlation ID 短值；刷新恢复服务端 active job；不显示虚假百分比，不把 UNKNOWN 写成不可行；不提供后端尚不支持的 retry/cancel 假按钮。

Tests: API credentials/session and response guards；EMPTY/INITIALIZED/RUNNING/READY_FOR_REVIEW/BASELINE_PUBLISHED/DRAFT recovery；action payload/idempotency/double-submit；job polling and terminal refresh；stage Chinese labels/timing/no percentage；activation confirmation and revision；error-code Chinese mapping/token sanitization；keyboard/focus/semantic landmarks；responsive browser smoke at 1440×900 and 1024×768。

Test IDs: DEMO-FE-001～018, DEMO-BROWSER-001～003

Benchmark impact: 本任务只记录 browser shell 首次可交互和关键布局 smoke，不形成 B5 正式 warmup + 5/p95/RSS baseline；D14 的 500+ 甘特渲染尚未发生。

Simulation scenarios: EMPTY、CNC-DEMO-SMOKE 快速交互链、已持久化 active job refresh fixture、Showcase 静态状态；全部为 zh-CN/SIMULATION。

Acceptance commands: TASK-DEMO-05 context manifest；`npm ci`；`npm run lint`、`npm run typecheck`、`npm run test -- --run`、`npm run build`；Python Demo regression；browser smoke；`git diff --check -- demo`；protected-root hash 与 demo-only scope check。

Artifacts: `demo/build/validation/task-context-manifest-demo-05.json`、`frontend-evidence-demo-05.json`、`task-machine-report-demo-05.json`；screenshots 放 `demo/build/validation/screenshots/`；`demo/frontend/node_modules`、`dist` 和 `demo/runtime/**` 不入 Git。

Provider evidence: local Demo-only。浏览器只连接 `127.0.0.1` 的 Vite proxy 与 Demo backend；不部署、不提交、不 push、不注册 P7。

Completion conditions: 所有业务可见文本默认中文；从 EMPTY 到 BASELINE_PUBLISHED 可仅用键盘完成；刷新从 bootstrap 恢复相同 run、active job 和正确步骤；SOLVING 只显示真实阶段/耗时/上限且无百分比；基线激活有中文确认并使用服务端 revision/fingerprint；状态、错误和 solver/validator 文案诚实；无底层 identity 输入；1440×900 与 1024×768 无页面级横向滚动；前端 gate、Python Demo regression、Demo-only scope 和 protected-root hashes PASS。

Completion evidence: `demo/frontend` production build、ESLint、TypeScript 和 3 files / 12 tests 均 PASS；真实 Chromium 连接本地 Demo backend 完成 Smoke profile 的 EMPTY→INITIALIZED→READY_FOR_REVIEW→BASELINE_PUBLISHED，刷新后恢复同一 `run-5556d9983fc18505f9553b45cdf1e77c`，所有主操作经 Enter 路径验证，确认按钮自动聚焦。1440×900 与 1024×768 均无页面级横向滚动，console 0 error / 0 warning，可见正文无 Bearer/Authorization。浏览器首次揭示 `current_publication` 不含重复 state 字段，consumer 已按真实 bootstrap contract 收紧适配并补回归；发布响应成功但随后 hydrate 失败时，activation request/key 会保留到确认服务端已发布后才清除。`frontend-evidence-demo-05.json` 19/19 assertions、3/3 screenshots PASS；Python Demo regression、Ruff、Pyright、diff check、protected-root hashes 与 Demo-only scope 由 `task-machine-report-demo-05.json` 复核为 PASS。

Failure handling: 前端失败不改变后端已有状态；网络中断保留最后成功状态并允许重新连接；terminal job failure 保留稳定 error code 和技术证据，不自动创建新命令；APPROVED 发布失败只允许用原 activation identity 恢复，不重新求解。

Explicitly excluded: P7 全部任务与状态、根 frontend、D14～D18、Production、真实客户数据、外部 identity、语言切换、英文主界面、自动发布 DRAFT、伪造进度、SLA。

Simulation assumptions: 中文区域固定 `zh-CN`、时区显示 `Asia/Shanghai`、默认 Showcase profile、SMOKE 只用于浏览器快速回归、轮询间隔 750～1000 ms、单 active job。

Rollback: 停止 Demo/Vite 服务，删除 TASK-DEMO-05 新增的 `demo/frontend`、测试、报告和 screenshots，恢复 Demo 文档/脚本到 TASK-DEMO-04 状态；不触碰根仓库、P7 或用户其他差异。
