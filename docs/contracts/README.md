---
doc_id: DOC-CONTRACT-INDEX
title: 合同文档索引
status: living
spec_version: 0.3.0
phase: P2
normative: false
source_sections: [24, 36, 38, 39, 63, 64, 67, 103]
last_reviewed: 2026-08-20
---

# 合同文档索引

本目录描述机器可执行 Schema 的人类语义。TASK-P0-03 发布 schema set `1.0.0` 的数据合同 skeleton；TASK-P0-04/05 以 set-level additive 方式发布 `1.1.0/1.2.0` 规则与Simulation合同；TASK-P1-02 以 breaking set release `2.0.0` 新增严格 canonical records、Import v2与Snapshot v2；TASK-P1-05/06再以additive `2.1.0/2.2.0`发布unit registry与Data Validation/error/report合同；TASK-P2-01以additive set `2.3.0`新增非互换的`planning-problem.v2`，并逐字保留既有v1合同。机器文件位于 `/schemas/json`、`/schemas/rules` 与 `/schemas/scenario`，data dictionary 位于 `/schemas/data_dictionary.yaml`。Schema 与对应合同必须同 Task、同版本语义更新。

## 当前基线

- `import-and-normalization.md`
- `planning-snapshot.md`
- `planning-problem.md`
- `planning-policy-and-solve-limits.md`
- `planning-solution-and-schedule-version.md`
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

`2.3.0` 保留 `1.0.0/1.1.0/1.2.0/2.0.0/2.1.0/2.2.0` 全部 artifact；Import/Snapshot/Problem v1与v2以及Error v1/v2/v3 document不可互换，consumer必须显式选择版本。Import/Snapshot v2自身固定的`schema_set_version=2.0.0`、unit registry v1固定的`2.1.0`、quality合同固定的`2.2.0`均不因set-level新增合同而原地改写。strict objects拒绝未知字段且不声明业务默认值。`planning-problem.v2.synthetic.json`是TASK-P2-01 builder固定回放输出；其他Schema samples的既有身份不被改写，也都不是生产数据。

TASK-P1-04已形成code-level `ReferenceFileAdapter@1.0.0` transport contract：fixed CSV/XLSX shape安全转换为TASK-P1-03 Raw Staging，manifest明确`production_binding=false`。`payload_json`在Adapter边界保持opaque，由TASK-P1-05的显式MappingProfile消费。因此下方真实`external-adapters.md`仍受OPEN-002/007/013/015阻塞，不能用Reference Adapter替代。

TASK-P1-05形成标准库pure `app.normalization`：批次必须精确绑定source system/version、mapping profile/version和unit registry version；canonical ID、UTC Z、integer seconds、collection ordering、package ID/bytes/dataset hash均可重放。它只生产Import v2，不执行DAG/reference/capability Data Validation、order expansion、Snapshot/Problem或Solver。

TASK-P1-06形成标准库pure `app.data_validation`：消费Import v2并收集structure/reference/lineage、routing DAG、resource/capability、unit/duration、UTC/calendar/fact/lock问题；Error按稳定诊断键去重排序，报告不含`generated_at`且report ID由其余字段的canonical bytes派生。PASS必须零Error，FAIL的count必须与数组相等。它不展开订单、不构建Snapshot/Problem，也不导入Planning/Solver/ScheduleValidator。

TASK-P1-12独立审计已重放全部合同、迁移、Generator和common-ingress gates：schema set保持`2.2.0`且没有Schema修改；Import/Snapshot/Problem的发布版本和hash边界均与实现证据一致。P1 Gate=`READY`只证明Data & Snapshot链，不形成PlanningSolution、Solver、Production Adapter或外部API合同。

## 等待实现事实后形成

- `api.md`：当前总规只有 endpoint inventory，payload/status/auth 尚未形成。
- `simulation-api.md`：需绑定环境开关、实际 job contract 和 OpenAPI。
- `external-adapters.md`：受 OPEN-002、OPEN-007、OPEN-013、OPEN-015 阻塞。

这些路径不创建空文档，避免被误认为已经批准的接口合同。
