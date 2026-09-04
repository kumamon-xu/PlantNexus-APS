# CNC Demo 实施任务清单

状态：本地交付候选已验证（TASK-DEMO-09 已正式关闭；D18 等待最终现场机复放）
范围约束：所有新增或修改资产必须位于 demo 目录  
完成定义：通过 [专项基准与验收标准](05-benchmark-and-acceptance.md)的 Gate A～F

## 1. 执行顺序

    D00 契约与边界验证
      ├── D01 工程骨架
      └── D02 数据资产
             └── D03 CNC 生成器
                    └── D04 早期专项基准

    D01 ── D05 组合根/数据库/授权
              └── D06 Job 与 Artifact 基础设施

    D03 + D06 ── D07 初始排产编排
                       └── D08 仿真基线生命周期

    D00 + D03 + D08 ── D09 加急事实与事件
                              └── D10 动态重排编排

    D07 + D10 ── D11 统一展示模型
    D06 + D08 + D09 + D11 ── D12 Demo API
    D12 ── D13 前端故事壳
              ├── D14 排产工作区
              └── D15 加急与比较工作区

    D13 + D14 + D15 ── D16 E2E / 可访问性 / 恢复
    D04 + D16 ── D17 正式专项基准与调优
    D17 ── D18 打包、运行手册与发布审计

D04 是架构可行性门。若 610 工序在候选预算内不能稳定返回已验证可行解，先处理场景或模型问题，再投入完整甘特图和视觉打磨。

当前进度（2026-09-04）：

- D00：5 个契约探针 `PASS`；确认 v1 workspace 不直接接受 PlanningProblem v2、`route_template_id` 不进入 ExecutionEvent、现有重排 Validator 具备 `ADDED` universe 和真实 KPI 注入边界。
- D01：Demo-local Python package、CLI、测试、类型检查和越界保护已完成；当时拆出的 runtime 已由 D05～D12 完成，前端骨架已由 D13 完成。
- D02：严格 JSON 资产、逐文件 SHA-256、聚合资产指纹和三档 golden profile 已完成。
- D03：确定性 Raw Staging 生成器与 DemoIngressPipeline 已完成；Showcase 精确生成 132 单、610 工序、24 设备、1,311 options、42 execution facts 和 12 locks。
- D04：B1/B2 单次 early spike 已完成；其后 D17 已把 B1～B6 扩展为三档各 1 preflight + 1 warmup + 5 measured 的独立进程正式基准，并形成 RSS、浏览器首屏、环境签名与 immutable baseline。最终现场机复跑仍属于 D18。
- D05～D08：独立 SQLite/Simulation 授权、durable job/artifact、初始排产和显式 current `PUBLISHED` 基线均已完成。
- D09～D10：业务加急命令、additive-only Standard Import、正式事件/checkpoint、Snapshot/ReplanRequest、真实 KPI、动态重排、v2 `DRAFT` 与 ChangeReport 已完成；current `PUBLISHED` 不变。
- D11：strict/immutable 的 Factory、v1/v2 统一 Schedule 与 ChangeReport-authoritative Comparison presentation 已完成；所有视图固定为 Simulation-only、`publishable=false`。
- D12：reset、initial-plan、baseline-activation、urgent-orders、job 和 factory/version/comparison 已形成完整演示主路径；授权、稳定错误、ETag/304、active-run/correlation headers 均有回归测试。manual retry/cancel 继续显式 fail closed，不属于 TASK-DEMO-04。
- D13：独立中文故事首页、同源 session、strict consumer contract、job polling/刷新恢复、初排与显式基线发布、键盘路径和 1440/1024 Chromium smoke 已完成。
- D14：中文订单风险表、订单→甘特联动、工厂/车间/设备筛选、72 小时有界甘特、日历/维护/执行/锁定语义、等价表格、计划负荷与校验证据已完成；Showcase 132/580/24 浏览器 smoke 和双宽度页面无溢出通过。
- D15：资产驱动的四路线中文插单表单、只读 current base、二次确认、durable urgent command 恢复、真实 job 阶段、自动 DRAFT 比较、ChangeReport 分类、交付/稳定性/Validator、120 条分页和刷新恢复已完成；Showcase 单次真实链与双宽度页面无溢出通过。
- D16：全新隔离 runtime 的中文 Chromium 完整链、四类业务 mutation 单次提交、双击/刷新、重启中断与原身份重试、stale、并发 reset、受控失败、Simulation 授权、scope、Production binding、token/log/path 消毒、键盘/focus/ARIA/对比度/reduced motion 和双宽度布局均已通过。
- D17：已正式关闭。SMOKE、SHOWCASE、UPPER 共 21 个隔离后端样本和 12 个真实 Chromium 首屏样本已封存；Showcase 7 项阈值、5/5 Validator/ChangeReport、Upper 700 工序 characterization 均 `PASS`，默认 profile、20/30 秒上限和固定加急 fixture 已冻结。最终机器报告保留外部 scope 差异导致的 `FAIL`；用户明确授权不复跑并接受该审计事实。

