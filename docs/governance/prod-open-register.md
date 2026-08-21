---
doc_id: DOC-GOV-006
title: PROD_OPEN 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [16, 59, 60, 61, 105, 106]
last_reviewed: 2026-08-21
registry_version: 1.0.0
---

# PROD_OPEN 注册表

未关闭的 `PROD_OPEN` 不阻止开发、仿真和 Benchmark，但阻止依赖该事实的生产发布。关闭必须附业务权威来源、决策日期、影响范围和验证证据。

| ID | 待确认问题 | 当前状态 | 主要影响 |
|---|---|---|---|
| OPEN-001 | Factory timezone | OPEN | Production 时间显示与边界；未知时 `BLOCK_PRODUCTION` |
| OPEN-002 | ERP/MES/WMS/CAM interfaces | OPEN | Adapter、字段、版本和错误处理 |
| OPEN-003 | Real factory topology | OPEN | Workshop/Line/Resource 建模与规模 |
| OPEN-004 | Calendar processing semantics | OPEN | 班次、休息、维护、跨日语义 |
| OPEN-005 | Freeze window | OPEN | Replan 锁定与稳定性 |
| OPEN-006 | Priority/tardiness business meaning | OPEN | 权重与 OBJ-001 业务含义 |
| OPEN-007 | material_ready_at authority | OPEN | MaterialReadinessProvider 和数据权威 |
| OPEN-008 | Lot splitting policy | OPEN | ProductionLot 展开；V1 不近似 Split/Merge |
| OPEN-009 | Cross-workshop transport rule | OPEN | transport_lag 来源和日历语义 |
| OPEN-010 | Approval responsibility | OPEN | 角色、权限和审计 |
| OPEN-011 | Historical benchmark data | OPEN | P7 Reality Calibration |
| OPEN-012 | Production runtime threshold | OPEN | 生产性能边界和部署预算 |
| OPEN-013 | Unit conversion | OPEN | Import/Normalization 拒绝与转换规则 |
| OPEN-014 | Duration fallback | OPEN | 标准工时/预测低置信度回退 |
| OPEN-015 | Field authority | OPEN | 字段级来源冲突解决 |

## 关闭记录要求

关闭一项问题时必须记录：权威人/系统、原始证据、决策值或规则、适用版本、受影响 Contract/Schema/ADR/Task/Test，以及是否需要迁移或历史重放。

关闭记录必须在本文件使用以下机器可检查的字段；表中状态只有在记录完整且引用路径存在后才能从 `OPEN` 改为 `CLOSED`：

```text
### OPEN-NNN closure
Authority: person-role or authoritative-system
Evidence: repository path or approved external reference
Decision date: YYYY-MM-DD
Decision: approved value or rule
Applies to: version/scope
Affected artifacts: Contract/Schema/ADR/Task/Test paths or IDs
Migration/replay: required with path | none with reason
```

不得以会议印象、Coding Agent 推断或 `SIM_ASSUMPTION` 作为关闭证据。`registry_version` 在字段结构、状态机或关闭证据语义变化时递增；关闭单个条目不改变格式版本。

TASK-P0-03 review：Schema/data dictionary 只引用 OPEN-001/002/003/004/007/013/015 等既有问题来标明未知生产事实；没有提供外部权威、closure record 或生产默认值。OPEN-001～015 全部继续为 `OPEN`，registry version 不变。

TASK-P0-04 review：rule sheet 显式引用 OPEN-004（日历）、OPEN-005（lock/freeze）、OPEN-007（material authority）、OPEN-009（transport）并在 state guard 中保留 OPEN-010（审批角色）；OPEN-006/008 只作为相邻业务政策审查，未写入权重或 lot 默认值。没有权威来源、closure record、生产值或状态变化，OPEN-001～015 全部继续为 `OPEN`，registry format version 不变。

