---
doc_id: DOC-DOM-006
title: 错误与求解状态模型
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [29, 32, 34, 60, 65, 91, 92]
last_reviewed: 2026-08-27
---

# 错误与求解状态模型

## TASK-P3-16 localization contract

双语展示不得改变七类product error、`error-code-registry.v2`的23个code、Workspace module-local reason或HTTP mapping。Frontend以namespace与code/reason查`official-zh-cn-terminology.v1`，中文模式仍同时显示原始code/reason和correlation ID；未知值显示raw并fail visibly。后端英文安全message仅作诊断fallback，禁止据其文本判断业务或猜测中文；自由文本、ID、actor reference、fingerprint与raw UTC不机器翻译。

TASK-P3-16已实现typed product/workspace error adapters与未知raw fallback；词典/组件/browser及zero-wire-drift检查已由exact implementation provider复验，未改变registry、HTTP mapping或后端message。

## TASK-P3-14 exact rejection Gate

聚合报告固定四个exit rejection：DRAFT/REJECTED publish为`DATA_ERROR/INVALID_STATE_TRANSITION`，PUBLISHED mutation为`WORKSPACE_CONTROL/STATE_CONFLICT`，unpublished export为`WORKSPACE_CONTROL/STALE_SOURCE`。stage/category/code必须逐字匹配且无副作用；Gate不改全局错误注册表或既有业务返回。

## TASK-P3-13 visible failure boundary

Action UI保持401/403/409/422为已知失败并逐字显示sanitized message/correlation；network与500被标记为unknown outcome，禁止假定成功，必须先refresh authority后以original key retry。Download的missing、state conflict、tamper/partial/mixed lineage与unexpected I/O继续经既有error adapter映射，不返回path、credential、stack或raw exception。Frontend contract/header/hash mismatch本地收敛为contract error且不保存文件。

本Task不新增全局error code/category，也不改变domain failure reason；P4 execution/replan error与Production incident taxonomy未形成。

## 产品错误分类

| Category | 含义 | 示例 |
|---|---|---|
| DATA_ERROR | 输入格式、引用、单位或业务数据无效 | route cycle、missing resource |
| UNSUPPORTED_CAPABILITY | 输入要求当前明确不支持的能力 | sequence-dependent setup |
| MODEL_INVALID | 问题/模型合同或建模系统缺陷 | invalid CP-SAT model |
| INFEASIBLE | 当前快照与模型被证明无可行解 | 互相冲突的 HARD_LOCK |
| NO_SOLUTION_WITHIN_LIMIT | 时间内没有可认证结论 | Solver status UNKNOWN |
| VALIDATION_FAILED | Solver 候选解未通过独立 Validator | overlap、wrong duration |
| SYSTEM_ERROR | 非业务性系统故障 | DB/worker failure |

禁止将所有失败映射为 HTTP 500。

## Solver 状态映射

| Solver Status | Product Meaning |
|---|---|
| OPTIMAL | 已证明达到当前模型的最优标准 |
| FEASIBLE | 当前最好可行方案，未证明最优 |
| INFEASIBLE | 已证明当前模型无解 |
| UNKNOWN | `NO_SOLUTION_WITHIN_LIMIT`，不是 INFEASIBLE |
| MODEL_INVALID | 模型或系统缺陷 |
| CANCELLED | 用户或系统取消 |
| FAILED | 系统异常 |

## 无解诊断顺序

```text
Precheck
→ Pure Feasibility Solve
→ Assumption Groups
→ Conflict Explanation
```

除非算法证明，Assumption conflict subset 不得称为 minimal conflict set。诊断不得通过删除硬约束或修改输入事实获得“可行”。

## P0 machine contracts

TASK-P0-03 的 [`error.v1`](../../schemas/json/error.schema.json) 与 [`validation-report.v1`](../../schemas/json/validation-report.schema.json) 原 envelope 保持不变。TASK-P0-04 新增：