因此当前结论是 `INITIAL_SOLVE_SCALE_GATE=PASS`、`DYNAMIC_REPLAN_BACKEND_GATE=PASS`、`PRESENTATION_READ_GATE=PASS`、`D13_STORY_SHELL_GATE=PASS`、`D14_WORKSPACE_GATE=PASS`、`D15_REPLAN_UI_GATE=PASS`、`D16_E2E_SECURITY_A11Y_GATE=PASS`、`D17_FORMAL_BENCHMARK_GATE=PASS` 且 `D18_LOCAL_DELIVERY_CANDIDATE=PASS`。M3 已满足，D17 已按用户授权关闭；D18 的本地打包、Runbook、release audit 和真实浏览器恢复演练已完成，但最终现场机身份与复放仍待确认，所以还不是最终 Demo ready。详见 [当前实施状态](IMPLEMENTATION-STATUS.md)、[D17 正式报告](D17-FORMAL-BENCHMARK-REPORT.md)与 [D18 Runbook](D18-DEMO-RUNBOOK.md)。

## 2. 总览

| ID | 优先级 | 任务 | 规模 | 依赖 | 主要产物 |
|---|---|---|---|---|---|
| D00 | P0 | 契约断点验证 | M | 无 | demo/tests/contract |
| D01 | P0 | Demo 工程骨架与边界检查 | M | D00 | demo/backend、demo/frontend |
| D02 | P0 | CNC 场景资产与 golden manifest | M | D00 | demo/data/cnc-showcase |
| D03 | P0 | 确定性 CNC 分层生成器 | L | D02 | demo/backend/.../data |
| D04 | P0 | 610/700 工序早期性能 spike | L | D03 | demo/benchmarks/results |
| D05 | P0 | SQLite 组合根与 Simulation 授权 | L | D01 | demo/backend/.../composition |
| D06 | P0 | durable job、artifact store 与 reset | L | D05 | demo/backend/.../jobs、persistence |
| D07 | P0 | 初始排产编排 | L | D03、D06 | demo/backend/.../application |
| D08 | P0 | 仿真基线批准/发布 | M | D07 | demo backend lifecycle adapter |
| D09 | P0 | 加急命令、标准导入与事件 | L | D00、D03、D08 | urgent orchestration |
| D10 | P0 | 动态重排与 KPI adapter | XL | D09 | replan orchestration |
| D11 | P0 | v1/v2 统一 presentation DTO | L | D07、D10 | demo/backend/.../presentation |
| D12 | P0 | Demo HTTP API | L | D06、D08、D09、D11 | demo/backend/.../api |
| D13 | P1 | 前端故事首页与 job 恢复 | L | D12 | demo/frontend |
| D14 | P1 | 订单、甘特图、负荷与校验视图 | XL | D13、D11 | schedule workspace |
| D15 | P1 | 加急表单与前后比较 | XL | D13、D11 | replan UX |
| D16 | P0 | E2E、安全、恢复与可访问性 | XL | D13～D15 | demo/tests/e2e |
| D17 | P0 | 正式基准、调优与参数冻结 | XL | D04、D16 | immutable baselines |
| D18 | P0 | 一键启动、runbook 与发布审计 | L | D17 | demo/scripts、demo/docs |

规模 S/M/L/XL 表示相对复杂度，不是工期承诺。

## 3. 任务明细

