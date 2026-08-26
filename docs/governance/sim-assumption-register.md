---
doc_id: DOC-GOV-007
title: SIM_ASSUMPTION 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [37, 38, 39, 43, 44, 49, 59, 62, 96]
last_reviewed: 2026-08-26
registry_version: 1.0.0
---

# SIM_ASSUMPTION 注册表

## TASK-P3-14 review

Gate复用已登记的P2 versioned synthetic inputs与`SIM-P3-HUMAN-CONTROL-001@1.0.0`，只增加两轮隔离重放和semantic comparison，不引入新的定量值、fixture identity或默认策略。Artifact `9593460266`复验双Backend/Chromium replay但不改变假设生命周期；SIM-ASSUMPTION-001～015全部继续`ACTIVE`，数量15且`registry_version=1.0.0`不变，browser/runtime observations不成为Production事实或SLA。

Simulation 用于模拟 APS Planning Reality，不代表真实物理工厂。每个定量假设必须在 FactoryProfile 或 ScenarioSpec 中版本化，并可追溯到本注册表。

| ID | 仿真假设边界 | 状态 | 约束 |
|---|---|---|---|
| SIM-ASSUMPTION-001 | 虚拟工厂拓扑可以为测试覆盖而构造 | ACTIVE | `synthetic_only=true`，不能成为生产默认值 |
| SIM-ASSUMPTION-002 | 场景随机性由显式 seed 控制 | ACTIVE | Scenario+Profile+Generator version+seed 必须可重放 |
| SIM-ASSUMPTION-003 | 设备故障、延迟、急单等概率只属于 Scenario | ACTIVE | 不得进入 Production Business Policy |
| SIM-ASSUMPTION-004 | 初始场景库覆盖 Flexible Job Shop、Bottleneck、High-Mix Setup、Assembly DAG、Cross-Workshop | ACTIVE | 不支持能力必须得到明确拒绝结果 |
| SIM-ASSUMPTION-005 | XS/S/M/L/XL 只表示 Benchmark 复杂度画像 | ACTIVE | 不代表真实生产容量承诺 |
| SIM-ASSUMPTION-006 | `SIM-MINIMAL-001@1.0.0` topology 仅为 correctness coverage：2 workshops、2 production lines、3 capacity-1 resources、1 order、3 operations | ACTIVE | 只适用于该 fixture version；不得成为真实 topology、通用 XS 或容量默认值 |
| SIM-ASSUMPTION-007 | `SIM-MINIMAL-001@1.0.0` 使用 `08:00Z`～`12:00Z` horizon、900 秒 tick、heat resource `09:00Z`～`10:00Z` maintenance | ACTIVE | 只验证 UTC/tick/calendar boundary；不得作为生产 timezone/calendar closure evidence 或定义生产班次 |
| SIM-ASSUMPTION-008 | `SIM-MINIMAL-001@1.0.0` 选中工时为 3600/1800/3600 秒，alternative 为 5400/2700 秒，edge min/max window 为 `[0,1800]` 秒，cross-workshop transport 为 900 秒 | ACTIVE | 只验证 candidate duration、precedence/max-lag/transport；不得作为生产 transport/duration closure evidence 或定义标准工时 |
| SIM-ASSUMPTION-009 | `SIM-MINIMAL-001@1.0.0` release 为 `08:00Z`，第二工序 material-ready 为 `09:00Z`，due 为 `11:30Z`，synthetic tardiness weight 为 2 | ACTIVE | 只验证 release/material/delivery calculation；不得作为生产 authority/policy closure evidence 或定义生产权重/交期规则 |
| SIM-ASSUMPTION-010 | `SIM-P1-INGRESS-001@1.0.0`固定2 workshops/lines、4 resources、2 orders、3 operations、2 candidates、1 calendar fragment和0.5 material/WIP/lock/cross-workshop quota；generator v1限定10～50 piece、0～600 s setup、300～900 s cycle、0/600 s transport、90 min material delay、30 min calendar fragment/3 h spacing、12 h medium due window、running与lock时间offset及seed-derived 2026 UTC origin | ACTIVE | 只验证P1 source→canonical ingress/replay；不得成为通用XS、生产拓扑/工时/日历/交期/WIP/lock分布或容量默认值 |
| SIM-ASSUMPTION-011 | `P2-GOLDEN-JSSP/FJSP`与`P2-CROSS-WORKSHOP/CALENDAR/MATERIAL-DELAY/RUNNING/HARD-LOCK@1.0.0`固定tiny topology、60秒tick、显式duration/due/calendar/material/fact/lock/transport值及seed `20260901`～`20260907` | ACTIVE | 只验证P2 C-001～C-011、OBJ-001、replay与Validator correctness；`XS`只表示可手算，不是Benchmark profile、Production分布、容量、策略默认值或SLA |
| SIM-ASSUMPTION-012 | `reference-scheduler-policy.v1`固定FCFS/EDD/SPT/Priority+EDD/Greedy Earliest Available Machine的operation/resource deterministic total-order tie-break，并只消费Problem显式priority | ACTIVE | 只验证Simulation baseline correctness/replay；不得成为Production dispatch、fallback、weight、capacity、optimality或SLA策略，也不得关闭任何production-open问题 |
| SIM-ASSUMPTION-013 | `benchmark-profile-set.v1`固定XS/S/M为4/8/12 orders、3/6/8 resources、2/3/4 operations per order、2 candidates、1/2/4 calendar fragments、180/480/900 ticks、seed `20261201`～`20261203`、1 warm-up + 3 measured runs及显式due/material/solve-limit；三个baseline绑定一次Windows AMD64/Python 3.12.13/OR-Tools 9.15.6755观测 | ACTIVE | 只用于P2 development synthetic scale/comparison；不得成为Production topology/distribution/capacity/SLA、L/XL、历史生产数据或部署预算 |
| SIM-ASSUMPTION-014 | `VERSIONED_SYNTHETIC_UI_120@1.0.0`固定120个只读Gantt row、30个order、6个resource、2个workshop、5分钟start offset与3600秒duration，并观察最多24个mounted visual row和完整table fallback | ACTIVE | 只用于TASK-P3-12 browser virtualization/accessibility regression；mock carrier的Production形状不赋予数据真实性，不得成为XS/S/M、Production topology/duration/capacity/SLA、browser matrix或部署预算 |
| SIM-ASSUMPTION-015 | `SIM-P3-HUMAN-CONTROL-001@1.0.0`固定isolated TEST actor、DRAFT/READY/APPROVED/PUBLISHED/ExportJob/audit mock carrier、1个operation与internal ZIP bytes，用于12条human-control/visualization Chromium flow | ACTIVE | 只用于TASK-P3-13 command/state/failure/download E2E；mock transport、5分钟drag量化、browser timing和package bytes不得成为Production role/policy/topology/SLA、external transfer或approval evidence |

