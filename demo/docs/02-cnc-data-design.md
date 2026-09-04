# CNC 场景与数据设计

## 1. 场景标识

| 字段 | 固定值 |
|---|---|
| scenario_id | CNC-DEMO-SHOWCASE |
| generator_version | PLANTNEXUS-DEMO-CNC-IMPORT-GENERATOR@1.0.0 |
| seed | 20260902 |
| factory | 华东精密机加工演示工厂 |
| display_timezone | Asia/Shanghai |
| planning_anchor | 2026-09-07 06:00:00 +08:00 |
| planning_horizon | 10 个自然日 |
| tick_seconds | 300 |
| initial_solve_limit | 20 秒，initial-solve early gate 已通过但未冻结 |
| replan_solve_limit | 30 秒，待 B4 加急重排基准确认 |

所有正式时间字段写入 UTC；浏览器只在显示层转换为工厂时区。固定 planning anchor 避免同一种子随演示日期变化。

## 2. 默认规模

### 2.1 订单与路线深度

默认档精确生成 132 个订单和 610 道总工序。

| 路线族 | 订单数 | 每单工序数 | 工序数 |
|---|---:|---:|---:|
| 简单隔套 | 20 | 3 | 60 |
| 安装板 / 支架，各 19 单 | 38 | 4 | 152 |
| 精密轴 / 薄壁套，各 23 单 | 46 | 5 | 230 |
| 阀体 / 壳体 | 28 | 6 | 168 |
| 合计 | 132 | 3～6 | 610 |

生成后的执行事实包含：

- COMPLETED：30 道；
- RUNNING：12 道；
- NOT_STARTED：568 道；
- 仍需进入计划的活动工序：580 道，其中包含 12 道正在加工工序。

这里的“610 道总工序”是业务数据规模，“580 道活动工序”是求解与展示口径。页面必须同时给出口径，不能混用。

### 2.2 候选设备

| 每道工序候选数 | 工序数 | 资源选项数 |
|---|---:|---:|
| 1 台 | 92 | 92 |
| 2 台 | 335 | 670 |
| 3 台 | 183 | 549 |
| 合计 | 610 | 1,311 |

候选设备只来自具备对应 capability 的资源。不同候选设备可以有不同 final_duration_seconds，以体现设备效率差异。

### 2.3 订单优先级

| 类别 | 订单数 | Simulation 权重 | UI 表述 |
|---|---:|---:|---|
| 普通 | 96 | 1 | 普通 |
| 重点 | 29 | 4 | 重点 |
| 加急 | 7 | 12 | 加急 |
| 合计 | 132 |  |  |

权重是 Demo 的显式仿真策略，不代表任何真实客户等级或生产规则。优先级必须通过现有 DemandPriorityInput sidecar 进入 v2 PlanningProblem，不能偷偷塞进导入记录。

## 3. 工厂拓扑

### 3.1 车间与设备

| 车间 | 设备族 | 数量 | 设备 ID |
|---|---|---:|---|
| WS-10 下料与车削 | 带锯 | 2 | SAW-01～02 |
| WS-10 下料与车削 | CNC 车床 | 4 | LATHE-01～04 |
| WS-10 下料与车削 | 车铣复合 | 2 | TURNMILL-01～02 |
| WS-20 铣削 | 立式加工中心 | 4 | VMC-01～04 |
| WS-20 铣削 | 卧式加工中心 | 4 | HMC-01～04 |
| WS-20 铣削 | 五轴加工中心 | 2 | FIVEAXIS-01～02 |
| WS-30 精加工与检测 | 外圆磨床 | 2 | GRINDER-01～02 |
| WS-30 精加工与检测 | 去毛刺 / 清洗单元 | 2 | FINISH-01～02 |
| WS-30 精加工与检测 | 三坐标测量机 | 2 | CMM-01～02 |
| 合计 |  | 24 |  |

建议 capability 集合：

