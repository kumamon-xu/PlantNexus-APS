---
doc_id: DOC-CORE-003
title: 术语表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [1, 13, 14, 19, 23, 24, 29, 32, 33, 34, 37, 38, 39]
last_reviewed: 2026-08-19
---

# 术语表

| 术语 | 项目语义 |
|---|---|
| APS | Advanced Planning and Scheduling；本项目的计划排程模块 |
| PlanningSnapshot | 截止某一时点形成的不可变、确定性、可重放计划输入快照 |
| PlanningProblem | 由 Snapshot 构建的可序列化、Solver-neutral 求解问题 |
| PlanningPolicy | 业务目标层级、锁定/稳定性等计划策略输入，不包含 Solver 对象 |
| SolveLimits | 时间、资源等求解预算；不得改变业务规则 |
| PlanningStrategy | 组织一个 PlanningRun 的求解策略；V1 默认 `GlobalCpSatStrategy` |
| SolverBackend | 面向 PlanningProblem 的可替换求解后端协议 |
| PlanningSolution | SolverBackend 的候选结果，不等于已经验证或已批准计划 |
| ScheduleValidator | 独立检查计划是否满足 C-001～C-011 的组件 |
| PlanningRun | 从输入到验证完成的计算生命周期，不包含批准和发布状态 |
| ScheduleVersion | 独立的计划业务版本，承载 Draft、Review、Approval、Publish 生命周期 |
| ExportJob | 成果包导出的异步、幂等、可重试任务 |
| OperationInstance | Solver 实际排程对象，由订单、批次和工艺展开而来 |
| RoutingOperation | 工艺定义，不是直接排程实例 |
| OperationResourceOption | 某 OperationInstance 在候选 Resource 上的 setup、cycle、final duration 等参数 |
| DeliveryDemand | PlanningProblem v2中绑定DemandOrder due/source与显式priority/source的Solver-neutral交付需求事实 |
| HistoricalCompletionAnchor | 已完成前驱跨入active precedence边界时保留fact/resource/actual times/source的只读历史锚点；不是future OperationInstance |
| Canonical Records | authority-neutral、严格版本化的APS实体集合；稳定ID与source provenance已固定，但外部系统字段mapping仍由Adapter/OPEN决定 |
| Standard Import | Production Adapter与Synthetic Generator共同输出的版本化canonical envelope；不是Raw Staging或Data Validation的替代品 |
| ImportQualityReport | Data Validation对一个Import v2产生的确定性PASS/FAIL报告；包含有序Error v3、精确计数和内容派生report ID，不是ScheduleValidator结果 |
| Order Expansion | DataValidation PASS后把显式ProductionLot与Routing DAG确定性映射为OperationInstance/precedence edge的纯步骤；不自动拆批、补工时或构建Solver模型 |
| Expansion Version | 控制derived instance/edge ID和展开语义的独立code-level版本；`order-expansion.v1`不得被未来实现原地重解释 |
| HARD_LOCK | 资源、开始和结束均固定的硬锁 |
| SOFT_LOCK | 通过稳定性目标施加变化成本的软锁 |
| material_ready_at | 上游权威来源提供的物料齐套门，不由 Solver 猜测 |
| FactoryProfile | 描述一类虚拟工厂的版本化 Simulation 配置，永远 `synthetic_only` |
| ScenarioSpec | 包含场景、版本、seed、能力、复杂度和期望行为的可重放定义 |
| ScenarioManifest | 记录 Scenario/Profile/Generator/seed、环境、generated-at、Standard Import package 与 dataset hash 的 synthetic run provenance；时间戳不进入 dataset hash |
| Generator Version | 生成逻辑的独立版本；不同于 Scenario/Profile asset version、Schema Set 与代码提交 |
| Reference Scheduler | FCFS、EDD 等非生产启发式基线，用于 sanity check 和 Benchmark |
| Golden Fixture | 足够小、可人工或暴力验证的确定性测试数据 |
| PROD_OPEN | 尚未由真实生产业务确认、会阻止生产发布的问题 |
| SIM_ASSUMPTION | 只在仿真中有效的显式假设，不能成为生产规则 |
| Tick | Solver 离散时间单位；`duration_ticks = ceil(duration_seconds / tick_seconds)` |
| Provenance | 从数据源、规则、问题、Solver、Scenario 到代码提交的全链路来源信息 |
| ADR | Architecture Decision Record；记录需要治理的架构或语义决策 |
| Schema Set | 同一发布批次的机器合同集合；当前为 `2.4.0`，保留 `1.0.0/1.1.0/1.2.0/2.0.0/2.1.0/2.2.0/2.3.0` artifacts，且不替代各 document/asset/registry version ID |
| Canonical ID | 跨合同稳定引用的非空、无空白标识；具体来源映射仍由字段权威规则决定 |
| Constraint Rule Sheet | C-001～C-018 的版本化机器规则元数据；固定输入、公式、正反例、violation 和 Test ID，但不等于 ScheduleValidator 实现 |
| Capability Registry | 固定 capability 名称与 V1_SUPPORTED/UNSUPPORTED/DEFERRED 状态；V1_SUPPORTED 不表示当前阶段代码已实现 |
| State Transition Registry | 固定 PlanningRun、ScheduleVersion、ExportJob 的允许 pair、终态与 guard/evidence；JSON Schema 只验证 state 名称 |