TASK-P3-13 review：新增SIM-ASSUMPTION-015并把fixture identity/provenance固定在development-only `.env.e2e`与runtime gate；普通runtime仍为Production-shaped default-deny。Artifact `9589931373`复验12/12 browser与scenario identity，但测试actor、状态carrier、network failure、internal ZIP和browser observations不关闭任何PROD_OPEN，也不表示真实身份、工厂事实或外部成果包。SIM-ASSUMPTION-001～015均`ACTIVE`，ID/状态语义和`registry_version=1.0.0`不变。

除SIM-ASSUMPTION-013明确绑定的P2 development XS/S/M profile和SIM-ASSUMPTION-014明确绑定的P3-12 UI render fixture外，具体workshop/resource数、候选设备密度、故障概率、到期压力等数值仍未批准为其他Profile或生产事实。后续数值必须由各自版本化FactoryProfile/ScenarioSpec/Generator明确，不能从任一fixture或本次baseline外推“通用默认工厂”。

本注册表的稳定 ID 前缀为 `SIM-ASSUMPTION-NNN`。总规示例中的 `SIM_ASSUMPTION-003` 是同类标记的上游拼写，校验时规范化为 `SIM-ASSUMPTION-003`；新引用必须使用本表前缀。条目只能为 `ACTIVE` 或 `RETIRED`，不得出现 `OPEN`/`CLOSED` 生产问题状态，也不得用于关闭任何 `OPEN-NNN`。

修改表结构、ID 前缀或状态语义必须提升 `registry_version`；具体 Scenario/Profile 参数变化由对应资产版本管理。

TASK-P0-03 review：`schemas/samples/*.synthetic.json` 使用显式 `synthetic=true` 和 `SCHEMA-SAMPLE-P0-03`，只验证 Schema，不定义 workshop/resource 数、概率或正式 Scenario/Profile。没有新增或修改 SIM-ASSUMPTION，五项状态继续为 `ACTIVE`。

