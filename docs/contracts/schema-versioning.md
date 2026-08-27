---
doc_id: DOC-CONTRACT-009
title: Schema 版本与兼容规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [23, 24, 40, 101, 103, 104]
last_reviewed: 2026-08-24
---

# Schema 版本与兼容规则

## TASK-P3-17 audit conclusion

P3 Exit验证已发布Schema/URN/version/fingerprint及negative cross-document interchange边界保持兼容，migration revision仍`0004`。Audit不发布新Schema、migration或superseding contract；P4与Production合同未形成。

## 每次 Schema 修改必须

1. 增加对应 `schema_version`；
2. 说明 backward/forward compatibility；
3. 提供 migration 或明确拒绝旧版本；
4. 更新 human-readable contract；
5. 增加/更新 contract test；
6. 更新 sample/fixture；
7. 检查 Snapshot/Problem hash、replay 和 export 影响。

## 兼容分类

- Additive optional：可能向后兼容，但仍需 version 和测试。
- Required/semantic change：不兼容，必须迁移或明确拒绝。
- Rename/unit/time semantic change：视为不兼容，不能用 alias 静默吸收。
- Ordering-only serialization change：若影响 hash，必须作为版本变化治理。

## TASK-P3-02 additive workspace carrier release

- Set release：global metadata由`2.5.0`提升为additive `2.6.0`；新建`schedule-version/workspace-query/workspace-command/schedule-version-comparison/audit-event/publication-result/export-job.v1`七个非互换document，stable URN与文件名逐项登记；
- Preservation：启动时冻结21份既有JSON Schema与13份sample，排序清单摘要=`sha256:76bb8ae4347ae8bbaa0b2781f74eccd7e4cb1ee97303533a5db3e49f27673723`；machine check还固定`state-machines.v1`、`error-code-registry.v2`和Solver capability registry，旧document内的`schema_set_version const`与所有bytes/URN均不改；
- Compatibility：set-level additive，但七份新document彼此及与PlanningSolution/ExportManifest均不互换。Consumer必须按exact version/URN离线解析，不得使用`latest`、alias、unknown字段或隐式default；
- Canonicalization：使用`canonical-json.v1`；Schedule content、query request、command request、comparison、publication result和ExportJob各有显式projection fingerprint，key ordering不改变结果，字段/value drift必须拒绝；
- Plane/isolation：SIMULATION只允许Development/Test/Benchmark且synthetic provenance为显式条件；PRODUCTION carrier必须`synthetic=false`/Production environment。P3 publication/export v1只表示`SIMULATION_INTERNAL`，因此Production external side effect不可表示；
- Migration/rollback：本release无DB migration和consumer behavior。TASK-P3-03消费前可整体回退metadata/new files；一旦consumer形成只能新增document version与显式migration，不得覆盖v1或P2历史；
- Dependency：runtime/dev dependency集合及`uv.lock`摘要`sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`不变。CI只增加非skippable machine contract step与artifact JSON。

该release实现ADR-0012的carrier层，不执行state transition、authorization、repository/API/UI/worker、publication/export或Production行为；OPEN-002/010/015保持OPEN。

Schema version、rule version、generator version 和 code commit 是不同维度，不能互相替代。

## 当前发布基线

- Schema set：`2.5.0`；`pyproject.toml` 与 `app.SCHEMA_VERSION` 一致；此前全部set artifacts保留；
- Current contract IDs：历史v1 skeleton、`canonical-records.v1`、`import-package.v2`、`planning-snapshot.v2`、`planning-problem.v2`、`planning-policy.v1`、`solve-limits.v1`、`planning-solution.v1`、`solver-report.v1`、`kpi.v2`、`export-manifest.v1`、`unit-conversion-registry.v1`、`error-code-registry.v2`、`error.v3`与`import-quality-report.v1`；单个document/version不得因set版本提升而重解释；
- Dialect：JSON Schema Draft 2020-12，使用稳定 URN `$id`；
- Compatibility：当前set包含P1-02 major release和P1-05/06 additive releases；具体兼容、migration与固定fingerprint见下方各release记录；
- Unknown/default policy：strict contracts使用`additionalProperties=false`且Schema不含业务`default`；Production authority仍必须显式提供，不能从synthetic/sample推断。