术语新增或语义变化必须同步检查 Schema、Constraint、状态机、测试和追踪矩阵。

当前Schema Set为`2.6.0`；`1.0.0`是TASK-P0-03数据合同发布，`1.1.0/1.2.0` additive增加rule/state/error/capability与Simulation contracts，`2.0.0` breaking set新增canonical-records.v1、Import v2与Snapshot v2，`2.1.0/2.2.0` additive增加unit/Data Quality，`2.3.0/2.4.0/2.5.0`依次增加Problem v2、planning-machine和KPI/ExportManifest，`2.6.0`增加P3 workspace carriers。全部历史artifact保留，document/registry version仍需显式选择。
## TASK-P3-02 machine-carrier terms

- **Workspace Query**：`workspace-query.v1`严格REQUEST/RESULT carrier；只选择受支持view并携带稳定sort/filter/page/fingerprint，不是repository/table selector。
- **Workspace Command**：`workspace-command.v1`严格human intent carrier；携带CAS、reason、target与idempotency，但不携带principal/role authority。
- **ScheduleVersion content fingerprint**：对`content={assignments,locks}`执行`canonical-json.v1`所得SHA-256；它不等于完整ScheduleVersion document fingerprint。
- **Workspace control reason**：`workspace-control.v1` module-local的`AUTHORIZATION_DENIED/IDEMPOTENCY_CONFLICT/EXPORT_FAILED`；不是global product error code。
- **PublicationResult**：APPROVED Version到`SIMULATION_INTERNAL`的成功logical result carrier；不等于approval、ExportJob或Production publish。
- **ExportJob**：从PUBLISHED ScheduleVersion创建的独立lifecycle carrier；不等于ExportManifest或外部传输。

这些词在TASK-P3-02只形成Schema与pure precheck含义；repository/application/API/UI/worker行为仍未形成。

## TASK-P3-03 persistence terms

- **State revision**：repository内部单调整数，只用于expected-state CAS并发控制，不是ScheduleVersion业务`revision`，也不进入机器carrier。
- **Creation bytes**：首次插入ScheduleVersion/ExportJob时保存的canonical carrier bytes；同identity exact replay必须与其一致，之后的合法state metadata由当前carrier另存。
- **Current publication reference**：按plane/target保存的唯一current ScheduleVersion projection；只能由PublicationResult storage transaction以expected reference CAS替换，不等于业务Publish授权。
- **Lease expiry metadata**：ExportJob repository显式接收的UTC storage coordination值；没有DB业务默认，不是`export-job.v1`字段，不能由API或worker自行补猜。

上述术语只描述TASK-P3-03持久化原语；approval/publish/export execution、HTTP/UI与Production topology仍未形成。