- [`error.v2`](../../schemas/json/error.v2.schema.json)：只接受 [`error-code-registry.v1`](../../schemas/rules/error-code-registry.v1.yaml) 中的 19 个 code，并验证每个 code 唯一映射到上述七类；
- [`validation-report.v2`](../../schemas/json/validation-report.v2.schema.json)：增加 `hard_violation_count`，PASS 必须为 0/空 violations，FAIL 至少 1；violation 只接受 C-001～C-011、severity=`HARD` 与 entity/observed/expected/message；
- `error.v1`/`validation-report.v1` 与 v2 不互换，consumer 必须显式选择版本。

关键 code family：

| Code | Category | 边界 |
|---|---|---|
| `UNSUPPORTED_CAPABILITY` | UNSUPPORTED_CAPABILITY | 已登记但当前禁止/延迟的 capability；不得静默忽略 |
| `INVALID_CAPABILITY_DECLARATION` / `DUPLICATE_CAPABILITY` | DATA_ERROR | 未登记或重复 capability declaration |
| `INVALID_STATE_TRANSITION` | DATA_ERROR | 不在 versioned transition table 的 pair；不是第八种顶层 category |
| `SCHEDULE_VALIDATION_FAILED` | VALIDATION_FAILED | C-001～C-011 violation envelope；不得只返回 false |
| `MODEL_INVALID` / `INFEASIBLE` / `NO_SOLUTION_WITHIN_LIMIT` | 同名 category | 三种结论保持独立，UNKNOWN 只映射 limit，不映射 infeasible |

`ContractViolation` 现使用同一 code registry 并暴露确定的 category，但仍只是 P0 数据合同 precheck，不是 HTTP mapping。

TEST-ERROR-MAPPING-001 已验证 YAML、纯枚举和 error.v2 code/category 一致。TASK-P0-07 的 fixture-local evaluator 对 FAIL report 逐 violation 映射 `error.v2`：category=`VALIDATION_FAILED`、code=`SCHEDULE_VALIDATION_FAILED`，detail 保留首要 entity、完整 entity IDs、constraint ID、observed value、expected contract 和 candidate source location；PASS 不生成 Error。13 个 mutation 的 exact Error 与 ValidationReport 均经现有 JSON Schema 验证。

该映射只覆盖 `SIM-MINIMAL-001-MUTATIONS@1.0.0` 的 P0 correctness 边界。HTTP status/API payload、状态持久化、正式 PlanningProblem/candidate 错误入口以及 Solver status/diagnostics 集成仍由后续 API/P2 Task 建立。

## TASK-P0-08 engineering health/error boundary

health-only API 不发布产品 `error.v2`：liveness 永远只判断 process；readiness 对 database/redis probe failure 返回 HTTP 503 与 `DATABASE_UNAVAILABLE`/`REDIS_UNAVAILABLE`，未知 probe 使用 `DEPENDENCY_UNAVAILABLE`，不返回 driver exception、endpoint 或 Secret。配置无效在创建 app/client 前以 sanitized `ConfigurationError` fail closed。

Job primitives 以 `JobTransitionError`、`LeaseOwnershipError`、`LeaseExpiredError`、`IdempotencyConflictError` 区分工程控制流；FAILED record 只保存 stable `failure_code`，不保存/回显原始 Secret-bearing exception。这些名称不是 `error-code-registry.v1` 新 code，也不改变七类产品 Error 或 Solver mapping。产品 HTTP mapping、ExportJob persistence 和 SYSTEM_ERROR audit 继续 `PLANNED`。

## TASK-P1-02 canonical precheck boundary

`CanonicalContractError`复用既有`ProductErrorCode`表达`DUPLICATE_ID`、`INVALID_REFERENCE`、`INVALID_TIME`、`INVALID_TIME_RANGE`、`INVALID_DURATION`、`INVALID_LAG_RANGE`、`INVALID_ENTITY_COUNT`、`MISSING_RUNNING_FACT`和synthetic isolation；没有新增或重解释error registry code。JSON Schema先拒绝missing/unknown/type/conditional shape，pure precheck再拒绝跨记录reference/unit/source/count/copy不一致。

