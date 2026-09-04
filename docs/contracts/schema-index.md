---
doc_id: DOC-CONTRACT-008
title: Schema 计划索引
status: living
spec_version: 0.3.0
phase: P0-P8
normative: true
source_sections: [36, 38, 39, 70, 71, 103]
last_reviewed: 2026-09-04
---

# Schema 计划索引

## 人类可读字段入口

[数据字段中文名称字典](data-field-dictionary.md)完整列出 `canonical-records.v1` 的根集合、16 类核心记录与共享嵌套字段；它只提供中文阅读/展示名，不改变英文 JSON key、类型、必填条件、enum 或 fingerprint。机器权威仍是 [`canonical-records.v1.schema.json`](../../schemas/json/canonical-records.v1.schema.json)和 [`data_dictionary.yaml`](../../schemas/data_dictionary.yaml)。

[API 接口开发清单](api-development-checklist.md)把当前 29 个 OpenAPI operation 映射到本索引中的 workspace、event、replan、schedule 和 export carrier，并明确尚无公开端点的能力。

## TASK-P8-02 additive `2.10.0` release

Global current schema metadata现为`2.10.0`。TASK-P8-02新增三个互不替换的strict JSON document和一个独立错误注册表，全部只形成carrier/validation evidence，不形成HTTP、数据库、Worker或Extension SDK实现。

| Document | Schema / stable identity | Compatibility and owner boundary |
|---|---|---|
| CanonicalIngressRequest v1 | [`canonical-ingress-request.schema.json`](../../schemas/json/canonical-ingress-request.schema.json) / `urn:plantnexus:aps:schema:canonical-ingress-request:v1` | exact `CREATE_PLANNING_RUN` + embedded Import v2；client Extension selection不可表示；consumer属P8-03/07 |
| CanonicalIngressResult v1 | [`canonical-ingress-result.schema.json`](../../schemas/json/canonical-ingress-result.schema.json) / `urn:plantnexus:aps:schema:canonical-ingress-result:v1` | accepted/rejected discriminated result；Runtime/Extension set仅为server-owned reference；行为属P8-03～07 |
| PlanningRun v1 | [`planning-run.schema.json`](../../schemas/json/planning-run.schema.json) / `urn:plantnexus:aps:schema:planning-run:v1` | 对齐`state-machines.v1`的16 states/31 pairs、terminal/actions与lineage；orchestration属P8-04/05 |
| Headless error registry v1 | [`headless-error-code-registry.v1.yaml`](../../schemas/rules/headless-error-code-registry.v1.yaml) / `HEADLESS_RUNTIME` | exact category/code/stage/retryability/action；HTTP mapping属P8-07，product registry v2不变 |

五份positive sample固定canonical request、accepted/rejected result以及CREATED/COMPLETED Run revision；十份negative vector固定unknown/version/type、plane/scope、authority、reference、idempotency、fingerprint和state-pair拒绝。样例均为明确synthetic shape，`0.0.0-p8-contract-sample`不代表Runtime/SDK/Kit release。启动98份schema目录artifact中只有current data dictionary受控更新，其余97份摘要保持`sha256:3c5ff508ec857f010c9f1211623cbceb44ec9ab2dcf45424566a921aa9a7f3dd`。

## TASK-P6-02 additive `2.9.0` release

Global current schema metadata现为`2.9.0`。TASK-P6-02只增加DurationFeatureRecord v1、DurationModelManifest v1、DurationEvaluationReport v1与DurationPrediction v1，以及5份正例和5份定点negative descriptor；每份carrier均为strict/no-default/self-offline-ref、`SIMULATION`/`production_binding=false`和content-derived identity。对应人类语义见[Duration Prediction Machine Contract v1](duration-prediction-machine-contract.md)。