`*.v1` 的字段或语义后续变化必须分类为 additive/breaking；即使 schema set 版本提升，也不得无痕覆盖本目录下已经发布的 v1 artifact。

## TASK-P0-04 additive set release

- Schema set：`1.1.0`，同步写入 `pyproject.toml`、`app.SCHEMA_VERSION` 与 data dictionary；
- 保留 `error.v1`、`validation-report.v1` 原文件和 URN；新增 `error.v2`、`validation-report.v2` 与 `state-transition.v1`；
- 新增四份 `*.v1` YAML rule/registry contract。它们的版本独立于 JSON document version；
- Set compatibility：添加新合同且保留全部 `1.0.0` artifact，属于 set-level additive；单个 v1/v2 document 仍不互换；
- Migration：没有数据库、持久化 Error/Validation consumer 或历史 run artifact，因此不执行数据迁移。v2 consumer 必须显式拒绝 v1；未来只能用 adapter/new artifact 迁移，不能 alias 或覆盖 v1；
- Validation：Draft 2020-12 `jsonschema==4.25.1`、PyYAML `6.0.2`、TEST-CONTRACT-001 与 TASK-P0-04 四项 contract tests；规则表 CLI 只验证完整性/一致性。

本次不修改 PlanningProblem、Snapshot、Import 或 KPI document version，不影响其 hash/serializer 语义。没有正式 sample/Fixture 可迁移；P0-04 tests 使用内联纯合同实例，不把它们声明为 Production 或 Scenario data。

## TASK-P0-05 additive Simulation set release

- Schema set：`1.2.0`，同步写入 `pyproject.toml`、`app.SCHEMA_VERSION` 与 data dictionary；
- 保留全部 `1.0.0/1.1.0` JSON/YAML artifact 与稳定 URN；新增 `factory-profile.v1`、`scenario-spec.v1`、`scenario-manifest.v1`；
- Set compatibility：只添加新 document types，属于 set-level additive；contract version（`*.v1`）、asset version（Profile/Scenario `1.0.0`）与 Generator version 相互独立；
- Migration：没有 DB、persisted consumer、正式 Fixture 或历史 run artifact，故 none；consumer 必须显式选择 Simulation v1，不通过 alias 吸收未来版本；
- Hash：`canonical-json.v1` 对 Standard Import envelope 稳定排序/编码并拒绝 NaN/Infinity，`dataset_hash=sha256(canonical_import_bytes)`；manifest `generated_at` 不参与 hash；
- Validation：Draft 2020-12 `jsonschema==4.25.1`、pure semantic precheck、TEST-CONTRACT-001、TEST-SCENARIO-REPLAY 与 TEST-SIM-ISOLATION。

本次不修改 `import-package.v1`、Snapshot/Problem、rule/state/error/capability artifact 内容。P0 empty package 的 `records={}` 是不猜生产字段的边界，不是 P1 canonical dataset 实现。

## TASK-P0-08 engineering metadata review

Schema set 与 `app.SCHEMA_VERSION` 均保持 `1.2.0`；没有修改 `schemas/**`、JSON/YAML contract、sample、Fixture、hash 或 serializer。`engineering_job_records` 与 `engineering_idempotency_records` 是 Alembic 管理的通用关系型工程 metadata，不是 Business Schema set；其 compatibility 由 revision `0001_engineering_job_metadata` 的空库 upgrade/downgrade test 管理。

因此本 Task 的 JSON Schema compatibility/migration 为 none；新增 runtime dependencies/lock 和 build commit metadata 不能借机提升或覆盖 schema set。未来若 Job/health payload 成为跨系统产品合同，必须由单独 Task 建立 versioned Schema，而不能把本 P0 Python/DB skeleton 当作已发布业务合同。

## TASK-P1-02 canonical major set release

