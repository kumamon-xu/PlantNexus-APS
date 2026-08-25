---
doc_id: DOC-GOV-002
title: 核心需求注册表
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [3, 4, 5, 6, 107]
last_reviewed: 2026-08-25
registry_version: 1.0.0
---

# 核心需求注册表

| ID | ID status | Requirement | 首要验收证据 | 计划阶段 |
|---|---|---|---|---|
| REQ-001 | ALLOCATED | 自动读取版本化计划输入 | Import contract test、ImportRun provenance | P1 |
| REQ-002 | ALLOCATED | 数据标准化、单位转换和不可变快照 | Snapshot hash replay、unit rejection test | P1 |
| REQ-003 | ALLOCATED | 订单、批次和工序实例展开 | Expansion contract/property tests | P1 |
| REQ-004 | ALLOCATED | 单 PlanningRun 跨车间排程 | Cross-workshop golden/simulation | P2 |
| REQ-005 | ALLOCATED | 独立硬约束验证 | Validator mutation suite | P0-P2 |
| REQ-006 | ALLOCATED | 标准成果包输出 | Export package contract/idempotency test | P2-P3 |
| REQ-007 | ALLOCATED | ScheduleVersion、审批、锁定和发布 | State transition and immutability tests | P3 |
| REQ-008 | ALLOCATED | 异常重排 | Disruption replay、ChangeReport | P4 |
| REQ-009 | ALLOCATED | 全链路 Provenance | Manifest and audit evidence | P1-P4 |
| REQ-010 | ALLOCATED | AI 工时预测扩展接口 | Versioned prediction/fallback contract | P6 |
| REQ-011 | ALLOCATED | Synthetic Factory Generator | Deterministic dataset hash | P0-P1 |
| REQ-012 | ALLOCATED | Scenario Library | Versioned scenario catalog and replay | P0-P2 |
| REQ-013 | ALLOCATED | Execution / Disruption Simulator | Deterministic event stream and fact preservation | P4 |
| REQ-014 | ALLOCATED | Benchmark Harness | Versioned BenchmarkReport and profiles | P2 |
| REQ-015 | ALLOCATED | Reference Scheduler Baseline | Five deterministic baselines；comparison and warning behavior | P2 |

本表定义需求根 ID，不代替详细 Contract。任何生产代码应能通过 `REQ / NFR / ENG → SCHEMA / ARCH / CONSTRAINT → TASK → TEST → ARTIFACT` 链路解释其存在理由。

`ALLOCATED` 只表示 ID 已稳定分配，不表示功能已经实现。ID 不得删除或复用；需求被取代时保留原行并改为 `RETIRED`，同时链接替代 Requirement/ADR 和迁移影响。修改表结构或 ID 生命周期语义必须提升 `registry_version`。

TASK-P0-03 review：REQ-001/002/003/009 已获得 versioned Schema/type/contract-test 落点，但 Import/Normalization、Snapshot/Problem builder、hash 与 end-to-end provenance 均未实现，因此所有根 ID 状态继续为 `ALLOCATED`，没有提升为业务完成状态，也不修改 registry format version。

TASK-P0-04 review：REQ-004/005 获得 C-001～C-018 rule/capability contract、ValidationReport v2 与 completeness tests；REQ-007 获得三套 state transition registry/test；REQ-008 只获得 capability/state contract boundary。没有 Solver、candidate ScheduleValidator、审批/发布持久化、Export worker 或 Replan implementation，因此相关 Requirement 仍为 `ALLOCATED`，registry format version 不变。

TASK-P0-05 review：REQ-011/012 获得 FactoryProfile/ScenarioSpec/ScenarioManifest v1、七层 Generator Protocol、empty Standard Import deterministic hash、TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION；REQ-013/014/015 只获得未来 execution/benchmark/reference baseline 可引用的 Scenario provenance boundary。没有非空生成、正式 Scenario Library、Execution Simulator、BenchmarkRunner、Reference Scheduler 或 Solver，因此所有 Requirement 继续 `ALLOCATED`，registry format version 不变。