TASK-P0-04 review：C-012～C-018 与 unsupported/deferred capability 的 expected result 可以是 `UNSUPPORTED_CAPABILITY`，但本 Task 没有创建 Scenario/Profile、概率、工厂参数或 synthetic fixture。规则正反例只是合同文字，不是 Simulation 事实。没有新增/修改 SIM-ASSUMPTION，五项状态继续为 `ACTIVE`，registry format version 不变。

TASK-P0-05 review：FactoryProfile/ScenarioSpec v1 为 SIM-ASSUMPTION-001/002/004/005 提供 version/seed/capability/complexity 的机器字段；Schema samples 明确 `synthetic_only=true`，其单值 count/ratio 只验证形状，不是正式 Profile/Scenario/Fixture 或通用默认值。没有故障概率、正式 XS baseline 或新假设，五项继续 `ACTIVE`，registry format version 不变。

TASK-P0-06 review：新增 SIM-ASSUMPTION-006～009，并在 [`SIM-MINIMAL-001@1.0.0`](../../fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md) 的 Import metadata、计算说明、Profile/Scenario 与 Golden tests 中逐项引用。新增条目只固定首个小型 correctness fixture 的 topology、time/calendar、routing/duration/lag 和 order/gate/due 数值；derived validation/KPI 不是新假设。SIM-ASSUMPTION-001～009 均为 `ACTIVE`，未改变 ID/状态语义或 registry format version。

TASK-P0-07 review：mutation suite 只引用 `SIM-MINIMAL-001@1.0.0` 和 SIM-ASSUMPTION-006～009 的 base facts；09:15 material gate、2700 秒 transport lag、10:45 shortened horizon、running/lock tuples 等值是刻意使约束失败的 test mutations，不是新增 Scenario/Profile 假设、通用 baseline 或生产默认值。没有新增/修改条目；SIM-ASSUMPTION-001～009 全部保持 `ACTIVE`，registry format version 不变。

TASK-P0-08 review：未修改 Simulation code/Schema/Profile/Scenario/Fixture/Benchmark；development/test/benchmark/production environment enum、data-plane guard、health synthetic probes、Compose service count 与 job timeout 只属于 engineering config/test，不是工厂或 Scenario 定量假设。没有新增/修改条目；SIM-ASSUMPTION-001～009 全部保持 `ACTIVE`，registry format version 不变。

TASK-P0-09 review：deterministic replay、Golden 与 mutation gates 复核了 SIM-ASSUMPTION-001～009 的 Scenario/Profile/version/seed/hash 链和 Production isolation boundary；所有值仍只属于 synthetic correctness evidence，没有用于关闭任何 production-open entry 或建立生产默认值。没有新增、修改或 retire 条目，九项全部保持 `ACTIVE`，registry format version 不变。

TASK-P0-10 review：本 Task 只重放既有 Simulation/Golden/Mutation machine gates 并交接 report 文件名，不修改 Profile、Scenario、Generator、Fixture、seed、canonical hash 或任何定量值。没有新增、修改或 retire 条目；SIM-ASSUMPTION-001～009 全部保持 `ACTIVE`，不用于关闭 production-open entry，registry format version 不变。

P1 Task 规划 review：TASK-P1-10 只规划把既有 Generator 输出接入 canonical import records，TASK-P1-11 规划以同一 ingress 对比 reference/synthetic 来源；执行中如需新增定量 Profile/Scenario 假设，必须另行注册并版本化。本次没有新增、修改或 retire 条目；SIM-ASSUMPTION-001～009 全部保持 `ACTIVE`，不用于关闭 production-open entry，registry format version不变。

TASK-P1-01 review：只重放既有Simulation/Golden/Mutation gates并重命名CI输出，不修改Profile、Scenario、Generator、seed、Fixture或定量值。SIM-ASSUMPTION-001～009全部保持`ACTIVE`，不用于生产结论，registry format version不变。

TASK-P1-02 review：两份v2 `.synthetic.json`使用`SCHEMA-SAMPLE-P1-02`、固定seed和小型shape值，只验证Schema/reference/round-trip，不是正式Scenario/Profile/Generator distribution、Fixture或Benchmark。没有新增/修改/retire假设；SIM-ASSUMPTION-001～009全部保持`ACTIVE`，sample数值不得成为生产默认值或OPEN closure evidence，registry format version不变。