本Task不是TASK-P1-06的deterministic multi-error DataValidation，也未分配`ROUTE_CYCLE`、`MISSING_RESOURCE`、`UNIT_CONVERSION_ERROR`、`MISSING_DURATION`新code/report。HTTP mapping、row/source-location quality details和完整ImportQualityReport仍为`PLANNED`；不能把单一exception precheck写成P1 DataValidation Gate PASS。

## TASK-P1-03 staging error boundary

Raw Staging分配6个module-local稳定control-flow code：`INVALID_STAGING_METADATA`、`INVALID_CONTENT_DIGEST`、`DUPLICATE_ROW_IDENTITY`、`IDEMPOTENCY_CONFLICT`、`DATA_PLANE_MISMATCH`、`STAGING_TRANSACTION_FAILED`。它们由`ImportStagingError`携带，错误文本只描述字段/合同，不包含raw payload、source observed value、driver exception、endpoint或Secret；transaction/query异常统一从原异常断链后返回sanitized code。

这些code不加入或重解释P0的19项`ProductErrorCode` registry，不是HTTP error schema，也不替代TASK-P1-06的multi-error ImportQualityReport。DB持久化失败属于staging system control，source/digest/row/plane conflict属于import precondition；未来API mapping必须另行版本化并保持七类产品错误语义。

## TASK-P1-04 adapter error boundary

`InputAdapterError`把文件入口拒绝稳定归类为`DATA_ERROR`，并携带module-local `AdapterErrorCode`、sanitized `source_location`、`expected_contract`和message。code family区分adapter ID/version、unsafe/missing path、unsupported/oversize file、UTF-8/CSV/workbook/archive、sheet/row/column/header/cell/record以及formula/macro/external-link拒绝；错误文本不包含原始cell、payload、绝对路径或parser exception。

这些module-local code不加入P0的19项产品error registry，也不是HTTP schema或ImportQualityReport。单文件遇到首个结构错误即fail closed；TASK-P1-06仍负责canonical data的deterministic multi-error报告及route/resource/unit/duration exact product code。

## TASK-P1-05 normalization error boundary

`NormalizationError`固定`category=DATA_ERROR`，携带module-local code、sanitized source location、field、expected contract和message。它区分raw JSON/profile/version/source/data-plane/authority问题，以及`INVALID_TIMEZONE`、`MISSING_DURATION`、`UNIT_CONVERSION_ERROR`、`DUPLICATE_CANONICAL_ID`；错误文本不回显payload value或parser exception。

本层首错fail closed并用于控制流，不改写既有19项产品error registry或error.v2。TASK-P1-06仍须把unit/missing-duration等结果映射到确定性ImportQualityReport并同时报告DAG/reference/capability问题；HTTP/status映射仍未实现。

## TASK-P1-06 Error v3 and ImportQualityReport

`error-code-registry.v2`是对v1的additive successor：七类category和既有19项code/category映射逐项保留，只增加`ROUTE_CYCLE`、`MISSING_RESOURCE`、`UNIT_CONVERSION_ERROR`、`MISSING_DURATION`四项`DATA_ERROR`。Python以独立`ProductErrorCodeV2`暴露新集合，原`ProductErrorCode`仍为19项，防止旧consumer被静默扩展。

`error.v3`要求每个detail完整携带entity type/ID、field、observed value、expected contract、稳定source location和action；`import-quality-report.v1`收集多个Error、精确校验count/status、稳定排序并用除self ID外的canonical content派生report ID。`UNSUPPORTED_CAPABILITY`仍属于独立category，不能降格为DATA_ERROR或合并成SYSTEM_ERROR。

该报告只属于canonical input gate，不是HTTP contract、PlanningRun persistence、infeasibility proof或`validation-report.v2`。Normalization/Adapter/Staging的module-local首错仍按各自边界存在；Error v1/v2与registry v1逐字保留且不可与v3互换。

## TASK-P1-07 expansion rejection boundary

Expansion继续要求匹配同package且content-derived ID自洽的ImportQualityReport PASS/0；FAIL、错误package/version或错误report ID在展开前拒绝。服务的module-local `OrderExpansionError`区分quality mismatch、missing explicit lot/route/option/duration、fact/lock lineage、derived-ID collision和expansion version mismatch；这些属于单请求边界错误，不修改`error-code-registry.v2`或Error v3 Schema。