| Document | Schema / stable URN | Compatibility and owner boundary |
|---|---|---|
| DurationFeatureRecord v1 | [`duration-feature-record.schema.json`](../../schemas/json/duration-feature-record.schema.json) / `urn:plantnexus:aps:schema:duration-feature-record:v1` | 新as-of evidence envelope；实际dataset/feature pipeline属P6-03 |
| DurationModelManifest v1 | [`duration-model-manifest.schema.json`](../../schemas/json/duration-model-manifest.schema.json) / `urn:plantnexus:aps:schema:duration-model-manifest:v1` | 新immutable lineage carrier、无状态机；训练/模型属P6-04 |
| DurationEvaluationReport v1 | [`duration-evaluation-report.schema.json`](../../schemas/json/duration-evaluation-report.schema.json) / `urn:plantnexus:aps:schema:duration-evaluation-report:v1` | measurements only、Gate=`NOT_EVALUATED_BY_P6_02`；评价/threshold属P6-05 |
| DurationPrediction v1 | [`duration-prediction.schema.json`](../../schemas/json/duration-prediction.schema.json) / `urn:plantnexus:aps:schema:duration-prediction:v1` | advisory quantiles/confidence + authoritative standard fallback；runtime/Planning ingress属P6-06/07 |

70份P0～P5 Schema/sample以POSIX path+LF manifest `sha256:ada3e2a0498bb5b42ef81aba01693a949cd41deac229ebad8ea6f9334e901c64`逐字冻结；`uv.lock`、5份migration、state pair和runtime owner不变。`p6-duration-contract-report.v1`要求10/10、20个schema rejection、7个semantic/lineage rejection、5个tamper rejection和`issues=[]`。Contract形成不表示dataset/model/evaluation Gate/runtime/Planning或Production authority形成。

## TASK-P4-03 first durable consumer

Schema set继续为`2.8.0`且九份P4 Schema/sample及58份历史artifact字节不变。Migration `0005_replan_event_persistence`首次消费ExecutionEvent v1与ReplanRequest v1 exact carriers；ChangeReport v1只以version/id/fingerprint reference进入terminal result记录，完整document repository仍属后继。由于durable consumer已形成，P4-02 additive files不再允许整体删除式rollback；未来合同变化必须新版本加显式迁移。

## TASK-P4-02 additive `2.8.0` release

本Task从冻结的set `2.7.0`加法发布九个彼此及历史版本均不可互换的document，全部使用JSON Schema Draft 2020-12、stable URN、`additionalProperties=false`、无`default`、offline `$ref`、exact version与canonical fingerprint。九份匹配sample均明确`data_plane=SIMULATION`/`production_binding=false`；58份P0～P3 Schema/sample按清单摘要`sha256:523ab38a466aa76c97ee39cfa52b7b1d43c77ba4dd622c3d27c409ee9af7242e`逐字冻结。

| Document | Schema / stable URN | Compatibility and owner boundary |
|---|---|---|
| ExecutionEvent v1 | [`execution-event.schema.json`](../../schemas/json/execution-event.schema.json) / `urn:plantnexus:aps:schema:execution-event:v1` | 新carrier；authority/source position/canonical identity；ingress由P4-04 |
| PlanningPolicy v2 | [`planning-policy.v2.schema.json`](../../schemas/json/planning-policy.v2.schema.json) / `urn:plantnexus:aps:schema:planning-policy:v2` | v1不可互换；freeze与OBJ-001→002→003；行为由P4-05～07 |
| ReplanRequest v1 | [`replan-request.schema.json`](../../schemas/json/replan-request.schema.json) / `urn:plantnexus:aps:schema:replan-request:v1` | immutable carrier、无状态机；P4-03 durable persistence已形成，应用仍由P4-08 |
| SolverReport v2 | [`solver-report.v2.schema.json`](../../schemas/json/solver-report.v2.schema.json) / `urn:plantnexus:aps:schema:solver-report:v2` | v1不可互换；三阶段与诚实status；求解由P4-07 |
| ChangeReport v1 | [`change-report.schema.json`](../../schemas/json/change-report.schema.json) / `urn:plantnexus:aps:schema:change-report:v1` | 新完整operation-universe carrier；生成由P4-06/08 |
| ScheduleVersion v2 | [`schedule-version.v2.schema.json`](../../schemas/json/schedule-version.v2.schema.json) / `urn:plantnexus:aps:schema:schedule-version:v2` | v1不可互换；沿用既有state pairs；应用由P4-08 |
| ExecutionSimulationManifest v1 | [`execution-simulation-manifest.schema.json`](../../schemas/json/execution-simulation-manifest.schema.json) / `urn:plantnexus:aps:schema:execution-simulation-manifest:v1` | 新无状态carrier；Simulator由P4-09 |
| ExportManifest v3 | [`export-manifest.v3.schema.json`](../../schemas/json/export-manifest.v3.schema.json) / `urn:plantnexus:aps:schema:export-manifest:v3` | v2不可互换；internal Simulation P4 lineage；消费由P4-11 |
| ExportJob v3 | [`export-job.v3.schema.json`](../../schemas/json/export-job.v3.schema.json) / `urn:plantnexus:aps:schema:export-job:v3` | v2不可互换；沿用既有五state/六pair；消费由P4-11 |