- Schema set：`2.0.0`，同步写入`pyproject.toml`、`app.SCHEMA_VERSION`与data dictionary；
- 新增`canonical-records.v1`、`import-package.v2`、`planning-snapshot.v2`及两份明确synthetic sample；所有`1.0.0/1.1.0/1.2.0` artifact、稳定URN和尤其Import/Snapshot v1文件逐字保留；
- Compatibility：从opaque Import v1/metadata-only Snapshot v1到strict required canonical payload属于set-level major与document-level breaking change。v1/v2前后均不互换，禁止alias、默认填充或静默upgrade；
- Migration：没有数据库或已发布v2 consumer，故无数据migration。v1 fixture/history保持只读；后续producer必须显式产出v2，旧consumer必须拒绝v2直到升级；
- Hash/replay：v2只固定`sha256:`格式、provenance和payload；dataset/Snapshot hash projection与builder仍由TASK-P1-05/08实现。Schema sample digest不构成hash evidence；
- Validation：JSON Schema Draft 2020-12/jsonschema `4.25.1`跨URN registry、positive/negative/round-trip、unknown/no-default、UTC/unit/duration/reference、synthetic isolation、v1 byte fingerprint及pure semantic precheck均由TEST-CONTRACT-001覆盖。

本release落实ADR-0007/0008/0009既有决定，不改变PlanningProblem、rule/state/error/capability/Simulation artifact，也不引入dependency、DB migration、Adapter、DataValidation、Builder或Solver。`uv.lock`依赖图因此保持不变。

## TASK-P1-04 metadata review

本Task只在`pyproject.toml` runtime dependencies增加exact openpyxl/defusedxml并更新`uv.lock`，没有修改`[tool.plantnexus-aps.versions]`、`app.SCHEMA_VERSION`、`schemas/**`、data dictionary、sample、serializer或hash projection。Schema set继续`2.0.0`，JSON/YAML compatibility与migration均为none；Reference Adapter`1.0.0`是独立code-level transport version，不能替代或提升Schema version。

未来改变三列Reference transport或opaque row serialization必须发布新的adapter version并提供replay/compatibility规则，但只有修改machine Schema时才按本文件提升schema set。Dependency lock变化不能无痕改写Import/Snapshot document版本。

## TASK-P1-05 additive normalization-rule release

- Schema set：`2.1.0`，同步更新`pyproject.toml`、`app.SCHEMA_VERSION`和data dictionary；新增`unit-conversion-registry.v1`，不新增或重写JSON document version；
- Preservation：`canonical-records.v1.schema.json`与`import-package.v2.schema.json`SHA-256继续分别为`fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e`、`166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56`；Import v2 document内固定`schema_set_version=2.0.0`；
- Compatibility：set-level只添加独立rule type，属于additive；mapping profile、unit registry与canonicalization version必须显式组合进入normalization rule version，禁止按`latest`重解释历史staged rows；
- Migration：无数据库迁移、无历史canonical package改写。旧rule version继续只读，consumer rollback必须显式选择旧版本；
- Validation：unit registry contract、Schema/data-dictionary同步、stable ID/UTC/integer seconds、same-input replay、mapping-version mutation和负向DATA_ERROR均由TEST-CONTRACT-001/TEST-NORMALIZATION-001覆盖。

`pyproject.toml`本次只改版本metadata，没有dependency或lock graph变化；`uv.lock`保持不变。规则版本变化必须发布新registry文件并回放canonical hashes，不能原地更改v1语义。

## TASK-P1-06 additive data-quality release

- Schema set：`2.2.0`，同步更新`pyproject.toml`、`app.SCHEMA_VERSION`与data dictionary；新增`error-code-registry.v2`、`error.v3`、`import-quality-report.v1`和明确PASS/FAIL samples；
- Preservation：canonical-records.v1、Import v2、error.v1、error.v2、error registry v1与unit registry v1的固定SHA-256继续逐字不变。Import v2 document仍固定`2.0.0`，unit registry v1仍固定`2.1.0`；
- Compatibility：registry v2只在保留19项code/category映射后增加四项DATA_ERROR；Error v3和Report v1是显式新consumer合同，Error v1/v2不得alias为v3。Report跨URN引用Error v3，validator必须使用显式registry而非网络解析；
- Migration：无数据库migration、无历史Error/Import改写。旧consumer显式停留v1/v2，新Data Validation consumer选择registry v2/Error v3/report v1；禁止`latest`重解释历史Error；
- Replay：同package与相同issue集合得到同排序、canonical bytes和report ID，PASS/FAIL sample与正反Schema/count/identity tests固定该行为。