TASK-P0-06 review：REQ-011/012 获得首个正式 `SIM-MINIMAL-001@1.0.0` Profile/Scenario/非空 Standard Import/manifest/hash/Golden artifacts 与 TEST-SCENARIO-REPLAY；REQ-004/005 获得 C-001～C-011 的独立 fixture-local positive calculation 和 `hard_violation_count=0` 期望。该证据不实现 Synthetic distribution generator、P1 Import pipeline、Solver 或通用 ScheduleValidator/negative mutation，因此全部 Requirement 继续 `ALLOCATED`，registry format version 不变。

TASK-P0-07 review：REQ-005 获得 fixture-local C-001～C-011 独立 evaluator、positive PASS、13 类 negative mutations/15 hard violations、exact `validation-report.v2` / `error.v2`、完整 coverage 与 TEST-VALIDATOR-MUTATION machine evidence。输入仍为 `sim-minimal-records.v1` / `golden-schedule.v1`，没有正式 PlanningProblem/candidate、Solver comparison、API/state integration 或 production/performance Validator，因此 REQ-005 及其他根 Requirement 继续 `ALLOCATED`，registry format version 不变。

TASK-P0-08 review：REQ-009 获得 environment-only build metadata（code/spec/schema/40-char commit）、health payload、structured log correlation/trace context、exact lock 与 machine/CI artifact 编排；这些只形成工程 build/log 关联，不是 Snapshot/Problem/source/Solver/Export manifest 或业务 audit。没有修改 Requirement 语义/状态或完成 P1-P4 provenance chain；REQ-001～015 全部继续 `ALLOCATED`，registry format version 不变。

TASK-P0-09 review：独立审计重新执行 90-test P0 suite、五类 machine contracts、deterministic replay、repository build、governance 与无 Solver 边界；REQ-001～015 的 P0 evidence slice 均可追溯。但 workflow 的 TASK-P0-08 diff step在 P0-09 commit上 exit 1，external provider run/URL/ID/artifact/required-check evidence也为 `NOT_RUN`。审计本身不实现任何业务 Requirement，也不把 P1/P2+ `PLANNED` 项提升为已完成；全部根 ID保持 `ALLOCATED`，registry format version 不变。两项缺口追踪到 planned TASK-P0-10，未创建 P1 Task。

TASK-P0-10 review：workflow 的当前 Task diff/report 与 uploaded artifact 引用已有界交接；GitHub baseline run `32227247262` 保留原失败反例，run `32228647627` 则对 immutable implementation commit 形成 job/artifact/required-check PASS。这只加强 REQ-009 的 repository/CI provenance slice，不实现真实 source/Snapshot/Problem/Solver/export manifest 或业务 audit。REQ-001～015 全部继续 `ALLOCATED`，registry format version 不变；P1 Task 未创建。

P1 Task 规划 review：TASK-P1-02～TASK-P1-11 已为 REQ-001/002/003/009/011/012 分配 import contract、raw staging、reference adapter、normalization、data-quality gate、order expansion、Snapshot/Problem hash、synthetic canonical records 与 common-ingress evidence；TASK-P1-12 只负责独立退出门审计。当前仅形成 `PLANNED` 追踪关系，没有执行任何 P1 实现、测试或 Gate，因此 REQ-001～015 全部继续 `ALLOCATED`，registry format version不变。

TASK-P1-01 review：REQ-009获得phase-aware Task attribution、event base与Task Diff base分层、generic CI report/artifact命名和no-stale-P0 workflow contract；completion commit `2d2a4432aa42e4f38ee8ae736e2acf2df1c694b9`的GitHub run `32237649319`、successful `validate` job与artifact `9359554539`进一步形成provider provenance。该证据不是source/Import/Snapshot/Problem/Solver/Export业务provenance；没有改变Requirement语义或完成任何P1数据能力，REQ-001～015全部继续`ALLOCATED`，registry format version不变。