TASK-P1-03 review：unit/integration与migration只使用显式synthetic inline bytes、版本、seed和1～2行小批次验证staging/replay/rollback/isolation；这些是test-local values，不是新FactoryProfile/Scenario、分布、容量或Benchmark baseline。没有新增/修改/retire假设；SIM-ASSUMPTION-001～009全部保持`ACTIVE`，不用于Production default或OPEN closure，registry format version保持`1.0.0`。

TASK-P1-04 review：temporary 2-row CSV/XLSX使用显式synthetic source/provenance只验证transport parity、安全拒绝与staging replay；4 MiB/10000-row/archive limits是reference security bounds，不是FactoryProfile规模、Benchmark baseline或Production capacity。没有新增/修改/retire假设；SIM-ASSUMPTION-001～009全部保持`ACTIVE`，不用于Production default或OPEN closure，registry format version保持`1.0.0`。

TASK-P1-05 review：tests中的reference mapping、UTC offsets、DST边界、`s/min/h`、small quantities与synthetic provenance只验证determinism/rejection，不是新FactoryProfile/Scenario distribution、Production timezone/unit policy或Benchmark baseline。没有新增/修改/retire假设；SIM-ASSUMPTION-001～009全部保持`ACTIVE`，不用于Production default或OPEN closure，registry format version保持`1.0.0`。

TASK-P1-06 review：quality tests只从既有P1-02 schema sample复制canonical records并注入cycle/missing resource/unit/duration及结构负例；它们不是新FactoryProfile/Scenario、概率、规模、capacity或Benchmark baseline。没有新增/修改/retire假设；SIM-ASSUMPTION-001～009全部保持`ACTIVE`，不用于Production default或OPEN closure，registry format version保持`1.0.0`。

TASK-P1-07 review：Hypothesis以fixed replay seeds生成test-local 1～3 explicit lots、4-op branch/merge、2 workshops/resources、candidate/fact/lock组合，并在每个Import保留`synthetic=true`与scenario seed。这些值仅用于generation/shrinking，不是新Profile/Scenario distribution、Benchmark baseline或Production topology/policy。没有新增/修改/retire条目；SIM-ASSUMPTION-001～009全部保持`ACTIVE`，registry format version保持`1.0.0`。

TASK-P1-08 review：Snapshot unit/property/integration tests复用P1-02 synthetic schema sample及其既有scenario/profile/generator/seed，新增的Hypothesis seeds只控制test generation；cutoff、hash、entity counts和单Snapshot migration row均不是新FactoryProfile/Scenario distribution或Benchmark baseline。没有新增/修改/retire条目；SIM-ASSUMPTION-001～009全部保持`ACTIVE`，不用于Production default或OPEN closure，registry format version保持`1.0.0`。

TASK-P1-10 review：新增SIM-ASSUMPTION-010并绑定`PROFILE-SIM-P1-INGRESS-001@1.0.0`、`SIM-P1-INGRESS-001@1.0.0`、generator `1.0.0`和seed `20260820`；Profile/Scenario可表达的counts/ratios与generator-only quantity/duration/time算法均逐项限定。该条目只支持49-record correctness/replay，不用于关闭任何PROD_OPEN或形成Benchmark/Production default；SIM-ASSUMPTION-001～010均保持`ACTIVE`，registry format version不变。

TASK-P1-11 review：重用SIM-ASSUMPTION-010的原Profile/Scenario/generator/seed和49-record dataset，没有修改生成分布或新增asset。Gate的cutoff/horizon/tick只是让既有RUNNING/lock facts在Problem v1可表达的fixture-local replay configuration，已记入machine report和Scenario文档，不传播为Production default。SIM-ASSUMPTION-001～010全部保持`ACTIVE`，registry format version不变。

TASK-P1-12 review：审计以原`SIM-P1-INGRESS-001@1.0.0`、Profile/Generator`1.0.0`、seed`20260820`和SIM-ASSUMPTION-010重放两次，并复验P0 Golden/Mutation assumptions；没有修改asset、version、seed、分布、cutoff/horizon/tick或新增定量值。SIM-ASSUMPTION-001～010全部保持`ACTIVE`，不用于关闭PROD_OPEN、建立Benchmark baseline或Production default，registry format version不变。