`lot_mode=SPLIT_MERGE`固定返回`UNSUPPORTED_CAPABILITY/UNSUPPORTED_SPLIT_MERGE`；其他输入缺失为`DATA_ERROR`，均不改写为INFEASIBLE、VALIDATION_FAILED或SYSTEM_ERROR。该边界不声称HTTP mapping、multi-error aggregation、ScheduleValidator result或Solver diagnosis。

## TASK-P1-10 generator rejection boundary

`SyntheticGeneratorError`固定`category=DATA_ERROR`，以module-local code区分invalid Profile/Scenario、Profile/Scenario mismatch、generator version mismatch、unsupported Profile shape、Normalization rejection、Data Validation rejection和package integrity failure。包装Normalization时只保留稳定code，包装quality FAIL时只给出error count，不回显source payload；任何拒绝都不得改写为INFEASIBLE、Solver status或Production error response。

Production target继续由Scenario context返回`SYNTHETIC_REFERENCE_IN_PRODUCTION`，unsupported platform capability继续由既有capability contract拒绝。Generator错误不新增`error-code-registry.v2`成员，不替代Error v3/ImportQualityReport，也不声称HTTP/status mapping形成。

## TASK-P1-11 application error propagation

Application层不捕获并改写Normalization、Expansion、Snapshot或Problem的结构化异常。Canonical Data Validation不抛异常，因此`DataQualityGateRejected`只从确定性有序Error v3列表透出首个`category/code`并保留完整quality report；不生成新product code或`SYSTEM_ERROR`。

P1四类Gate实际经同一入口得到`DATA_ERROR/ROUTE_CYCLE`、`DATA_ERROR/MISSING_RESOURCE`、`DATA_ERROR/UNIT_CONVERSION_ERROR`、`DATA_ERROR/MISSING_DURATION`，且每个失败均在所属stage停止下游。它们不是`INFEASIBLE`、Solver status或HTTP mapping。

## TASK-P2-01 PlanningProblem v2 rejection boundary

Problem module继续使用module-local稳定code，不修改`error-code-registry.v2`或Error v3 Schema。v2新增`INVALID_PRIORITY_FACT`、`INVALID_LOCK_FACT`和`INVALID_HISTORICAL_FACT`，均归`DATA_ERROR`；版本/config/snapshot/reference缺口继续使用既有code，canonical shape/semantic/hash tamper归`MODEL_INVALID`或`HASH_MISMATCH`。`UNSUPPORTED_PROBLEM_FACT`仍单独归`UNSUPPORTED_CAPABILITY`。

这些错误全部发生在Backend/Solver之前，不能写成`INFEASIBLE`、`NO_SOLUTION_WITHIN_LIMIT`、ScheduleValidator violation或HTTP状态。CLI machine report失败只输出error type，不回显输入值或内部异常；完整产品错误注册表如需新增必须由独立合同Task升版。

## TASK-P2-02 seven-status machine mapping

PlanningSolution与SolverReport对七种status使用唯一映射：OPTIMAL/FEASIBLE→PlanningRun `SOLVED`且无product error；INFEASIBLE→`INFEASIBLE/INFEASIBLE`；UNKNOWN→`NO_SOLUTION_WITHIN_LIMIT/NO_SOLUTION_WITHIN_LIMIT`；MODEL_INVALID→`MODEL_INVALID/MODEL_INVALID`；CANCELLED→`CANCELLED`且无product error；FAILED→`FAILED/SYSTEM_ERROR`。只有前两者允许candidate，FEASIBLE不得伪装成OPTIMAL，UNKNOWN不得伪装成INFEASIBLE。

Machine contract自身的shape/version/reference/time/metric/provenance拒绝使用module-local`PlanningContractReason`并稳定归`MODEL_INVALID`，不扩展`error-code-registry.v2`。该pure rejection不是HTTP mapping、Solver诊断或ScheduleValidator violation；FAILED与CANCELLED的持久化/audit动作仍未实现。

## TASK-P2-04 formal validation failure

