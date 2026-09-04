# PlantNexus APS CNC 演示设计文档

状态：实施中（中文主故事链与加急比较已通过；D16 完整 E2E、D17 正式基准待续）
适用范围：仅限 Simulation 演示环境  
目标行业：精密机械零部件 / CNC 机加工车间  
固定场景：CNC-DEMO-SHOWCASE  
固定种子：20260902

## 1. 结论

本 Demo 采用“独立 Simulation 组合根 + 行业化数据包 + 演示编排 API + 演示前端”的实现方式。所有新增代码、数据、测试、运行产物说明和文档都放在 demo 目录；只把现有 backend、frontend 和 schemas 作为被复用的产品能力与只读契约来源。

不建议直接改造当前默认启动入口。默认后端与前端有意采用 fail-closed 的 unavailable provider，现有重排工作台还要求演示人员手工填写底层 identity。Demo 应通过独立组合根注入 SQLite 仓储、Simulation 授权和实际 application facade，同时保留产品默认入口的安全语义。

演示主线为：

1. 初始化或重置固定种子的 CNC 工厂。
2. 自动生成 132 个订单、610 道工序、24 台设备的数据包，并走标准导入链。
3. 运行初始排产和独立 Validator，形成 READY_FOR_REVIEW 版本。
4. 由演示人员显式点击“设为仿真基线”，完成批准和发布；动态重排只接受当前 PUBLISHED 基线。
5. 填写面向业务的加急订单表单。
6. 先导入加急订单事实，再追加精确的 URGENT_DEMAND_RECEIVED 事件，创建 Snapshot 和 ReplanRequest。
7. 保留已完成、正在加工、硬锁及冻结窗口约束，运行动态重排。
8. 形成新的 DRAFT 排程，自动进入前后版本比较页，展示 ChangeReport 和 Validator 结果；不自动批准或发布。

初始排产 20 秒预算已在当前开发机完成一次 610 工序实测：2.427 秒求解、2.924 秒 Solver 总耗时、`OPTIMAL`、独立 Validator `PASS`；700 工序在 30 秒预算下为 6.304 秒求解、6.947 秒 Solver 总耗时、`OPTIMAL`、Validator `PASS`。固定 Showcase 加急链也完成一次实测：在 132 单 current `PUBLISHED` 基线上新增 5 道工序，urgent job 约 24.16 秒返回 `FEASIBLE`、Validator `PASS`，ChangeReport 为 5 `ADDED` / 23 `CHANGED` / 557 `UNCHANGED`。这些都只是单次、合成、当前环境的早期规模证据，不是稳定基线、生产性能或 SLA；warmup + 5 measured、独立进程 RSS 和目标机复测仍未完成。

TASK-DEMO-02 已把这条能力装配为可运行后端：每次 reset 新建独立 SQLite run、执行现有 Alembic、持久化真实阶段和规范 artifact；Showcase 端到端实测成功形成 `READY_FOR_REVIEW`，再经显式确认和现有批准/发布服务成为 current `PUBLISHED`。默认产品入口未改变，Demo 通过本地 cookie session 和 fail-closed Simulation provider 独立启动。

TASK-DEMO-03 已完成 D09～D10：严格 `UrgentOrderCommand` 经白名单路线展开为 additive-only Standard Import candidate，正式追加 `URGENT_DEMAND_RECEIVED` 并提交 projection checkpoint；随后复用现有 `ReplanApplicationService`、六轮 CP-SAT 重排、fresh Validator、真实 candidate KPI 和 ChangeReport 形成 `schedule-version.v2 DRAFT`。同 key formal replay 不增加第二条 event/request/attempt/version，`route_template_id` 与备注只留在 Demo audit，current `PUBLISHED` 始终不变。