TASK-P1-02 review：REQ-001/002/003/009获得schema set`2.0.0`的canonical-records.v1、Import v2、Snapshot v2、data dictionary、pure types/prechecks与TEST-CONTRACT-001落点；v1 artifacts保持不变。该证据只形成严格机器合同，不实现Adapter/staging/Normalization/DataValidation/Expansion/Snapshot或Problem builder/hash，因此所有Requirement仍为`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-03 review：REQ-001/009获得immutable raw batch/row、source/version/content与row digest/location/UTC received-at、synthetic provenance、plane-scoped durable repository、exact replay/conflict、atomic rollback和reversible migration证据。该slice只持久化opaque bytes，不读取Adapter文件、不形成canonical Import/Normalization/DataValidation/Snapshot/Problem或run/export audit；因此REQ-001/009及其他Requirement仍为`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-04 review：REQ-001获得`plantnexus.reference-file@1.0.0`、strict UTF-8 CSV/read-only XLSX、fixed reference header和bounded active-content rejection，REQ-009获得source manifest、actual file SHA-256/length/media/leaf name与format-specific row locations；CSV/XLSX semantic parity和durable restaging由TEST-IMPORT-ADAPTER-001形成。该slice不绑定真实ERP/MES/WMS/CAM、不解析mapping/unit/time、不生成canonical Import/Snapshot/Problem或run/export audit；所有Requirement继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-05 review：REQ-002获得显式ID/time/unit normalization、stable sorting及canonical Import bytes/hash；REQ-003获得Order/Lot/Routing canonical field mapping能力但不含deterministic expansion；REQ-009获得source/mapping/unit/canonicalization version chain、record source reference和replay hash。Data Validation、Expansion、Snapshot/Problem及完整run/export audit仍PLANNED；所有Requirement继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-06 review：REQ-001/002获得canonical Import structure/reference/unit/time/duration/resource质量门与PASS/FAIL报告；REQ-003获得Routing DAG/option/lineage pre-expansion拒绝但尚未展开OperationInstance；REQ-009获得rule/error/report/canonicalization版本、稳定source detail与内容派生report ID。Snapshot/Problem/common-ingress/真实source authority与完整run/export audit仍PLANNED；所有Requirement继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-07 review：REQ-003获得`order-expansion.v1`显式Lot×RoutingOperation实例、逐lot precedence、candidate duration/source、RUNNING/COMPLETED/lock copy及Hypothesis generation/shrinking证据；REQ-009获得Import/PASS report/source/synthetic/expansion version与versioned derived-ID/hash链。该slice不创建lot、不构建/持久化Snapshot或Problem，也不形成common-ingress/Solver/Production证据；所有Requirement继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-08 review：REQ-002获得`planning-snapshot.v2`canonical builder、`snapshot-hash-projection.v1`、deterministic bytes/hash/ID、frozen value及insert-only persistence/migration证据；REQ-003的expanded OperationInstance/edge与完整canonical facts被不可变绑定；REQ-009获得Import dataset hash、quality report、source/rule/schema/normalization/expansion/synthetic provenance和storage integrity链。该slice尚无PlanningProblem、common-ingress、PlanningRun/code-commit manifest、独立Production deployment或Solver；所有Requirement继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-09 review：REQ-002获得verified immutable Snapshot→canonical Problem bytes/hash与tick/horizon/fact sensitivity；REQ-003获得active OperationInstance/candidate/edge、RUNNING和COMPLETED过滤的deterministic Problem投影；REQ-009获得Snapshot content identity→builder/hash projection→Problem hash链。Active lock、multi-factory与completed-active historical lag在v1不可表达时明确拒绝。该slice尚无common ingress、PlanningRun/code-commit manifest、Generator distribution、Backend/Solver/Validator/Export或Production evidence；所有Requirement继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-10 review：REQ-001获得synthetic source rows→Raw Staging→explicit mapping/unit Normalization→Import v2/Data Validation PASS链；REQ-003获得2 orders/lots×3-operation routing、candidate、material、RUNNING fact与lock canonical records；REQ-009获得Profile/Scenario/Generator/seed/mapping/unit/quality/package/hash provenance；REQ-011获得七层non-empty deterministic generator；REQ-012获得`SIM-P1-INGRESS-001@1.0.0`catalog asset。该slice尚无Production source/common-ingress、Snapshot/Problem handoff、Solver/Benchmark/Execution Simulator或真实distribution；所有Requirement继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P1-11 review：REQ-001/002/003现由`CommonIngressPipeline`把ReferenceFileAdapter与Synthetic Generator的Raw Staging连到同一Normalization/Data Validation/Expansion/Snapshot/Problem链，并形成Import/Snapshot/Problem完整bytes/hash parity；REQ-009获得`p1-data-pipeline-report.v1`的commit、版本、配置、ID/hash/count/code链；REQ-011/012获得公开staging与Scenario E2E replay。参考文件仍是synthetic temporary CSV，没有Production binding、Solver/Validator/Benchmark/Execution/Export。TASK-P1-11完成时P1-12尚未审计，所有Requirement根ID继续`ALLOCATED`，registry format version不变。