本次没有dependency变化，`uv.lock`保持不变；也没有Snapshot/Problem/Solver/HTTP contract。未来改变四类Gate映射、detail必填字段、排序或report ID projection必须发布新registry/document version并提供兼容与重放证据。

## TASK-P1-07 code-level expansion version review

本Task发布独立`order-expansion.v1`行为版本，但不修改`schemas/**`、`app.SCHEMA_VERSION`或`[tool.plantnexus-aps.versions].schema`；全局schema set继续`2.2.0`，Import/Snapshot v2 document继续各自固定`2.0.0`。`pyproject.toml`只增加exact dev-only `hypothesis==6.165.10`，`uv.lock`增加Hypothesis及transitive `sortedcontainers==2.4.0`，runtime dependency集合和Business Schema metadata均不变。

Compatibility为code-level additive consumer：stable derived ID把expansion version纳入hash，consumer必须显式保存/选择版本，禁止把未来实现标成v1重解释历史输出。没有DB migration、Schema sample或历史artifact改写；Snapshot builder仍由TASK-P1-08负责。若expanded shape字段不足，必须另发Schema set/document version，而不能在本service隐藏字段。

## TASK-P1-12 Exit Gate version audit

本审计没有修改`schemas/**`、data dictionary、`pyproject.toml`、`uv.lock`、migration或任一serializer/hash projection。Full contract/regression、Snapshot/Problem replay与provider artifacts确认global schema set仍为`2.2.0`，Import/Snapshot v2 document仍显式`2.0.0`，unit registry v1仍显式`2.1.0`；历史release/fingerprint没有被`latest`重解释。

因此compatibility=`none`、Schema migration=`none`、database migration change=`none`。P1 Gate=`READY`是既有版本链的审计结果，不是新Schema release；PlanningSolution/Solver/P2合同仍须由后续显式版本与迁移规则形成。

## TASK-P2-01 additive PlanningProblem v2 release

- Global schema set提升到`2.3.0`，同步`pyproject.toml`、`app.SCHEMA_VERSION`与data dictionary；新建`planning-problem.v2`及其synthetic replay sample；
- Compatibility：这是set-level additive、Problem consumer层breaking/non-interchangeable release。v1 Schema/sample/default builder/API/hash projection和fixed bytes/hash保持原样；v2只能由version-specific opt-in API产生和消费；
- Preservation：v1 Schema/sample SHA-256分别为`41b01bfbcdfdb0a6dc52da1121383f630ac3f08ca7db4d21c0b66dea3a96e943`、`aa31fbb20b862b7ef51a0e1ed781cddca07c00a0d2724d9ea34e6a75d08a4093`，fixed Problem/canonical bytes digest保持`sha256:6e4aff...ff72`/`1f00ad...8645`；Import/Snapshot v2=`2.0.0`、unit registry=`2.1.0`、quality/error release=`2.2.0`均不原地改写；
- Migration：PlanningProblem没有持久化表或已发布v2 consumer，因此database/data migration为none。v2被后继消费后只能通过新Problem version/ADR迁移，不得覆盖历史v2 bytes；rollback在P2-01边界内回到v1默认API；
- Hash/replay：v2显式记录builder/canonicalization/hash-projection版本，projection覆盖全部新增事实。Schema/sample正反/round-trip、same-input/reordering/mutation/property、v1 fingerprint与machine report固定兼容行为；
- Dependency：无新增或变更dependency，`uv.lock`逐字保持；OR-Tools仍禁止。

ADR-0010记录due/priority来源、capacity=1、active lock cutoff、historical anchor与v1兼容策略。该release只形成Solver-neutral输入合同，不形成Solution、Solver、Validator、OBJ-001计算或Production authority。

## TASK-P2-02 additive planning-machine contract release