TASK-DEMO-04 已完成 D11 和 D12 的展示读取面：Demo 服务端从已提交的规范 artifact 构建 strict、immutable 的 `DemoFactoryView v1`、统一 `DemoScheduleView v1` 与 `DemoComparisonView v1`，同时适配初排 v1 和重排 v2。`GET /factory`、`GET /versions/{version_id}`、`GET /comparisons/{request_id}` 已支持授权、稳定筛选/排序、500 条分页、UTC 半开时间窗口、ETag/304，以及 active-run/correlation headers；所有视图固定 `publishable=false`，ChangeReport 是变更分类唯一 authority，读取不会改变故事状态或 current Publication。

TASK-DEMO-05 已完成 D13：`demo/frontend` 提供独立的中文 React 故事首页，经同源 HttpOnly Simulation session 从服务端恢复 run、active job、ScheduleVersion 与故事状态；页面可完成初始化、自动排产和显式发布仿真基线，显示真实阶段/耗时、Solver/Validator/KPI，并将完整 identity 与指纹默认折叠。发布确认使用服务端 revision、fingerprint 和持久化幂等身份；刷新可恢复同一运行。

TASK-DEMO-06 已完成 D14：已发布仿真基线会自动装载中文排产工作区，提供订单/交期、工厂—车间—设备甘特、计划负荷、校验与证据四个视图。Showcase 精确读取 132 单、580 个排程工序和 24 台设备；默认 72 小时时间窗只渲染一个 160 条服务端分页，并以文字、图形和等价表格同时表达完成/加工中、硬锁/软锁、冻结、班次与维护。订单行可通过 GET 聚焦全部工序，计划负荷明确不是设备综合效率。

TASK-DEMO-07 已完成 D15：第四步提供资产驱动的四条中文路线、数量/交期/优先级/备注和二次确认，自动绑定 current `PUBLISHED` 且隐藏底层 identity。真实 Showcase 插入 5 道工序后约 21 秒得到 `FEASIBLE + Validator PASS` 的 v2 `DRAFT`，页面自动展示 PUBLISHED→DRAFT、5 `ADDED` / 25 `CHANGED` / 555 `UNCHANGED`、设备/时间偏移、交付与稳定性，以及 ChangeReport/Validator lineage；保持不变页按 120 条服务端分页，刷新恢复不会重复提交命令。新草稿不会自动发布或替换 current Publication。

## 2. 文档导航

- [调研、边界与设计决策](01-research-and-scope.md)
- [CNC 场景与数据设计](02-cnc-data-design.md)
- [架构、编排与 API 设计](03-architecture-and-api.md)
- [交互设计与演示脚本](04-ux-and-demo-script.md)
- [专项基准与验收标准](05-benchmark-and-acceptance.md)
- [实施任务清单](TASKS.md)
- [当前实施状态与实测结果](IMPLEMENTATION-STATUS.md)
- [TASK-DEMO-02 后端运行闭环](TASK-DEMO-02-durable-runtime-initial-plan-and-baseline.md)
- [TASK-DEMO-03 加急事实与动态重排闭环](TASK-DEMO-03-urgent-order-and-dynamic-replan.md)
- [TASK-DEMO-04 统一展示与只读 API](TASK-DEMO-04-unified-presentation-and-read-api.md)
- [TASK-DEMO-05 中文故事首页与 Job 恢复](TASK-DEMO-05-chinese-story-shell-and-job-recovery.md)
- [TASK-DEMO-06 中文排产工作区与计划负荷](TASK-DEMO-06-schedule-workspace-and-capacity-view.md)
- [TASK-DEMO-07 中文加急重排与版本比较](TASK-DEMO-07-urgent-replan-and-comparison-workspace.md)

## 3. 设计原则