TASK-P1-12 review：独立审计把REQ-001/002/003/009/011/012的P1 formed链与P1-01～11 exact provider artifacts、271项回归、14/14 common-ingress、四类exact rejection、migration/build/docs evidence汇总为P1 Gate=`READY`且无blocking gap。审计不改变根ID生命周期；`ALLOCATED`仍不是“功能完成”状态。真实Production binding、Solver/Validator/Benchmark/Execution/Export及REQ-004～015后续阶段边界均未被提升，REQ-001～015全部继续`ALLOCATED`，registry format version不变。

TASK-P2-01 review：REQ-002/003获得verified Snapshot→Problem v2的complete Resource/active operation/historical fact deterministic projection；REQ-004获得跨车间可消费的solver-neutral topology/resource事实但尚无排程；REQ-009获得due/priority/fact/lock source、版本和v2 hash链；REQ-012获得versioned synthetic priority/lock/historical replay slice。C-008/OBJ-001仅input contract formed，Solver/Validator/Scenario Library/Benchmark/Production authority仍未形成。所有REQ根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-02 review：REQ-004获得Problem→Policy/Limits→Solution/Report的solver-neutral机器边界、C-001～C-011与OBJ-001 stage声明及七种status carrier，但没有C-ID/目标执行；REQ-005获得formal Validator可消费的assignment/tick/UTC/status candidate合同，但Validator仍未实现；REQ-009获得Policy/Limits/Solution/Report version/source/fingerprint/solver-parameter/code-commit链。四份sample为Simulation `CONTRACT_SAMPLE`且无Solver执行。REQ-004/005/009及全部Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-03 review：REQ-004获得exact CP-SAT binary、solver-neutral Protocol实现边界、七状态adapter和显式SolveLimits参数传递的engineering foundation，但真实`solve()`因业务model builder未实现而稳定拒绝，未形成C-ID/OBJ-001/candidate；REQ-009获得Backend/solver exact identity、lock/wheel/platform、参数/status和machine-report provenance。Empty/model-invalid smoke不构成PlanningRun业务证据。REQ-004/009及全部Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-04 review：REQ-004获得正式Problem/Solution上C-001～C-011独立判定，但尚无CP-SAT business candidate、OBJ-001或vertical slice；REQ-005获得formal Validator、stable violation ordering、ValidationReport/Error v2、13类mutation与property/independence证据；REQ-009获得Problem/Solution→constraint result→report/error及exact implementation provider artifact链。证据限synthetic correctness；所有Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-05 review：REQ-004获得C-001/003/004/010/011的exact-pinned CP-SAT实现、完整candidate与INFEASIBLE边界；REQ-005获得candidate必须经formal Validator PASS、失败即丢弃assignments的consumer gate；REQ-009获得Problem/Policy/Limits fingerprints、solver identity/status、model/timing/memory与machine report链。C-002/005～009、OBJ-001搜索、Strategy、完整vertical slice与Production仍未形成；所有Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-06 review：REQ-004获得C-002/005/006/009的exact precedence/calendar/release/material/transport CP-SAT slice；REQ-005获得四类temporal candidate必须经独立formal Validator PASS及mutation交叉；REQ-009获得冻结合同/Builder/Validator/lock fingerprints、constraint/model delta与machine report链；REQ-012获得仅限versioned in-memory synthetic的temporal correctness vectors。C-007/008、OBJ-001搜索、Strategy、完整vertical slice、Benchmark与Production仍未形成；所有Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-10 local review：REQ-015获得五个`reference-*.v1` deterministic non-production algorithms、完整candidate/explicit failure、同Problem/formal Validator/KPI及`reference-scheduler-report.v1`；REQ-004/005获得35个七场景candidate的fresh C-001～C-011 PASS，REQ-009获得algorithm/policy/problem/candidate/report fingerprints与CI carrier。Global comparison/warning、XS/S/M Benchmark、Production fallback和P2 Gate仍未形成；所有Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-10 provider closure：implementation `8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`的required run `32449742281` / artifact `9435264655`精确复现REQ-004/005/009/015的reference/Validator/KPI/report链及38-path治理证据，故Task=`done`。Global comparison/warning、XS/S/M Benchmark、Production fallback、P2 Gate及所有Requirement根ID状态不变，仍为`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-07 review：REQ-004获得C-007/C-008的RUNNING remaining/resource、COMPLETED anchor与HARD exact tuple CP-SAT slice；REQ-005获得candidate mandatory formal PASS、C-007/C-008 mutation与SOFT non-hard交叉；REQ-009获得Problem identity、lock references、冻结fingerprints、fact/lock metrics与machine report链；REQ-012获得仅限versioned in-memory synthetic的Running/Hard Lock correctness vectors。OBJ-001/002搜索、Strategy、dynamic Replan、完整vertical slice、Benchmark与Production仍未形成；所有Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-08 local review：REQ-004获得完整C-001～C-011硬可行域上的唯一OBJ-001 priority-weighted tardiness seconds目标与单一GlobalCpSatStrategy；REQ-005获得所有candidate必须经formal independent Validator PASS、失败即丢弃candidate/objective的consumer gate；REQ-009获得Problem/Policy/Limits fingerprint、strategy/backend/solver/code identity、七状态、objective/bound/gap、timing/model/memory与`objective-strategy-report.v1`链。四个tiny brute-force optimum、一个certified infeasible和Production policy拒绝仅形成local Simulation correctness；exact provider evidence、P2-09 Golden/scenario integration、Reference/Export/Benchmark/Gate与Production仍未形成。所有Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-08 provider closure：implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的required run `32438785162` / artifact `9431673977`精确复现REQ-004/005/009的objective/strategy/Validator/report链及52-path治理证据，故Task=`done`。这只关闭versioned Simulation OBJ-001/Global Strategy slice；P2-09 Golden/scenario、Reference/Export/Benchmark/Gate、Production及所有Requirement根ID状态不变，仍为`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-09 local review：REQ-004获得七个versioned JSSP/FJSP/Cross Workshop/Calendar/Material/Running/Hard Lock Scenario经正式Raw→Problem→Global Strategy的OPTIMAL schedule；REQ-005获得7个fresh Validator PASS及11个Solver-candidate formula-free exact C-ID mutation；REQ-009获得Profile/Scenario/assembler/seed/pipeline/policy/backend/solver/object/artifact hash与machine report lineage；REQ-012获得正式P2 correctness catalog及row-order replay。该证据仍待exact provider，且不形成Reference/Export/XS-S-M Benchmark/P2 Gate或Production authority；全部Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-09 provider closure：implementation `20e49c92306128b47313059fabe31534814dbe3d`的required run `32442651322` / artifact `9432982306`精确复现REQ-004/005/009/012的7 scenarios、7 Validator/property、11 mutations、hash/provenance及58-path治理链，故Task=`done`。Reference/Export/XS-S-M Benchmark/P2 Gate/Production仍未形成；全部Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-11 local review：REQ-004/005获得validated Solution必须绑定fresh exact PASS和真实SolverReport后才可进入输出链；REQ-006获得`p2-internal-export.v1`的9个payload、canonical JSON/RFC4180-LF、hash/bytes/rows/count/lineage及atomic replay/cleanup；REQ-009获得Snapshot/Problem/Solution/Validation/Solver/ImportQuality/KPI/manifest/file content identity链。该证据只限synthetic、`publishable=false`；Benchmark、ScheduleVersion/ExportJob、approval/publish、Production与P2 Gate未形成。所有Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-11 provider closure：implementation `546292831c3bd52185687a4c646c10ae10541ae2`的required run `32454693799` / artifact `9436863185`精确复现REQ-004/005/006/009的validated output、9 payload、8/8 checks、hash/count/lineage及58-path治理链，故Task=`done`。Benchmark、ScheduleVersion/ExportJob、approval/publish、Production与P2 Gate仍未形成；全部Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-12 local review：REQ-014获得strict Profile/Report/Baseline v1、XS/S/M formal source→Problem replay、Global/五Reference warm-up/repetition、环境/规模/时间/质量/内存与CI XS carrier；REQ-015获得同Problem/Validator/公共KPI comparison及`BENCHMARK_WARNING`规则；REQ-004/005获得每个measured candidate fresh formal PASS，REQ-009/012获得version/seed/hash/fingerprint/environment/baseline provenance。该范围只形成development evidence，完整P2 Gate/audit与Production仍待后续；全部Requirement根ID继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-12 provider closure：implementation `01e7f4bdca88fc903e7caa771f875fc1a70ff357`的required run `32460861563` / artifact `9438899443`精确复现REQ-004/005/009/012/014/015的XS report 8/8、19/19 reports与49-path治理链，故Task=`done`。S/M保留local policy evidence；P2-13 Gate、P2-14 audit、Production与所有root生命周期状态不变。

