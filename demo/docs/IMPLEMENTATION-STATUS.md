# CNC Demo 当前实施状态

状态日期：2026-09-04
最新完成任务：TASK-DEMO-08
任务族：demo-exclusive（不注册 P7，不改变根项目阶段）  
结论：固定数据、初排规模门、durable runtime、显式 current `PUBLISHED` 基线、加急事实到 v2 `DRAFT`、v1/v2 统一展示 API、中文 D13 故事首页、D14 初始排产工作区、D15 加急比较和 D16 完整浏览器 E2E/安全/恢复/可访问性矩阵均 `PASS`；D17 正式性能基线仍开放

## 1. 已交付闭环

- TASK-DEMO-01：严格行业资产、固定 CNC 生成器、标准 import/validation/expansion/Snapshot/Problem v2 链、Solver/Validator benchmark 和契约 probes。
- TASK-DEMO-02：Demo-only `control.db`、per-run SQLite、根 Alembic `head`、Demo 辅助 migration、run/job/stage/idempotency/artifact/command audit persistence。
- TASK-DEMO-03：严格 `UrgentOrderCommand v1`、四个批准路线模板的确定性展开、additive-only Standard Import candidate、精确 `URGENT_DEMAND_RECEIVED`、event projection/checkpoint、新 Snapshot/ReplanRequest、真实六轮 CP-SAT 重排、fresh Validator、before/after KPI 和 ChangeReport。
- TASK-DEMO-04：strict/immutable `DemoFactoryView v1`、统一 `DemoScheduleView v1` 与 `DemoComparisonView v1`；规范 artifact/lineage fail-closed reader；服务端筛选、稳定排序、500 条分页、UTC 半开窗口；展示 GET API、ETag/304 和 read-only invariant。
- TASK-DEMO-05：独立 Vite/React 中文故事首页、同源 cookie session、strict runtime response guards、服务端故事恢复、真实 job polling、中文 Solver/Validator/KPI、显式仿真基线确认、持久化命令身份、折叠技术证据，以及 1440/1024 Chromium smoke。
- TASK-DEMO-06：完整 Factory/Schedule 前端 guards、GET-only 查询 client、中文订单风险表、订单→甘特联动、层级与时间窗筛选、日历/维护/执行/锁定/冻结双编码、等价明细、服务端计划负荷排序、中文求解/校验/关键指标证据，以及 Showcase 132/580/24 的有界 Chromium smoke。
- TASK-DEMO-07：bootstrap 资产配置与 durable comparison 引用、完整 Urgent/Comparison 前端 guards、持久化插单身份、四路线中文业务表单与二次确认、真实重排 Job、自动 PUBLISHED→DRAFT 比较、ChangeReport/交付/稳定性/Validator、120 条服务端分页，以及刷新恢复和双宽度 Chromium 证据。
- TASK-DEMO-08：隔离具名 runtime、完整 API/SQLite 安全与恢复审计、中文 Chromium 空状态到比较页、同步防重入与 pending job 恢复、`INTERRUPTED` 同 identity 重试、共享模态焦点管理、ARIA 引用闭合、关键对比度、reduced motion、双宽度布局、日志/token 消毒，以及指纹化汇总证据。
- Reset：新数据库迁移、自检后以 active-run CAS 切换；失败不替换旧 run；仅清理路径验证后的过期非活动 run，默认保留最近 3 个。
- Job：单 worker、最大并发 1、QUEUED 以原 identity 恢复、遗留 RUNNING/CANCELLING 标记 INTERRUPTED、同 key 精确重放、不同输入冲突、stale run 与 active-job mutex；INTERRUPTED 可在相同 job identity 上显式进入下一 attempt。
- 授权：本地 HttpOnly cookie session、SimulationLocalAuthorizationProvider、capability/scope 检查和拒绝审计；错 token/capability/scope 与 Production 均 fail closed。
- 初排：正式 `GlobalCpSatStrategy`、批准的 Simulation policy/limits、再次独立 Validator、KPI，以及 `ValidatedSolutionToScheduleVersionService.create_reviewable`。
- 基线：显式 `ACTIVATE_SIMULATION_BASELINE` 确认，正式 APPROVE/PUBLISH 服务，APPROVED 后发布失败可沿同一身份恢复，current Publication 精确读回。
- 加急写前校验：active run、expected run/current base、`PUBLISHED` 状态、horizon、时区、数量、模板与 candidate 都在正式 command-side 写入前 fail closed。
- 动态重排：同 key formal replay 不重复 event/checkpoint/request/attempt/result/version；新版本固定为 v2 `DRAFT`，current `PUBLISHED` 的 ID 与 fingerprint 不变。
- HTTP：独立 create_app 组合根与 `/api/demo/v1` 的 session、bootstrap、state、resets、initial-plans、baseline-activations、urgent-orders、jobs、factory、versions、comparisons；默认产品 app.py 不变。
- Presentation：v1/v2 共享同一 Schedule DTO；工厂层级/日历/维护来自 approved assets 与 Snapshot，订单指标来自 KPI，变更分类来自通过正式 query service 校验的 ChangeReport；所有视图固定 `SIMULATION`、`publishable=false`。
- P4 装配：ExecutionEvent、projection checkpoint、ReplanRequest/attempt/result 与 audit 均接真实 repository；Demo manual cancel/retry 仍明确 `SERVICE_UNAVAILABLE`。

