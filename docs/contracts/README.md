---
doc_id: DOC-CONTRACT-INDEX
title: 合同文档索引
status: living
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [24, 36, 38, 39, 63, 64, 67, 103, 113]
last_reviewed: 2026-09-04
---

# 合同文档索引

## P8 Headless contract plan

ADR-0017已固定canonical JSON为唯一外部产品输入，宿主负责第三方采集/映射/展示，APS负责验证、计划、异步运行和结果合同；宿主与可选Frontend使用同一API。TASK-P8-01将形成详细人类集成合同，TASK-P8-02才允许发布additive machine carrier；当前两者均未开始，schema set仍为`2.9.0`且全部既有bytes不变。

现阶段请以[Headless产品化架构](../architecture/headless-productization-and-platform-integration.md)、[API清单](api-development-checklist.md)和[Import/Normalization合同](import-and-normalization.md)区分目标与当前事实。不得从P8计划推断canonical submission、PlanningRun创建或Production identity endpoint已经存在。

## 当前开发入口

- [API 接口开发清单](api-development-checklist.md)：按当前 OpenAPI 列出全部健康、Planning Workspace 与动态重排 operation，区分路由完成、运行时适配器缺口和未提供端点。
- [数据字段中文名称字典](data-field-dictionary.md)：完整覆盖 `canonical-records.v1` 核心业务字段的英文 key、中文名、类型与必填条件。
- [Schema 索引](schema-index.md)：机器 Schema、stable URN、版本和兼容性权威入口。
- [Schema 版本规则](schema-versioning.md)：新增、兼容、迁移和 preserved bytes 规则。

API 清单和中文字段名是人类可读索引，不替代 JSON Schema、状态机或语义合同；发现不一致时必须修正索引，不能通过改写机器事实让说明成立。

## TASK-P6-08 aggregate monitoring contract

[Duration Prediction Governance Contract](duration-prediction-governance.md)和[Machine Contract](duration-prediction-machine-contract.md)现追加default-off Simulation monitoring投影：content-addressed policy、固定8项aggregate window、fallback/feature-distribution/quality/late/version检测、aggregate-only privacy与run-scoped no-persistence retention。全部threshold由`SIM-ASSUMPTION-026`和policy携带，不从环境变量或代码默认值推断。

Monitor输出独立internal machine report，不新增第五份P6 JSON Schema或product API carrier。任何breach/invalid/tamper产生stable reason、`DEFAULT_DISABLE`建议和`DRIFT_GATE_DISABLED`标准工时fallback要求；它不自动执行disable、retrain、promotion、rollback、external alert或state mutation。P6-02 Schema、P6-04 model、P6-05 Gate、P6-06 runtime、P6-07 ingress及Production边界均不变。

## TASK-P6-06 local runtime contract

[Duration Prediction Machine Contract v1](duration-prediction-machine-contract.md)现追加P6-06 executable runtime章节：content-addressed policy只授权exact P6-04 model与P6-05 READY Gate在Simulation/Test、显式UTC调用中形成P6-02 carrier。Strict provider验证Feature/Model/Evaluation/Policy与独立standard-duration authority，正常选择model p50，其余19项reason精确选择标准工时；invalid standard authority无carrier并fail closed。

Runtime无network/cache/persistence/Planning/API/state/promotion权限；resource/latency数值只是development evidence。P6-02 Schema bytes、P6-04 artifact、P6-05 Gate与标准工时owner均不改；P6-07后来形成独立Planning adapter，P6-08后来形成上节所述aggregate-only monitor。

## TASK-P6-05 offline evaluation and fallback contract

[Duration Prediction Machine Contract v1](duration-prediction-machine-contract.md)现追加P6-05 executable evaluation章节：冻结profile只消费P6-03 validation/test和P6-04 safe model，以exact rational aggregate比较model与standard duration，强制partition/family no-regression、P90 coverage、`9/10` confidence与完整fallback precedence；train label读取为0，input/report tamper fail closed。

