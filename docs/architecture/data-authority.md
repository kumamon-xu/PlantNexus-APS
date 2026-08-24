---
doc_id: DOC-ARCH-005
title: 数据权威边界
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [15, 22, 59, 61, 90]
last_reviewed: 2026-08-24
---

# 数据权威边界

| 数据 | 权威来源 | 当前注意事项 |
|---|---|---|
| Order | ERP | 字段级权威仍受 OPEN-015 约束 |
| BOM | ERP | V1 不负责自动 MRP |
| Purchase Promise | ERP | 与 material readiness 的关系待确认 |
| Execution | MES | 已完成/运行中事实不可被计划覆盖 |
| Machine Runtime State | MES | 故障/恢复成为执行事实或事件 |
| Physical Inventory | WMS | V1 不做完整库存平衡 |
| CAM Processing Feature | CAM | V1 不做联合优化 |
| Planning Decision | APS | 必须经过 Validator 和人工审批 |

## AI 边界

AI 可以输出 `duration`、`risk`、`confidence` 及版本信息。AI 不能成为 routing、resource compatibility、hard constraint、schedule state 或业务权重的权威来源。

## Material Readiness

V1 接受上游提供的 `material_ready_at`，并执行 `operation.start >= material_ready_at`。Solver 不猜库存齐套时间。若上游不能直接提供，应通过 `MaterialReadinessProvider` 扩展，并由 OPEN-007/OPEN-015 关闭其权威问题。

## 冲突处理

来源冲突不得由最后写入或 AI 推断解决。应在 Raw Staging/Normalization 阶段保留来源、版本和冲突诊断，根据字段权威规则拒绝或等待业务决策。

## P0 Schema boundary

`import-package.v1` 只建立 source version、synthetic 标记和 records envelope，记录体保持明确的 P1 扩展点；它没有批准 ERP/MES/WMS/CAM 字段映射。`planning-snapshot.v1` 与 `planning-problem.v1` 只编码总规已经决定的字段和单位。OPEN-002/007/013/015 全部保持 OPEN，sample 中的 source/scenario 值不能成为 Production authority。

## P0 rule/state authority review

`constraint-rule-sheet.v1` 只规定如何验证已经进入正式合同的事实，不成为业务数据权威。C-006 仍消费上游 `material_ready_at`，C-007 仍服从 MES execution facts，C-008 lock/approval actor 与 C-009 transport 来源分别受 OPEN-005/010/009 约束。`capability-registry.v1` 的 V1_SUPPORTED 也不是资源 capability 主数据来源。

规则 example、state guard/evidence 文本和 synthetic expected rejection 都不能关闭 PROD_OPEN、填充 Production 字段或替代 ERP/MES/WMS/CAM/人工审批权威。

## TASK-P0-08 infrastructure review

health payload 只公开 service/build metadata 与 database/redis availability code，不读取或返回 Order/BOM/Execution/Inventory/Planning Decision。`engineering_job_records`、`engineering_idempotency_records` 是通用执行元数据，不成为业务事实、Schedule 状态或发布权威；process-local idempotency reference store 也不能授权任何业务副作用。

Compose 的 database name、user、network endpoint 和 non-production placeholder 只用于 development skeleton，不回答 OPEN-002/003/015，也不成为生产字段或系统权威。P0-08 未建立任何产品 API 或外部 adapter。

## TASK-P1-02 canonical authority boundary

`canonical-records.v1`固定APS内部语义、稳定引用、单位/UTC/duration形状与record-level source provenance；`import-package.v2`要求envelope source versions与record source/version一致。它不声明任何ERP/MES/WMS/CAM列名、系统优先级、冲突解决、单位换算、timezone、lot split、duration fallback或生产日历规则。

Pure precheck只拒绝不一致的ID/reference/unit/time/duration/provenance，不能把“Schema接受”解释为字段权威或DataValidation PASS。OPEN-001/002/003/004/007/008/009/013/014/015均保持OPEN；synthetic sample值不能用于关闭任何条目。