所有新增和修改仍限定在 `demo/**`。进入 Demo 实现前已有的 10 个非 Demo 工作区文件继续由 SHA-256 基线保护。

## 2. Showcase 端到端证据

证据：`demo/build/validation/runtime-evidence-demo-02.json`。

| 项目 | 实测结果 |
|---|---|
| 场景 | CNC-DEMO-SHOWCASE / seed 20260902 |
| 输入规模 | 132 单 / 610 总工序 / 580 active / 24 设备 |
| active resource options | 1,253 |
| Reset job | SUCCEEDED / 10 stages / exact replay PASS |
| Initial-plan job | SUCCEEDED / 10 stages / exact replay PASS |
| Solver | OPTIMAL（仅限本 synthetic instance） |
| 独立 Validator | PASS / 0 hard violations |
| 规范 artifact | 7 类：Quality、Snapshot、Problem、Solution、SolverReport、Validation、KPI |
| 初始版本 | READY_FOR_REVIEW / state revision 1 |
| 激活后版本 | PUBLISHED / state revision 3 |
| Publication current | version id 与 content fingerprint 精确一致 |
| Activation replay | PASS |
| 最终故事状态 | BASELINE_PUBLISHED |

本次完整 harness 耗时约为 reset 2.74 秒、initial-plan 6.22 秒、activation 0.19 秒；其中 initial-plan 包含重新生成、标准 ingress、求解、Validator、KPI、artifact 和版本事务，不能与 TASK-DEMO-01 单独 Solver total 直接等同。

## 3. Showcase 加急动态重排证据

证据：`demo/build/validation/runtime-evidence-demo-03.json`。

| 项目 | 实测结果 |
|---|---|
| 基线与插单 | 132 个初始订单、580 个基线 active assignments；新增 1 个 demand、5 道工序 |
| 正式事件 | 1 条 `URGENT_DEMAND_RECEIVED` / exact schema PASS / `route_template_id` 与 note 不在 payload |
| Projection | 1 checkpoint；12 running、4 explicit hard、8 freeze-derived hard、8 soft 均有证据 |
| 历史 completed | 基线前 30 道 completed Snapshot tuples byte-for-byte 保留 |
| Replan Solver | FEASIBLE（不称为最优） |
| 独立 Validator | PASS |
| 新版本 | schedule-version.v2 `DRAFT` |
| current Publication | 原 PUBLISHED version id/fingerprint 不变 |
| ChangeReport universe | 585 = 5 ADDED + 23 CHANGED + 557 UNCHANGED |
| 稳定性 | 580 个可比较既有工序中 557 未变化；2 次设备变化、3 次软锁违反 |
| Durable lineage | event/checkpoint/request/request-event/attempt/result 各 1，schedule versions 共 2 |
| Formal replay | exact replay PASS；未增加第二套 lineage |
| Urgent job | SUCCEEDED / 10 个真实阶段 / 约 24.16 秒 |
| 最终故事状态 | DRAFT_COMPARISON_READY |

本次 urgent job 包含标准导入、event append、projection、request、求解、fresh Validator、KPI、ChangeReport、事务提交与 artifact。它是当前开发机上的单次 synthetic early evidence，不是 warmup + 5、p95、目标机基线、生产容量或 SLA。

## 4. Showcase 展示读取证据

证据：`demo/build/validation/runtime-evidence-demo-04.json`。