P6-02 EvaluationReport bytes和Schema不变，只承载compatible measurement；实际`READY_FOR_SIMULATION_RUNTIME|NOT_READY`与threshold/gaps位于strict aggregate-only Gate envelope。该Gate本身没有runtime、Planning、promotion或Production authority；P6-06后来另获授权并形成上节所述local runtime，OPEN-010/011/014/015继续OPEN。

## TASK-P6-04 baseline model implementation contract

[Duration Prediction Machine Contract v1](duration-prediction-machine-contract.md)现追加P6-04 deterministic baseline章节：trainer只消费P6-03 exact dataset/manifest的4条train row，以grouped median residual、exact rational arithmetic、fixed rounding与nearest-rank margin生成versioned safe model；existing ModelManifest绑定dataset/feature/code/lock/config/algorithm/artifact/scope/decision/rollback/replay。Loader对unsafe serialization、unknown/duplicate/non-finite、oversize、symlink及所有lineage/version/tamper fail closed，writer保证atomic replace和no partial。

Machine evidence为`p6-duration-model-report.v1`及safe model/manifest/replay：10项检查、14项mutation rejection、2项atomic failure rejection、same-input/source-order replay和no-raw/no-label provider boundary。8个baseline estimate不是formal `DurationPrediction`，没有confidence/evaluation Gate、runtime、Planning或Production authority；P6-05必须独立授权。

## TASK-P6-03 dataset implementation contract

[Duration Prediction Machine Contract v1](duration-prediction-machine-contract.md)现追加P6-03 executable dataset章节：唯一versioned Simulation source、completed-normal label eligibility、RUNNING/INTERRUPTED censoring、四项as-of feature、4/2/2 group-safe UTC split、source/row/manifest/bundle identity、privacy/retention与atomic write。实现严格消费`duration-feature-record.v1`，没有修改四份P6-02 Schema或10份sample。

Machine evidence为`p6-duration-dataset-report.v1`：10项检查、safe manifest/count/fingerprint、mutation rejection和no-partial boundary；source与expected bundle不进入Provider artifact。该合同不形成trained model、evaluation Gate、runtime、Planning integration或Production data/model authority。

## TASK-P6-02 duration machine contract

[Duration Prediction Machine Contract v1](duration-prediction-machine-contract.md)现把P6-01人类治理基线发布为additive schema set `2.9.0`的四份strict Simulation carrier：FeatureRecord、ModelManifest、EvaluationReport与Prediction。五份正例、五份定点negative descriptor及`p6-duration-contract-report.v1`固定canonical identity、as-of leakage、exact cross-lineage、quantile/confidence、20项stable fallback、authoritative standard-duration selection、unknown/mixed/tamper拒绝和OPEN-010/011/014/015边界。

70份历史Schema/sample、runtime/dev dependency pins、`uv.lock`、migration head `0005`和所有state pairs逐字不变。CI只新增同一FULL job内的non-skippable离线checker；没有dataset、训练model、evaluation Gate、runtime、Planning ingress、API或Production authority，`AI_DURATION_PREDICTION`继续`DEFERRED / CONTRACT_ONLY / NO_RUNTIME`。TASK-P6-03不会自动启动。

## TASK-P6-01 human governance contract

[`duration-prediction-governance.md`](duration-prediction-governance.md)现作为ADR-0016的accepted人类治理合同，固定标准工时与预测candidate的authority分离、completed-label eligibility/censoring、feature as-of/leakage、privacy/retention/deletion、immutable dataset/model/evaluation provenance、human promotion/rollback、fallback decision table以及OPEN-010/011/014/015 closure conditions。

该文档在TASK-P6-01完成时不是机器Schema；TASK-P6-02现已另行授权并以本页上方additive `2.9.0` package承载其可机器表达部分。当前仍没有dataset、trained model、runtime、planning integration或Production authority，能力继续DEFERRED。

## TASK-P4-15 Exit contract audit

独立审计重新验证schema set `2.8.0`的九个P4 carrier/sample、`0005_replan_event_persistence`、`state-machines.v1`及ADR-0013～0015，与P0～P3冻结字节、ExecutionEvent→facts/Snapshot→ReplanRequest→Solver/Validator→new DRAFT/ChangeReport和Simulator共同入口一致。fresh machine/Gate与provider下载均未发现合同、Schema、migration、dependency、state pair或版本漂移，故合同分项为PASS；本Audit未修改任何carrier、migration、ADR或state machine。

