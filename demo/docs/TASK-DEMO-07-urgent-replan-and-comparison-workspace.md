---
doc_id: TASK-DEMO-07
title: Chinese Urgent Replan and Comparison Workspace
status: complete
spec_version: demo-task-card.v1
phase: demo
normative: true
last_reviewed: 2026-09-04
---

# TASK-DEMO-07 — Chinese Urgent Replan and Comparison Workspace

Task family: demo-exclusive

Depends on: TASK-DEMO-03, TASK-DEMO-04, TASK-DEMO-05, TASK-DEMO-06

Start gate: 用户要求继续实施。TASK-DEMO-06 machine report 为 `PASS`，中文故事页已能恢复 current `PUBLISHED` 基线并展示 132/580/24 初始计划；TASK-DEMO-03 已提供 durable urgent command/replan job，TASK-DEMO-04 已提供 strict、immutable Comparison presentation API。

Goal: 完成 D15：把首页第四步升级为中文业务化加急订单表单，自动带入 current `PUBLISHED` 基线，提交真实 `POST /urgent-orders` 后展示 durable job 阶段并恢复；成功后自动切换新 v2 `DRAFT` 比较工作区，展示前后甘特、ChangeReport 权威分类、设备与时间偏移、交付变化、稳定性和独立 Validator 证据。

Non-goals: 本任务不实现 D16 的完整服务重启/失败注入/并发/安全/无障碍审计矩阵，不修改 root `frontend/**`、默认产品入口、正式 schema、状态机、求解器、Validator、publication 生命周期或 P7；不批准或发布重排 DRAFT，不允许浏览器推导 ChangeReport 分类或 KPI，不开放同一 run 的第二个不同加急事件。

Inputs: `demo/docs/03-architecture-and-api.md` 第 8～10 节；`demo/docs/04-ux-and-demo-script.md` 第 2.4、2.5、3～8、10 节；`demo/docs/05-benchmark-and-acceptance.md` B4/B5、Gate D/E/F 与测试矩阵；`demo/docs/TASKS.md` D15；TASK-DEMO-03 urgent orchestration contract；TASK-DEMO-04 comparison contract/reader/API/tests；TASK-DEMO-05/06 frontend client/story/workspace/tests；固定 Showcase/Smoke assets 与现有 Demo API。

Diff base: b0cc126522e3916d72b438e7f237851a36b51a3d

Validation profile: DEMO_HIGH_RISK