TASK-P2-01 review：v2 fixed replay从P1-02 synthetic Schema sample派生，并显式使用`plantnexus-synthetic-policy@1.0.0`、priority weight 2、两个测试lock及一个completed→active历史边界；这些只验证字段/时间/hash语义，不是新Scenario asset、分布、Benchmark profile或Production policy。未新增/修改/retire注册项；SIM-ASSUMPTION-001～010继续`ACTIVE`，不得关闭任何Production authority问题，registry format version保持`1.0.0`。

TASK-P2-02 review：四份sample使用explicit Simulation policy/limits source，30秒、1 worker、seed `20260820`、UNKNOWN/no-candidate/zero metrics仅用于Schema、status与fingerprint replay。它们不新增FactoryProfile/Scenario、distribution或Benchmark baseline，也不描述一次Solver执行。未新增/修改/retire注册项；SIM-ASSUMPTION-001～010继续`ACTIVE`，不得作为Production default或PROD_OPEN closure，registry format version保持`1.0.0`。

TASK-P2-03 review：parameter smoke复用P2-02显式30秒/1 worker/seed vector，只验证字段到native参数映射；empty/model-invalid model不是Scenario或Factory假设。未新增、修改或retire任何SIM项；SIM-ASSUMPTION-001～010继续`ACTIVE`，不得作为Production default、业务feasibility或Benchmark evidence，registry format version保持`1.0.0`。

TASK-P2-04 review：formal validator check在进程内构造fresh synthetic Problem/Solution与13个声明式mutation，property seeds只控制测试生成；它们不新增FactoryProfile/Scenario、distribution、size profile或Benchmark baseline，也不修改P0 fixture bytes。未新增、修改或retire任何SIM项；SIM-ASSUMPTION-001～010继续`ACTIVE`，仅支持correctness，不得用于Production default、容量推断或PROD_OPEN closure，registry format version保持`1.0.0`。

TASK-P2-05 review：machine CLI在进程内构造versioned tiny JSSP/FJSP、unary overload与四个choice/load oracle cases；Hypothesis seeds只控制bounded生成，不新增仓库fixture、FactoryProfile、Scenario、distribution或XS/S/M baseline。未新增、修改或retire任何SIM项；SIM-ASSUMPTION-001～010继续`ACTIVE`，这些case只证明core correctness，不得外推Production容量、default或关闭PROD_OPEN，registry format version保持`1.0.0`。

TASK-P2-06 review：machine/property checks仅在进程内派生precedence、historical anchor、fragmented calendar、release/material与transport values，不新增仓库fixture、FactoryProfile、Scenario、distribution或XS/S/M baseline。未新增、修改或retire任何SIM项；SIM-ASSUMPTION-001～010继续`ACTIVE`，synthetic值只证明temporal correctness，不得外推Production日历、物料、运输或容量，registry format version保持`1.0.0`。

TASK-P2-07 review：machine/property checks仅在进程内派生RUNNING remainder/resource、COMPLETED anchor、HARD/SOFT locks及calendar/resource/horizon conflict values，不新增仓库fixture、FactoryProfile、Scenario、distribution或XS/S/M baseline。未新增、修改或retire任何SIM项；SIM-ASSUMPTION-001～010继续`ACTIVE`，synthetic lock比例/值只证明bounded correctness，不得外推Production事实频率、freeze policy、容量或default，registry format version保持`1.0.0`。

TASK-P2-08 local review：machine/unit/property checks使用代码内固定的`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`、source `plantnexus-synthetic-policy@1.0.0`、显式limits/seed及2～5 job tiny due/priority vectors；这些值只验证OBJ-001/Global Strategy/status/Validator correctness，不形成仓库Scenario/Profile、distribution或XS/S/M baseline。未新增、修改或retire任何SIM项；SIM-ASSUMPTION-001～010继续`ACTIVE`，不得外推Production weight/default/capacity/SLA或关闭PROD_OPEN，registry format version保持`1.0.0`。

TASK-P2-08 provider closure：required run/artifact精确重放相同in-memory tiny vectors，没有新增、修改或retire任何SIM项。SIM-ASSUMPTION-001～010继续`ACTIVE`；provider执行不把测试值提升为Scenario distribution、XS/S/M baseline或Production default，registry format version保持`1.0.0`。