### D00 — 契约断点验证

目标：在写业务代码前用可执行测试确认四个高风险接口。

工作：

- 建立初始 schedule-version.v1 与重排 schedule-version.v2 的最小 fixture。
- 证明现有 P3 workspace reader 拒绝 v2，并把这一行为固化为 demo adapter 的输入测试。
- 构造加急 candidate，验证允许新增该 demand 所需的订单/批次/工序及 routing 引用，同时拒绝任何既有记录、topology、execution fact 或 lock 变更。
- 验证 route_template_id 不属于 execution-event.v1；正式事件仍通过 require_p4_document。
- 用真实 LexicographicReplanStrategy 验证 after KPI capture adapter 的可行方式，禁止预填 dummy KPI。
- 列出批准、发布、Publication current reference 的现有服务和 CAS 条件。

完成条件：

- demo/tests/contract 下测试可单独运行；
- 每个断点有 PASS 证据或明确 fail-closed 结论；
- 若必须改 backend 或 schemas，立即停止相应实现并提出范围变更。

### D01 — Demo 工程骨架与边界检查

目标：建立不会向根工程泄漏新增文件的独立工作区。

工作：

- 创建 demo/backend Python package、demo/frontend Vite/React 工程和 demo/tests。
- 配置只读导入根 backend/app 与必要 frontend 组件。
- 增加边界测试：git diff 中除 demo 外出现路径即失败。
- 增加 demo/runtime/.gitignore，禁止提交数据库、token、日志和 benchmark 临时文件。
- 记录锁定的 Python/Node 依赖来源；优先复用根环境，不复制未锁定依赖。

完成条件：

- 后端 health 与前端空壳可启动；
- 边界测试能捕获故意创建的越界 fixture；
- clean install 文档化且不修改根配置。

### D02 — CNC 场景资产与 golden manifest

目标：把行业假设从代码常量变成可审计资产。

工作：

- 编写 resource catalog、route templates、duration parameters、priority policy、calendar 与 maintenance assets。
- 固定 planning anchor、timezone、tick、seed 与生成器版本。
- 编写精确计数的 golden manifest。
- 给每个资产生成 SHA-256 并在 manifest 互相引用。
- 编写中文名称、说明与 UI copy，标明 Simulation。

完成条件：

- 资产 JSON 有自有严格 schema 或 typed loader；
- 未知字段、重复 resource、非法 capability、非法时区、非 tick 对齐均被拒绝；
- golden manifest 精确表达 132/610/24 和 1,311 options。

### D03 — 确定性 CNC 分层生成器

目标：生成行业化 StagedImportBatch 并只通过标准入口进入系统。

工作：

- 按 topology、calendar、routing、order、material、execution fact、lock 七层实现。
- 使用现有确定性 seed 派生方式；不得使用全局 random 或当前时间。
- 生成 3～6 道混合路线和 1～3 候选设备。
- 计算按数量和设备效率变化的 final duration。
- 生成 30 completed、12 running、568 not-started、18 material delayed、4 hard lock、8 soft lock。
- 复用正式 Mapping、Normalization、Data Validation、Expansion 与 Snapshot 边界；由 demo adapter 显式构建 PlanningProblem v2，因为根 CommonIngressPipeline 默认产出 v1 Problem。
- 保存规范 batch、Snapshot 与 Problem 的 golden fingerprints。

完成条件：

- Gate A 全部通过；
- 相同输入两次输出逐字节一致；
- 任何失败都不换 seed、不降规模；
- 生成器不直接构造 Solver 输入或 ScheduleVersion。

### D04 — 早期专项基准

目标：在完整 UI 前验证默认规模是否成立。

工作：

- 实现 CNC-SMOKE、CNC-SHOWCASE、CNC-UPPER profile。
- 跑 B1 数据导入、B2 初排和 B4 加急重排的命令行 spike。
- 单 worker、固定 seed，记录环境、raw samples、状态、目标、bound、Validator、ChangeReport 和 RSS。
- 至少对 SHOWCASE 做 1 warmup + 5 measured。
- 调整 scripted urgent fixture，使 ADDED、CHANGED 和 UNCHANGED 均非空。
- 输出 baseline candidate，不覆盖现有 P2 baseline。