该PASS只覆盖Simulation/development P4合同。ReplanRequest仍无独立state，new ScheduleVersion仍止于DRAFT；Production event/approval authority、external endpoints/publish、UAT、deployment、capacity/SLA和P5字段均未形成。

## TASK-P4-05 freeze/effective-lock consumer boundary

TASK-P4-05只消费既有`planning-policy.v2`、`planning-snapshot.v2`、`planning-problem.v2`与base `PUBLISHED` ScheduleVersion，形成独立content-addressed `effective-lock-projection.v1`和`freeze-window-precheck.v1`；九份P4 Schema/sample、schema set `2.8.0`、migration与state pair均未修改。`p4-freeze-window-report.v1`只证明Simulation policy/投影/拒绝语义，未形成ReplanRequest结果、OBJ-002、ChangeReport、Solver或新ScheduleVersion。

## TASK-P4-04 runtime consumer boundary

P4-04现以consumer-only方式解释既有`execution-event.v1`并生成既有`planning-snapshot.v2`；没有修改九份P4 Schema/sample、schema set `2.8.0`、`0005` migration或dependency。接收与投影使用P4-03 caller-owned事务primitive，Urgent Demand复用P1 Import/Validation/Expansion链；不新增wire carrier、state machine或私有业务合同。Implementation `47f55b41e370aa9d24fd9c987cff4663672c3ee8` / artifact `9644190441`已把该consumer evidence升级为`PROVIDER_VERIFIED`。


## TASK-P4-03 consumer boundary

`0005_replan_event_persistence`现以consumer-only方式持久化P4-02的ExecutionEvent/ReplanRequest exact carrier bytes，并以versioned internal storage projection保存checkpoint、PlanningRun attempt/result reference和transaction audit。Schema set继续`2.8.0`且所有Schema/sample逐字不变；internal records不是第二套业务wire contract，不得携带event payload解释、fact projection、ChangeReport内容或ScheduleVersion application语义。

## TASK-P4-02 machine-contract baseline

Additive schema set现为`2.8.0`。TASK-P4-02发布九份strict/offline/no-default机器carrier与九份Simulation sample，并由纯合同precheck、四个Test ID及`p4-machine-contract-report.v1`固定exact fingerprints、authority/order、immutable lineage、half-open freeze、OBJ-001→002→003、ChangeReport completeness、既有state pairs及P4 export/simulator边界。58份历史Schema/sample、migration `0004`和dependency lock保持逐字不变。

该baseline仅可被后继Task消费，不实现event ingress/persistence/projection、freeze calculation、Solver、new DRAFT、Simulator、export、API或UI。Production authority、external endpoints、deployment、capacity/SLA与P5字段不可表示或default-deny；TASK-P4-03不会自动启动。

## TASK-P4-01 contract baseline

TASK-P4-01已通过registry precheck接受ADR-0013～0015，并形成ExecutionEvent authority/order/idempotency、fact→new Snapshot、ReplanRequest无独立状态机、freeze/effective locks、OBJ-002整数词典序、complete ChangeReport与deterministic Simulator common-path的人类语义。TASK-P4-02随后才允许以additive新版本发布机器合同；P4-03～13只能消费这些决定，P4-14/15分别聚合与独立审计。

P4-01完成时schema set仍为`2.7.0`且没有机器carrier；该历史边界现由上方经独立授权形成的`2.8.0` release取代。Migration仍为`0004`，没有dependency、state pair、API operation或业务实现变化；Production event authority/freeze/identity/external target/capacity/SLA继续未形成。

## TASK-P3-17 contract audit conclusion

P3 Exit独立重放确认P2 frozen contracts、P3 workspace `2.6.0`、export `2.7.0`、state/error/capability、HTTP与Frontend wire合同均PASS且相对Diff base零变化。审计为`READY`/0 gaps但provider pending；不形成P4 carrier、external contract或Production authority。

