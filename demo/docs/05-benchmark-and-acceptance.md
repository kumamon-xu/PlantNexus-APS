# 专项基准与验收标准

实施更新（2026-09-04）：D17 已按本文件协议在具名本地演示参考机完成 SMOKE、SHOWCASE、UPPER 三档 B1～B6 正式基准、独立进程树 RSS 和真实 Chromium 首屏观察。三档各有 1 次 preflight、1 次 warmup、5 次 measured；Showcase 7 项发布目标和 Upper characterization 均 `PASS`。版本化 raw samples、环境签名、不可变 baseline 与复算证据见 [D17 正式专项基准与参数冻结报告](D17-FORMAL-BENCHMARK-REPORT.md)。D18 已完成本地候选机的一键交付、Runbook、Chromium 和 release audit，最终现场机复放仍 pending；两阶段结果均不建立生产容量或 SLA。

## 1. 现有证据边界

当前最大正式基准档位是 [benchmarks/profiles.yaml](../../benchmarks/profiles.yaml) 的 M：

| 指标 | 现有 M 档 |
|---|---:|
| 订单 | 12 |
| 工序 | 48 |
| 设备 | 8 |
| 候选选项 | 96 |
| horizon ticks | 900 |
| warmup / measured | 1 / 3 |

[p2-m.v1.json](../../benchmarks/baselines/p2-m.v1.json)在一台 AMD64 Windows、Python 3.12.13、OR-Tools 9.15.6755 的机器上记录了：

- solve median：0.296411 秒；
- total p95：0.3318861 秒；
- synthetic_only：true；
- production_sla：NOT_ESTABLISHED_OPEN_012。

这份根项目 baseline 只证明 12 单、48 工序的特定合成样本，不能外推到 132 单、610 工序，更不能用来承诺“百单半秒”。Demo 已另行建立 `cnc-demo-formal-benchmark-baseline.v1`；它只适用于该固定合成数据、被测源码和具名本地参考环境，同样不能外推为生产性能。

## 2. 基准问题

专项基准回答五个问题：

1. 610 道活动规模能否在 20/30 秒求解上限下稳定产生 Validator PASS 的候选？
2. 六轮字典序重排在加入加急单后是否仍能稳定完成，并产生完整 ChangeReport？
3. 数据生成、标准导入、Snapshot、Problem、持久化和 presentation 的非求解开销是多少？
4. 单 worker、固定 seed 在目标演示机上的状态、目标值和方案变动范围如何？
5. 700 工序上界是否仍有可接受行为，还是需要降低默认档、放宽离线预算或简化场景？

## 3. 基准档位

| 档位 | 订单 | 工序 | 设备 | 周期 | 用途 |
|---|---:|---:|---:|---:|---|
| CNC-SMOKE | 24 | 108 | 12 | 7 天 | PR/本地快速检查 |
| CNC-SHOWCASE | 132 | 610 | 24 | 10 天 | 默认现场 Demo |
| CNC-UPPER | 150 | 700 | 30 | 14 天 | 上界刻画，不作为默认现场参数 |

CNC-SMOKE 的路线分布为 4×3 + 8×4 + 8×5 + 4×6 = 108。CNC-UPPER 为 20×3 + 40×4 + 60×5 + 30×6 = 700。三档都必须使用 1～3 台候选设备、设备日历、维护、物料到齐和执行事实；不能用只有 precedence 的简化模型冒充专项结果。

### 3.1 求解参数

| 档位 | 初排上限 | 重排上限 | max_workers | random_seed |
|---|---:|---:|---:|---:|
| CNC-SMOKE | 5 秒 | 10 秒 | 1 | 20260902 |
| CNC-SHOWCASE | 20 秒 | 30 秒 | 1 | 20260902 |
| CNC-UPPER | 60 秒 | 90 秒 | 1 | 20260902 |

SHOWCASE 的 20/30 秒已由 D17 在本地演示参考机通过并冻结为 Demo 默认参数。UPPER 的 60/90 秒继续只用于离线刻画。最终现场机若环境签名变化，D18 必须先复跑，不得静默沿用本地性能结论。