完成条件：

- 得出 20/30 秒是否可用的证据；
- 若失败，提交原因分析和候选降级规模，不开始 D14/D15；
- 所有输出位于 demo/benchmarks。

### D05 — SQLite 组合根与 Simulation 授权

实施归属：`TASK-DEMO-02`（已完成；Demo 专属，不注册 P7）。P4 append/read 已接真实 repository；依赖尚未生成的 request/attempt 的 cancel/retry 在 D09/D10 前保持 fail closed。

目标：让现有正式路由在 Demo 中有真实 application 与 fail-closed 权限。

工作：

- 构建 engine、迁移和全部 P3/P4 repository。
- 用 RoutedPlanningWorkspaceApplication 绑定需要的查询/控制 handler。
- 用 RoutedDynamicReplanningApplication 绑定事件、request、result、cancel/retry handler。
- 实现 SimulationLocalAuthorizationProvider、scope/capability matrix 和本地 token bootstrap。
- 组合现有 create_app 并挂载 demo router 占位。
- 默认绑定 127.0.0.1。

完成条件：

- 正确 token 能访问白名单 Simulation scope；
- 无 token、错 capability、错 scope、Production 请求全部 fail closed；
- 默认产品 app.py 行为未改变；
- token 不出现在日志、异常、fixture snapshot。

### D06 — Durable Job、Artifact Store 与 Reset

实施归属：`TASK-DEMO-02`（已完成；Demo 专属，不注册 P7）。

目标：提供可刷新恢复的异步编排基础。

工作：

- 实现 control.db、run registry、job repository、artifact repository 和 demo command audit。
- 实现单 worker executor 与阶段状态。
- 进程启动时恢复 QUEUED，把遗留 RUNNING 标记 INTERRUPTED。
- 实现新数据库 reset、迁移、自检、原子 active pointer 切换和有限保留。
- 增加 idempotency、active-job mutex、stale-run CAS。
- 增加失败注入：迁移失败、生成失败、切换前崩溃。

完成条件：

- 刷新/重启后 job 状态可恢复；
- reset 失败时旧 run 仍可读；
- 并发 reset 只有一个成功登记；
- 路径逃逸测试 PASS；
- 所有核心 append-only 表未被清空。

### D07 — 初始排产编排

实施归属：`TASK-DEMO-02`（已完成；Demo 专属，不注册 P7）。

目标：从已初始化场景形成真实 READY_FOR_REVIEW。

工作：

- 实现 InitialPlanningOrchestrator。
- 从 artifact/manifest 读取 priority facts、horizon、tick 和 solve limits。
- 构建 v2 Problem，调用 GlobalCpSatStrategy。
- 严格处理 OPTIMAL、FEASIBLE、INFEASIBLE、UNKNOWN 和无 candidate。
- 重新执行独立 Validator，构建 KPI。
- 调用 ValidatedSolutionToScheduleVersionService.create_reviewable。
- 保存完整 WorkspaceSourceDocuments 所需 artifact。
- 对每个真实阶段写 job evidence。

完成条件：

- Gate B 全部通过；
- FEASIBLE 文案与证据不包含“最优”；
- Validator mutation 阻止版本创建；
- 同 idempotency key 精确重放。

### D08 — 仿真基线批准与发布

实施归属：`TASK-DEMO-02`（已完成；Demo 专属，不注册 P7）。

目标：满足 Replan 的 current PUBLISHED 前置条件。

工作：

- 实现 BaselineActivationService。
- 校验 version id、fingerprint、state revision 和显式 confirmation。
- 调用现有批准与发布生命周期，不直接改状态字段。
- 在每一步后读回 schedule 与 Publication current。
- 实现 APPROVED 后发布失败的可恢复重试。
- 禁止自动激活和静默激活。

完成条件：

- Gate C 全部通过；
- READY_FOR_REVIEW 前加急按钮禁用且原因清楚；
- current Publication 与 exact schedule reference 一致；
- 命令审计包含 demo actor、correlation 和 idempotency reference。

### D09 — 加急命令、标准导入与正式事件