- SAW；
- TURN_2AXIS；
- TURN_MILL；
- MILL_3AXIS；
- MILL_4AXIS；
- MILL_5AXIS；
- GRIND_OD；
- DEBURR_WASH；
- CMM_INSPECTION。

一个资源可以声明多个 capability，但不能像现有通用合成数据那样让所有设备拥有所有能力。

### 3.2 日历与维护

基础班次：

- 周一至周五 06:00～22:00，两班连续可用；
- 周六 08:00～16:00；
- 周日不可用；
- 计划周期内为 5～7 台设备生成一次 2～6 小时的维护停机。

维护窗口必须完全落在规范时间轴上，且不可用区间之间不重叠。生成器在输出前检查：

- 起止时间合法且按 300 秒对齐；
- resource_id 存在；
- 同资源窗口不重叠；
- RUNNING 和硬锁安排不落入维护窗口；
- horizon 能容纳所有固定执行事实。

### 3.3 跨车间运输

只在工序相邻且 workshop 发生变化时加入固定运输时间：

| 路径 | 时间 |
|---|---:|
| WS-10 → WS-20 | 15 分钟 |
| WS-10 → WS-30 | 20 分钟 |
| WS-20 → WS-30 | 15 分钟 |

这表示车间间流转准备，不表示物流路径优化。

## 4. 路线模板

模板是 Demo 的输入便利层，不是 execution-event.v1 的字段。

| template_id | 展示名称 | 工序链 |
|---|---|---|
| CNC-ROUTE-3 | 短轴类 | 锯切下料 → 数控车削 → 终检 |
| CNC-ROUTE-4 | 法兰类 | 锯切下料 → 数控车削 → 铣削加工 → 终检 |
| CNC-ROUTE-5 | 精密套筒类 | 锯切下料 → 数控车削 → 铣削加工 → 精密磨削 → 终检 |
| CNC-ROUTE-6 | 复杂壳体类 | 锯切下料 → 数控车削 → 粗铣 → 五轴精铣 → 精密磨削 → 终检 |

该表与 `demo/data/cnc-showcase/route-templates.json` 的批准资产一致。前端必须从 bootstrap 配置读取这四条路线，不能继续展示早期设计中的六条候选路线。

每个业务订单生成自己的确定性 order、lot、operation instance 和必要的 routing/version 引用。业务 ID 由 scenario、seed、模板和序号派生，不使用进程随机 UUID。

## 5. 数量与加工时长

普通初始化订单按路线族使用确定性分层数量，例如 1～30 件；加急表单允许 1～50 件。每个资源选项的最终时长在进入标准导入前计算：

    raw_seconds = setup_seconds + cycle_seconds_per_unit × quantity
    final_duration_seconds = 向上取整到 300 秒

规则：

- setup_seconds 是该工序与资源选项的固定准备分量；
- cycle_seconds_per_unit 由模板与资源效率系数决定；
- 同一工序不同候选资源可有不同 final duration；
- final duration 至少一个 tick；
- 输入 PlanningProblem 的时长已经是最终整数秒，不让求解器再解释公式；
- 固定准备分量不得在页面中称为“序列相关换型”。

时长参数表必须版本化并存入 demo/data/cnc-showcase，而不能只存在于 Python 常量中。

## 6. 交期、release 与物料

### 6.1 交期生成

先用确定性参考排程估算每个路线族的合理工作量，再按订单等级设置交期松紧：

- 普通：参考完工时间后增加较宽缓冲；
- 重点：中等缓冲；
- 预置加急：较窄缓冲，但默认档仍应存在可验证解。

交期生成不能只按均匀随机天数；它必须与路线工作量、数量和 release 相关。生成完成后运行可行性 smoke solve，失败则整个数据包无效，而不是在运行时偷偷换 seed。

### 6.2 物料到齐

132 个订单中固定选取 18 个订单，物料在 release 后 4～18 小时到齐。物料约束只表达 earliest start：