| 项目 | 实测结果 |
|---|---|
| Factory | 3 车间 / 7 设备组 / 24 设备 / 6 个维护事件 / 462 unavailable intervals |
| v1 基线 | `PUBLISHED` / 132 单 / 580 assignments / `OPTIMAL` / Validator `PASS` |
| v2 新方案 | `DRAFT` / 133 单 / 585 assignments / `OPTIMAL` / Validator `PASS` |
| Schedule 分页 | v1 为 500+80；v2 为 500+85 |
| ChangeReport universe | 585 = 5 `ADDED` + 22 `CHANGED` + 558 `UNCHANGED` |
| 默认比较 | 同时包含 `ADDED` 与 `CHANGED`；8 个受影响订单 |
| 稳定性 | 580 个可比较既有工序中 558 未变化；unchanged ratio 0.9621 |
| 确定性 | 重复 comparison query 的 view fingerprint 一致 |
| 只读性 | 读取前后 7 类关键表计数、故事状态与 current Publication 均不变 |
| 契约 | 3 个 strict schema；根 `additionalProperties=false`；全部 `publishable=false` |

单次服务端构建为 Factory 0.317 秒、v1 首页 0.383 秒、v2 首页 0.562 秒、默认比较 0.898 秒、全量比较首页 0.930 秒；相应 JSON 为 149,658、653,182、656,621、42,895、714,477 bytes。本次运行环境是 Python 3.12.13、OR-Tools 9.15.6755、Windows 11、32 logical CPUs。它没有 warmup + 5、p95、浏览器渲染或 RSS，只能作为 early evidence；不构成 SLA。

## 5. 中文故事首页与浏览器证据

证据：`demo/build/validation/frontend-evidence-demo-05.json`，截图位于 `demo/build/validation/screenshots/`。

| 项目 | 实测结果 |
|---|---|
| 前端范围 | 独立 `demo/frontend`，不修改根 `frontend` |
| 默认语言 | `zh-CN`；业务状态、错误、Solver/Validator 说明均为中文 |
| 真实故事链 | EMPTY → INITIALIZED → READY_FOR_REVIEW → BASELINE_PUBLISHED |
| 服务端恢复 | 刷新后仍为同一 run 与已发布仿真基线 |
| 键盘 | 初始化、自动排产、打开确认、确认发布均可用 Enter；对话框确认按钮自动聚焦 |
| Job 反馈 | 真实阶段、经过时间与 solve limit；不显示虚假百分比 |
| 发布安全 | 服务端 revision/fingerprint + 原幂等身份；响应契约异常 fail closed |
| 结果文案 | Smoke 实例 `OPTIMAL`、独立 Validator `PASS`、0 hard violations |
| 响应式 | 1440×900 与 1024×768 的 client width 等于 scroll width |
| 浏览器控制台 | 0 error / 0 warning |
| 可见凭证检查 | 页面正文不含 `Bearer` 或 `Authorization`；技术证据不包含 token |
| TASK-DEMO-05 当时边界 | D15 主按钮当时明确为“下一阶段”且禁用；已由 TASK-DEMO-07 接续完成 |

本次 Chromium smoke 使用 24 单、108 工序、12 台设备的固定 Smoke profile，以验证交互链、恢复和布局；它不是 D14 的 500+ 甘特渲染证据，也不是性能基线或 SLA。

### 5.1 初始排产工作区与浏览器证据

证据：`demo/build/validation/frontend-evidence-demo-06.json`，截图位于 `demo/build/validation/screenshots/`。

| 项目 | 实测结果 |
|---|---|
| 场景 | Showcase current `PUBLISHED` / 132 单 / 580 assignments / 24 设备 |
| 四视图 | 订单与交期、排程甘特、计划负荷、校验与证据 |
| 默认请求 | 72 小时时间窗 / `ORDER_START_ASC` / `limit=160` / GET |
| 甘特节点 | 160 assignments；30 completed；12 running；4 hard lock；8 soft lock |
| 日历图层 | 24 freeze、120 非工作时段、2 个当前窗口维护块 |
| DOM | 1,173 节点；未同时挂载 580 assignments |
| 订单联动 | `demand-order-cnc-036` 搜索 1 条，GET 聚焦 5 道工序 |
| 计划负荷 | 24 行，`GRD-01` 为当前计划负荷最高；明确不是 OEE |
| 校验证据 | `OPTIMAL` / Validator `PASS` / 0 hard violations / Simulation-only |
| 响应式 | 1440×900 与 1024×768 页面级无横向滚动；窄屏甘特内部滚动 |
| 浏览器控制台 | 0 error / 0 warning |