实施归属：`TASK-DEMO-03`（已完成；Demo 专属，不注册 P7）。当前四个已批准路线模板可生成 3～6 道加急工序；同一 deterministic run 的首个不同加急事实可提交，同 key 可精确重放，多次不同插单留给后续链式基线设计。

目标：把业务表单安全转换为标准事实和正式事件。

工作：

- 定义严格 UrgentOrderCommand v1。
- 实现路线模板展开、数量→时长和工厂本地时间→UTC。
- 校验 expected run/base 和 horizon。
- 生成标准 import candidate，运行标准 normalization/Data Validation。
- 调用 urgent candidate validator 并提交新增记录。
- 构造精确 URGENT_DEMAND_RECEIVED，走现有 event append。
- 服务端生成 authority、stream position、fingerprints；前端不传。
- 同一 key 重放不重复增加 demand 或 event。

完成条件：

- Gate D 的事件/事实部分通过；
- route_template_id 仅在 demo audit；
- 旧记录 byte-for-byte 不变；
- schema mutation 全部被拒绝；
- stale base 在任何写入前失败。

### D10 — 动态重排与真实 KPI Adapter

实施归属：`TASK-DEMO-03`（已完成；Demo 专属，不注册 P7）。现有投影器会携带基线前 30 个历史 completed 事实，而版本比较 universe 只含基线 active assignments；Demo 保留 Snapshot 历史锚点原字节，并通过单 worker 范围内的兼容 adapter 仅收窄 effective-lock comparison view，不修改正式投影器或 Validator。

目标：从加急事件形成经过完整验证的 v2 DRAFT 与 ChangeReport。

工作：

- 建立严格 ReplanRequest factory，调用现有 schema validator。
- 投影 checkpoint、新 Snapshot、priority facts 和 effective locks。
- 复用 Simulation 900 秒 freeze policy。
- 实现真实 candidate KPI-capturing strategy adapter。
- 调用 ReplanApplicationService，并测试 first apply 与 exact replay。
- 交叉核对 ScheduleVersion、SolverReport、Validation、KPI、ChangeReport 的 lineage/fingerprint。
- 对 terminal no-candidate 保存诊断但不创建 DRAFT。

完成条件：

- Gate D 全部通过；
- 新版本固定为 DRAFT，PUBLISHED 基线不变；
- completed/running/hard/freeze preservation 有逐项断言；
- ChangeReport operation universe 精确覆盖；
- dummy/stale KPI mutation 被拒绝。

### D11 — v1/v2 统一 Presentation

状态：已完成（TASK-DEMO-04）。

目标：给前端稳定、不可发布的统一只读模型。

工作：

- 定义 DemoScheduleView v1 和 DemoComparisonView v1 JSON contract。
- 分别实现 schedule-version.v1 与 v2 adapter。
- 从规范 artifact 构建订单、层级甘特图、日历、维护和计划负荷。
- 从 ChangeReport 构建完整 operation comparison。
- 从 KPI 构建交付指标；派生指标记录公式和 evidence。
- 增加 artifact/fingerprint mismatch fail-closed。
- 对 610+ 工序实现服务端筛选、排序和必要分页/窗口查询。

完成条件：

- Gate E 的数据部分通过；
- 同一 assignment 在 v1/v2 时区显示一致；
- 所有 change classification 与 ChangeReport 一致；
- publishable 永远为 false；
- DTO 不泄漏 token 或内部异常。

### D12 — Demo HTTP API

状态：演示主路径与只读查询已完成；manual retry/cancel 保持 fail closed。

目标：提供业务化、幂等、可恢复的 API。

工作：

- 实现 bootstrap、state、resets、initial-plans、baseline-activations、urgent-orders。
- 实现 jobs、retry、factory、versions、comparisons 查询。
- 建立 Pydantic strict request/response 与 OpenAPI。
- 所有写请求验证 Idempotency-Key；异步命令返回 202。
- 错误映射使用稳定 Demo error codes。
- 增加 correlation、cache/ETag 和 active run headers。

完成条件：

- API contract tests 覆盖成功、重放、冲突、stale、未授权和失败终态；
- UNKNOWN 不映射为 INFEASIBLE；
- 浏览器无需手填任何底层 identity；
- OpenAPI 示例仅包含合成数据。

### D13 — 前端故事首页与 Job 恢复