TASK-P0-05 review：FactoryProfile/Scenario Schema sample 的 count/range/calendar/complexity 值全部标识 synthetic-only，不成为 OPEN-003/004 的真实拓扑或日历答案；empty Import records 不提供 OPEN-002/013/015 字段权威；manifest/hash 不提供 OPEN-011 历史数据或 OPEN-012 生产阈值。没有权威来源或 closure record，OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-06 review：本 Task 注册的 synthetic-only assumptions 和 `SIM-MINIMAL-001@1.0.0` 的 2/2/3 topology、900 秒 tick、maintenance、duration/lag、due/weight 都不能作为本注册表的权威证据。fixture-local `records` 不回答 OPEN-002/013/015，数值不回答 OPEN-001/003/004/006/007/009/014，correctness runtime 不回答 OPEN-011/012。没有权威来源或 closure record；OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-07 review：calendar/material/transport/lock/duration/horizon mutation 只是在 `SIM-MINIMAL-001@1.0.0` synthetic facts 上制造明确非法反例，不提供 OPEN-004/005/007/009/014 的生产语义或权威值；fixture evaluator runtime 也不回答 OPEN-011/012。没有外部权威、closure record、production default 或迁移结论；OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-08 review：environment/data-plane/Production config guard、development Compose database name/credentials placeholder、health timeout、heartbeat=30/lease=120 与 conditional PR Benchmark hook 全是工程/本地测试值，不回答 OPEN-001/002/003/010/011/012/015，也不是生产 topology、SLA、角色、接口或字段权威。没有 CI provider、Production deployment、外部权威或 closure record；OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-09 review：P0 registration gate 确认 OPEN-001～015 共 15 项全部存在，且没有任何条目被 SIM_ASSUMPTION、本地测试值、Compose/config 或 audit 推断关闭；因此“全部登记”Gate 为 `PASS`。本审计没有 authority、closure record、生产值或 migration/replay 决定，15 项全部继续 `OPEN`，registry format version不变；`P0-GAP-001/002` 是 CI 审计缺口，不是新的生产业务开放项。

TASK-P0-10 review：GitHub Actions run/artifact/required-check 仅用于关闭 P0 CI evidence gap，不提供 factory timezone、真实接口/拓扑/日历、业务策略/权威、历史数据或生产 runtime threshold。没有 authority、closure record、production value 或 migration/replay 决定；OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

P1 Task 规划 review：reference adapter 被限定为非生产权威来源，单位/时区/字段缺失必须显式拒绝，任何真实字段映射、接口、日历、策略和规模阈值仍须由 OPEN closure record 授权。当前没有 authority、closure evidence、production default 或 migration/replay 决定；OPEN-001～015 全部继续 `OPEN`，registry format version不变。

TASK-P1-01 review：CI event SHA、Task Diff base、workflow report名称和本地测试不提供任何生产业务权威、接口、字段、参数、阈值或closure record。OPEN-001～015全部继续`OPEN`，registry format version不变。

TASK-P1-02 review：canonical-records.v1中的timezone/unit/duration/calendar/lot/source字段只固定“必须显式提供”的authority-neutral shape；synthetic samples与pure consistency precheck不提供真实interface、topology、conversion、field authority或fallback决策。没有Authority/Evidence/closure record/migration决定，OPEN-001/002/003/004/007/008/009/013/014/015及其余条目全部继续`OPEN`，registry format version不变。

TASK-P1-03 review：Raw Staging的source system/version、source name/media type、digest、row location和internal table列只保存调用方明确提供的接收事实，不定义ERP/MES/WMS/CAM接口或字段mapping，也不解决field authority conflict。SQLite synthetic migration/replay不是外部Authority或Production deployment；没有closure record、生产默认值或历史migration决定。OPEN-002/015及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P1-04 review：`plantnexus.reference-file@1.0.0`的三列transport、文件安全limits和`production_binding=false`只建立参考文件入口，不定义真实ERP/MES/WMS/CAM endpoint/auth/version/field mapping；opaque `payload_json`不定义单位转换或字段权威。Temporary synthetic CSV/XLSX、openpyxl dependency和positive/negative tests均不是Authority/Evidence closure record。OPEN-002/013/015及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P1-05 review：unit registry的`s/min/h`只形成显式数学换算机制，MappingProfile与test-local source/timezone/unit值不构成真实interface、Factory timezone、字段权威或Production默认单位。没有Authority/Evidence/closure record，`production_binding=false`边界不变；OPEN-001/002/013/015及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P1-06 review：Data Validation只拒绝显式canonical事实中的route/reference/resource/capability/time/calendar/unit/duration问题；test-local `CUTTING/piece`、interval、lag与duration不是Production authority、默认值或closure evidence。没有Authority/Evidence/closure record，也未决定真实interface、calendar/material/transport/unit/fallback/field precedence；OPEN-002/004/007/009/013/014/015及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P1-07 review：Expansion只接受source-explicit Lot、material gate、candidate duration/source、fact/lock并拒绝自动SPLIT_MERGE/fallback；property中的1～3 lots、2 workshops/resources、300秒transport与duration均为synthetic test values。没有Authority/Evidence/closure record，也未决定lot policy、material/duration/field authority；OPEN-007/008/014/015及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P1-08 review：Snapshot只冻结显式facts/cutoff/source/rule/version并以hash证明重放，不定义Factory timezone、真实interface、calendar/material/transport、field authority或Production参数。Schema sample的cutoff/entity count/duration与临时SQLite migration均不是Authority或closure evidence；没有关闭记录或生产默认值。OPEN-001/002/004/007/009/015及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P1-10 review：P1 ingress asset的topology、piece quantity、duration、UTC timeline、calendar/material/WIP/lock/cross-workshop值已在独立Simulation注册表登记；source system/mapping也固定`synthetic`且无Production binding。Normalization PASS、quality PASS和stable hash均不是Authority/Evidence closure record，不决定真实interface、topology、calendar、unit、duration、field precedence或规模阈值。OPEN-003/004/011/012/013/015及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P1-11 review：ReferenceFileAdapter parity使用temporary synthetic CSV且manifest明确`production_binding=false`；application data-plane guard、Import/Snapshot/Problem hash和exact rejection都只证明通用链路correctness。没有Authority/Evidence closure record，不决定真实source binding、unit/timezone、lot/lock/horizon、字段优先级、容量或SLA。OPEN-001～015全部保持`OPEN`，registry format version不变。

