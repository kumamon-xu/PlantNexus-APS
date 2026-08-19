---
doc_id: DOC-GOV-007
title: SIM_ASSUMPTION 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [37, 38, 39, 43, 44, 49, 59, 62, 96]
last_reviewed: 2026-08-19
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

除上表明确绑定到 `SIM-MINIMAL-001@1.0.0` 的 correctness 参数外，具体 workshop/resource 数、候选设备密度、故障概率、到期压力等数值仍未批准为通用 Profile、Benchmark baseline 或生产事实。后续数值必须由各自版本化 FactoryProfile/ScenarioSpec 明确，不能从本 fixture 外推“通用默认工厂”。

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