## TASK-P3-14 contract aggregation

`p3-vertical-slice-report.v1`是internal Gate machine report，不增加Business schema set或外部API版本。它严格消费P3-02～13已发布carrier/报告以及P2 Gate，保留raw evidence并以`p3-gate-semantic-projection.v1`比较两次fresh replay；任何version/task/check/count、语义或拒绝映射漂移均fail closed。Schema set继续为`2.7.0`，没有migration、dependency或合同行为变更。

本目录描述机器可执行 Schema 的人类语义。TASK-P0-03 发布 schema set `1.0.0` 的数据合同 skeleton；TASK-P0-04/05 以 set-level additive 方式发布 `1.1.0/1.2.0` 规则与Simulation合同；TASK-P1-02 以 breaking set release `2.0.0` 新增严格 canonical records、Import v2与Snapshot v2；TASK-P1-05/06再以additive `2.1.0/2.2.0`发布unit registry与Data Validation/error/report合同；TASK-P2-01以additive set `2.3.0`新增非互换的`planning-problem.v2`；TASK-P2-02以`2.4.0`新增Policy/Limits/Solution/SolverReport v1；TASK-P2-11以`2.5.0`新增`kpi.v2`和`export-manifest.v1`；TASK-P3-02现以additive `2.6.0`新增七份Workspace/Version/Audit/Publication/ExportJob carrier。机器文件位于 `/schemas/json`、`/schemas/rules` 与 `/schemas/scenario`，data dictionary 位于 `/schemas/data_dictionary.yaml`。Schema 与对应合同必须同 Task、同版本语义更新。

## 当前基线

- `import-and-normalization.md`
- `planning-snapshot.md`
- `planning-problem.md`
- `planning-policy-and-solve-limits.md`
- `planning-solution-and-schedule-version.md`
- `planning-workspace-api.md`
- `authorization-and-audit.md`
- `execution-events-and-replan-request.md`
- `export-package.md`
- `schema-index.md`
- `schema-versioning.md`

## 已形成的机器合同