一次 fresh Showcase navigation 的 Factory/工作区 payload 为 149,658/305,326 bytes，工作区响应结束于导航后约 1,438.4 ms。这是一个样本的 early evidence，不是 warmup + 5/p95、目标演示机、独立 RSS、Production capacity 或 SLA。

### 5.2 加急重排与版本比较浏览器证据

证据：`demo/build/validation/frontend-evidence-demo-07.json`，截图位于 `demo/build/validation/screenshots/`。

| 项目 | 实测结果 |
|---|---|
| 场景与基线 | Showcase current `PUBLISHED` / 132 单 / 580 个可比较既有工序 |
| 中文业务输入 | `CNC-ROUTE-5` 精密套筒类 / 数量 5 / 2026-09-09 18:00 北京时间 / URGENT |
| 路线资产 | 仅展示批准的 `CNC-ROUTE-3`～`CNC-ROUTE-6` 四张中文路线卡 |
| 提交安全 | current base 只读；技术 identity 隐藏；二次确认；`Idempotency-Key`；仅 1 次 urgent POST |
| Job | 10 个真实阶段 / 约 21 秒总耗时 / 求解阶段 14.235 秒 / 30 秒上限 |
| 结果 | `FEASIBLE`（未称最优）/ Validator `PASS` / 0 hard violations / v2 `DRAFT` |
| Publication | 原 `PUBLISHED` ID 保持不变；新 DRAFT parent 精确指向该基线 |
| ChangeReport | 585 = 5 `ADDED` + 25 `CHANGED` + 555 `UNCHANGED` |
| 稳定性 | 95.7% 既有工序保持不变；3 次设备变更；3 次软锁偏离；累计开始偏移 3,027,000 秒 |
| 交付 | 132→133 单，前后按期率均为 100%，延期订单均为 0，makespan +3,000 秒 |
| 有界比较 | 默认变化页 30 道；保持不变页 `limit=120`，翻页到 121～240 / 共 555；CMM-01 筛选 17 道 |
| 刷新恢复 | 同一 run、DRAFT 和 comparison reference 自动恢复；active job 为空；0 次重复 mutation |
| DOM | 默认 30 张工序卡 / 比较区域 728 个节点，未同时挂载 585 张卡 |
| 响应式 | 1440×900 与 1024×768 页面级无横向滚动 |
| 浏览器控制台 | 0 error / 0 warning |

单次重读变化页/保持不变页分别约 1,168.9/808.5 ms，对应 47,686/176,479 bytes。这些数字连同 21 秒 Job 都是当前开发机的单次 synthetic early evidence，不是 warmup + 5/p95、目标演示机、独立 RSS、Production capacity 或 SLA。不同 TASK-DEMO-03/04 证据文件来自各自独立 fixed-seed 求解运行，CP-SAT 在时间预算内可得到不同但均经 Validator 验证的可行排程；不得把各报告的 CHANGED/UNCHANGED 数直接混成同一次运行。

### 5.3 D16 E2E、安全、恢复与可访问性证据

证据：`demo/build/validation/e2e-evidence-demo-08.json`；原始输入为 `e2e-audit-demo-08.json` 与 `browser-e2e-observation-demo-08.json`，截图位于 `demo/build/validation/screenshots/`。

| 项目 | 实测结果 |
|---|---|
| 真实中文主线 | 空 runtime → reset → initial plan → activate → route 5 / quantity 5 urgent → comparison |
| 业务写请求 | `RESET / INITIAL_PLAN / ACTIVATE / URGENT_REPLAN` 各一次；双击与刷新未产生重复 mutation |
| 浏览器结果 | `FEASIBLE + Validator PASS` / v2 `DRAFT` / current `PUBLISHED` 不变 |
| ChangeReport | 585 = 5 `ADDED` + 23 `CHANGED` + 557 `UNCHANGED` |
| API/SQLite 审计 | 50/50；完整 Smoke 主线、stale、授权、Production、并发、重启、失败和路径矩阵 |
| 并发 reset | 一个 `ACCEPTED`、一个 `ACTIVE_JOB_CONFLICT`；仅一个 durable job |
| 重启恢复 | 遗留执行任务为 `INTERRUPTED / PROCESS_INTERRUPTED`；同 job identity attempt 2 `SUCCEEDED` |
| 失败 reset | candidate `FAILED / RESET_FAILED`；旧 active run 保持不变 |
| 浏览器断言 | 68/68；控制台 0 error/warning；页面不含凭证、本机路径或 Traceback |
| 可访问性 | 28 个可交互控件均有名称；0 重复 ID；0 悬空 ARIA 引用；标题无跳级；状态均有文字 |
| 对比度/动效 | 八组关键文字达到 WCAG AA 阈值；reduced motion 为单次 0.01 ms、取消平滑滚动 |
| 响应式 | 1440×900 与 1024×768 页面级横向溢出均为 0；两张截图哈希通过 |
| 汇总证据 | 39/39 assertions；24 个实现源文件 SHA-256；跨报告 fingerprint 闭合 |