TASK-P2-09 local review：新增SIM-ASSUMPTION-011并绑定七个`1.0.0` Scenario、三份Profile、assembler `PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`、approved Simulation Delivery Policy及固定seed。所有输入值在Profile/Scenario/blueprint/calculation note中显式保存，并由manifest固定对象hash和Import/Snapshot/Problem hash；它们只形成Golden/Scenario/property/mutation correctness，不形成XS/S/M baseline、Production default或PROD_OPEN closure。SIM-ASSUMPTION-001～011均保持`ACTIVE`，registry format version保持`1.0.0`。

TASK-P2-09 provider closure：required run/artifact精确重放同一批versioned assets、seeds与hashes，没有修改或retire任何assumption。SIM-ASSUMPTION-001～011继续`ACTIVE`；provider执行不把tiny correctness值提升为XS/S/M distribution、Production default或SLA，registry format version保持`1.0.0`。

TASK-P2-10 local review：新增SIM-ASSUMPTION-012并绑定`reference-scheduler-policy.v1`及五个`reference-*.v1` identity；tie-break、blocked-calendar failure和single-run timing只用于deterministic baseline correctness，不修改P2-09 assets或创建XS/S/M Profile。SIM-ASSUMPTION-001～012均保持`ACTIVE`，不用于Production fallback/default/weight/capacity/SLA或PROD_OPEN closure，registry format version保持`1.0.0`。

TASK-P2-10 provider closure：required run/artifact精确重放同一policy、algorithm identities、Problem hashes与failure boundary，没有修改或retire任何assumption。SIM-ASSUMPTION-001～012继续`ACTIVE`；provider执行不把tiny timing提升为XS/S/M baseline、Production fallback/default或SLA，registry format version保持`1.0.0`。

TASK-P2-11 local review：内部包复用SIM-ASSUMPTION-011的P2 correctness Scenario/Profile/seed与manifest，并保留SIM-ASSUMPTION-012的Reference边界不变；KPI/manifest/sample只是既有synthetic run的派生产物，不新增topology、distribution、权重、calendar、capacity或Benchmark假设。未新增、修改或retire任何条目；SIM-ASSUMPTION-001～012继续`ACTIVE`，internal package不得作为Production或XS/S/M事实，registry format version保持`1.0.0`。

TASK-P2-11 provider closure：required run/artifact精确重放同一synthetic Scenario/Profile/seed、KPI与package lineage，没有新增、修改或retire任何assumption。SIM-ASSUMPTION-001～012继续`ACTIVE`；provider执行不把internal package或single-run telemetry提升为Production事实、XS/S/M baseline或SLA，registry format version保持`1.0.0`。

TASK-P2-12 local review：新增SIM-ASSUMPTION-013并绑定strict profile set、generator `1.0.0`、三个Problem hash、warm-up/repetition和真实baseline environment；XS/S/M全部经formal pipeline/Validator/KPI，但只构成development synthetic evidence。SIM-ASSUMPTION-001～013均`ACTIVE`；任何profile变更必须新版本，数值不得用于Production topology/distribution/capacity/SLA、L/XL，也不得关闭相邻的历史数据或生产运行阈值问题，registry format version保持`1.0.0`。

TASK-P2-12 provider closure：required XS artifact精确复现同一profile/version/seed/Problem hash、1+3 runs与环境carrier，没有修改或retire任何assumption。SIM-ASSUMPTION-001～013继续`ACTIVE`；S/M仍为本地policy，provider执行不把任一数值提升为Production事实，registry format version保持`1.0.0`。

TASK-P2-13 local review：Gate仅重放SIM-ASSUMPTION-011～013既有correctness/reference/benchmark资产及其version/seed/hash，不新增、修改或retire任何assumption。`repeat=2`是Gate验收配置，不是工厂、Scenario或Production定量假设；四类拒绝输入也是contract vectors而非新事实。SIM-ASSUMPTION-001～013全部继续`ACTIVE`，不得用于Production默认值、capacity/SLA或PROD_OPEN closure，registry format version保持`1.0.0`。

TASK-P2-13 provider closure：required artifact精确复现既有Scenario/Profile/seed/hash与两次Gate，没有新增、修改或retire任何assumption。SIM-ASSUMPTION-001～013继续`ACTIVE`；provider执行不把repeat、timing、memory或拒绝向量提升为Production事实，registry format version保持`1.0.0`。

TASK-P2-14 local audit review：审计只重放SIM-ASSUMPTION-011～013的既有versioned correctness/reference/XS-S-M assets；额外`repeat=2`逐场景measurement是审计观测配置，不新增Factory/Profile/Scenario参数或分布。没有新增、修改或retire条目；SIM-ASSUMPTION-001～013全部继续`ACTIVE`，timing/memory/size不得成为Production default、capacity/SLA或PROD_OPEN closure，registry format version保持`1.0.0`。