Files allowed to change: demo/**

Files forbidden to change: demo 之外的全部路径。

Implementation steps: 冻结 UrgentOrderCommand/Comparison TypeScript consumer types 和 fail-closed guards；扩展同源 client 的 urgent POST 与 comparison GET；建立 persistent urgent command identity 和 replan recovery；实现四张批准路线卡、数量/交期/优先级/备注、服务端基线摘要和二次确认；提交后复用现有 job polling；终态成功从 bootstrap 恢复 DRAFT/request 并自动切换比较；实现分类/订单/设备筛选、前后时间条或上下分屏、偏移明细、交付与稳定性卡、Validator/ChangeReport lineage；用服务端分页限制可视 comparison 节点；补单元/组件测试、真实 Chromium Showcase 主链、双宽度布局、GET/POST 边界、刷新恢复和机器门禁。

Outputs: 扩展后的 `demo/frontend/**`；D15 consumer/controller/components/tests；更新后的中文 UX/运行文档；`TASK-DEMO-07` context、frontend replan evidence、screenshots 与 machine report。

Documentation impact: required

Documents to update: `demo/docs/README.md`、`demo/docs/TASKS.md`、`demo/docs/IMPLEMENTATION-STATUS.md`、`demo/docs/03-architecture-and-api.md`、`demo/docs/04-ux-and-demo-script.md`、`demo/docs/05-benchmark-and-acceptance.md`、本任务卡。

Traceability updates: D15；Gate D 的 UI command/recovery 子集；Gate E 的 DRAFT comparison 子集；B4/B5 浏览器 early evidence；中文 UI 约束。

Schema changes: formal schema none。前端只消费现有 Demo command/DTO；unknown field 可忽略，但全部必需字段、枚举、authority/boundary、分页、版本、request、ChangeReport/KPI lineage 必须 fail closed。不得把 `route_template_id` 写入正式 ExecutionEvent，也不得在前端重算变更分类或稳定性。

Migration: none。

Dependency changes: none expected。沿用 TASK-DEMO-05 锁定的 React/Vite/Vitest/Testing Library/TypeScript/ESLint，不修改根 package 或 lockfile。

ADR impact: none。

State-machine impact: none。前端只调用既有 durable Demo command；重排成功必须保持 current Publication 指向原 `PUBLISHED`，新版本固定为 `DRAFT`；失败或刷新不得产生第二个不同命令。

Error behavior: 未初始化、无 current PUBLISHED、stale run/base、active job、idempotency conflict、非法路线/数量/交期、UNKNOWN/no candidate、INFEASIBLE、Validator fail、网络中断和 comparison 契约/lineage 错误均显示中文稳定提示；不显示 raw backend message、token 或堆栈。失败保留原基线；只有服务端确认成功后才进入比较页。

Tests: UrgentOrderCommand/JobAccepted/Comparison 完整 guards 与 malformed mutations；route/数量/交期/优先级表单验证；current base 自动带入且不可编辑；确认摘要；持久幂等 identity；双击防护；urgent job polling/刷新恢复；成功自动切换 DRAFT；失败保持 PUBLISHED；Comparison 分类/分页/筛选；ADDED/CHANGED/UNCHANGED；base/new 时间和设备；交付/稳定性/Validator；中文边界文案；1440×900 与 1024×768 页面级无横向滚动。

Test IDs: DEMO-FE-053～088, DEMO-BROWSER-010～017

Benchmark impact: 记录一次固定 Showcase 的 urgent command、job、comparison payload、响应耗时、可视 comparison 节点和 DOM 节点 early evidence。它不是 warmup + 5/p95、独立 RSS、目标演示机或 Production SLA；如求解返回 `FEASIBLE + Validator PASS`，界面必须如实称“已验证可行”而非最优。

Simulation scenarios: CNC-DEMO-SHOWCASE current `PUBLISHED` + 文档第 8 节固定加急样本为主；Smoke fixture 用于单元/快速回归；固定 seed 20260902、合成数据、`Asia/Shanghai`，每个 deterministic run 只接受一个不同加急事件。

Acceptance commands: TASK-DEMO-07 context manifest；`npm ci`；frontend lint/typecheck/test/build；Python Demo regression、Ruff、Pyright；真实 Chromium Showcase reset→initial-plan→activate→urgent→DRAFT comparison；frontend replan evidence；`git diff --check -- demo`；protected-root hash 与 demo-only scope check。

Artifacts: `demo/build/validation/task-context-manifest-demo-07.json`、`frontend-evidence-demo-07.json`、`browser-replan-observation-demo-07.json`、`task-machine-report-demo-07.json`；截图放 `demo/build/validation/screenshots/`；node_modules/dist/runtime/Playwright session 不入 Git。

Provider evidence: local Demo-only。浏览器只连接 127.0.0.1 的 Vite proxy 与 Demo backend；不部署、不提交、不 push、不注册或恢复 P7。

Completion conditions: 所有新增业务界面和信息默认中文；BASELINE_PUBLISHED 显示四张批准路线卡和业务表单且无底层 identity；提交前显示不可编辑 current base 与确认摘要；一次 scripted fixture 形成 `URGENT_DEMAND_RECEIVED`、成功 job 和新 v2 `DRAFT`；current `PUBLISHED` 不变；页面自动进入比较；`ADDED`、`CHANGED`、`UNCHANGED` 均可筛选并来自 ChangeReport；前后设备/时间、交付、稳定性、Validator 和 Simulation/DRAFT 边界可见；请求分页有界；刷新不重复写命令；1440×900/1024×768 无页面级横向滚动；front/Python/scope/protected-root gates 全 PASS。

Completion evidence: D15 已完成。bootstrap 现在从批准资产返回四个路线模板/三类优先级，并从 latest succeeded durable urgent job 恢复精确 comparison lineage；前端实现 strict Urgent/Comparison consumer、同源 command/query client、按 run 持久化的原 payload/幂等键、中文业务表单与二次确认、真实 job polling、自动 DRAFT comparison、服务端分类/订单/设备筛选和 `limit=120` 分页。5 个前端测试文件共 35 tests、Python Demo regression、Ruff、Pyright、production build、diff hygiene、protected-root 与 demo-only scope 均通过。

真实 Chromium Showcase 使用 `CNC-ROUTE-5`、数量 5、北京时间 2026-09-09 18:00、URGENT 完成一次插单：job 约 21 秒，其中 SOLVING 14.235 秒，得到 `FEASIBLE + Validator PASS` 的 v2 `DRAFT`；原 current `PUBLISHED` 未变。页面展示 5 `ADDED`、25 `CHANGED`、555 `UNCHANGED`、3 次设备变更、3 次软锁偏离和 95.7% 保持比例；保持不变页以 120 条分页并成功翻至 121～240，CMM-01 筛选返回 17 道。刷新恢复同一 run/DRAFT/comparison reference 且没有重复 mutation；1440×900 与 1024×768 无页面级横向滚动，控制台 0 error / 0 warning。42/42 frontend evidence assertions 与 3/3 screenshots 为 `PASS`。证据见 `demo/build/validation/frontend-evidence-demo-07.json` 和 `task-machine-report-demo-07.json`。以上为单次 synthetic early evidence，不是 p95、目标机基线、Production capacity 或 SLA；D16 完整失败/安全/可访问性矩阵和 D17 正式基准仍明确排除。

Failure handling: command 未被服务端接受时允许修改并重试；已获 JobAccepted 后持久保存 identity，只轮询/恢复该 job，不生成新命令；终态失败保留 current PUBLISHED 并显示安全原因；comparison 任一契约/lineage/page 失败即丢弃本次结果；同 run 已有不同 urgent 事实时显示需重置演示，不伪装成可连续插单。

Explicitly excluded: P7、Production、真实客户数据、D16 完整故障/安全/可访问性 closure、自动批准/发布 DRAFT、连续多次不同插单、根 frontend、正式 schema/migration、浏览器计算 KPI/ChangeReport、500+ comparison 节点同屏、生产性能/容量/SLA 承诺。

Simulation assumptions: 中文 `zh-CN`、时区 `Asia/Shanghai`、默认 Showcase、四个批准路线模板、固定 scripted urgent payload、只读 single active comparison、分页/筛选由服务端执行；确认后只创建一个 durable urgent command。

Rollback: 删除 TASK-DEMO-07 新增的 D15 frontend modules/tests/evidence/screenshots，恢复 TASK-DEMO-06 的基线页和 Demo 文档/校验器；不触碰 backend 规范数据、root frontend、P7 或用户其他差异。