Formal candidate的schedule违反继续使用既有`error.v2`映射：`VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED`，每个detail保存首个entity、`candidate.assignments`字段、C-ID/entity/value、expected rule与`planning_solution.assignments`来源。PASS不生成Error；多条violation按稳定report顺序产生等量details。

权威PlanningProblem v2 shape/hash错误属于Validator输入合同缺陷，由`ProblemScheduleValidationInputError`在C-ID执行前fail closed，不改写成INFEASIBLE或candidate validation failure。Candidate reference/assignment结构问题可在现有C-001/C-003/C-007/C-008/C-010/C-011语义内稳定聚合；本Task不新增error code/registry/schema/HTTP mapping或Solver diagnostics。

## TASK-P2-08 status/error review

Strategy precheck对Production/未批准Simulation Policy或priority source显式抛出`DeliveryPolicyError`，objective demand映射/priority/int64不可表达显式抛出`DeliveryObjectiveError`，不得进入INFEASIBLE。Search无candidate且无证明保持UNKNOWN并映射`NO_SOLUTION_WITHIN_LIMIT`；只有complete hard model证明才为INFEASIBLE；有candidate未证明最优为FEASIBLE。

Independent Validator拒绝optimized candidate时映射FAILED/SYSTEM_ERROR语义、丢弃assignments与objective candidate，并保留sanitized diagnostic；不新增error registry code、Schema、HTTP/API mapping或诊断子系统。Production authority未批准不是可重试Solver结论。

## TASK-P2-13 Gate rejection behavior

Gate新增的四项evidence只调用既有public contracts：`SECONDARY_CAPACITY`稳定为`UNSUPPORTED_CAPABILITY`并在Planning前拒绝；空/invalid PlanningProblem稳定为`MODEL_INVALID/MODEL_INVALID`并在Solver前拒绝；`max_wall_time_seconds=0`稳定为Planning contract `MODEL_INVALID/INVALID_METRIC`；Solver `UNKNOWN`稳定映射无candidate的`NO_SOLUTION_WITHIN_LIMIT`且明确不是INFEASIBLE。

任一correctness/benchmark/Validator/export/rejection/semantic-hash stage异常都会生成`p2-vertical-slice-report.v1` `FAIL`、blocking gap与非零exit；成功阶段不能抵消失败，也不在Gate中修复。该编排不增加error-code registry、Schema、HTTP/status/persistence mapping；P2 Exit decision始终`NOT_PERFORMED`。

Required run `32465737712`精确复验四类rejection与FAIL/nonzero contract测试，artifact内Gate仍为0 blocking gaps且Exit=`NOT_PERFORMED`。没有新增error code或Production mapping。

## P3 error allocation

P3-01须先固定`INVALID_STATE_TRANSITION`、`AUTHORIZATION_DENIED`、`IDEMPOTENCY_CONFLICT`、`VALIDATION_FAILED`与`EXPORT_FAILED`的责任层和HTTP/UI映射；P3-02只能形成carrier，P3-04～10形成行为，P3-13验证用户可见负向路径。UNKNOWN仍不得写成INFEASIBLE，未授权Production必须fail closed；本次不新增error code或实现映射。

## TASK-P3-01 error contract baseline

P3先行合同现固定计划映射：request/reference/data-plane `DATA_ERROR`与client-supplied `MODEL_INVALID`为HTTP 422；fresh Validator `VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED`为422；既有`INVALID_STATE_TRANSITION`为409；module-local `AUTHORIZATION_DENIED`为403、`IDEMPOTENCY_CONFLICT`为409、`EXPORT_FAILED`以`SYSTEM_ERROR` carrier为500。已持久化权威artifact损坏或unknown exception统一sanitized 500；not-found可用`INVALID_REFERENCE`/404而不泄漏跨scope资源。

后三个reason尚未加入`error-code-registry.v2`或Error Schema；TASK-P3-02必须在strict workspace carrier中以`workspace-control.v1`和product error显式分namespace，保持七类category兼容，不得把authorization/idempotency强塞进`DATA_ERROR`或改写P2 registry bytes。Export底层system cause可引用sanitized `SYSTEM_ERROR`，但control result仍为独立`EXPORT_FAILED`。所有失败在副作用前拒绝或保持可审计失败Job；UNKNOWN继续是`NO_SOLUTION_WITHIN_LIMIT`且无candidate，绝不映射INFEASIBLE/Validation PASS/可发布Version。HTTP/API/UI行为测试仍为`PLANNED`。
## TASK-P3-02 workspace carrier error boundary