- Global schema set提升到`2.4.0`，同步`pyproject.toml`、`app.SCHEMA_VERSION`与data dictionary；新增PlanningPolicy/SolveLimits/PlanningSolution/SolverReport四个v1 document和四份explicit synthetic samples；
- Compatibility：set-level additive，新document之间通过稳定URN与exact version/fingerprint引用；Problem v1/v2、Import/Snapshot、quality/error/unit及所有历史sample/registry不改。Consumer必须显式选择四个v1 ID，不得用`latest`或推断字段补齐；
- Migration：没有PlanningRun/Solution/Report持久化表或已发布consumer，database/data migration为none。新合同被消费后，只能通过显式新document version迁移，不能原地重解释v1；未消费时rollback可删除四份additive artifact并恢复global metadata；
- Defaults：四份Schema全部strict且没有`default`。Policy和Limits必须携带data plane/source/version；仓库中的Simulation值不得成为Production policy、weight、limit或SLA；
- Replay：Schema/sample原始bytes和canonical fingerprints由`planning-machine-contract-report.v1`固定，跨URN round-trip、七种status、非法组合、tick/UTC、timing/model/memory、provenance与cross-document mismatch由TEST-CONTRACT-001/TEST-ERROR-MAPPING-001覆盖；
- Dependency：runtime/development dependencies和`uv.lock`不变，OR-Tools仍未安装。该release没有Backend、Constraint、ScheduleValidator、Benchmark、DB/API/Worker或P3动作。

Problem v1/v2 Schema/sample及`uv.lock`启动fingerprint在Task卡中固定；后继consumer若要求修改status语义、目标顺序、time unit或fingerprint projection，必须先停止并以新version/ADR处理。

## TASK-P2-03 dependency-only review

本Task不修改Schema、sample、`app.SCHEMA_VERSION`或任何document语义；global schema set继续`2.4.0`。启动冻结的四份P2-02 Schema SHA-256与Problem v1/v2 artifacts保持原字节。`cp-sat-backend.v1`是Backend implementation identity，不是JSON Schema release，也不允许改写七种status、Policy/Limits或Solution/Report合同。未来solver/backend版本升级按ADR-0011执行lock、status、Golden/Scenario和Benchmark replay。

## TASK-P2-11 additive output-contract release

- Global schema set提升到`2.5.0`，同步`pyproject.toml`、`app.SCHEMA_VERSION`与data dictionary；新增`kpi.v2`、`export-manifest.v1`及各自synthetic sample；
- Compatibility：set-level additive；KPI v1、PlanningSolution/SolverReport v1及全部历史Schema/sample bytes保持不变。新consumer必须显式选择KPI v2和`p2-internal-export.v1`，不得用`latest`或原地解释旧artifact；
- Identity：JSON使用`canonical-json.v1`；KPI ID和package ID均由排除自身ID字段后的canonical内容派生，文件fingerprint绑定exact bytes；CSV固定UTF-8、RFC 4180、LF、稳定列序；
- Migration：没有KPI/ExportJob/ScheduleVersion persistence或已发布consumer，database/data migration为none。未发布internal package可丢弃重建，合同回滚只能移除新增additive类型并恢复set metadata，不能改写历史artifact；
- Validation：Schema positive/sample round-trip、KPI v1 fingerprint preservation、same-input bytes、formal run lineage、hash/size/row count、mixed/tamper/missing/partial-write negatives及8-check machine report；
- Dependency/ADR：runtime/dev pins与`uv.lock`不变；internal immutable package未改变架构或状态语义，因此不新增ADR。若进入persistence/publish/external storage必须停止并由P3 Task/ADR治理。

## P3 planning boundary

TASK-P3-02如获授权，只能执行additive set release：旧P2 document version、URN、sample bytes和consumer replay必须保留；新P3 documents须独立版本化、离线解析并提供compatibility/fingerprint negatives。P3-03 migration只消费已发布Schema，不得用数据库默认值反向定义合同；本次transition不改变`2.5.0`或任何依赖/lock。

TASK-P3-09是additive set `2.7.0` owner。原因是冻结`export-job.v1`的P3 profile与P2-only manifest v1 reference不能共同表达标准XLSX及Version/publication/job/audit lineage；经用户批准，以新URN发布manifest/job v2，绝不原地重解释v1。旧workspace v1 carriers继续固定`2.6.0`，global current metadata才为`2.7.0`；`uv.lock`与dependency pins不变。
