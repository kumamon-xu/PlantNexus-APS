---
doc_id: DOC-CONTRACT-008
title: Schema 计划索引
status: living
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [36, 38, 39, 70, 71, 103]
last_reviewed: 2026-08-27
---

# Schema 计划索引

## P4 planned schema allocation

TASK-P4-02预期在TASK-P4-01三份ADR全部accepted后，以独立additive set release定义ExecutionEvent、ReplanRequest、ChangeReport及Execution Simulator carrier，并逐项登记URN、compatibility、fingerprint、sample、negative interchange与rollback。当前TASK-P4-00不创建或修改任何`schemas/**`文件；具体version、字段与set release号仍为`NOT_ASSIGNED`，不得从本规划推断机器合同已经形成。

## TASK-P3-17 audit conclusion

独立Audit确认schema set `2.7.0`、P2 retained bytes、P3 `2.6.0` workspace carriers、P3 export v2 carriers、samples、strict/offline refs与canonical fingerprints全部回归PASS；本Task没有Schema新增、删除、版本或字节变化。

当前 schema set 为additive `2.7.0`。`CONTRACT_V1/V2/V3`表示机器可验证的合同已形成，不表示ScheduleVersion/ExportJob状态持久化、审批、发布或Production业务动作已完成。此前所有set artifact均保留，未被原地覆盖。

| Schema | 目标路径 | 首个 Task | 状态 |
|---|---|---|---|
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