TASK-P2-14 provider closure：required run `32677741558` / artifact `9503227240`复验既有Scenario/Profile/seed/hash与两次Gate，没有新增、修改或retire assumption。SIM-ASSUMPTION-001～013全部继续`ACTIVE`，registry format version保持`1.0.0`。

## P3 planning review

P3规划只允许复用既有P2 validated synthetic schedule与Simulation plane测试actor验证状态、命令、API/UI、publish/export；没有新增拓扑、角色、权限、性能、分布或业务默认值，因此不登记新的SIM_ASSUMPTION。若后续Task需要新的定量Scenario，必须先版本化并注册，且不得关闭PROD_OPEN。

SIM-ASSUMPTION-001～013全部继续`ACTIVE`。内部Simulation publish/export只证明P3工作流行为，不代表真实Production authority、capacity、SLA或external side effect，`registry_version=1.0.0`格式不变。

TASK-P3-00 provider run `32681493976`没有生成或修改Scenario/Profile/seed/value；SIM-ASSUMPTION-001～013全部继续`ACTIVE`，P3 planned test actor仍不是Production authority。

TASK-P3-01 review：页面/命令/approval合同只定义非定量Simulation test principal和`SIMULATION_INTERNAL` target边界；没有新增Scenario/Profile/seed/topology/size/latency threshold或业务默认值。规模测试只登记观测维度，P2 XS/S/M数值不外推UI/Production容量。SIM-ASSUMPTION-001～013全部继续`ACTIVE`，无新增/修改/retire条目，`registry_version=1.0.0`不变。

TASK-P3-01 provider run `32684713630` / artifact `9505303054`没有生成或修改Scenario/Profile/seed/value，只复验非定量合同边界。SIM-ASSUMPTION-001～013全部继续`ACTIVE`，Simulation test principal与internal target仍不得外推为Production事实。

## TASK-P3-02 simulation assumption review

七份sample复用既有`SIM-P2-GOLDEN-JSSP-001@1.0.0`、Profile、Generator与显式seed作为contract vector；没有新增Factory拓扑、分布、runtime、latency、size或业务默认值。Sample timestamp/ID/fingerprint仅用于确定性Schema replay，不是新的定量Simulation assumption。

因此不新增、修改或retire条目，SIM-ASSUMPTION-001～013全部继续`ACTIVE`；internal target和CI replay不得外推为Production事实，`registry_version=1.0.0`不变。

## TASK-P3-03 simulation assumption review

Repository/migration tests继续只使用既有P3 synthetic samples、固定UTC和临时SQLite；表数、row数、lease秒数、attempt和执行时间仅为contract vector，不是工厂拓扑、分布、SLA或worker默认。`lease_expires_at_utc`逐调用显式传入，不从sample推导Production配置。

没有新增、修改或retire任何条目，SIM-ASSUMPTION-001～013继续`ACTIVE`；Simulation/internal evidence不得外推Production，`registry_version=1.0.0`不变。

## TASK-P3-04 review

Machine/contract/integration只复用既有`P2-GOLDEN-JSSP`及P2 lock correctness case的原Profile/Scenario/assembler/version/seed/hash，未修改fixture bytes或增加新的定量参数。Transaction观测微秒只作单次diagnostic且明确`SLA=NOT_DEFINED`，不登记为性能假设、baseline或Production容量。

SIM-ASSUMPTION-001～013继续`ACTIVE`，没有新增/修改/retire；implementation provider artifact `9510215582`只复验同一synthetic lifecycle，不把fixture、test actor或单次timing外推为Production事实，`registry_version=1.0.0`不变。

## TASK-P3-05 review

Machine/property/contract/integration复用既有`P2-GOLDEN-JSSP`与`P2-GOLDEN-FJSP`的原Scenario/Profile/assembler/version/seed，不改fixture或建立新分布。两个Version、23个普通view payload、source/projected bytes及elapsed microseconds只作synthetic XS observation；不新增threshold、baseline或Production容量假设。SIM-ASSUMPTION-001～013继续`ACTIVE`，`registry_version=1.0.0`不变。

Implementation artifact `9512423712`精确复验相同两个versioned synthetic inputs及边界；没有新增、修改或retire任何SIM assumption。