TASK-P1-12 review：P1 Exit Gate的`READY`来自versioned synthetic/reference correctness replay、测试/build/docs与CI provider证据，不是生产业务Authority。审计没有收到任何closure record、真实接口/字段/拓扑/日历/策略/历史数据/SLA或migration decision；因此OPEN-001～015共15项全部继续`OPEN`，并继续阻止依赖这些事实的Production声明。Registry格式与`registry_version=1.0.0`不变。

TASK-P2-01 review：Problem v2允许显式传入due/priority、Resource topology/calendar/capability、historical fact和locks，但Schema/sample/synthetic policy不是Production Authority或closure evidence。没有决定真实material/calendar/transport/lock owner、priority weight、field precedence或fallback；OPEN-004/005/006/007/009/010/015及OPEN-001～015全部继续`OPEN`。`capacity=1`只固定primary unary contract，不关闭secondary capacity/规模项；registry format version保持`1.0.0`。

TASK-P2-02 review：Policy/Limits明确要求Production调用方自行提供versioned source，但没有提供任何真实authority；published 30秒/1 worker/seed、OBJ-001 stage和UNKNOWN report均为Simulation `CONTRACT_SAMPLE`。没有决定真实priority weight、freeze/lock policy、Solver limit/default/SLA、规模、角色或field precedence，也没有closure record。尤其OPEN-006/011/012继续`OPEN`，OPEN-001～015全部保持`OPEN`；registry format version保持`1.0.0`。

TASK-P2-03 review：exact solver/version/adapter只形成工程依赖，不决定Production参数、运行时限制、平台规模、worker并发、SLA或安全批准。Smoke复用显式Simulation limit vector但不产生业务schedule；没有closure record。OPEN-011/012及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P2-04 review：formal Validator只判断Problem/Solution显式事实，不推断真实calendar/material/transport/lock owner、priority policy、field authority或solve limits。Fresh positive/mutation vector与provider CI均不是Authority/Evidence closure record；尤其OPEN-004/005/007/009/010继续`OPEN`，OPEN-001～015全部保持`OPEN`。本Task不引入Production default或关闭记录，registry format version保持`1.0.0`。

TASK-P2-05 review：tiny core solve只验证synthetic assignment/resource可行域，不决定真实resource/calendar/material/transport/lock authority、priority policy、solve limits、规模或发布流程。OPEN-007/009/010/011/012按Task卡明确保持`OPEN`，OPEN-001～015全部继续`OPEN`；没有Authority/Evidence closure record、Production default或状态变更，registry format version保持`1.0.0`。

TASK-P2-06 review：temporal Solver只消费Problem中显式versioned calendar/material/transport/anchor事实，不猜测班次、物料状态、跨车间时长、solve limit或发布权限。OPEN-004/009/010/011/012及OPEN-001～015全部继续`OPEN`；in-memory temporal cases、rounding规则和telemetry不是Authority/Evidence closure、Production default、capacity或SLA，registry format version保持`1.0.0`。