- 不建立库存数量；
- 不在订单间竞争同一库存；
- 不宣称做了 MRP 或齐套分配。

## 7. 执行事实、冻结和锁定

固定状态分布为 30 COMPLETED、12 RUNNING、568 NOT_STARTED。选择顺序按确定性哈希排序，并满足：

- COMPLETED 工序只出现在其订单路线的已完成前缀；
- RUNNING 工序的前序全部完成；
- 每个订单最多一条 RUNNING 工序；
- RUNNING 的 resource、started_at 和 remaining duration 自洽；
- 同设备上的固定区间不重叠。

默认加入 4 个硬锁和 8 个软锁。锁定目标先从一个确定性可行参考安排中提取，再写入数据包；正式演示排程仍由 CP-SAT 重算。硬锁、运行中任务和 900 秒 Simulation 冻结窗口之间不得冲突。

## 8. 加急订单表单与命令

表单字段：

| 字段 | UI 类型 | 校验 |
|---|---|---|
| route_template_id | 路线卡片单选 | 六个白名单模板之一 |
| quantity | 整数 | 1～50 |
| due_at_local | 工厂本地时间 | 晚于当前仿真时钟且不晚于 horizon |
| priority_class | 普通 / 重点 / 加急 | 映射为 1 / 4 / 12 |
| note | 可选短文本 | 仅 demo 审计，不进入正式事件 |

服务端流程：

1. 规范化命令并计算 idempotency fingerprint。
2. 从模板和数量展开新的标准导入候选记录与最终工时。
3. 运行标准 mapping、normalization 和 Data Validation。
4. 验证旧记录完全不变，新增记录只属于一个新 demand。
5. 提交导入。
6. 追加 URGENT_DEMAND_RECEIVED 事件，其 payload 仅包含正式 schema 要求的 demand_order_id、quantity、due_at_utc、priority_weight 和 priority_source。
7. 创建新的 Snapshot 和 ReplanRequest，进入动态重排。

在依赖该流程前必须增加契约测试，证明现有 urgent candidate validator 允许所需的 product/routing 新增，同时拒绝 topology、既有事实和既有记录变更。若不允许，则使用预声明模板路线的兼容方案，不能放宽正式验证器。

## 9. 数据包结构

计划中的 demo 数据资产：

    demo/data/cnc-showcase/
      manifest.json
      factory-profile.json
      resource-catalog.json
      route-templates.json
      duration-parameters.json
      priority-policy.json
      maintenance-plan.json
      ui-copy.zh-CN.json

运行时生成的规范文档、指纹、基准结果和数据库位于 demo/runtime，不提交到仓库；金丝雀样本和 golden manifest 位于 demo/tests/fixtures。

manifest 至少记录：

- scenario_id、generator_version、seed、planning_anchor；
- 各实体精确计数；
- 各源资产 SHA-256；
- 生成批次 content fingerprint；
- 规范化后 Snapshot fingerprint；
- PlanningProblem fingerprint；
- Python、OR-Tools 与平台版本；
- 单 worker 与求解参数。

## 10. 生成器不变量

生成器完成的定义不是“成功写出 JSON”，而是以下检查全部通过：

- 相同版本、种子、时钟和资产产生逐字节相同的规范输出与指纹；
- 订单、工序、资源和候选分布精确等于本文默认档；
- 所有引用闭合，ID 唯一，时间为规范 UTC；
- 每道工序有 1～3 台 capability 匹配的候选设备；
- 路线图无环，工序深度为 3～6；
- 日历、维护、执行事实和锁无结构冲突；
- 标准 Normalization 与 Data Validation 通过；
- Snapshot 和 v2 PlanningProblem 构建通过；
- 独立 smoke solve 至少返回 Validator PASS 的可行解；
- 任何检查失败时 fail closed，不自动换 seed 或降低数据规模。