固定 seed 和单 worker 可减少非确定性，但 wall-time 截止仍可能因机器调度导致 FEASIBLE 方案不同。因此：

- 数据包、Snapshot 和 Problem 必须逐字节确定；
- OPTIMAL 结果应要求内容指纹一致；
- 在时间上限处停止的 FEASIBLE 结果，要求状态可接受、Validator PASS、目标/稳定性在记录范围内，并报告指纹差异；
- 不把“固定 seed”夸大为跨 OR-Tools 版本、跨硬件完全相同的排程。

## 4. 基准场景

每个档位至少运行：

### B1：数据与导入

生成 → staging → normalization → Data Validation → Snapshot → v2 Problem。

验证精确计数、hash、引用闭合和重复运行一致性。

### B2：初始排产

从同一 Problem 运行 Global CP-SAT、独立 Validator、KPI 和 READY_FOR_REVIEW 持久化。

### B3：基线激活

批准并发布到 SIMULATION_INTERNAL，测量状态迁移和 Publication 读回，不包含求解。

### B4：加急重排

使用版本化 urgent fixture：标准导入 → ExecutionEvent → projection → Snapshot → ReplanRequest → 六层字典序求解 → Validator → KPI → ChangeReport → DRAFT。

### B5：展示读取

分别构建初始 v1、重排 v2 和比较 presentation DTO，测量服务端处理、JSON 大小与浏览器首屏。

#### TASK-DEMO-04 单次 early evidence

`demo/build/validation/runtime-evidence-demo-04.json` 记录了一次固定 Showcase、当前开发机、同进程的服务端读取。它用于验证 610 总工序规模下的契约、数据量和明显性能断点，不是按第 5 节协议形成的 warmup + 5/p95 baseline，也没有测量浏览器渲染或 RSS。

| 读取 | 返回规模 | 单次构建耗时 | canonical JSON |
|---|---:|---:|---:|
| Factory | 3 车间 / 24 设备 / 462 unavailable intervals | 0.317 秒 | 149,658 bytes |
| v1 PUBLISHED 首页 | 500 / 580 assignments | 0.383 秒 | 653,182 bytes |
| v2 DRAFT 首页 | 500 / 585 assignments | 0.562 秒 | 656,621 bytes |
| 默认 Comparison | 27 / 585 operations（5 ADDED + 22 CHANGED） | 0.898 秒 | 42,895 bytes |
| 全量 Comparison 首页 | 500 / 585 operations | 0.930 秒 | 714,477 bytes |

同一次读取证明 v1/v2 分页分别为 500+80、500+85；ChangeReport universe 为 585 = 558 `UNCHANGED` + 22 `CHANGED` + 5 `ADDED`，默认过滤同时观察到 `ADDED` 与 `CHANGED`；重复比较 fingerprint 一致，资源过滤返回 9 条且全部匹配。读取前后 schedule/replan/artifact/publication 行数、故事状态与 current Publication 完全不变。环境为 Python 3.12.13、OR-Tools 9.15.6755、Windows 11、32 logical CPUs；这些单次数字不得替代第 8 节的 p95 门槛判定。

#### TASK-DEMO-06 浏览器单次 early evidence

`demo/build/validation/frontend-evidence-demo-06.json` 记录固定 Showcase current `PUBLISHED` 基线的真实 Chromium 读取。默认 72 小时时间窗匹配 546/580 assignments，单页返回并挂载 160 个 assignment 节点；同屏还有 30 个 completed 事实、24 个资源行、120 个非工作时段块、2 个维护块和 24 个冻结图层，总 DOM 为 1,173 个节点。一次 fresh navigation 中，Factory/工作区 payload 分别为 149,658/305,326 bytes，工作区响应结束于导航后约 1,438.4 ms。1440×900 和 1024×768 均无页面级横向滚动，1024 宽仅甘特容器内部滚动。

