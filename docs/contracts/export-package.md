---
doc_id: DOC-CONTRACT-007
title: 标准成果包合同
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [4, 34, 36, 40, 55, 67, 93]
last_reviewed: 2026-08-24
---

# 标准成果包合同

成功 PlanningRun 的标准包：

```text
export_package/
├─ manifest.json
├─ schedule.json
├─ schedule_operations.csv
├─ order_summary.csv
├─ resource_load.csv
├─ kpi.json
├─ validation_report.json
├─ solver_report.json
├─ change_report.json
└─ import_quality_report.json
```

Synthetic Run 额外包含 `scenario_manifest.json` 和 `benchmark_report.json`。

上面是跨P2/P3的完整规范成果集合，不等于当前已经具备发布能力。TASK-P2-11只形成下述内部profile；P3必须以ScheduleVersion/ExportJob、审批和发布合同补齐后才能形成对外标准包。

## P2 internal profile

`p2-internal-export.v1`固定为`manifest.json`加以下9个payload：

```text
schedule.json
schedule_operations.csv
order_summary.csv
resource_load.csv
kpi.json
validation_report.json
solver_report.json
import_quality_report.json
scenario_manifest.json
```

`schedule.json`是已由formal Validator判定PASS的`planning-solution.v1`，不是ScheduleVersion。`change_report.json`在manifest登记为`DEFERRED_P4_DYNAMIC_REPLAN`，`benchmark_report.json`登记为`DEFERRED_P2_12`，二者不得以空文件或伪造内容补位。该profile只允许`synthetic=true`、`publishable=false`，并固定ScheduleVersion/ExportJob=`NOT_CREATED`、approval/publication=`NOT_STARTED`。

## manifest

完整P3 manifest至少记录 package/schema version、ScheduleVersion、Snapshot/Problem hash、rule/solver/parameter/code versions、文件清单与 hash、生成时间和 synthetic 标识。

P2的`export-manifest.v1`使用global schema set`2.5.0`、profile`p2-internal-export.v1`、`canonical-json.v1`与`rfc4180-lf.v1`，逐payload保存role、media type、SHA-256、exact byte length和CSV data-row count。`package_id`由排除自身字段后的canonical manifest内容派生；manifest exact bytes另有fingerprint。KPI、Solution、Validation、Solver与ImportQuality均保存document identity和exact content fingerprint。

## 一致性

- 所有文件引用同一 ScheduleVersion 和 Problem；
- CSV/JSON 中 operation 数量与 manifest/entity counts 一致；
- KPI、validation、solver、change 和 quality report 不能来自其他 run；
- synthetic 包不可作为 production publish payload；
- 同一 ExportJob 幂等键重复执行得到逻辑等价成果，不能 double publish。

P2还要求重新验证所有JSON canonical bytes、package/KPI自身份、文件hash/size/row count、CSV run/problem/solution引用、SolverReport与Solution/Validation的正式绑定以及Scenario provenance。Validator非PASS、mixed run/version/hash、篡改、缺失、数量不一致或非canonical JSON必须稳定拒绝。

## 写入与回滚边界

纯内存package先完整验证；目录materialization只允许在目标同一父目录创建临时目录，先写payload、最后写manifest，再用同文件系统原子rename提交。已存在且exact byte-for-byte等价的目录是幂等replay；任何差异是destination conflict。I/O失败必须映射为稳定错误、清理临时目录且不得留下可解释为成功的目标目录或manifest。该机制不是ExportJob retry/persistence，也不授权外部storage或publish。

## TASK-P2-12 regression boundary

BenchmarkRunner对每个profile的正式replay构建并验证一次既有`p2-internal-export.v1`，报告package ID、manifest fingerprint、9个payload count和KPI version，用于证明Snapshot→validated Solution→KPI/Export链未回归。Exporter代码、manifest Schema、package bytes规则和state boundary均未修改。

P2-12 BenchmarkReport是独立machine evidence，不被追加入P2-11 package；该历史profile仍明确声明`benchmark_report.json=DEFERRED_P2_12`以保持已发布manifest语义与bytes，不应被解释为P2-12未执行。把BenchmarkReport纳入可发布成果包属于新合同/Task，当前禁止。

## TASK-P2-13 Gate aggregation boundary

Gate每次full replay既重放P2-11独立output contract，也验证XS/S/M各自已有embedded internal package，因此`repeat=2`记录2个显式package contract executions和6个Benchmark embedded Export executions。每个原始package ID、manifest/file hash、bytes/rows、KPI/SolverReport/Validation lineage和atomic/non-publishable boundary均原样嵌入Gate report。

SolverReport时间和timing-dependent KPI会使跨完整run的package identity合法变化；Gate只对不含这些run-specific identity的versioned business projection要求一致，并诚实保留所有原始hash。Exporter实现/Schema/bytes规则未修改，Gate不把自身报告装入package，不创建ScheduleVersion/ExportJob，也不改变`publishable=false`。