## TASK-P1-03 staging authority boundary

Raw Staging新增的source system/version、content/row digest、row identity/location、received-at、media type与source name只构成接收和审计事实，不决定Order/Execution/Inventory/CAM/Planning字段权威，也不解决来源冲突。repository保存opaque bytes且没有canonical/Snapshot/Problem转换方法；同idempotency scope下的source/version/content差异被拒绝，不能以最后写入覆盖。

`raw_import_*`列是internal persistence schema，不是ERP/MES/WMS/CAM接口或field mapping。SQLite synthetic测试和migration sample不提供OPEN-002/015的权威来源，两个条目继续OPEN；后续Adapter/Normalization必须在本边界之后显式解释来源而不能从staging列名推断生产字段。

## TASK-P1-04 reference adapter authority boundary

ReferenceFileAdapter v1只权威记录“调用方声明的source system/version + 实际文件bytes/位置 + transport三列”。`record_type`与opaque `payload_json`不批准canonical collection、业务字段、单位、timezone、冲突优先级或系统权威；即使文件被成功读取并持久化，也不能称为Canonical/DataValidation PASS。

`production_binding=false`表示该实现不是任何真实ERP/MES/WMS/CAM连接器。Adapter可以按调用方显式data plane构造Raw Staging batch，但不能据此授权Production映射；OPEN-002/013/015继续OPEN，冲突和mapping必须由后续versioned Normalization/authority evidence处理。

## TASK-P1-05 explicit mapping authority boundary

MappingProfile只能声明一个精确source system/version的record/field转换，profile/version与unit registry version进入canonical provenance。不同source version、同source多profile、混合data plane或synthetic provenance冲突均拒绝；payload不能覆盖自动注入的`source`，未映射字段也不能被忽略。

这些profile是通用可测试机制，不是Production ERP/MES/WMS/CAM authority配置。仓库未提交任何真实系统mapping、field precedence、timezone或unit default；OPEN-001/002/013/015继续OPEN。Raw Staging保留transport truth，canonical package只承载显式映射结果，两者不能互相伪造。

## TASK-P1-06 validation authority boundary

Data Validation只判断“显式canonical事实是否自洽”：record source/version必须出现在Import envelope，引用与order/routing/fact/lock lineage必须闭合，单位逐级一致，route必须为DAG，resource option必须存在且能力匹配。Error v3的source location由record source reference与canonical field组合，不用数组位置或推测原始文件坐标。

该Gate没有资格选择冲突source、定义真实machine capability、转换新增unit、补duration、合并calendar或决定material/transport authority；它只能拒绝不完整/不一致事实。OPEN-001/002/004/007/009/013/014/015全部继续OPEN，PASS报告不构成Production authority批准。

## TASK-P1-07 expansion authority

Order Expansion只投影已经明确存在的authority-neutral canonical事实：Demand/ProductionOrder/Lot/Routing lineage、lot quantity/unit、candidate duration/source、release/material gate、execution fact和lock。Derived ID与排序由code version决定，但不创造业务事实；output中的Import/quality/source/synthetic provenance保留回链，OperationInstance字段不足时必须升级合同而不能隐藏数据。

多个显式lot可逐一展开，但服务无权决定lot数、lot size或split/merge；也无权重算duration、选择resource、改变fact/lock或定义transport/material规则。OPEN-007/008/014/015继续OPEN，PASS与Expansion hash均不是Production authority closure evidence。

## TASK-P1-08 Snapshot authority boundary

PlanningSnapshot只冻结已经由Import/PASS/Expansion链显式提供的事实和版本，不把derived ID、entity count、hash或repository row提升为ERP/MES/WMS/CAM authority。Builder核对content-derived package identity和完整provenance，但不选择冲突source、不补timezone/calendar/material/transport/unit/duration/lot规则，也不把synthetic值转换为Production事实。