状态：已完成（TASK-DEMO-05）。

目标：建立可单页完成主流程的外壳。

工作：

- 实现同源 session bootstrap 和 API client。
- 实现四步 stepper、场景卡、Simulation/版本状态徽标。
- 实现初始化、重置、自动排产、基线激活主操作。
- 实现 job polling、阶段计时、刷新恢复与错误重试。
- 技术证据放入折叠抽屉。

完成条件：

- 从 EMPTY 到 BASELINE_PUBLISHED 可用键盘完成；
- 刷新后恢复相同 run、job 和页面；
- SOLVING 无虚假百分比；
- APPROVED 发布失败状态可恢复。

完成证据：独立 `demo/frontend` 的 lint、typecheck、12 个 Vitest/Testing Library 测试和 production build 均通过；Chromium 真实连接 Demo backend 完成 EMPTY→INITIALIZED→READY_FOR_REVIEW→BASELINE_PUBLISHED，并在刷新后恢复相同 run。主操作与确认可用键盘完成，1440×900 和 1024×768 页面级无横向滚动，控制台 0 error / 0 warning；证据见 `frontend-evidence-demo-05.json`。

### D14 — 排产工作区

状态：已完成（TASK-DEMO-06）。

目标：展示初始计划的业务价值与证据。

工作：

- 实现订单表、风险筛选、订单→甘特图联动。
- 实现工厂/车间/设备层级甘特图。
- 绘制班次、非工作时间、维护、completed/running、hard/soft/freeze。
- 实现计划负荷和瓶颈排序。
- 实现 KPI 与 Validator/Solver evidence panel。
- 采用虚拟滚动或时间窗渲染支撑 610+ 条目。

完成条件：

- 1440×900 主流程清晰；
- 甘特图有等价表格；
- 计划负荷文案明确不是 OEE；
- 大数据视觉测试无明显卡顿或遮挡。

完成证据：`demo/frontend` 的 lint、typecheck、5 个测试文件/26 个测试和 production build 均通过。真实 Chromium 连接固定 Showcase 的 current `PUBLISHED` 基线，读取 132 单、580 assignments、24 设备；默认 72 小时时间窗匹配 546 道、仅挂载 160 个 assignment 节点，观察到 30 个 completed 事实、12 个 running、4 个 hard lock、8 个 soft lock、24 个 freeze 图层、120 个非工作时段块和 2 个当前窗口维护块。订单 `demand-order-cnc-036` 搜索为 1 条并以 GET 聚焦 5 道工序；1440×900 和 1024×768 均无页面级横向滚动，控制台 0 error / 0 warning。证据见 `frontend-evidence-demo-06.json`；性能数字是单次 early evidence，不是 p95 或 SLA。

### D15 — 加急表单与前后比较

状态：已完成（TASK-DEMO-07）。

目标：完成“一键插单—自动重排—新旧比较”故事。

工作：

- 实现与已批准资产一致的路线卡片（当前四个）、数量、交期、优先级和确认摘要。
- 自动带入 current base，但提交时仍做 stale CAS。
- 实现 replan job 阶段与终态文案。
- 成功后自动切换 DRAFT comparison。
- 实现 overlay/上下分屏甘特、分类筛选、偏移表、交付与稳定性卡。
- 显示 ChangeReport 和 Validator PASS/FAIL。

完成条件：

- 不出现 identity 表单；
- scripted fixture 一次完成；
- CHANGED、UNCHANGED、ADDED 都可筛选；
- DRAFT 不被表述为已发布；
- UNKNOWN、INFEASIBLE、Validator FAIL 有正确恢复路径。

完成证据：`demo/frontend` 的 lint、typecheck、5 个测试文件/35 个测试和 production build 均通过。真实 Chromium 连接固定 Showcase current `PUBLISHED`，使用 `CNC-ROUTE-5`、数量 5、北京时间交期 2026-09-09 18:00、URGENT 完成一次业务表单提交；约 21 秒后得到 `FEASIBLE + Validator PASS` 的 v2 `DRAFT`，原 current Publication 不变。比较页展示 5 `ADDED`、25 `CHANGED`、555 `UNCHANGED`、3 次设备变更、3 次软锁偏离和 95.7% 保持比例；保持不变首/次页分别返回 1～120、121～240 / 共 555 道，CMM-01 筛选返回 17 道。刷新恢复同一 run/比较引用且不重复写命令；1440×900 与 1024×768 无页面级横向滚动，控制台 0 error / 0 warning。证据见 `frontend-evidence-demo-07.json`；性能数字是单次 synthetic early evidence，不是 p95、目标机基线或 SLA。