这只有 1 个当前开发机样本，没有 warmup + 5、p95、独立 RSS 或目标演示机环境签名，因此只证明消费路径和节点上限没有明显断点，不建立首屏 SLA。

### B6：重置恢复

创建新数据库、迁移、初始化、原子切换，并注入中途失败，确认旧 active run 不受损。

## 5. 运行协议

目标演示机上每个档位：

1. 记录 CPU、核心数、内存、OS、电源模式、Python、OR-Tools、Node、浏览器和 commit。
2. 关闭无关高负载任务，保留正常演示所需服务。
3. 运行 1 次 preflight、1 次 warmup、5 次 measured。
4. 初排 measured 每次从同一不可变 Problem 开始。
5. 重排 measured 每次从同一 PUBLISHED 基线和同一 urgent command 开始，使用隔离 run。
6. 每次运行后重新执行 Validator 与 ChangeReport validation。
7. 保留原始 JSON、汇总 Markdown 和不可变 baseline；新结果写新版本，不覆盖旧基线。

如果现场使用另一台机器或升级 OR-Tools，先跑 CNC-SMOKE；环境签名变化时不得悄悄沿用旧性能徽标。

## 6. 必采指标

### 6.1 规模与模型

- order、lot、operation、precedence edge；
- resource、calendar fragment、maintenance window；
- candidate option 与平均候选数；
- completed、running、hard lock、soft lock；
- material-delayed ratio；
- 跨车间比例；
- horizon ticks；
- CP-SAT variables 与 constraints 摘要，如果现有报告可提供。

### 6.2 阶段耗时

对每阶段记录 raw samples、median、p95、max：

- generation；
- staging/normalization/data validation；
- snapshot；
- problem build；
- solver；
- independent validation；
- KPI；
- persistence；
- ChangeReport；
- presentation；
- end-to-end。

当前求解接口没有可靠的 first-feasible callback，因此不能从总 solve time 反推“首个可行解时间”。只有以后新增正式、经过测试的回调证据后才记录该指标。

### 6.3 求解质量

- solver status；
- planning run outcome；
- objective value；
- best bound；
- 可计算时的 absolute/relative gap；
- wall time 与配置上限；
- Validator status、版本和指纹；
- scheduled / unscheduled operation count。

对于重排还记录：

- 六个目标轮次的状态与预算；
- soft_lock_violations；
- changed_existing_operations；
- resource_changes；
- absolute_start_shift_seconds；
- unchanged_existing / comparable_existing / unchanged_ratio；
- ADDED、CHANGED、UNCHANGED、REMOVED_BY_FACT 计数；
- ChangeReport validation。

### 6.4 资源

- 进程 RSS peak；
- SQLite 数据库大小；
- artifact JSON 总大小；
- API response 字节数；
- 浏览器 comparison 页节点数与首屏渲染时间。

内存测量方法和采样周期必须写入 baseline，不能把 Python allocation 与进程 RSS 混为一谈。

## 7. 状态验收