本次真实浏览器整链约 79.89 秒，独立 API Smoke 审计约 14.45 秒。它们是单次 synthetic 功能/恢复证据；求解状态可能在相同时间预算内为 `OPTIMAL` 或经 Validator 验证的 `FEASIBLE`。这些 wall time 不形成 warmup + 5、p95、目标机性能、Production capacity 或 SLA。

## 6. 固定数据与早期规模门

Showcase 固定为 132 个订单、610 道工序、30 已完成、12 正在加工、568 未开始、24 台设备、1,311 个 source resource options、96/29/7 普通/重点/加急订单、18 个物料延迟订单、4 个硬锁、8 个软锁、10 天 horizon、300 秒 tick。

TASK-DEMO-01 当前开发机单次结果仍为：Showcase 20 秒预算下 solve 2.427 秒、Solver total 2.924 秒、`OPTIMAL`、Validator `PASS`；Upper 700/665 工序在 30 秒预算下 solve 6.304 秒、total 6.947 秒、`OPTIMAL`、Validator `PASS`。它们不是 warmup + 5、RSS、目标机或 Production SLA 证据。

## 7. 验证状态

- `uv run pytest demo/tests -q`：40 passed。
- `uv run ruff check demo/backend demo/scripts demo/tests`：PASS。
- `uv run pyright -p demo/pyrightconfig.json`：0 errors。
- `git diff --check -- demo`：PASS。
- Demo contract probes：5/5 PASS。
- Showcase TASK-DEMO-03 dynamic-replan evidence：PASS。
- Showcase TASK-DEMO-04 presentation evidence：PASS。
- TASK-DEMO-05 frontend evidence：19/19 assertions、3/3 screenshots PASS。
- TASK-DEMO-06 workspace evidence：30/30 assertions、5/5 screenshots PASS。
- TASK-DEMO-07 replan frontend evidence：42/42 assertions、3/3 screenshots PASS。
- TASK-DEMO-08 API/SQLite audit：50/50 assertions PASS。
- TASK-DEMO-08 browser E2E：68/68 assertions、2/2 screenshots PASS。
- TASK-DEMO-08 aggregate evidence：39/39 assertions PASS。
- `npm --prefix demo/frontend run lint`：PASS。
- `npm --prefix demo/frontend run typecheck`：PASS。
- `npm --prefix demo/frontend run test:run`：5 files / 36 tests PASS。
- `npm --prefix demo/frontend run build`：PASS。
- 根受保护文件 hash 与 Demo-only scope：由 TASK-DEMO-08 machine report 复核。

新增 TASK-DEMO-04 测试覆盖 strict schema/unknown fields、Factory 层级与资产计数、v1/v2 时间语义、KPI provenance、负荷公式、稳定筛选/排序/分页/窗口、ChangeReport 精确分类、artifact mutation fail closed、ETag/304、缺权限/越权 scope/not-found、OpenAPI strict response 和读取前后状态不变。

新增 TASK-DEMO-05 测试覆盖响应契约 fail closed、同源 credentials/session、幂等命令 payload、原始异常消毒、EMPTY 初始化、active job 刷新恢复、无虚假百分比、基线确认 revision/fingerprint、发布后读取失败沿同一 identity 恢复、键盘焦点与 Escape。真实浏览器另覆盖本地后端主链、刷新、两个目标宽度、控制台和可见凭证检查。

新增 TASK-DEMO-06 测试覆盖完整 Factory/Schedule contract guards、query 编码与 200 条上限、订单风险筛选、时间窗/刻度/裁剪、订单联动、层级筛选、计划负荷非 OEE 文案、求解与校验中文证据，以及 loading/error/recovery。真实 Showcase 浏览器另覆盖 132/580/24、语义节点计数、GET-only 交互、双宽度溢出和五张视图截图。

