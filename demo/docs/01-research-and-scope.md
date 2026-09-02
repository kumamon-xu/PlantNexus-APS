# 调研、边界与设计决策

调研日期：2026-09-02

## 1. 调研方法

本设计同时检查了四类证据：

1. 仓库内正式 JSON Schema、domain contract 和状态机。
2. 后端组合根、导入链、求解、Validator、持久化和动态重排实现。
3. 前端运行时、工作台契约和当前重排页面。
4. 官方行业与求解器资料，用于校准术语、信息架构和状态文案。

结论只覆盖 Simulation 合成数据。当前项目阶段文件明确缺少真实业务数据、真实接入和 P7 性能证据，因此本文不产生生产容量、性能或可上线结论。

## 2. 行业适配结论

精密机械零部件 / CNC 机加工是当前能力最匹配的演示行业，原因如下：

- 一个订单可自然映射为一件或一批零件，按既定路线经过 3～6 道有前后关系的加工与检测工序。
- 同类 CNC 设备可作为候选资源；不同设备允许具有不同最终加工时长。
- 班次、周末、保养停机可映射为资源日历不可用窗口。
- 毛坯或外协件到齐时间可映射为 material-ready 约束，但当前不应解释为库存分配。
- 已完成、正在加工、硬锁、软锁与冻结窗口可表达滚动计划中的稳定性边界。
- 加急单会同时影响交付目标与现有作业稳定性，正好适合展示六层字典序重排和 ChangeReport。