依据 [CP-SAT 官方状态定义](https://developers.google.com/optimization/cp/cp_solver)：

| Solver 结果 | Validator | 是否可作为 Demo 结果 |
|---|---|---|
| OPTIMAL | PASS | 是，显示“已证明最优” |
| FEASIBLE | PASS | 是，显示“已找到并验证可行，未证明最优” |
| UNKNOWN，无 candidate | 不适用 | 否；保留当前基线 |
| INFEASIBLE | 不适用 | 否；该 scripted profile 不得发布 |
| 任意 | FAIL | 否；阻止版本与页面切换 |

脚本化 SHOWCASE 的 5 次 measured 必须全部得到前两类结果。一次 UNKNOWN、INFEASIBLE 或 Validator FAIL 即阻止发布该数据包。

## 8. 冻结的 Demo 性能门槛

这些是 `formal-protocol.v1` 冻结的 Demo 发布目标，不是生产 SLA。D17 在运行前固定门槛，运行后逐项报告 PASS/FAIL；本次没有反向调整指标或降低场景规模。

### 8.1 CNC-SHOWCASE

| 指标 | 冻结门槛 |
|---|---:|
| 初排 solver limit | 20 秒 |
| 初排端到端 p95 | ≤ 30 秒 |
| 加急重排 solver limit | 30 秒 |
| 加急重排端到端 p95 | ≤ 45 秒 |
| 非求解阶段合计 p95 | ≤ 8 秒 |
| 单个 presentation API p95 | ≤ 1.5 秒 |
| job/state API p95 | ≤ 250 毫秒 |
| 后端 RSS peak p95 | ≤ 2 GiB |
| Validator / ChangeReport | 5/5 PASS |

页面显示的是配置上限和本次实际耗时，而不是门槛数字。

若 SHOWCASE 未通过：

1. 先分析模型大小、日历碎片、候选密度和六轮预算；
2. 做不改变业务语义的建模/查询优化；
3. 重新建立新版本 baseline；
4. 仍未通过时，将默认档降低到通过验证的规模，并在文档与 UI 同步精确计数。

不能保留“132/610”文案却在运行时静默抽样。

### 8.2 CNC-UPPER

UPPER 是 characterization gate：

- 5 次运行全部产生 Validator PASS 的 OPTIMAL 或 FEASIBLE candidate；
- 无 OOM、进程崩溃或数据库损坏；
- ChangeReport 完整；
- 报告 60/90 秒预算下的实际分布。

UPPER 不满足时，不影响已通过的 SHOWCASE 发布，但 README 必须注明上界未通过及观测原因。

### 8.3 D17 正式判定

| 检查 | D17 实测 | 结果 |
|---|---:|---|
| Showcase 初排端到端 p95 | 7.517 秒（门槛 ≤ 30 秒） | PASS |
| Showcase 加急重排端到端 p95 | 22.601 秒（门槛 ≤ 45 秒） | PASS |
| Showcase 非求解阶段 p95 最大值 | 5.782 秒（门槛 ≤ 8 秒） | PASS |
| Showcase presentation API p95 | 0.839 秒（门槛 ≤ 1.5 秒） | PASS |
| Showcase job/state API p95 | 0.013 秒（门槛 ≤ 0.25 秒） | PASS |
| Showcase 后端进程树 RSS p95 | 277.3 MiB（门槛 ≤ 2 GiB） | PASS |
| Showcase Validator + ChangeReport | 5/5 | PASS |
| Upper 700 工序初排 / 重排 p95 | 12.181 / 32.014 秒 | PASS（characterization） |

Showcase 5 次初排均为 `OPTIMAL + Validator PASS`；5 次重排为 4 次 `OPTIMAL`、1 次 `FEASIBLE`，且全部 `Validator PASS + ChangeReport PASS`。页面必须保留两种中文状态的区别。真实 Chromium 基线/比较页 measured 首屏 p95 分别为 1,365.5/2,398.5 ms；协议未为浏览器首屏设置数值门，因此这两项只作为 D18 对照观察，不追加事后门槛。

## 9. 功能验收门

### Gate A：数据确定性

- 132/610/24、候选数、优先级、状态与锁计数精确匹配；
- 同输入生成两次，规范数据、Snapshot 和 Problem 指纹一致；
- 标准导入和 Data Validation PASS；
- 非法引用、重叠日历和 capability 错配 mutation 均被拒绝。

### Gate B：初排链路

- 从空 run 到 READY_FOR_REVIEW 的完整链可重复；
- SolverReport 与 Validator 文案正确；
- Validator FAIL 注入时不产生可评审版本；
- artifact lineage 和指纹闭合。

### Gate C：生命周期

- READY_FOR_REVIEW 不能直接被 Replan 使用；
- 显式基线激活后 current Publication 指向 exact PUBLISHED；
- 相同 key 精确重放，不同 payload 同 key 冲突；
- 批准后发布失败可恢复，不重新求解。

### Gate D：加急重排

- 表单新增事实后生成精确 URGENT_DEMAND_RECEIVED；
- route_template_id 不进入正式事件；
- 既有规范记录不被改写；
- completed、running、hard lock、freeze 全部保留；
- 新版本是 v2 DRAFT，current PUBLISHED 不变；
- ChangeReport operation universe 完整且 validation PASS。

### Gate E：展示

- v1 基线和 v2 新方案通过同一 DTO 展示；
- 变更分类与 ChangeReport 逐项一致；
- KPI 不由浏览器重算；
- 默认过滤能同时显示 CHANGED 与 ADDED；
- DRAFT 和 Simulation 标识始终可见；
- 1440×900 主路径无横向页面滚动。

TASK-DEMO-04 已通过统一展示契约与只读性证据；TASK-DEMO-05 验证了中文故事壳不重算 KPI、Simulation 标识持续可见和双宽度布局；TASK-DEMO-06 进一步验证了初始 580 assignments 通过 160 节点分页/时间窗有界展示、订单联动、日历与锁定语义、计划负荷口径以及 1440×900/1024×768 无页面级横向滚动。TASK-DEMO-07 真实连接 Showcase current `PUBLISHED`，一次业务表单提交形成 v2 `DRAFT`，默认变化页、保持不变分页、设备筛选、PUBLISHED→DRAFT lineage、交付/稳定性、Validator 和刷新恢复均通过。TASK-DEMO-08 又从全新 runtime 重放完整中文链，取得 68/68 浏览器断言、两张已校验截图、八组关键文字 AA 对比度、无悬空 ARIA 引用和双宽度 0 页面溢出。TASK-DEMO-09 再以 production build/preview 的真实 Chromium 完成基线与比较状态各 1 warmup + 5 measured，12/12 样本均加载中文页面且关键 API 返回成功。Gate E 功能、视觉与 D17 多样本观察现为 `PASS`。

### Gate F：恢复与安全

- 默认只绑定 127.0.0.1；
- 无 token 写入日志或仓库；
- stale run/base、越权 scope、production binding 均 fail closed；
- reset 失败不切换 active run；
- 服务重启后 QUEUED 以原 identity 续跑，遗留 RUNNING/CANCELLING 进入明确 INTERRUPTED；
- 路径逃逸、任意数据库路径和并发 reset 被拒绝。

TASK-DEMO-05 已在真实 Chromium 验证同源 HttpOnly session、EMPTY 到基线发布、刷新恢复同一 run、响应契约 fail closed、中文安全错误和可见正文不含凭证；TASK-DEMO-07 又验证了 durable urgent 成功后刷新恢复同一 DRAFT comparison 且不重复 POST。TASK-DEMO-08 的 50/50 API/SQLite 断言和 68/68 浏览器断言已覆盖 exact replay/idempotency conflict、stale run/base、非 loopback、错误 token/capability/scope、Production binding、并发 reset、切换前 reset 失败、路径逃逸、重启 `INTERRUPTED` 与同 identity attempt 2，以及日志/数据库/仓库/页面凭证消毒。Gate F 现为 `PASS`；manual cancel/retry 仍是明确未开放能力，不属于该 Gate 的成功宣称。

## 10. 测试矩阵

| 层级 | 必测内容 |
|---|---|
| Unit | 生成分布、duration、ID、时区、优先级、DTO、状态文案 |
| Contract | demo command、job、presentation；正式 schema 精确兼容 |
| Property | 任意允许数量/模板下引用闭合、候选匹配、时间对齐 |
| Mutation | 旧记录篡改、route 写入事件、锁冲突、错误指纹、ChangeReport 缺项 |
| Integration | SQLite 迁移、仓储、完整初排、基线发布、完整重排与精确重放 |
| Concurrency | 双击提交、并发重置、stale base、服务重启 |
| Security | Simulation-only、scope/capability、token 消毒、路径约束 |
| E2E | 浏览器从重置到比较页、刷新恢复、失败/重试、键盘操作 |
| Visual | 1440×900、1024 宽、长订单号、580 条数据的有界甘特、比较页与色盲检查 |
| Benchmark | SMOKE、SHOWCASE、UPPER 的 B1～B6 |

D16 测试矩阵证据汇总于 `demo/build/validation/e2e-evidence-demo-08.json`：API/SQLite 50 项、真实浏览器 68 项、跨报告/截图/源码 39 项全部 `PASS`。浏览器整链约 79.89 秒、API Smoke 审计约 14.45 秒只是本次功能运行 wall time；没有 warmup + 5、p95、独立 RSS 或目标机签名，因此不能写入 D17 性能基线。

D17 基准证据汇总于 `demo/build/validation/benchmark-evidence-demo-09.json`：复算 21 个后端 raw samples、12 个浏览器样本、环境/源码 digest、三档分布、Showcase 7 项门槛与参数冻结，结果为 `PASS`。浏览器观察单独保存在 `browser-benchmark-observation-demo-09.json`；版本化 sealed baseline 位于 `demo/benchmarks/baselines/cnc-demo-formal-benchmark.v1/`。

## 11. 发布判定

只有以下材料齐全才能标记 Demo ready：

- 数据 golden manifest；
- SHOWCASE 专项基准 baseline 与原始 samples；
- 全部 Gate A～F 证据；
- 脚本化 urgent fixture；
- 一键启动与一键重置 runbook；
- 已知限制和状态文案核对；
- 目标演示机 smoke 结果。

该判定只表示“CNC Simulation Demo 可重复演示”，不改变项目当前 P7 状态，也不建立生产 SLA。

D17 已补齐第二、第四和第五项中的基准/fixture/状态证据。D18 已在当前本地候选机补齐一键控制面、中文 Runbook、冷启动、固定重置、真实 Chromium 首屏、重启恢复和版本化 release manifest/audit；最终现场机仍未由用户确认，所以状态保持 `PENDING_FINAL_SITE_REPLAY`，当前仍不得标记最终 Demo ready。

## 12. D18 发布审计

D18 的交付验收分为本地候选与最终现场两层，不能用本地 PASS 替代现场放行：

| 检查 | 本地候选结果 | 最终现场要求 |
|---|---|---|
| doctor | Python 3.12、Node 24.19.0、npm 12.0.2、uv、npx、锁文件、资产、D17 指纹、端口与写权限 PASS | 目标机重新执行并保存环境签名 |
| production cold start | 含 `npm ci` / build，ready 约 10.735 秒 | 目标 checkout 默认 `start` PASS |
| fixed reset | Showcase 132 / 610 / 24、seed `20260902`，约 4.718 秒 | 计数与边界逐字段一致 |
| real Chromium | 两次 `zh-CN` / `INITIALIZED`，page/console/server error 均为 0 | 目标浏览器重新执行 `smoke` |
| restart | 同 runtime ready 约 3.234 秒，run identity 保留 | 停止、重启、health、smoke 全部 PASS |
| interrupted job | D16 `INTERRUPTED`、原 identity attempt 2 `SUCCEEDED` | 语义不得因打包改变 |
| safe stop | PID 与创建标记匹配后才停止，state 清理 | 无遗留监听进程；未知 PID fail closed |
| release inventory | `demo/**` SHA-256、lock、D16/D17/D18 evidence 闭合 | 提交后重新核对 manifest/audit |

本地发布审计可以给出 `LOCAL_CANDIDATE_VERIFIED`，但 `final_release_ready=false`。D17 TASK-DEMO-09 的原机器报告继续保持 `FAIL / SCOPE_CHECK`、`functional_status=PASS`，其用户 closure 授权不改变机器事实，也不构成 D18 范围或最终发布豁免。

最终现场机只有在 release manifest、默认一键启动、固定 reset、真实 Chromium 中文 smoke、环境差异说明和安全 stop 均通过后，才可标记“CNC Simulation Demo ready”。该结论仍只针对合成数据、Simulation 和本次版本，不建立 Production 能力或 SLA。