TASK-P2-13 local review：REQ-004/005/006/009/012/014/015由`p2-vertical-slice-report.v1`聚合两次完整七场景correctness、XS/S/M Global+五Reference Benchmark、formal Validator/common KPI与九payload internal Export链，并对四类退出拒绝形成exact code/stage/category证据。两次业务语义投影一致、11项Gate checks均PASS且blocking gaps为空；原始timing/memory/hash仍完整保留，未被稳定投影伪装为跨运行相同。该证据当前仅为local Simulation/development Gate，exact implementation provider尚待提交后核验，TASK-P2-14独立Exit Audit与Production authority/publish仍未执行。REQ-001～015全部继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-13 provider closure：implementation `dc2e5cd41080603606090ebfc4bc6162941c5f7f`的required run `32465737712` / artifact `9440650646`精确复现REQ-004/005/006/009/012/014/015的20/20 reports、两次Gate 11/11与37-path治理链，故Task=`done`。这只把bounded Simulation/development Gate提升为provider-verified；P2-14独立audit、Production authority/publish与全部Requirement根ID生命周期不变，继续`ALLOCATED`，registry format version保持`1.0.0`。

TASK-P2-14 local audit review：REQ-004/005/006/009/012/014/015的P2完整链已由13组Task topology、26个exact prerequisite provider artifacts、476项全仓测试、两次Gate 11/11、七correctness场景×两轮完整§76 measurement、XS/S/M各8/8、formal Validator/Reference/Export与四类拒绝独立复核为PASS，blocking gaps为空，故Exit decision=`READY`。Decision-writing时audit implementation provider尚待闭环；本结论不改变根ID生命周期，REQ-001～015继续`ALLOCATED`，Production authority/publish与P3仍未形成，registry format version保持`1.0.0`。