Snapshot事实被发现错误时必须由权威上游产生新Import/quality/expansion并创建新Snapshot，禁止就地修补历史bytes。OPEN-001/002/004/007/009/015及全部OPEN项继续OPEN；hash一致只证明输入重放一致，不证明业务来源真实、生产批准或校准完成。

## TASK-P1-10 synthetic-source authority boundary

P1 Generator只对`SIM-P1-INGRESS-001@1.0.0`及其版本化Profile/Scenario/seed负责；source system `plantnexus-synthetic`、mapping和生成的quantity/duration/time/calendar值都是合成provenance，不是ERP/MES/WMS/CAM或人工业务权威。Normalization仍只按显式mapping/unit规则转换，Data Validation仍只判断canonical自洽；PASS/hash不把synthetic值升级为Production事实。

`cycle_seconds_per_unit`分类修复只恢复既有integer-duration authority链，不批准新unit、default或source precedence。OPEN-002/004/013/015及全部PROD_OPEN保持OPEN；真实系统binding、冲突优先级和校准仍须外部authority evidence。

## TASK-P1-11 authority preservation

Common ingress不新建authority层：ReferenceFileAdapter仅读取同一synthetic source rows的temporary CSV，并保留`production_binding=false`。Application只校验所选data plane、传递明确versions和组合既有artifacts；PASS、hash和双入口parity均不使synthetic values成为Production权威数据。

所有PROD_OPEN继续OPEN，未决定ERP/MES/WMS/CAM binding、field precedence、unit/timezone、lock/freeze、horizon或真实分布。

## TASK-P2-01 Problem v2 authority projection

DemandOrder `due_at_utc`及source三元组从Snapshot canonical record逐字进入DeliveryDemand；priority不是Snapshot已有权威字段，因此v2 builder要求调用方为每个active demand提供非boolean正整数权重和独立source system/version/record ID，禁止默认`1`、缺省排序或把Scenario值冒充Production authority。OPEN-006/015未关闭时Production使用继续阻断；Simulation只允许显式versioned policy。

Resource topology/status/calendar/capabilities、ExecutionFact和OperationLock仍只由Snapshot canonical facts提供，Problem builder不成为数据owner。`capacity=1`是C-003 primary unary contract语义，不推断人数/模具/工装或secondary capacity。真实lock owner、due/priority policy、resource/calendar/transport authority继续受OPEN-004/005/007/009/010约束。

## TASK-P2-13 authority boundary

Vertical Gate只重放已版本化的synthetic Profile/Scenario/Policy/Limits和已有canonical lineage，不新增、选择或覆盖任何业务权威。四类边界明确拒绝unsupported capability、invalid Problem、invalid SolveLimits，并把UNKNOWN保持为无candidate的`NO_SOLUTION_WITHIN_LIMIT`；这些machine结论既不是Production数据权威，也不能把缺失事实补成默认值。

报告中的due/priority、resource/calendar/material/transport、fact/lock、runtime与memory仍分别受原Scenario/Problem/baseline provenance约束。全部PROD_OPEN继续OPEN，尤其OPEN-006/011/012/015没有Authority/Evidence closure record；Gate PASS只证明Simulation链路可重放，不批准Production binding、capacity、SLA或发布。

Provider artifact `9440650646`精确复现相同Simulation-only authority boundary；20份报告均未引入Production source/default/closure record。TASK-P2-13=`done`不改变任何PROD_OPEN或Production publishability。

## P3 authority planning

ScheduleVersion内容权威来自validated PlanningSolution与显式human command；状态权威只属于server application/state machine，UI/API transport不得自封权威。OPEN-010关闭前capability matrix只能表达view/edit/lock/approve/reject/publish/export/audit并在Production default-deny，Simulation test actor也不能成为真实角色。外部publish target与字段authority继续受OPEN-002/015约束。