## TASK-P3-06 review

Machine/property/contract/validation/integration只复用既有`P2-GOLDEN-JSSP`与`P2-GOLDEN-FJSP`版本、Profile/Scenario/assembler/seed，不修改fixture bytes或增加新定量policy。Generated idempotency key/lock suffix与command microseconds只属test-local evidence，不登记分布、threshold、baseline或Production容量。SIM-ASSUMPTION-001～013继续`ACTIVE`，无新增/修改/retire且`registry_version=1.0.0`不变。

Implementation artifact `9515126567`精确复验相同versioned synthetic inputs与上述边界；没有新增、修改或retire任何SIM assumption。

## TASK-P3-07 review

Machine/unit/contract/integration/security只复用既有P2-GOLDEN-JSSP与P3-04 reviewable lifecycle，生成的test actor、capability set、resource scope、idempotency key和decision microseconds均为非定量test-local evidence。未修改Scenario/Profile/assembler/version/seed/fixture bytes，未新增role分布、approval比例、latency threshold、baseline或Production容量假设。

SIM-ASSUMPTION-001～013继续`ACTIVE`，无新增/修改/retire且`registry_version=1.0.0`不变；artifact `9544333991`只复验既有synthetic输入与test policy，Simulation APPROVED/REJECTED结果不得外推真实责任或Production authority。

## TASK-P3-08 review

Machine/unit/contract/integration/security继续复用既有P2-GOLDEN-JSSP与P3 lifecycle，test actor/capability/scope/idempotency/current race和publication microseconds均为非定量test-local evidence。没有修改Scenario/Profile/assembler/version/seed/fixture bytes，也没有新增publish率、并发分布、latency threshold、external target或Production容量假设。

SIM-ASSUMPTION-001～013继续`ACTIVE`，无新增/修改/retire，`registry_version=1.0.0`不变；implementation artifact `9545782727`只复验同一test-local carrier与state evidence，internal Simulation PUBLISHED/SUPERSEDED不得外推真实发布或Production authority。

TASK-P3-09复用既有synthetic scenario/profile/generator/seed与P2 correctness payload；未新增假设ID。Provider artifact `9548027237`精确复验synthetic target、12 payload、4 sheets与Simulation-only边界；Package size、row/sheet count、SQLite lease与local atomic rename仍只作为development evidence，不外推真实数据规模、distributed filesystem或Production retry。13项假设继续ACTIVE且registry version不变。

TASK-P3-10只复用synthetic carrier/resource、stable test principal与test application facade，未新增假设ID。Provider artifact `9550224090`精确复验17 routes/delegations、Simulation flag/plane与Production pre-provider denial；TestClient、URL-encoded query字节、OpenAPI fingerprint、route数和本地latency仍不外推真实用户、网络、identity provider、Production流量或SLA，13项假设继续ACTIVE且registry version不变。

## TASK-P3-11 provider closure review

Frontend unit/component测试可复用显式versioned synthetic carrier，并记录bundle bytes、virtualized rows和test-local render/query observation；不得新增真实订单/资源/用户分布、浏览器容量阈值、网络latency、identity或Production SLA假设。Production navigation不得显示synthetic seed或Simulation-only入口。

SIM-ASSUMPTION-001～013继续`ACTIVE`，本Task不新增、修改或retire假设，`registry_version=1.0.0`不变。Development fixture、jsdom和local bundle observation不得外推P3-12/13 browser E2E、P4或Production证据。

TASK-P3-12 review：新增SIM-ASSUMPTION-014，把120-row/30-order/6-resource/2-workshop/5-minute-offset/3600-second-duration数据绑定到`VERSIONED_SYNTHETIC_UI_120@1.0.0`，仅用于read-only Chromium virtualization、可访问table fallback和development render observation。Artifact `9555196470`复验120 total/最多24 mounted rows与4/4 browser，但其mock响应保持Production-shaped frontend carrier只为验证runtime isolation，不构成真实Production数据或authority；不得外推XS/S/M、browser matrix、topology/duration/capacity/SLA。SIM-ASSUMPTION-001～014均`ACTIVE`，表结构、ID/状态语义与`registry_version=1.0.0`不变。

Implementation artifact `9552386549`复验25 tests只使用in-memory versioned payload，runtime明确拒绝Simulation/Development plane；没有新增seed/profile/distribution。全部13项假设继续ACTIVE且registry version不变。