TASK-P2-14 provider closure：implementation `65c556789f176ad9de55523d6420737bb60f933f`的required run `32677741558` / artifact `9503227240`精确复现20/20 reports、476 tests、Gate 11/11及30-path治理链，故Task=`done`、Exit=`READY`。全部Requirement根ID继续`ALLOCATED`，Production authority/publish与P3仍未形成，registry format version保持`1.0.0`。

## P3 planning allocation

用户批准transition后，REQ-006分配到TASK-P3-01～03、09/10、13～15，REQ-007分配到TASK-P3-01～15，REQ-009贯穿TASK-P3-01～15；REQ-004/005作为validated-solution与formal-Validator只读前提进入P3-04～06、10～15。该分配建立合同→Schema→persistence→application→API/UI→Gate→Audit链，但P3-01～15均未形成业务实现证据。

REQ-008/013继续只属于P4，ExecutionEvent、ReplanRequest、OBJ-002、freeze、ChangeReport和Execution Simulator不得进入P3。REQ-001～015的根生命周期全部保持`ALLOCATED`，P2 historical evidence不改写，OPEN-010等Production authority问题未关闭，`registry_version=1.0.0`格式不变。

TASK-P3-00 provider closure：implementation `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7` / run `32681493976` / artifact `9504310381`只验证phase allocation与治理一致性，不形成REQ-004/005/006/007/009业务行为；全部根ID继续`ALLOCATED`。P3-01随后由新的明确授权启动，不是依赖自动推进。

## TASK-P3-01 contract review