新增 TASK-DEMO-07 测试覆盖 bootstrap 资产配置/comparison reference、UrgentOrderCommand/Job result/Comparison strict guards、malformed lineage 与分页、urgent POST/idempotency/query 编码、表单校验与二次确认、持久化 command recovery、成功后自动 DRAFT 比较和刷新恢复。真实 Showcase 浏览器另覆盖四路线表单、十阶段 job、`ADDED`/`CHANGED`/`UNCHANGED`、保持不变翻页、设备筛选、长时长中文化、双宽度溢出、控制台与可见凭证检查。

新增 TASK-DEMO-08 测试覆盖安全具名 runtime、并发 ControlStore 登记、非 loopback session、重启中断/同 identity 重试、reset 切换前失败、同步双击防护、pending job 刷新恢复、模态焦点环绕/还原、错误字段关联和 tabpanel 引用。独立 API/SQLite 审计覆盖完整安全/恢复矩阵；真实浏览器从空 runtime 覆盖四步主线、双击、刷新、键盘、ARIA、非颜色表达、关键对比度、reduced motion、双宽度、console、DOM/响应规模和可见敏感信息检查。

## 8. 当前边界与后续工作

- 当前批准的数据资产只有 `CNC-ROUTE-3`～`CNC-ROUTE-6` 四个路线模板；前端应据资产生成四张路线卡，不宣称已有六条路线。
- 当前 D09/D10 切片允许每个 deterministic run 提交一个不同的加急事件，并支持该命令精确重放；第二个不同插单在同一 run 中以 `BASELINE_STATE_CONFLICT` fail closed。多次连续插单需要先明确 DRAFT 取舍或新 current 基线的链式语义。
- 根 `project_effective_locks` 会把 Snapshot 中基线前的历史 completed 事实带入 projection，而版本比较 universe 只包含基线 active assignments。Demo 不改根实现、不删除历史事实；它保留 Snapshot anchors 原字节，并在单 worker、单次服务调用范围内把 effective-lock 的 completed comparison view 收窄为 base→new 实际移除集合。该兼容 adapter 是显式技术边界，未来应由正式 projector injection 或统一 universe 语义替代。
- D04/D17 剩余证据：B4/B5 warmup + 5 measured、浏览器首屏、独立进程 RSS、目标演示机和 immutable performance baseline。
- Demo manual cancel/retry 仍保持 fail closed；本切片没有把它包装为可用功能。

下一实施切片应是 Demo 专属 D17 正式专项基准、调优与参数冻结。D16 新结果仍只能是 DRAFT，不可自动批准、发布或替换 current baseline。

## 9. 可复现命令

```powershell
uv run pytest demo/tests -q
uv run ruff check demo/backend demo/scripts demo/tests
uv run pyright -p demo/pyrightconfig.json
uv run python demo/scripts/run_frontend_evidence.py --observation demo/build/validation/browser-smoke-observation-demo-05.json --report demo/build/validation/frontend-evidence-demo-05.json
uv run python demo/scripts/run_workspace_evidence.py --observation demo/build/validation/browser-workspace-observation-demo-06.json --report demo/build/validation/frontend-evidence-demo-06.json
uv run python demo/scripts/run_replan_frontend_evidence.py --observation demo/build/validation/browser-replan-observation-demo-07.json --report demo/build/validation/frontend-evidence-demo-07.json
uv run python demo/scripts/run_e2e_audit.py --report demo/build/validation/e2e-audit-demo-08.json
uv run python demo/scripts/run_browser_e2e.py --headless --report demo/build/validation/browser-e2e-observation-demo-08.json
uv run python demo/scripts/run_e2e_evidence.py --api-audit demo/build/validation/e2e-audit-demo-08.json --browser-observation demo/build/validation/browser-e2e-observation-demo-08.json --report demo/build/validation/e2e-evidence-demo-08.json
uv run python demo/scripts/task_context_manifest.py --task-id TASK-DEMO-08 --report demo/build/validation/task-context-manifest-demo-08.json
uv run python demo/scripts/validate_demo.py --task-id TASK-DEMO-08 --context demo/build/validation/task-context-manifest-demo-08.json --report demo/build/validation/task-machine-report-demo-08.json
uv run python demo/scripts/start_demo.py
npm --prefix demo/frontend ci
npm --prefix demo/frontend run dev
```

`OPTIMAL` 只适用于对应 synthetic instance；`FEASIBLE` 只有在独立 Validator `PASS` 时可展示，且不得称为最优。