TASK-P2-07 review：fact/lock Solver只消费Problem中显式RUNNING/anchor/HARD/SOFT事实，不猜测execution fact ID、freeze window、lock优先级、稳定性权重、事实authority或发布权限。OPEN-005/007及OPEN-001～015全部继续`OPEN`；in-memory Running/Hard Lock cases、precheck与telemetry不是Authority/Evidence closure、Production default、capacity或SLA，registry format version保持`1.0.0`。

TASK-P2-08 local review：唯一获准的`POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`及显式SolveLimits只用于Simulation correctness，代码会拒绝Production data plane、未知policy/source与隐式limits。它不决定真实priority weight、Production solve defaults、runtime/SLA、容量或发布权限；因此OPEN-006/011/012及OPEN-001～015全部继续`OPEN`。Tiny objective/timing与本地PASS不是Authority/Evidence closure，registry format version保持`1.0.0`。

TASK-P2-08 provider closure：GitHub required run/artifact只复现Simulation policy/limits与OBJ-001 correctness，不是业务Authority或closure record。OPEN-006/011/012及OPEN-001～015全部继续`OPEN`，没有Production default、SLA、capacity或发布决定，registry format version保持`1.0.0`。

TASK-P2-09 local review：七个Scenario/Profile/blueprint及其已登记synthetic assumption均明确synthetic-only，60秒tick、tiny topology、due/calendar/material/fact/lock/transport值只用于correctness。它们不提供真实source authority、priority/calendar/transport/default limits、capacity、SLA或独立Production infrastructure evidence；OPEN-006/011/012及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P2-09 provider closure：GitHub required run/artifact只复现versioned Simulation correctness，不是业务Authority或closure record。OPEN-001～015全部继续`OPEN`，没有Production source/default/SLA/capacity/infrastructure或发布决定，registry format version保持`1.0.0`。

TASK-P2-10 local review：五个Reference algorithms、tie-break、tiny runtime及priority consumption均由`reference-scheduler-policy.v1`及独立Simulation注册项限定为Simulation-only，不能决定真实priority、dispatch/fallback、历史baseline、capacity或runtime threshold。没有Authority/Evidence closure record；OPEN-006/011/012及OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P2-10 provider closure：GitHub required run/artifact只复现versioned Simulation reference correctness，不是业务Authority或closure record。OPEN-001～015全部继续`OPEN`，没有Production priority/default/fallback/SLA/capacity或发布决定，registry format version保持`1.0.0`。

TASK-P2-11 local review：KPI/manifest/sample/package全部标记synthetic且`publishable=false`，只消费既有P2 correctness authority。它不决定真实外部接口（OPEN-002）、priority/KPI权重（OPEN-006）、审批角色（OPEN-010）或生产输入契约（OPEN-015），也不创建ScheduleVersion/ExportJob/publish。没有Authority/Evidence closure record；OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P2-11 provider closure：GitHub required run/artifact只复现synthetic、non-publishable internal package和确定性输出控制，不是业务Authority、审批、发布或closure record。OPEN-001～015全部继续`OPEN`，没有Production interface/default/KPI weight/role/input或发布决定，registry format version保持`1.0.0`。

TASK-P2-12 local review：XS/S/M profile、Windows baseline、development ceilings和2.5倍same-environment factor全部由本次新增的simulation assumption限定为synthetic engineering evidence，不是历史生产数据、部署预算、容量或SLA。尤其OPEN-011仍缺真实历史benchmark，OPEN-012仍缺经授权的Production runtime/memory/scale threshold；没有Authority/Evidence closure record。OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P2-12 provider closure：GitHub required XS run/artifact只复现synthetic development benchmark、formal correctness和环境/性能carrier，不是历史生产数据、部署预算、容量或SLA Authority/Evidence closure record。OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。

TASK-P2-13 local review：两次完整Gate聚合的correctness、XS/S/M Benchmark、internal Export与四类exit rejection全部是Simulation/development evidence；Gate明确`publishable=false`、Production authority absent、Exit Audit未执行。它不提供真实接口/字段/拓扑/日历/priority/default limit、历史性能、容量、SLA、审批或发布决定，尤其不关闭OPEN-006/010/011/012/015。没有Authority/Evidence closure record；OPEN-001～015全部继续`OPEN`，registry format version保持`1.0.0`。
