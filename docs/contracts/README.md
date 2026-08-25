---
doc_id: DOC-CONTRACT-INDEX
title: 合同文档索引
status: living
spec_version: 0.3.0
phase: P3
normative: false
source_sections: [24, 36, 38, 39, 63, 64, 67, 103]
last_reviewed: 2026-08-24
---

# 合同文档索引

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

P3现为active，TASK-P3-01已形成[`planning-workspace-api.md`](planning-workspace-api.md)、[`authorization-and-audit.md`](authorization-and-audit.md)、三份Frontend规范和accepted [ADR-0012](../adr/ADR-0012-planning-workspace-command-state-publication.md)。TASK-P3-02据此发布七份strict Draft 2020-12 Schema、七份synthetic vector、pure fingerprint/precheck与required CI machine report；TASK-P3-03～13只能显式消费这些version/URN，不能自建私有字段或第二套状态/错误事实。

当前schema set为additive `2.6.0`。冻结清单证明21份既有JSON Schema与13份sample共34个P2 artifact逐字节不变；`error-code-registry.v2`、`state-machines.v1`与Solver capability registry也不变。新Schema不执行migration、repository、transition、authorization、API、Frontend、worker、publish或export；OPEN-002/010/015继续OPEN。Implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a` / artifact `9506913562`已精确闭环机器合同，P3-03仍未启动。

## TASK-P3-05 strict carrier consumer

`app.domain.workspace`与`app.application.workspace_queries/schedule_comparison`现严格消费既有`workspace-query.v1`及`schedule-version-comparison.v1`，不改Schema bytes、URN或set version。Query result只在carrier中保存`item_id/item_type/payload_fingerprint`，完整只读payload由application result持有并逐项绑定；14个view、empty/missing/stale/plane/cursor及comparison重放由`p3-workspace-read-model-report.v1`验证。当前没有HTTP/OpenAPI/UI、command、transition、publish/export或P4 carrier。

TASK-P3-09经用户扩卡发布additive set `2.7.0`：新增`export-manifest.v2`与`export-job.v2`，旧`export-manifest.v1`/`export-job.v1`及全部P2/P3-02 bytes/URN不变。v2只表达internal Simulation标准包和v2 artifact reference；consumer必须显式选版本，禁止`latest` alias。