[Google OR-Tools 的 Job Shop 说明](https://developers.google.com/optimization/scheduling/job_shop)把问题描述为有序任务链、机器互斥和可存在多个合法排程，这与本项目的工序 precedence 和 unary resource 约束一致。[ISA-95](https://www.isa.org/standards-and-publications/isa-standards/isa-95-standard)提供了企业、工厂、区域/车间和设备层级的通用语义，因此 Demo 使用工厂→车间→设备层级，但不宣称实现完整 ISA-95。

## 3. 仓库现状与证据

| 能力 | 仓库证据 | Demo 判断 |
|---|---|---|
| 默认 API 组合 | [app.py](../../backend/app/api/app.py#L89)在未注入时使用 Unavailable workspace、replanning 和 authorization provider | 需要 demo 独立组合根 |
| 默认前端会话 | [main.tsx](../../frontend/src/main.tsx#L17)注入 unavailableSessionProvider；[runtime.ts](../../frontend/src/api/runtime.ts#L63)仅在显式 E2E 开关下允许 Simulation | 需要 demo 本地会话与运行时 |
| 标准导入 | [CommonIngressPipeline](../../backend/app/application/import_pipeline.py#L76)证明统一的 Staging/Normalization/Validation/Expansion/Snapshot 顺序，但其默认 Problem 是 v1；合成生成器可产出 StagedImportBatch | Demo 继续复用这些公开边界，并在 demo adapter 中显式调用 `build_planning_problem_v2`，不复制规则 |
| 合成数据 | [package_generator.py](../../backend/app/simulation/generators/package_generator.py#L439)已有确定性分层生成器 | 可复用结构和映射，但不能直接复用数据形态 |
| 当前生成器深度 | [contracts.py](../../backend/app/simulation/generators/contracts.py#L460)要求 generator v1 的 routing depth 等于一次选定的 operation count | 无法直接表达同包内 3～6 道混合路线 |
| 初始求解 | [GlobalCpSatStrategy](../../backend/app/planning/strategies/global_cp_sat.py#L93)执行 CP-SAT 和独立 Validator | 直接复用，不能绕过 Validator |
| v2 问题构建 | [builder.py](../../backend/app/planning/problem/builder.py#L1028)提供 build_planning_problem_v2 | 初排与重排都以 v2 问题语义为准 |
| 初始版本构建 | [schedule_versions.py](../../backend/app/application/schedule_versions.py#L123)可从已验证解创建可评审版本 | 初排输出 READY_FOR_REVIEW |
| 动态重排 | [ReplanApplicationService](../../backend/app/application/replan_application.py#L429)实现事件投影、重排和持久化 | 复用服务，由 demo 编排器提供完整输入 |
| 重排基线 | [replan_application.py](../../backend/app/application/replan_application.py#L669)要求基线为 PUBLISHED | 必须加入显式基线激活步骤 |
| 冻结窗口 | [freeze_window.py](../../backend/app/planning/policy/freeze_window.py#L37)定义 Simulation 900 秒窗口 | Demo 复用 15 分钟，不另造策略 |
| 事件契约 | [execution-event.schema.json](../../schemas/json/execution-event.schema.json#L168)规定加急事件只有订单、数量、交期和优先级等字段 | 路线模板是 demo command，不写入事件 |
| 现有重排 UI | [ReplanningWorkspacePage.tsx](../../frontend/src/features/replanning/ReplanningWorkspacePage.tsx#L35)要求多项底层 identity | 需要业务化一键插单表单 |
| 工作台版本 | [workspace_contracts.py](../../backend/app/domain/workspace_contracts.py#L52)和[前端 contracts.ts](../../frontend/src/api/contracts.ts#L200)固定读取 schedule-version.v1 | v2 重排结果需要 demo presentation adapter |
| SQLite | [config.py](../../backend/app/infrastructure/config.py#L73)和多组 integration tests 支持 SQLite | 可用于单机演示专用数据库 |

## 4. 可直接使用的约束

当前 CP-SAT 与 Validator 能覆盖本演示所需的核心语义：

- 所有待排工序都有且只有一个资源与时间区间。
- 同一订单的工序遵守先后关系。
- 每台 unit-capacity 设备上的工序不重叠。
- 工序只能选择声明的候选设备。
- 设备日历和计划维护窗口限制可用时间。
- 订单 release、物料到齐时间限制最早开工。
- 已完成和正在加工工序按执行事实投影。
- 硬锁、软锁和冻结窗口按现有策略处理。
- 跨车间后继工序可包含运输时间。
- 订单交期、显式优先级、加工时长和 horizon 进入问题。

这些能力足以讲清“从可行生产计划到加急扰动后的稳定重排”，但不等同于完整 MES、ERP 或高级工艺规划系统。

## 5. 明确的能力边界

演示中禁止使用下列表述或暗示：

| 不支持或未证明 | 演示中的替代表述 |
|---|---|
| 人员、刀具、夹具等二级容量优化 | 本场景只调度主设备；工艺能力已预先编码到候选设备 |
| 库存竞争与物料分配 | 只使用每单物料到齐时间 |
| 序列相关换型矩阵 | 只使用已计入 final duration 的固定准备时间 |
| 批处理、拆分、合并、可抢占 | 每个工序作为不可抢占任务 |
| 多工厂协同 | 单工厂、三个车间 |
| 设备实际利用率或 OEE | 展示计划负荷，不展示实际绩效 |
| 生产级吞吐与 SLA | 仅展示当前机器、当前版本、当前合成数据的实测 |
| FEASIBLE 等于最优 | FEASIBLE 只表示找到并验证可行 |

[MTConnect 文档](https://www.mtconnect.org/documentation)说明标准化设备数据可服务监控和分析。当前 Demo 没有接入真实设备数据，所以计划甘特图和计划负荷必须与实际状态、OEE 清楚分开。

## 6. 关键设计决策

### D-001：所有新增资产留在 demo

新增后端、前端、数据、测试、基准、脚本和文档全部位于 demo。Demo 可以导入现有 Python 模块、复用现有 TypeScript 组件或调用正式 API，但不修改 backend、frontend 和 schemas。

如果实施时发现必须修改核心契约或产品代码，应暂停该项工作并单独申请范围扩展，不得把修改悄悄混入 Demo。

### D-002：独立 Simulation 组合根

Demo 后端组合根向现有 create_app 注入：

- 实际 PlanningWorkspace application adapter；
- 实际 DynamicReplanning application adapter；
- 仅本地 Simulation 的 authorization provider；
- SQLite 仓储、迁移与演示 artifact store；
- demo 专用编排 router 和单 worker job runner。

这样既能复用正式路由，也不改变默认 fail-closed 行为。

### D-003：业务命令与正式事件分离

加急表单提交 demo command，包含 route_template_id、quantity、due_at_local 和 priority_class。服务端先把路线模板展开为标准导入记录，再追加严格符合 execution-event.v1 的 URGENT_DEMAND_RECEIVED 事件。

route_template_id 只进入 demo 审计和幂等指纹，不扩展正式事件 payload。

### D-004：统一演示只读模型

初始工作台读取 v1，而重排产生 v2。Demo 不改变两者，而是在服务端构建版本无关的 presentation DTO：

- 从 v1 或 v2 ScheduleVersion 提取规范 assignment；
- 从对应 PlanningProblem、KPI、Validator 和 ChangeReport 生成页面数据；
- 前后比较以 ChangeReport 的 UNCHANGED、CHANGED、ADDED、REMOVED_BY_FACT 为权威分类；
- DTO 明确 publishable=false，不能被误用为正式发布载体。

### D-005：重置采用新数据库，不删除事件历史

执行重置时创建新的 SQLite 数据库文件、运行迁移和固定种子初始化，再原子切换活动 run。旧 run 作为有限保留的本地归档，不在 append-only 核心表中做破坏性删除。

重置只允许在没有活动 job 时执行；所有路径必须解析并验证位于 demo/runtime 下。

### D-006：真实的粗粒度进度

当前求解 API没有可靠的目标轮次进度回调。Demo 只报告已实际到达的阶段和该阶段耗时；SOLVING 阶段使用经过时间而不是完成百分比。任何更细进度都必须以后端新增正式 progress port 为前提。

### D-007：显式激活仿真基线

初始自动排产完成后显示 READY_FOR_REVIEW。演示人员点击“设为仿真基线”才执行批准和发布状态迁移。重排服务随后以该 PUBLISHED 版本为基线，新版本保持 DRAFT，不自动批准。

若批准成功而发布失败，系统展示可恢复的 APPROVED 状态并允许重试发布，不重新求解。

## 7. 本阶段产出边界

本文最初只形成设计文档与实施任务清单。2026-09-02 已在 `demo` 内完成 TASK-DEMO-01 基础切片，没有修改现有产品代码，也没有把 Demo 注册为 P7 证据；新增结论仅为 610/700 工序 synthetic initial-solve 单次 early spike。后续仍须按照 [专项基准与验收标准](05-benchmark-and-acceptance.md)逐门通过，当前实测边界见 [实施状态](IMPLEMENTATION-STATUS.md)。