- `canonical-records.v1`：严格固定 Factory/Resource、Product/Routing、Order/Lot、execution fact与lock collections，每条记录携带source/version/record ID；
- `import-package.v2`：固定schema/source/normalization/canonicalization versions、strict records与synthetic provenance；
- `planning-snapshot.v2`：固定validated Import/quality provenance、canonical records、expanded OperationInstance/edge payload与entity counts；TASK-P1-08已形成hash构建、immutable value和insert-only persistence；
- `import-package.v1`：只固定版本化 metadata envelope；Canonical records 字段仍由 P1 authority mapping 决定；
- `planning-snapshot.v1`：固定不可变快照元数据与 Production/Simulation provenance 分离；
- `planning-problem.v1`：固定 Solver-neutral 顶层、Operation/Option/Edge/Calendar interval skeleton；TASK-P1-09已形成builder/hash与immutable replay，Solver仍未形成；
- `planning-problem.v2`：新增sourced due/priority、完整capacity=1 Resource facts、active HARD/SOFT locks、historical completion anchors与跨边界edge；builder/hash/verify为opt-in，v1默认API与固定向量保持；
- `kpi.v1`、`error.v1`、`validation-report.v1`：TASK-P0-03 的原始顶层 envelope，原文件保持不变；
- `error.v2`：固定 19 个当前已分配 code 与七类 category 的唯一映射；
- `error.v3`：使用error registry v2并要求entity type/ID、field、observed、expected、source location和action的完整诊断；
- `import-quality-report.v1`：绑定Import v2 package、data-quality-rules.v1、error registry v2、PASS/FAIL、精确错误计数与内容派生report ID；
- `validation-report.v2`：固定 `hard_violation_count`、C-001～C-011 与 `HARD` violation shape；
- `state-transition.v1`：固定三套 machine/state 名称；允许转移由 `state-machines.v1` registry 判定；
- `constraint-rule-sheet.v1`、`capability-registry.v1`、`error-code-registry.v1`、`state-machines.v1`：机器可读 P0 规则合同。
- `factory-profile.v1`：固定 synthetic-only 工厂分布边界、asset version 与适用/预期拒绝 capability；
- `scenario-spec.v1`：固定 profile/generator reference、显式 seed、复杂度矩阵与 expected behavior；
- `scenario-manifest.v1`：固定 synthetic target、Scenario/Profile/Generator/seed/generated-at/Import package/dataset hash provenance。
- `unit-conversion-registry.v1`：只登记`s/min/h`到`second`的精确整数因子，禁止alias、隐式default和浮点舍入。
- `error-code-registry.v2`：additive保留v1全部19项映射，并增加`ROUTE_CYCLE`、`MISSING_RESOURCE`、`UNIT_CONVERSION_ERROR`、`MISSING_DURATION`四项DATA_ERROR。
- `planning-policy.v1`、`solve-limits.v1`：显式数据平面、来源、版本、C-001～C-011、OBJ-001及wall-time/worker/seed，不提供Production默认值；
- `planning-solution.v1`、`solver-report.v1`：七种status、Problem/Policy/Limits/Solution指纹、tick/UTC、objective/bound/gap、timing/model/memory/version provenance，并区分合同样例与未来真实Solver run。
- `kpi.v2`：绑定同一Snapshot/Problem/validated Solution/Validation/Solver/ImportQuality run，独立计算Delivery/Planning/Resource并显式声明无base ScheduleVersion时Stability不适用；
- `export-manifest.v1`：固定`p2-internal-export.v1`的9个payload、逐文件hash/bytes/rows、entity counts、完整lineage、synthetic/non-publishable状态及P2-12/P4 deferred artifacts。
- `schedule-version.v1`：固定immutable content、parent/source、P2 validated lineage、content fingerprint、validation/decision/publication evidence与server-derived allowed actions；
- `workspace-query.v1` / `workspace-command.v1`：固定query/result稳定分页与严格command discriminator、CAS、reason、target、idempotency/request fingerprint；body不承载principal/role authority；
- `schedule-version-comparison.v1`：只表达两份immutable Version的operation/KPI read-model delta；
- `audit-event.v1`：append-only carrier，保存pseudonymous actor/capability、sanitized intent、before/after、result/error namespace与trace；
- `publication-result.v1` / `export-job.v1`：只表达`SIMULATION_INTERNAL`成功发布结果和独立ExportJob lifecycle；不授权Production或外部target。

`2.6.0`保留此前全部artifact；consumer必须显式选择document版本。Import/Snapshot v2固定`2.0.0`、unit registry固定`2.1.0`、quality固定`2.2.0`、Problem v2固定`2.3.0`、PlanningSolution/SolverReport固定`2.4.0`、KPI v2/ExportManifest固定`2.5.0`，均不因set-level新增合同而改写。strict objects拒绝未知字段且不声明业务默认值。P3-02七份sample只证明Schema shape、offline `$ref`、canonical fingerprint与negative vector，不是状态行为、授权、持久化、Production或发布证据。

TASK-P1-04已形成code-level `ReferenceFileAdapter@1.0.0` transport contract：fixed CSV/XLSX shape安全转换为TASK-P1-03 Raw Staging，manifest明确`production_binding=false`。`payload_json`在Adapter边界保持opaque，由TASK-P1-05的显式MappingProfile消费。因此下方真实`external-adapters.md`仍受OPEN-002/007/013/015阻塞，不能用Reference Adapter替代。

TASK-P1-05形成标准库pure `app.normalization`：批次必须精确绑定source system/version、mapping profile/version和unit registry version；canonical ID、UTC Z、integer seconds、collection ordering、package ID/bytes/dataset hash均可重放。它只生产Import v2，不执行DAG/reference/capability Data Validation、order expansion、Snapshot/Problem或Solver。

TASK-P1-06形成标准库pure `app.data_validation`：消费Import v2并收集structure/reference/lineage、routing DAG、resource/capability、unit/duration、UTC/calendar/fact/lock问题；Error按稳定诊断键去重排序，报告不含`generated_at`且report ID由其余字段的canonical bytes派生。PASS必须零Error，FAIL的count必须与数组相等。它不展开订单、不构建Snapshot/Problem，也不导入Planning/Solver/ScheduleValidator。