TASK-P3-01现形成该合同：ScheduleVersion content由P2 immutable lineage加server接受的copy-on-write command派生；state/current publication、`allowed_actions`和decision result只由application/state repository事务授权；ExportJob/artifact有独立authority且不能反写publish。actor只能保存已认证principal reference和resolved capability，客户端自报role、UI按钮与test fixture均无authority。

Production没有principal→capability/resource/target mapping时DENY，`SIMULATION_INTERNAL`只用于隔离测试。OPEN-002/010/015没有closure record；真实角色、字段owner、external target和approval仍未知。
## TASK-P3-02 carrier authority review

七份P3 Schema固定carrier中的authority边界：P2 artifact references/content fingerprint是ScheduleVersion事实；state pair仍由`state-machines.v1`授权；`allowed_actions`是未来server结果而非client grant；authenticated principal/role明确不进入command body；Publication/Export v1 target仅`SIMULATION_INTERNAL`。Synthetic sample和CI provider均不是Production authority。

`app.domain.workspace_contracts`只验证canonical/cross-value invariant，不读取DB、environment identity provider或客户端role。真实repository/application/auth/API authority仍未形成，OPEN-002/010/015继续default-deny。

## TASK-P3-03 persistence authority

机器Schema继续是carrier形状/字段权威，`state-machines.v1`继续是pair权威；migration没有用DB default补造任何业务字段。Repository只保存完整carrier并维护storage-only state/reference revision与显式lease expiry。ScheduleVersion content/lineage/validation以creation+immutable fingerprint为权威历史，AuditEvent/PublicationResult只能追加，current publication reference只是可CAS projection。

Repository不是capability、approval、publish或export authority；`SIMULATION_INTERNAL`存储成功也不授权Production。OPEN-002/010/015保持OPEN，真实identity/target/field owner仍不能由test actor或DB row推断。

## TASK-P3-04 authority review

P2 Snapshot/Problem/Solution/Validation/KPI/SolverReport继续分别拥有其事实与计算证据；P3-04只复制validated assignment/lock projection并引用fingerprint，不成为上游事实修改者。Formal Validator和`build_kpi_v2`仍是correctness authority，repository只是durability/CAS authority，application只拥有本次消费/事务编排。

Audit中的actor、auth-policy version与resolved `edit` capability是caller-supplied upstream context，不建立identity/RBAC authority；READY的`allowed_actions`是carrier state能力集合，不是对某用户的审批授权。OPEN-010未关闭，Production channel继续default-deny。

## TASK-P3-05 projection authority

Snapshot仍拥有orders/calendars/source，Problem拥有operations/resources/horizon/locks，PlanningSolution拥有assignments，KPI拥有delivery/planning/resource指标，Solver/Validation/Quality report拥有各自diagnostic/status，ScheduleVersion拥有immutable content/state/lineage，Audit repository拥有event历史。Read layer只关联并投影这些事实；Resource Load从assignment求和后必须与KPI resource事实一致，任何冲突均停止而不是选择或修补一方。

Query carrier、cursor、collection fingerprint和comparison都只是derived read evidence，不获得write、state、authorization、Solver、Validator或P4 authority。

## TASK-P3-06 command authority

Human content command intent经server接受后成为新ScheduleVersion content的派生权威；source Version、immutable Problem和execution facts仍拥有其历史/约束事实。Server semantic guard拥有command shape/reference/time/lock authority，fresh formal Validator拥有C-001～C-011 correctness authority，repository只拥有durability/CAS/idempotent replay authority。显式review submission在第二次fresh PASS后只授予manual DRAFT既有`READY_FOR_REVIEW`状态事实，不授予approval。Origin PlanningSolution/KPI/SolverReport保留为provenance，不得被宣称为人工content的逐字等同或重算KPI。

客户端`required_capability`、UI按钮和Simulation actor都不是authorization authority；应用只接受server-resolved capability context，Production在OPEN-010关闭前default-deny。PUBLISHED/current publication不因command改变，P4 fact/freeze/replan authority也未形成。
