---
doc_id: DOC-CORE-003
title: 术语表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [1, 13, 14, 19, 23, 24, 29, 30, 32, 33, 34, 37, 38, 39, 114]
last_reviewed: 2026-09-04
---

# 术语表

## TASK-P4-04 formed terms

- **Event ingress transaction**：验证一个ExecutionEvent后，仅原子append ledger记录与对应audit；不解释事实。
- **Fact projection transaction**：消费同一authority stream从position 1开始的完整连续prefix，在pure projector外原子提交new immutable Snapshot、checkpoint和audit。
- **Urgent Demand standard ingress**：用Raw Staging+MappingProfile重走Normalization/Data Validation/Expansion/Snapshot的唯一合法urgent数据路径；不是private canonical shortcut。
- **Projection checkpoint**：保存已消费position、prefix fingerprint与当前Snapshot reference的operational CAS，不是业务状态机。


## TASK-P4-02 machine terms

- **ExecutionEvent v1**：带显式Simulation plane、authority/source stream、单调position、occurred/received时间、typed payload与canonical identity的不可变事件carrier；不是已接入的外部事件。
- **ReplanRequest v1**：绑定PUBLISHED base、new Snapshot/Problem、ordered events/facts、resolved freeze、Policy/Limits的immutable intent/result lineage；没有业务状态机。
- **ChangeReport v1**：对base operation全集逐项分类并绑定before/after KPI、facts/locks/reasons与完整replan lineage的不可变报告carrier。
- **ExecutionSimulationManifest v1**：记录Scenario/Profile/Generator/Simulator、seed、virtual clock、authority stream与checkpoint的Simulation-only manifest；不是Simulator执行证据。

| 术语 | 项目语义 |
|---|---|
| APS | Advanced Planning and Scheduling；本项目的计划排程模块 |
| APS Core | 通用领域、Problem、Solver、Validator、状态与不变量实现；不得包含企业项目分支或反向依赖Extension |
| APS Runtime | 装配Core、Headless API、Solver Worker、Validator、持久化与受控Extension loader的实际服务端运行载体 |
| APS Extension SDK | 面向可信Enterprise Extension的versioned内部SPI；不是外部HTTP API或安全沙箱 |
| Enterprise Extension | 单个企业独立维护、只依赖指定SDK并由Runtime加载的Constraint/Objective/Rule/Policy artifact与配置 |
| Plugin Registry | 按stable ID/version/capability确定性校验、排序、解析并fingerprint Extension贡献的Runtime registry |
| APS Developer Kit | 经共同兼容验证并锁定Runtime、SDK、模板、工具、示例、文档和供应链证据的不可变开发交付组合 |
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

## TASK-P3-04 terms

- **Validated Planning Output Bundle**：同一PlanningRun的Snapshot、Problem、PlanningSolution、SolverReport、fresh ValidationReport、ImportQualityReport与exact KPI；缺一、mixed或stale均不得形成ScheduleVersion。
- **Reviewable ScheduleVersion**：已由application原子经历DRAFT→READY_FOR_REVIEW且绑定完整lineage/audit的immutable Version；不等于APPROVED、PUBLISHED、Production-ready或有审批人授权。
- **Lifecycle exact replay**：same plane/scope/key reference与same request返回原READY carrier和原AuditEvent，不新增self-transition、版本或audit；same key/different request为conflict。
- **Upstream auth-policy context**：写入audit的已解析引用信息，只用于追踪；P3-04不实现identity/RBAC mapping，OPEN-010仍OPEN。
- **Workspace projection**：从一个exact immutable source set确定生成的只读payload；strict carrier只保存stable item identity/type与payload fingerprint，不能成为第二事实源。
- **Query-scope cursor**：绑定view、filter、sort、page size、Version precondition、source与collection fingerprint的opaque游标；不保存业务权威且source变化时必须拒绝。
- **P3 Version Comparison**：两个immutable ScheduleVersion的operation/KPI delta只读DTO；不是P4 ChangeReport、ReplanRequest或新Version。
- **Schedule command identity**：由plane、command type、source、target组成的server scope与raw idempotency key的SHA-256 reference；决定new Version/Audit ID，raw key不进入durable audit。
- **Copy-on-write command DRAFT**：Move/Assign/Set/Remove Lock经server semantic guard和fresh formal Validator后创建的独立DRAFT；parent/source state/content保持不变。
- **Manual review submission**：对`MANUAL_EDIT|LOCK_CHANGE` DRAFT执行的独立`SUBMIT_FOR_REVIEW`命令；第二次fresh Validator PASS且lineage fingerprint一致后，只以既有pair把同一ID/content推进`READY_FOR_REVIEW`并原子追加audit，不等于approve/reject。
- **Failed command candidate**：尚未成为ScheduleVersion的内存candidate；TASK-P3-06在任何Validator/identity/persistence失败时丢弃，不得称为“已保存但不可评审”版本。
- **Approval decision context**：server-resolved的authenticated principal reference、capability set、exact ScheduleVersion scope、test policy、plane binding、UTC与code facts；不是客户端role声明，也不是Production RBAC。
- **Decision identity**：plane、APPROVE/REJECT、ScheduleVersion、workspace target与raw key reference形成的deterministic Audit identity；same request重放原logical result，raw key不进入durable event。
- **Authorization denial audit**：高风险decision在capability/scope/authentication或Production default-deny时追加的sanitized DENIED event；不读取或保存source/lineage/before/after reference，也不改变ScheduleVersion。
- **Approved ScheduleVersion**：READY经authorized `approve` capability与atomic decision audit进入的同ID/content状态；只成为P3-08 publish的前置候选，不等于PUBLISHED、Production-approved或外部已发布。
- **Publication context**：server-resolved authenticated actor、publish capability、exact ScheduleVersion scope、Simulation test policy、plane binding、UTC与code facts；不是客户端role/target声明。
- **Current publication reference**：按plane+internal target唯一保存当前PUBLISHED ScheduleVersion/content/publication identity与CAS revision的projection；不是可编辑Version内容。
- **Publication exact replay**：same scope/key/request从append-only success audit重建原APPROVED→PUBLISHED及optional supersession logical result，设置response replay marker但不重复state/audit/current side effect。
- **Superseded ScheduleVersion**：旧current在新Version原子成为current时由PUBLISHED进入的历史状态；content、decision与原publication evidence保持不可变，`superseded_by`指向当次新PUBLISHED reference。
- **Standard Export Package v1**：由`export-manifest.v2`描述的P3 internal Simulation package profile；含12个JSON/CSV/XLSX payload并绑定PUBLISHED Version、PublicationResult、ExportJob attempt、audit与P2 lineage。其版本号与manifest document version彼此独立，不代表external/Production delivery。
- **Manifest-last**：同一临时目录先写全部payload并校验，最后写`manifest.json`，随后原子rename；Job只有在该边界成功后才能进入EXPORTED。