TASK-P1-12独立审计已重放全部合同、迁移、Generator和common-ingress gates：schema set保持`2.2.0`且没有Schema修改；Import/Snapshot/Problem的发布版本和hash边界均与实现证据一致。P1 Gate=`READY`只证明Data & Snapshot链，不形成PlanningSolution、Solver、Production Adapter或外部API合同。

## 等待实现事实后形成

- `api.md`：当前总规只有 endpoint inventory，payload/status/auth 尚未形成。
- `simulation-api.md`：需绑定环境开关、实际 job contract 和 OpenAPI。
- `external-adapters.md`：受 OPEN-002、OPEN-007、OPEN-013、OPEN-015 阻塞。

这些路径不创建空文档，避免被误认为已经批准的接口合同。

## TASK-P2-14 Exit contract audit

P2独立Exit审计已重跑schema set`2.5.0`及全部registered contract tests，并核对Problem v2、Policy/Limits、Solution/Report、Validation、KPI/Export Manifest各自固定document版本与历史fingerprints。结果为PASS，Schema、data dictionary、migration、dependency/lock和ADR均零变化；C-012～018、OBJ-002/003、P3 API/state/publish合同没有被补猜。Audit implementation required run `32677741558` / artifact `9503227240`已精确复验并闭环，TASK-P2-14=`done`、Exit=`READY`；P3合同仍未授权。

## TASK-P3-02 workspace machine contract release

P3已completed；TASK-P3-01形成[`planning-workspace-api.md`](planning-workspace-api.md)、[`authorization-and-audit.md`](authorization-and-audit.md)、三份Frontend规范和accepted [ADR-0012](../adr/ADR-0012-planning-workspace-command-state-publication.md)。TASK-P3-02据此发布七份strict Draft 2020-12 Schema、七份synthetic vector、pure fingerprint/precheck与required CI machine report；TASK-P3-03～13均显式消费这些version/URN，没有自建私有字段或第二套状态/错误事实。

该P3-02 release时schema set为additive `2.6.0`，后续P3-09以`2.7.0`扩展export carriers；当前总set见本页顶部规划边界。冻结清单证明21份既有JSON Schema与13份sample共34个P2 artifact逐字节不变；`error-code-registry.v2`、`state-machines.v1`与Solver capability registry也不变。P3-02新Schema当时不执行migration、repository、transition、authorization、API、Frontend、worker、publish或export；OPEN-002/010/015继续OPEN。Implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a` / artifact `9506913562`已精确闭环机器合同。

## TASK-P3-05 strict carrier consumer

`app.domain.workspace`与`app.application.workspace_queries/schedule_comparison`现严格消费既有`workspace-query.v1`及`schedule-version-comparison.v1`，不改Schema bytes、URN或set version。Query result只在carrier中保存`item_id/item_type/payload_fingerprint`，完整只读payload由application result持有并逐项绑定；14个view、empty/missing/stale/plane/cursor及comparison重放由`p3-workspace-read-model-report.v1`验证。当前没有HTTP/OpenAPI/UI、command、transition、publish/export或P4 carrier。

TASK-P3-09经用户扩卡发布additive set `2.7.0`：新增`export-manifest.v2`与`export-job.v2`，旧`export-manifest.v1`/`export-job.v1`及全部P2/P3-02 bytes/URN不变。v2只表达internal Simulation标准包和v2 artifact reference；consumer必须显式选版本，禁止`latest` alias。

## TASK-P3-10 HTTP binding

FastAPI组合根现暴露合同固定的17个`/api/v1` operation，以strict `workspace-query.v1`、`workspace-command.v1`、comparison carrier以及P3-09 `export-job.v2`参考绑定已有application port。OpenAPI不是第二套业务Schema；Schema set保持`2.7.0`，migration、dependency/lock、state-machine bytes和所有已发布carrier字节零变化。本地`p3-planning-workspace-api-report.v1`为8/8 PASS且`issues=[]`，exact provider待implementation提交后核验。