`audit-event.v1`及共享defs显式区分`PRODUCT`与`WORKSPACE_CONTROL`。PRODUCT继续只接受既有七类category；module-local `workspace-control.v1`只接受`AUTHORIZATION_DENIED`、`IDEMPOTENCY_CONFLICT`、`EXPORT_FAILED`，三者未写入且不得冒充`error-code-registry.v2`。`UNKNOWN`的既有product含义继续是`NO_SOLUTION_WITHIN_LIMIT`，没有candidate，不得变成INFEASIBLE或ScheduleVersion。

Schema/纯precheck错误在consumer副作用前拒绝unknown field/version/state、plane/provenance混用、fingerprint/reference drift和raw secret-bearing key。它们不决定HTTP、retry、audit persistence或真实授权；这些行为仍分配给P3-03/06～10。

## TASK-P3-03 persistence error boundary

Repository新增module-local `PersistenceFailure`：`INVALID_DOCUMENT`、`DATA_PLANE_MISMATCH`、`IDENTITY_CONFLICT`、`IDEMPOTENCY_CONFLICT`、`STATE_CONFLICT`、`LEASE_CONFLICT`、`APPEND_ONLY`、`PERSISTENCE_FAILED`。它们统一由`WorkspacePersistenceError`返回field与sanitized message，不暴露SQL、DSN、credential或stack；SQLAlchemy/driver异常不会穿透边界。这些不是global Product Error code，也没有修改`error-code-registry.v2`；P3-10才负责稳定HTTP映射。

Carrier top-level required/unknown、plane/environment/provenance和canonical fingerprint在write前fail closed；CAS/lease/identity冲突不写成功state或audit。事务调用者回滚由测试证明，但真实PostgreSQL故障分类和Production retry policy仍未形成。

## TASK-P3-04 lifecycle error boundary

Application新增module-local sanitized reasons：`INVALID_INPUT`、`PLANNING_RUN_NOT_COMPLETED`、`VALIDATION_FAILED`、`MIXED_LINEAGE`、`DATA_PLANE_MISMATCH`、`IDEMPOTENCY_CONFLICT`、`STATE_CONFLICT`、`PERSISTENCE_FAILED`。P2 reporting错误先按validation/mixed/invalid映射；P3 repository identity/idempotency/state/plane错误再映射为稳定lifecycle reason，SQL/credential/stack不进入message或machine artifact。

这些reason没有加入`error-code-registry.v2`，也不是HTTP status合同。所有输入/Validator/KPI错误发生在事务前；transaction/audit错误回滚本次DRAFT/READY。未来P3-10若公开HTTP mapping，必须消费既有namespace并在合同Task中版本化，不得从本地异常文本推断status。

## TASK-P3-05 read rejection boundary

Read domain使用module-local `INVALID_QUERY`、`SOURCE_MISSING`、`MIXED_LINEAGE`、`DATA_PLANE_MISMATCH`、`STALE_VERSION`、`STALE_CURSOR`与`KPI_MISMATCH`。不存在的schedule query返回strict `found=false`而不是异常，存在但无投影返回`found=true/items=[]`；comparison缺少任一Version则显式`SOURCE_MISSING`。所有message固定且不泄露payload、SQL、credential或stack；P3-10公开HTTP前不得把这些local reason冒充global error registry变更。

## TASK-P3-06 command rejection boundary

Command domain/application使用module-local sanitized reasons：`INVALID_COMMAND`、`UNAUTHORIZED`、`PRODUCTION_AUTHORITY_UNAVAILABLE`、`DATA_PLANE_MISMATCH`、`SOURCE_NOT_FOUND`、`STALE_SOURCE`、`MIXED_LINEAGE`、`INVALID_REFERENCE`、`INVALID_TIME`、`IMMUTABLE_EXECUTION_FACT`、`LOCK_CONFLICT`、`NO_OP`、`VALIDATION_FAILED`、`IDEMPOTENCY_CONFLICT`和`PERSISTENCE_FAILED`。所有失败都不写成功Version/audit；adapter错误只映射stable reason/field/message，不泄露SQL、credential或stack。

