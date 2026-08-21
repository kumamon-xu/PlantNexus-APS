---
doc_id: DOC-GOV-007
title: SIM_ASSUMPTION 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [37, 38, 39, 43, 44, 49, 59, 62, 96]
last_reviewed: 2026-08-21
registry_version: 1.0.0
---

# SIM_ASSUMPTION 注册表

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

除上表明确绑定到versioned synthetic asset的correctness参数外，具体workshop/resource数、候选设备密度、故障概率、到期压力等数值仍未批准为通用Profile、Benchmark baseline或生产事实。后续数值必须由各自版本化FactoryProfile/ScenarioSpec/Generator明确，不能从任一fixture外推“通用默认工厂”。

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