- 契约优先：继续使用现有标准导入、Snapshot、PlanningProblem、SolverReport、ScheduleVersion、ExecutionEvent、ReplanRequest、ChangeReport 和 Validator 契约。
- 诚实展示：OPTIMAL 表示已证明最优；FEASIBLE 且 Validator 通过只表示已找到并验证可行，不表示最优。
- 演示隔离：只允许 Simulation，默认监听 127.0.0.1，使用独立 SQLite 数据库和演示身份。
- 可重放：固定种子、固定时钟、固定版本号和单求解 worker；同一输入应产生相同业务 ID 与内容指纹。
- 生命周期显式：初始版本必须经过可见的“设为仿真基线”步骤；加急重排只生成 DRAFT。
- 不伪造进度：求解阶段只展示真实的粗粒度阶段和耗时，不显示未经求解器回调支持的虚假百分比。
- 不越界宣传：计划负荷不是设备实际利用率或 OEE；本 Demo 不是生产性能、容量或 SLA 证据。

## 4. 关键风险摘要

| 风险 | 影响 | 设计响应 |
|---|---|---|
| 当前最大基准仅 12 单、48 工序 | 无法外推百单耗时 | 在 UI 完成前先跑 610/700 工序专项基准 |
| 初始工作台使用 v1，重排产出 v2 | 新版本不能直接接入原甘特图 | 在 demo 内构建统一 presentation DTO，不修改核心契约 |
| 现有生成器 v1 对所有订单使用同一工序数 | 无法表达 3～6 道工序混合 | 新建 demo 专用分层 CNC 生成器，输出标准 StagedImportBatch |
| 默认 app/session provider 不可用 | 默认启动不是开箱即用 | 建立 demo 独立组合根并显式注入实际 provider |
| 求解 API 没有细粒度进度回调 | 百分比可能误导 | 只报告真实阶段、计时和最终状态 |
| 动态重排要求当前 PUBLISHED 基线 | 两步演示链不完整 | 加入显式“设为仿真基线”步骤 |
| 加急事件契约不包含路线 | 不能把 route 字段塞入事件 | route_template_id 留在 demo command；服务端展开为标准导入事实 |
| 基线前已完成工序不属于版本比较 universe | 把全部历史完成事实计为本次 removed 会造成 Validator universe mismatch | 保留 Snapshot/历史锚点原字节，仅把 effective-lock 的 completed comparison view 收窄为 base→new 实际移除集合 |
| 连续多次插单的 DRAFT/基线链尚未定义 | 不同加急事实可能引用不再适用的 current 基线 | 当前每个 deterministic run 只接受一个不同加急事件，同命令可精确重放；后续先定义链式语义再开放多次插单 |

## 5. 明确不做

本版本不声称支持多工厂协同、人员与刀具二级容量、竞争性物料分配、批处理、拆分/合并、可抢占加工或序列相关换型。资源选项中的固定准备时间可以进入最终工时，但不能表述为序列相关换型优化。

外部调研采用的权威参考包括 [Google OR-Tools Job Shop 指南](https://developers.google.com/optimization/scheduling/job_shop)、[CP-SAT 状态说明](https://developers.google.com/optimization/cp/cp_solver)、[ISA-95 标准概览](https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard) 和 [MTConnect 文档](https://www.mtconnect.org/documentation)。这些材料用于校准建模术语和界面表述，不替代本仓库的正式契约。

## 6. 当前启动方式

先启动 Demo 后端：

```powershell
uv run python demo/scripts/start_demo.py
```

再开一个终端启动中文前端：

```powershell
npm --prefix demo/frontend ci
npm --prefix demo/frontend run dev
```

访问 `http://127.0.0.1:4174/demo/`。后端只绑定 `127.0.0.1:8765`，Vite 也只绑定本机并通过同源 `/api` 代理访问后端。`POST /api/demo/v1/session` 建立 HttpOnly、SameSite=Strict 的本地 Simulation 会话；token 只保存在被 Git 忽略的 `demo/runtime/session.token`，不进入响应正文、日志或测试快照。当前中文 UI 覆盖 D13 初始化、初排、基线发布与恢复，D14 订单/甘特/计划负荷/校验证据工作区，以及 D15 一键插单、真实重排、DRAFT 比较与刷新恢复。manual retry/cancel 仍保持显式 fail-closed，不伪装为可用能力。