### D16 — E2E、安全、恢复与可访问性

目标：用真实浏览器和真实 SQLite 覆盖完整故事及失败路径。

工作：

- 从空 runtime 运行 reset→initial plan→activate→urgent→comparison。
- 覆盖双击、刷新、重启、stale base、并发 reset、失败注入。
- 覆盖权限、scope、production binding、token/log 消毒和路径逃逸。
- 键盘遍历、focus、ARIA、对比度、非颜色状态表达。
- 1440×900 与 1024 宽视觉回归。
- 验证所有新增/修改文件仍只在 demo。

完成条件：

- Gate F 和 E2E/Visual 矩阵全部通过；
- 没有预录 schedule fallback；
- 截图和测试报告只含合成数据。

完成证据：真实 Playwright CLI/Chromium 从空 Showcase runtime 完成中文 reset→initial plan→activate→urgent→comparison，总计 68/68 浏览器断言，四次业务 mutation 各一次，刷新后 0 次重复 mutation；该次结果为 `FEASIBLE + Validator PASS` 的 v2 `DRAFT`，ChangeReport 为 5 `ADDED` / 23 `CHANGED` / 557 `UNCHANGED`，原 current `PUBLISHED` 不变。独立 API/SQLite Smoke 审计为 50/50，覆盖 concurrent reset 仅一个 durable job、`INTERRUPTED` 原 identity attempt 2 成功、失败 reset 保留 active run、stale/权限/Production/path/token 负向矩阵。汇总证据 39/39、两张截图哈希、控制台 0 error/warning、关键文字对比度和两个宽度 0 页面溢出均 `PASS`；见 `e2e-evidence-demo-08.json`。所有耗时仍只是单次 synthetic 功能证据，不是 D17 p95 或 SLA。

### D17 — 正式专项基准与调优

状态：已完成（TASK-DEMO-09）。未因结果失败而调整规模或阈值；严格 machine report 因共享工作区中非本任务产生的 `demo/**` 外差异保持 `FAIL`，用户明确授权不复跑并正式关闭。

目标：冻结可以如实公开的 Demo 参数。

工作：

- 在目标演示机按协议跑 SMOKE、SHOWCASE、UPPER。
- 保存 raw samples、环境签名、JSON baseline 和 Markdown 摘要。
- 分析 p50/p95/max、RSS、模型大小、状态和 gap。
- 对失败只做有证据的优化；每次参数变化升级 profile/version。
- 冻结 default profile、solve limits 和 scripted urgent fixture。
- 更新 README 中仍为“待验证”的状态。

完成条件：

- SHOWCASE 达到状态与 Validator 强制门；
- 暂定性能门槛明确 PASS 或经评审后版本化调整；
- 700 工序上界有真实 characterization；
- 报告明确 synthetic-only、无 SLA。

完成证据：三档各完成 1 次 preflight、1 次 warmup 与 5 次 measured，共 21 个独立后端进程 raw samples；真实 Chromium 对基线/比较状态各完成 1 次 warmup 与 5 次 measured。Showcase 初排/重排端到端 p95 为 7.517/22.601 秒，RSS p95 277.3 MiB，5 次初排均 `OPTIMAL`，重排为 4 `OPTIMAL` + 1 已验证 `FEASIBLE`，Validator/ChangeReport 5/5 `PASS`；Upper 700 工序初排/重排 p95 为 12.181/32.014 秒且 5/5 `OPTIMAL`。默认 Showcase、20/30 秒限制与 fixture `CNC-DEMO-URGENT-FIXTURE-001` 已冻结；证据见 `demo/benchmarks/baselines/cnc-demo-formal-benchmark.v1/`、`benchmark-evidence-demo-09.json` 和 [中文正式报告](D17-FORMAL-BENCHMARK-REPORT.md)。所有结论 synthetic-only、非 SLA，最终现场机仍待 D18。