Provider artifact `9440650646`内两次显式output与六次embedded Export证据均PASS并绑定implementation SHA；package仍不可发布，ScheduleVersion/ExportJob仍未创建。TASK-P2-13闭环不改变P3合同或状态边界。

## TASK-P2-14 Exit audit

审计重新执行两次完整Gate与476项回归，确认2次显式output contract、6次benchmark embedded Export、fresh Validation/KPI/SolverReport、9 payload hash/count/lineage及atomic replay均PASS。Export Schema/bytes与实现零差异；`publishable=false`、ScheduleVersion/ExportJob=`NOT_CREATED`、approval/publish=`NOT_STARTED`保持，P2 READY不等于P3发布能力。

## P3 planned export boundary

TASK-P3-09被分配为首个business ExportJob/standard package owner，必须等待immutable ScheduleVersion、approval与idempotent internal publication语义形成。Export与Publish是分离副作用：相同key/target/version只能same-result replay，内容冲突fail closed，FAILED retry不得改变ScheduleVersion状态。外部MES/Production target受OPEN-002/010/015约束，本次仍保持P2 `publishable=false`历史事实。

## TASK-P3-01 export/publication contract baseline

P3合同现固定：internal Publish只允许APPROVED并改变ScheduleVersion/current reference；Export只从PUBLISHED创建独立ExportJob/standard package，任何ExportJob pair、retry或失败都不得调用Publish或改变ScheduleVersion state。Approve/Reject、Publish和Export使用独立idempotency scope；same key/same fingerprint返回同一logical result，same key/different fingerprint冲突。

P3标准包未来必须增加ScheduleVersion、approval/publication、ExportJob/attempt、audit和target lineage，同时保留P2 payload hash/count/Validator/KPI/SolverReport事实。TASK-P3-01没有修改`export-manifest.v1`、P2 package bytes或创建新Schema/文件；外部MES/ERP/storage target与Production publish继续受OPEN-002/010/015阻止。

## TASK-P3-02 publication and ExportJob carriers

[`publication-result.v1`](../../schemas/json/publication-result.schema.json)现固定APPROVED source→PUBLISHED logical result、可选previous-current→SUPERSEDED一一对应、idempotency reference/replay/audit与canonical result fingerprint；plane/target强制`SIMULATION`/`SIMULATION_INTERNAL`，所以它不能被解释为Production publish approval。

[`export-job.v1`](../../schemas/json/export-job.schema.json)现固定PUBLISHED ScheduleVersion source、`p3-standard-export.v1` profile identity、既有五state、attempt/lease/heartbeat、manifest/storage reference、sanitized error、timestamps/audit与canonical job fingerprint。它与`export-manifest.v1`不互换，且不会修改P2 `p2-internal-export.v1` bytes。Schema/pure precheck不创建Job、不写package、不重试、不发布、不访问外部storage；这些行为分别等待TASK-P3-03/08/09，OPEN-002/010/015继续阻塞外部和Production target。

## TASK-P3-03 ExportJob storage contract

ExportJob repository现形成create/exact replay/conflict、state+revision CAS、explicit lease claim、heartbeat owner/expiry校验、failure→retry attempt递增和append-only identity/delete guards。Source必须匹配同plane已存PUBLISHED Version；Production repository construction和cross-plane read/write均拒绝。PublicationResult/current reference另由独立repository持久化，ExportJob永不改变current或ScheduleVersion state。

该证据不创建`export-manifest.v1`、文件、package、storage reference或外部side effect；`EXPORTED`只能由P3-09在manifest-last/package integrity成功后提交。SQLite行数/延迟不构成OPEN-012或Production容量证据。

## TASK-P3-08 publish/export separation evidence

Internal publication service现只消费APPROVED并原子形成PUBLISHED/current/可选SUPERSEDED、PublicationResult和AuditEvent；它不导入Exporter、ExportJob repository、package profile、manifest、filesystem、storage或network。PUBLISHED carrier开放`export` action只是P3-09的state precondition，不自动创建、排队或重试ExportJob。

Publication与Export继续使用独立idempotency scope和审计动作；publication replay不会生成包，Export retry未来也不得触发Publish或改变current。P2 `publishable=false`历史、P3 standard package PLANNED状态及OPEN-002/010/015不变。

## P3 standard export v2

`export-manifest.v2`固定`p3-standard-export.v1`与12个payload：PUBLISHED `schedule_version.json`、原P2 `planning_solution.json`及三份CSV、KPI/Validation/Solver/ImportQuality/Scenario、`publication_result.json`和4-sheet `standard_package.xlsx`。P2 payload bytes原样复用；manifest记录逐文件SHA-256/bytes、CSV row、XLSX sheet及完整lineage，`package_id`和storage reference均内容派生。Writer同parent写临时目录、payload first、manifest last、atomic rename；exact bytes重放，差异冲突，失败清理。XLSX禁止formula/macro/external link/active content。`change_report.json`明确`DEFERRED_P4_DYNAMIC_REPLAN`，target仅`SIMULATION_INTERNAL`且`publishable=false`。