REQ-006获得Publish与Export分离、PUBLISHED-only ExportJob、standard package lineage和独立idempotency scope的人类语义合同；REQ-007获得copy-on-write new DRAFT、既有state pair、capability/default-deny、approve/reject/publish guard与PUBLISHED immutability合同；REQ-009获得query/command/decision/publication/export/audit/provider的version/fingerprint/correlation链和accepted ADR-0012。

这些仅是六份新Markdown与现有文档的contract baseline，没有Schema、repository、state transition、API/UI或artifact behavior。REQ-006/007/009及全部根ID继续`ALLOCATED`；P3-02+、P4和Production边界保持`PLANNED`，`registry_version=1.0.0`不变。

TASK-P3-01 provider closure：implementation `3bf99cbafdad983795a83a88646240dbb0b24509`的required run `32684713630` / artifact `9505303054`精确复验上述contract baseline与43-path治理链，故Task=`done`。这不形成REQ-006/007/009业务行为；全部Requirement根ID继续`ALLOCATED`，P3-02+、P4与Production状态不变。

## TASK-P3-02 requirement review

REQ-006获得PublicationResult/ExportJob strict carrier，REQ-007获得ScheduleVersion/query/command/comparison与既有state集合对齐，REQ-009获得AuditEvent、完整lineage和canonical fingerprint/provider report路径。7 Schema/7 sample、pure prechecks、24 shape negative、6 fingerprint negative和P2 34 artifact preservation形成machine-contract slice。