### D18 — 一键启动、Runbook 与发布审计

状态：本地候选已验证、最终现场待复放（TASK-DEMO-10 保持 `in_progress`）。

目标：交付不依赖开发者现场手工拼装的 Demo。

工作：

- 编写 demo/scripts 下的启动、停止、health、reset、smoke 命令。
- 启动前检查依赖、迁移、asset hash、端口和 runtime 权限。
- 编写演示人员 runbook、故障恢复、日志位置与清理说明。
- 完成一次冷启动和一次中断恢复彩排。
- 生成发布清单：commit、profile、baseline、fixture、已知限制。
- 审计 git diff，确认没有 demo 外改动和运行产物。

本地完成证据：一键 controller/wrappers 已提供七个中文命令；11 项 delivery 单测及全量 Demo 回归通过。当前候选机完成含 `npm ci` / production build 的 cold ready（约 10.735 秒）、固定 Showcase reset（约 4.718 秒）、两次真实 Chromium `zh-CN / INITIALIZED` smoke、同 runtime restart ready（约 3.234 秒）和 D16 `INTERRUPTED → same identity attempt 2 SUCCEEDED` 复核。版本化 manifest 与 release audit 已闭合 Demo-only inventory、locks、D16/D17/D18 evidence、共享工作区外部差异和安全边界；本地结论为 `LOCAL_CANDIDATE_VERIFIED`。

机器门结果：3/3 benchmark checks、13/13 commands 及全部 context/artifact/hygiene 检查通过，`functional_status=PASS`；总状态因 5 个受保护根文档的共享工作区外部变化保持 `FAIL / SCOPE_CHECK`。D18 未获得范围豁免，不把本地候选审计 PASS 改写成任务机器 PASS。

完成条件：

- 新 checkout 按文档一条命令启动；
- 一键重置恢复固定场景；
- 用户确认的目标演示机 smoke PASS；
- 文档中的数量、状态和性能数字与最新 baseline 一致；
- 发布结论仅为 CNC Simulation Demo ready。

当前剩余条件：最终现场机尚未由用户确认，`target_site_status=PENDING_FINAL_SITE_REPLAY`；D18 因此不正式关闭，不把当前本地候选机冒充最终现场，也不把单次交付时延当作 Solver 或 Production SLA。

## 4. 建议里程碑

### M1：模型与规模可行

包含 D00～D04。退出条件是 610 工序 early spike 有真实结论。

### M2：无 UI 的完整业务链

包含 D05～D12。退出条件是 API 可完成重置、初排、发布、加急、重排和比较。TASK-DEMO-04 已满足该主路径退出条件；manual retry/cancel 是保留的显式不可用边界。

### M3：可讲解的现场体验

包含 D13～D16。退出条件是标准演示脚本和失败恢复 E2E 通过。

状态：已满足。D16 已从空 runtime 走通中文业务主线，并完成恢复、安全、可访问性和双宽度证据闭环。

### M4：可重复交付

包含 D17～D18。退出条件是专项基准、脚本化 fixture、runbook 与目标机 smoke 齐全。

状态：本地条件已满足、最终现场条件待满足。D17 的专项基准、脚本化 fixture 和参数冻结已完成并正式关闭；D18 的一键交付、Runbook、本地真实 Chromium smoke、重启恢复、manifest 与 release audit 已通过。最终现场机仍待用户确认并复放，故 M4 尚未最终关闭。

## 5. 不得作为“完成”的捷径

- 在 demo 中复制或简化 CP-SAT/Validator 来绕过正式模块；
- 直接写 Snapshot、Problem、ScheduleVersion 或 ExecutionEvent JSON 而不走标准入口；
- 把 route_template_id 加入 execution-event.v1；
- 用浏览器计算权威 KPI 或 ChangeReport 分类；
- 自动批准/发布初始版本；
- 把动态重排 DRAFT 自动发布；
- 用预录 schedule 替代本次失败的 live solve；
- 通过减小运行数据却保留 132/610 展示文案；
- 以现有 12 单 baseline 宣称百单性能；
- 修改 demo 目录外的代码而不单独获得范围授权。
