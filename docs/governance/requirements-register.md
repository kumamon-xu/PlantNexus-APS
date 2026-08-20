---
doc_id: DOC-GOV-002
title: 核心需求注册表
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [3, 4, 5, 6, 107]
last_reviewed: 2026-08-20
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
| REQ-015 | ALLOCATED | Reference Scheduler Baseline | Baseline comparison and warning behavior | P2 |

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

TASK-P1-11 review：REQ-001/002/003现由`CommonIngressPipeline`把ReferenceFileAdapter与Synthetic Generator的Raw Staging连到同一Normalization/Data Validation/Expansion/Snapshot/Problem链，并形成Import/Snapshot/Problem完整bytes/hash parity；REQ-009获得`p1-data-pipeline-report.v1`的commit、版本、配置、ID/hash/count/code链；REQ-011/012获得公开staging与Scenario E2E replay。参考文件仍是synthetic temporary CSV，没有Production binding、Solver/Validator/Benchmark/Execution/Export。P1-12尚未审计，所有Requirement根ID继续`ALLOCATED`，registry format version不变。