没有migration/repository/state/application/API/UI/worker、standard package或Production authority形成，因此REQ-006/007/009根ID及全部Requirement仍为`ALLOCATED`；P3-03+、P4与Production保持PLANNED/排除，`registry_version=1.0.0`不变。Implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a` / artifact `9506913562`只闭环machine carrier slice，故TASK-P3-02可标为`done`而根ID生命周期不提升。

## TASK-P3-03 requirement review

REQ-006获得PublicationResult/current reference与ExportJob durable exact replay/conflict/CAS/lease-attempt storage primitive；REQ-007获得ScheduleVersion creation-byte replay、immutable content/lineage/validation、existing-pair state CAS与DB mutation guard；REQ-009获得canonical document SHA、append-only AuditEvent、idempotency/current/version lineage及machine report路径。`0004` empty/populated round-trip、caller rollback与plane isolation由真实tests/8-check report覆盖。

这些不创建DRAFT、执行approval/publish/export、生成standard package或提供API/UI/worker/Production side effect；REQ-006/007/009及全部root仍为`ALLOCATED`。Implementation `e315dbf4f6c079df6d19b52f0403b00827126232` / artifact `9508445635`已精确复验8/8 machine与52-path治理链，故只闭环TASK-P3-03 storage slice。OPEN-002/010/012/015、P3-04+、P4与Production边界不变，`registry_version=1.0.0`不变。

## TASK-P3-04 requirement review

REQ-004/005获得validated P2 output消费与fresh formal Validator/KPI gate；REQ-007获得immutable DRAFT→READY_FOR_REVIEW既有pair的application执行；REQ-009获得full lineage、deterministic identity、atomic append-only audit与exact replay/conflict。形成路径为`app.domain.schedule_version`、`app.application.schedule_versions`、限定tests和8-check lifecycle report。

该slice不形成read model/edit/approval/rejection/publish/export/API/UI/worker/P4或Production authority，故所有15个root Requirement继续`ALLOCATED`。Implementation `a9be974855bb825784d639b7f6675e5a33e4273d` / artifact `9510215582`已精确复验8/8 lifecycle与45-path治理链，故只闭环TASK-P3-04 reviewable slice；OPEN-010及其他OPEN、SIM assumption、风险状态不变，`registry_version=1.0.0`不变。

## TASK-P3-05 requirement review

REQ-002/003获得Snapshot/Problem/Version facts的stable filter/sort/cursor只读投影；REQ-004获得Gantt、Resource Load及两个Version comparison；REQ-005获得KPI/diagnostic/validation lineage而不复制Validator；REQ-007获得ScheduleVersion/Audit只读workspace；REQ-009获得source-set、payload、collection、query及comparison fingerprint链。形成路径为`app.domain.workspace`、`app.application.workspace_queries/schedule_comparison`、四类tests和8-check machine report。

Implementation `f236fab47aa2565b87a060b2c8bde8f2e8d66229` / artifact `9512423712`已精确复验8/8 read-model及50-path治理链，故只闭环TASK-P3-05 bounded read slice；没有edit/approval/publish/export/API/UI/P4或Production authority。全部15个root Requirement继续`ALLOCATED`，OPEN/SIM/risk状态及`registry_version=1.0.0`不变。

## TASK-P3-06 requirement review

REQ-005获得Move/Assign candidate与Set/Remove Lock后的fresh independent Validator gate，以及manual DRAFT显式submit的第二次fresh gate；REQ-007获得command-only copy-on-write new DRAFT、source/current publication不变，并只复用既有DRAFT→READY pair；REQ-009获得server precondition、deterministic idempotency identity、source/new lineage与atomic insert/CAS + append-only audit。形成路径为`app.domain.schedule_commands`、`app.application.schedule_commands/schedule_command_check`、unit/property/contract/validation/integration tests和8-check machine report。

Implementation `08317637c7fbb51d46880d32523545bb0b4fe1c0` / artifact `9515126567`已精确复验8/8 command及57-path治理链，故只闭环TASK-P3-06 bounded command slice。该slice不形成Solver/Replan、approval/rejection/publication/export、HTTP/UI、Production identity/authority或P4；全部15个root Requirement继续`ALLOCATED`，OPEN/SIM/risk状态与`registry_version=1.0.0`不变。

## TASK-P3-07 requirement review

REQ-007获得authority-neutral APPROVE/REJECT、READY-only同content state CAS、terminal rejection、decision evidence、success/denial audit、exact replay/conflict/concurrency与rollback的application行为；REQ-009获得actor/policy/capability/resource scope、reason、request/key reference、source/new/lineage/correlation/code commit及machine report链。形成路径为`app.domain.authorization`、`app.application.approval/approval_decision_check`、unit/contract/integration/security/CI tests和8-check report。

该slice不形成真实RBAC/SSO/责任人、HTTP/UI、publish/export、P4或Production authority/readiness；APPROVED只成为P3-08前置，OPEN-010继续OPEN。Corrective implementation `9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6` / artifact `9544333991`已精确复验26/26 JSON、8/8 decision与50-path治理链，故只闭环TASK-P3-07 bounded slice。全部15个root Requirement保持`ALLOCATED`且`registry_version=1.0.0`不变。

## TASK-P3-08 requirement review

REQ-006获得Publish/Export分离的internal publication behavior、PublicationResult与current exact replay/conflict边界，但standard package/ExportJob behavior仍等待P3-09；REQ-007获得authorized APPROVED→PUBLISHED、old current PUBLISHED→SUPERSEDED、immutable content和DRAFT/READY/REJECTED/double publish拒绝；REQ-009获得request/key/Publication/Audit identity、source/new/previous/superseded/lineage/correlation/code及atomic provider report路径。形成路径为`app.domain.publication`、`app.application.publication/publication_check`、unit/contract/integration/security/CI tests和8-check report。

该slice只面向`SIMULATION_INTERNAL`，不形成ExportJob/package、external MES/ERP、HTTP/UI、P4或Production authority/readiness；OPEN-002/010保持OPEN。Implementation `e90475f462b365d2e031445ad28a02ea0b89d2f5` / artifact `9545782727`精确复验27/27 JSON、8/8 machine与51 committed/0 working paths、8 rows、19 checks、0 issues，故该bounded slice为provider-verified；全部15个root Requirement继续`ALLOCATED`，`registry_version=1.0.0`不变。

TASK-P3-09 provider closure：REQ-006获得PUBLISHED-only durable ExportJob、standard JSON/CSV/XLSX、manifest-last、retry/cancel/recovery和Publish分离；REQ-007获得server authorization、既有state pair/lease CAS及ScheduleVersion不变边界；REQ-009获得P2→Version→Publication→Job attempt→Audit→manifest/file exact lineage。Implementation `42278239332e61e55a4e0305705534db768dc22f` / artifact `9548027237`精确复验28/28 JSON、8/8 machine及76 committed/0 working paths、13 rows、19 checks、0 issues；API/UI、external/P4/Production仍未形成，全部root继续`ALLOCATED`且registry version不变。