`p4-machine-contract-report.v1`离线验证9/9 Schema与9/9 sample、35个Schema rejection和7个semantic rejection。该release无migration、dependency或runtime consumer；rollback在无consumer时可移除additive files并恢复metadata，一旦P4-03+消费则只能发布后继版本与显式迁移。

## TASK-P4-01 schema decision handoff

ADR-0013～0015现已accepted；TASK-P4-02的启动输入明确为ExecutionEvent、ReplanRequest、ChangeReport及必要Execution Simulator/freeze/objective references的独立additive set release。它必须逐项分配stable URN/document version/set version，使用strict/no-default/offline refs，固定canonical projection/fingerprint、positive/negative/non-interchangeable samples、P2/P3 byte preservation及rollback。

当前schema set仍为`2.7.0`，具体新version/文件/URN仍由TASK-P4-02在独立授权后分配。本Task没有创建或修改任何`schemas/**`文件、sample、data dictionary或consumer，不能从accepted ADR推断机器合同已形成。

## TASK-P3-17 audit conclusion

独立Audit确认schema set `2.7.0`、P2 retained bytes、P3 `2.6.0` workspace carriers、P3 export v2 carriers、samples、strict/offline refs与canonical fingerprints全部回归PASS；本Task没有Schema新增、删除、版本或字节变化。

当前 schema set 为additive `2.10.0`。`CONTRACT_V1/V2/V3`表示机器可验证的合同已形成，不表示canonical ingress、PlanningRun、ScheduleVersion/ExportJob状态持久化、审批、发布或Production业务动作已完成。此前所有set artifact均保留，未被原地覆盖。