这些reason不修改`error-code-registry.v2`且尚不是HTTP status合同。P3-10必须按既有command API文档映射403/409/422/500并保留correlation，不能把local exception文本直接外放；Validator FAIL仍关联正式C-ID details，绝不转换Solver UNKNOWN或INFEASIBLE。

## TASK-P3-07 decision failures

Decision domain/application使用module-local sanitized reasons：`INVALID_REQUEST`、`AUTHORIZATION_DENIED`、`PRODUCTION_AUTHORITY_UNAVAILABLE`、`DATA_PLANE_MISMATCH`、`SOURCE_NOT_FOUND`、`STALE_SOURCE`、`INVALID_STATE_TRANSITION`、`IDEMPOTENCY_CONFLICT`和`PERSISTENCE_FAILED`。Authorization/capability/scope/Production拒绝统一写carrier允许的`WORKSPACE_CONTROL/AUTHORIZATION_DENIED` audit error而不暴露所需role或resource existence；非法carrier/actor/reason不能安全序列化时不写audit。Adapter的identity/state/other failure分别收敛到conflict/stale/sanitized persistence，SQL/stack/DSN不会外放。

本Task不改`error-code-registry.v2`，也不形成HTTP 401 challenge或endpoint mapping。P3-10必须把module-local authorization与Production default-deny映射为既有计划的403、state/stale/idempotency映射为409、invalid request映射为422、persistence映射为500，并始终保留correlation而不回显credential。

## TASK-P3-08 publication error boundary

Publication domain/application新增module-local sanitized reasons：`INVALID_REQUEST`、`AUTHORIZATION_DENIED`、`PRODUCTION_AUTHORITY_UNAVAILABLE`、`DATA_PLANE_MISMATCH`、`SOURCE_NOT_FOUND`、`PREVIOUS_CURRENT_NOT_FOUND`、`STALE_SOURCE`、`INVALID_STATE_TRANSITION`、`CURRENT_REFERENCE_CONFLICT`、`IDEMPOTENCY_CONFLICT`和`PERSISTENCE_FAILED`。Authorization/Production拒绝仍只写carrier允许的`WORKSPACE_CONTROL/AUTHORIZATION_DENIED`；adapter state/current/identity失败分别收敛到stale/current/idempotency或generic persistence，绝不外放SQL/stack/DSN。

Global `error-code-registry.v2`未修改，因为这些是未暴露的module-local控制原因。P3-10未来必须按冻结HTTP error model映射且不新造Product error category；P3-08没有HTTP surface、external failure或ExportJob error。

P3-09使用module-local `ExportJobFailure`与`StandardExportErrorCode`：invalid/auth/Production/source/stale/idempotency/state/lease/export/persistence及invalid/mixed/hash/XLSX/destination/I/O。Job失败carrier只使用冻结`WORKSPACE_CONTROL/EXPORT_FAILED`并保存sanitized message；授权拒绝用`AUTHORIZATION_DENIED` audit。Global product error registry、HTTP mapping和stack/SQL/path泄漏均未修改。

## TASK-P3-10 HTTP error adapter

Transport现把已有module-local reason收敛到strict `planning-workspace-error.v1`：缺失/非法Bearer=401，authorization/Production deny=403，source missing=404，stale/state/current/idempotency=409，invalid carrier/reference/time/validation=422，unexpected/persistence/export failure=500，composition unavailable=503。所有response保留correlation、stable namespace/reason、retryable与可选safe resource reference，但不返回raw exception、credential、SQL、stack或absolute path。

该adapter未修改`error-code-registry.v2`、七类product category或module内部失败事实，也不将Solver `UNKNOWN`转换为`INFEASIBLE`。Contract/integration/security和machine report覆盖八类映射与泄漏防护，并已随implementation artifact `9629193057`核验。
