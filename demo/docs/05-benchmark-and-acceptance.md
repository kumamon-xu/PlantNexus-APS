# 专项基准与验收标准

实施更新（2026-09-02）：Showcase 610 工序和 Upper 700 工序的 B1/B2 单次 sequential early spike 已取得 `OPTIMAL + Validator PASS`，详见 [实施状态](IMPLEMENTATION-STATUS.md)与 `demo/benchmarks/results`。该结果尚不满足本文件要求的 B4、warmup + 5 measured、RSS、目标机与 immutable baseline，所以下文正式验收标准保持不变。

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

这份根项目 baseline 只证明 12 单、48 工序的特定合成样本，不能外推到 132 单、610 工序，更不能用来承诺“百单半秒”。Demo 当前已有早期 raw reports，但仍必须完成自己的版本化重复专项基线。

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

SHOWCASE 的 20/30 秒是待验证的现场候选参数；只有基准通过才进入 scenario manifest。UPPER 的较长预算只用于离线刻画。

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

## 8. 暂定性能门槛

这些是 Demo 发布目标，不是已经取得的结果；第一次基准后必须在报告中明确 PASS/FAIL，不能反向改指标掩盖失败。

### 8.1 CNC-SHOWCASE

| 指标 | 暂定门槛 |
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

### Gate F：恢复与安全

- 默认只绑定 127.0.0.1；
- 无 token 写入日志或仓库；
- stale run/base、越权 scope、production binding 均 fail closed；
- reset 失败不切换 active run；
- 服务重启后活动 job 进入明确 INTERRUPTED；
- 路径逃逸、任意数据库路径和并发 reset 被拒绝。

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
| Visual | 1440×900、1024 宽、长订单号、500+ 甘特条目、色盲检查 |
| Benchmark | SMOKE、SHOWCASE、UPPER 的 B1～B6 |

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