| Schema | 目标路径 | 首个 Task | 状态 |
|---|---|---|---|
| Canonical ingress request v1 | [`/schemas/json/canonical-ingress-request.schema.json`](../../schemas/json/canonical-ingress-request.schema.json) | TASK-P8-02 | CONTRACT_V1；canonical-only request/authority/idempotency carrier；API/persistence NOT_FORMED |
| Canonical ingress result v1 | [`/schemas/json/canonical-ingress-result.schema.json`](../../schemas/json/canonical-ingress-result.schema.json) | TASK-P8-02 | CONTRACT_V1；accepted/rejected + server resolution carrier；behavior NOT_FORMED |
| PlanningRun v1 | [`/schemas/json/planning-run.schema.json`](../../schemas/json/planning-run.schema.json) | TASK-P8-02 | CONTRACT_V1；existing lifecycle/evidence projection；orchestration/worker NOT_FORMED |
| Headless error registry v1 | [`/schemas/rules/headless-error-code-registry.v1.yaml`](../../schemas/rules/headless-error-code-registry.v1.yaml) | TASK-P8-02 | RULE_V1；HEADLESS_RUNTIME tuple形成；HTTP mapping NOT_FORMED |
| Duration feature record v1 | [`/schemas/json/duration-feature-record.schema.json`](../../schemas/json/duration-feature-record.schema.json) | TASK-P6-02 | CONTRACT_V1；Simulation evidence only；dataset pipeline NOT_FORMED |
| Duration model manifest v1 | [`/schemas/json/duration-model-manifest.schema.json`](../../schemas/json/duration-model-manifest.schema.json) | TASK-P6-02 | CONTRACT_V1；immutable lineage/no state；model NOT_FORMED |
| Duration evaluation report v1 | [`/schemas/json/duration-evaluation-report.schema.json`](../../schemas/json/duration-evaluation-report.schema.json) | TASK-P6-02 | CONTRACT_V1；measurements only；Gate NOT_EVALUATED |
| Duration prediction v1 | [`/schemas/json/duration-prediction.schema.json`](../../schemas/json/duration-prediction.schema.json) | TASK-P6-02 | CONTRACT_V1；advisory candidate + exact standard fallback；runtime NOT_FORMED |
| Canonical records | [`/schemas/json/canonical-records.v1.schema.json`](../../schemas/json/canonical-records.v1.schema.json) | TASK-P1-02 | CONTRACT_V1；Normalization/Data Validation/Expansion formed |
| Canonical import v1 | [`/schemas/json/import-package.schema.json`](../../schemas/json/import-package.schema.json) | TASK-P0-03 skeleton | SKELETON_V1 retained |
| Canonical import v2 | [`/schemas/json/import-package.v2.schema.json`](../../schemas/json/import-package.v2.schema.json) | TASK-P1-02 | CONTRACT_V2；Reference/Synthetic common-ingress pipeline formed；Production binding PLANNED |
| Unit conversion registry | [`/schemas/rules/unit-conversion-registry.v1.yaml`](../../schemas/rules/unit-conversion-registry.v1.yaml) | TASK-P1-05 | RULE_V1；explicit integer duration conversion formed，Production default forbidden |
| PlanningSnapshot v1 | [`/schemas/json/planning-snapshot.schema.json`](../../schemas/json/planning-snapshot.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| PlanningSnapshot v2 | [`/schemas/json/planning-snapshot.v2.schema.json`](../../schemas/json/planning-snapshot.v2.schema.json) | TASK-P1-02 | CONTRACT_V2；builder/hash/insert-only persistence formed |
| PlanningProblem v1 | [`/schemas/json/planning-problem.schema.json`](../../schemas/json/planning-problem.schema.json) | TASK-P0-03；TASK-P1-09 | CONTRACT_V1；default builder/hash/fixed replay preserved，Solver PLANNED |
| PlanningProblem v2 | [`/schemas/json/planning-problem.v2.schema.json`](../../schemas/json/planning-problem.v2.schema.json) | TASK-P2-01 | CONTRACT_V2；opt-in builder/hash、due/priority/resource/lock/historical-anchor input formed，Solver/Validator PLANNED |
| PlanningPolicy v1 | [`/schemas/json/planning-policy.schema.json`](../../schemas/json/planning-policy.schema.json) | TASK-P2-02 | CONTRACT_V1；C-001～C-011 + OBJ-001 + explicit policy provenance formed；Production defaults PLANNED |
| SolveLimits v1 | [`/schemas/json/solve-limits.schema.json`](../../schemas/json/solve-limits.schema.json) | TASK-P2-02 | CONTRACT_V1；explicit wall time/workers/seed + provenance formed；Production limits/SLA PLANNED |
| PlanningSolution v1 | [`/schemas/json/planning-solution.schema.json`](../../schemas/json/planning-solution.schema.json) | TASK-P2-02 | CONTRACT_V1；status/assignment/tick/UTC/objective/fingerprint carrier formed；Solver/Validator PLANNED |
| SolverReport v1 | [`/schemas/json/solver-report.schema.json`](../../schemas/json/solver-report.schema.json) | TASK-P2-02 | CONTRACT_V1；status/parameters/timing/model/memory/provenance carrier formed；real run/benchmark PLANNED |
| KPI v1 | [`/schemas/json/kpi.schema.json`](../../schemas/json/kpi.schema.json) | TASK-P0-03 skeleton | SKELETON_V1 retained；不原地升级 |
| KPI v2 | [`/schemas/json/kpi.v2.schema.json`](../../schemas/json/kpi.v2.schema.json) | TASK-P2-11 | CONTRACT_V2；validated synthetic run calculator/lineage formed，Production口径PLANNED |
| Export manifest v1 | [`/schemas/json/export-manifest.schema.json`](../../schemas/json/export-manifest.schema.json) | TASK-P2-11 | CONTRACT_V1；9-payload internal non-publishable profile formed，P3 state/publish PLANNED |
| ScheduleVersion v1 | [`/schemas/json/schedule-version.schema.json`](../../schemas/json/schedule-version.schema.json) | TASK-P3-02 | CONTRACT_V1；immutable content/lineage/fingerprint/state evidence carrier formed；persistence/transition PLANNED |
| Workspace query v1 | [`/schemas/json/workspace-query.schema.json`](../../schemas/json/workspace-query.schema.json) | TASK-P3-02 | CONTRACT_V1；strict request/result、stable sort/page/freshness/allowed-actions carrier formed；read service PLANNED |
| Workspace command v1 | [`/schemas/json/workspace-command.schema.json`](../../schemas/json/workspace-command.schema.json) | TASK-P3-02 | CONTRACT_V1；strict discriminator/CAS/reason/target/idempotency carrier formed；authorization/command behavior PLANNED |
| ScheduleVersion comparison v1 | [`/schemas/json/schedule-version-comparison.schema.json`](../../schemas/json/schedule-version-comparison.schema.json) | TASK-P3-02 | CONTRACT_V1；immutable version read comparison formed；service/UI PLANNED |
| AuditEvent v1 | [`/schemas/json/audit-event.schema.json`](../../schemas/json/audit-event.schema.json) | TASK-P3-02 | CONTRACT_V1；append-only/no-secret/error-namespace carrier formed；durable append PLANNED |
| PublicationResult v1 | [`/schemas/json/publication-result.schema.json`](../../schemas/json/publication-result.schema.json) | TASK-P3-02 | CONTRACT_V1；Simulation-internal successful-result carrier formed；publication behavior PLANNED |
| ExportJob v1 | [`/schemas/json/export-job.schema.json`](../../schemas/json/export-job.schema.json) | TASK-P3-02 | CONTRACT_V1；published-version/internal-target lifecycle carrier formed；persistence/worker/package behavior PLANNED |
| ValidationReport v1 | [`/schemas/json/validation-report.schema.json`](../../schemas/json/validation-report.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| ValidationReport v2 | [`/schemas/json/validation-report.v2.schema.json`](../../schemas/json/validation-report.v2.schema.json) | TASK-P0-04 rules；TASK-P0-07 mutations | SKELETON_V2 + C-ID shape formed；schedule evaluation PLANNED |
| Error v1 | [`/schemas/json/error.schema.json`](../../schemas/json/error.schema.json) | TASK-P0-03 | SKELETON_V1 retained |
| Error v2 | [`/schemas/json/error.v2.schema.json`](../../schemas/json/error.v2.schema.json) | TASK-P0-04 | SKELETON_V2 + code/category registry formed |
| Error v3 | [`/schemas/json/error.v3.schema.json`](../../schemas/json/error.v3.schema.json) | TASK-P1-06 | CONTRACT_V3；rich deterministic Data Validation detail formed |
| ImportQualityReport v1 | [`/schemas/json/import-quality-report.schema.json`](../../schemas/json/import-quality-report.schema.json) | TASK-P1-06 | CONTRACT_V1 + deterministic evaluator/sample + Snapshot handoff formed |
| StateTransition | [`/schemas/json/state-transition.schema.json`](../../schemas/json/state-transition.schema.json) | TASK-P0-04 | SKELETON_V1；machine/state names formed，business persistence PLANNED |
| Constraint Rule Sheet | [`/schemas/rules/constraint-rule-sheet.v1.yaml`](../../schemas/rules/constraint-rule-sheet.v1.yaml) | TASK-P0-04 | C-001～C-018 machine contract + fixture-local evaluator/mutations formed；P2 integration PLANNED |
| Capability/Error/State registries | [`/schemas/rules/`](../../schemas/rules/) | TASK-P0-04；TASK-P1-06 error v2 | versioned registry contracts formed；error v2 additive，capability implementation claims remain false |
| FactoryProfile | [`/schemas/scenario/factory-profile.schema.json`](../../schemas/scenario/factory-profile.schema.json) | TASK-P0-05 | SKELETON_V1；versioned P1 synthetic generator asset formed；Production distribution PLANNED |
| ScenarioSpec | [`/schemas/scenario/scenario-spec.schema.json`](../../schemas/scenario/scenario-spec.schema.json) | TASK-P0-05 | SKELETON_V1；P0 fixture与`SIM-P1-INGRESS-001` formed；broader Scenario library PLANNED |
| Scenario manifest | [`/schemas/scenario/scenario-manifest.schema.json`](../../schemas/scenario/scenario-manifest.schema.json) | TASK-P0-05 | SKELETON_V1 + empty Import replay formed；run/export audit PLANNED |

[`/schemas/data_dictionary.yaml`](../../schemas/data_dictionary.yaml) 登记 schema set、canonical collections、版本/provenance、未知字段/默认值策略、兼容边界和 PROD_OPEN/SIM_ASSUMPTION 关联。Set-level `2.6.0`在P2 `2.5.0`之后新增七份P3 carrier；Import/Snapshot/quality/Problem/PlanningSolution/SolverReport/KPI/ExportManifest均保持各自原set版本且34份历史artifact hash不变。P3 samples只证明合同shape/replay；没有业务状态或Production证据。

TASK-P2-02新增四份Schema/sample并将global set提升到`2.4.0`；Problem v1/v2 Schema/sample、builders与fixed replay不改，Import/Snapshot/quality/unit document版本也不改。Planning machine类型、pure cross-document checks与status mapping已形成；Solver backend、C-ID、ScheduleValidator、Benchmark和Production authority继续`PLANNED`。

TASK-P2-11新增两份strict Draft 2020-12 Schema和两份synthetic sample，将global set additive提升到`2.5.0`。KPI v1及全部既有Schema/sample bytes由fingerprint regression保护；没有migration或dependency变化。`export-manifest.v1`只描述P2 internal profile，不是ScheduleVersion、ExportJob或publish合同。

## TASK-P3-02 additive schema release

TASK-P3-02作为P3首个additive Schema release owner，已按TASK-P3-01冻结的七组文件名/URN/document version发布`2.6.0`。全部对象`additionalProperties=false`、无`default`、显式plane/environment/provenance并离线解析跨URN `$ref`；24个shape/version/plane/non-interchangeability负例与6个canonical fingerprint drift负例fail closed。P2 bytes/URN、state pair与global error registry没有改写；implementation artifact `9506913562`已精确复验并支持本closure把Task标为`done`。

## TASK-P3-05 consumer review

本Task只生成并验证既有`workspace-query.v1` REQUEST/RESULT和`schedule-version-comparison.v1`文档；`schema_set_version=2.6.0`、canonical projection和offline `$ref`均由contract tests复验。没有新增、修改或重新发布Schema/sample/URN；完整payload不被私自塞入strict carrier，P4 ChangeReport也未借comparison名义出现。

TASK-P3-09新增`urn:plantnexus:aps:schema:export-manifest:v2`与`urn:plantnexus:aps:schema:export-job:v2`，current set为additive `2.7.0`。Manifest固定12个payload、hash/bytes/CSV rows/XLSX sheets、PUBLISHED/publication/job/audit/P2 lineage和external/P4/Production边界；Job v2只将成功artifact限定为manifest v2，五state/六pair不变。2 Schema/2 sample offline validate，四份v1 artifact继续hash冻结。
