---
doc_id: DOC-CONTRACT-010
title: P3 Planning Workspace API 语义合同
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 63, 65, 66, 68, 69, 77, 78, 91, 94]
last_reviewed: 2026-08-31
---

# P3 Planning Workspace API 语义合同

## TASK-P4-12 additive dynamic-replanning HTTP surface

`dynamic-replanning-http.v1`以additive方式新增8 path/9 operation：`appendExecutionEvent`、`getExecutionEvent`、`listExecutionEvents`、`createReplanRequest`、`getReplanRequest`、`cancelReplanRequest`、`retryReplanRequest`、`getReplanResult`与`getChangeReport`。ExecutionEvent/ReplanRequest POST直接消费P4-02 machine carrier；GET使用canonical/fingerprinted `dynamic-replanning-query.v1`；cancel/retry使用strict `replan-attempt-action-http.v1`绑定request fingerprint、attempt ID/number、expected PlanningRun state、reason、plane/correlation与hashed Idempotency-Key。

所有operation只在server-derived capability和exact planning scope通过后调用`DynamicReplanningApplicationPort`；结果必须以`dynamic-replanning-response.v1`反向绑定operation/resource/correlation。POST成功为202，GET为200；401/403/404/409/422/500/503继续使用sanitized `planning-workspace-error.v1`。`UNKNOWN_OUTCOME`=503且`retryable=false`，client必须先查询exact result而不是盲目换key重试。

P3 18-operation清单现以精确path/operation子集复验，允许后续Phase只做additive route；P3 route、carrier、operation ID、status、authority与router语义不变。P4 router不计算fact/freeze/OBJ-002，不调用Solver/Validator/Simulator，不推进ScheduleVersion或ReplanRequest state，不暴露P5/external/Production capability。

## TASK-P4-01 future API boundary

ADR-0013～0015固定未来P4 transport只能调用server event ingress、ReplanRequest/read与ChangeReport application ports；router不得排序事件、投影facts、计算freeze/OBJ-002、调用Solver/Validator或推进Version。Authority scope/source position、idempotency/fingerprint、stale/current、correlation/audit和Simulation isolation均由application返回并fail closed。

该P4-01基线要求TASK-P4-12等待P4-02/03/04/08/11全部`done`后再独立设计/实现；上述启动门现已满足，当前实现见本页顶部。P3 18个operation仍作为冻结子集保持不变；真实identity/event/approval authority、external publish或deployment接口仍未形成。

## TASK-P3-17 audit conclusion

18个operation（17个frozen P3-10 + 1个bounded verified download）的path/header/body/error/correlation/idempotency与server delegation完成zero-drift复验：18 delegations、0 router transition、0 Solver/Validator调用、0 Production provider lookup/application call。P3 Exit本地READY不形成external API authority。

## TASK-P3-16 localization boundary

TASK-P3-16双语已只实现于Frontend display adapter。Route、JSON key、Schema/URN/version、OpenAPI `operationId`、query/command discriminator、state/error/C-ID、HTTP status、fingerprint/idempotency和response bytes逐字不变；请求仍发送`APPROVE`、`READY_FOR_REVIEW`等英文机器值。P3没有增加`Accept-Language`协商或中文API字段/枚举。UI按error namespace/code/reason映射官方术语并保留raw/correlation，未知值fail visibly；zero-wire-drift evidence已由exact implementation provider复验。规范来源为[`official-zh-cn-terminology.v1`](../frontend/official-zh-cn-terminology-map.md)。

## TASK-P3-14 transport Gate

Gate消费P3-10已发布18-operation HTTP边界和P3-13 Frontend evidence，检查API/UI只经application/state guards并与Backend replay语义一致。报告不会发布新endpoint、payload、OpenAPI fingerprint或错误映射；发现transport/consumer漂移即形成blocking gap。当前仅为本地Gate证据，exact provider verification仍待implementation提交。

## TASK-P3-13 additive download operation

历史P3-10 17-operation集合保持不可变；经用户明确批准，当前合同additive增加第18项`GET /api/v1/export-jobs/{export_job_id}/download`（operation ID `downloadExportPackage`）。请求沿用Bearer/correlation和`export` capability，不带command body或Idempotency-Key；application只可返回verified binary result。200固定`application/zip`、attachment filename、`no-store`、`nosniff`及package/manifest/archive/completion-audit/correlation headers；其他失败继续使用sanitized `planning-workspace-error.v1`。

该operation只接受internal Simulation `EXPORTED` Job，不发布JSON Schema或新state。Local machine report现为18 paths/18 operations/18 delegations、Production provider lookup=0、router transition=0，OpenAPI fingerprint=`sha256:a2de2adb15aae7cccbac13b1ad1ffb953c82f1ef735eb00eb95bb3a3be8035a4`。这不表示external download service或Production API readiness。

本文件是P3 read/command HTTP的先行人类语义合同。TASK-P3-01不创建JSON Schema、Pydantic/FastAPI、OpenAPI、数据库或行为；TASK-P3-02发布机器carrier，TASK-P3-05～10实现read/application/API，TASK-P3-11～13消费。

## 合同版本与Schema分配

当前全局schema set为additive `2.7.0`。下表的P3-02文件和URN已由TASK-P3-02新增；机器文件、offline `$ref`、sample、canonical fingerprint和machine report已经形成，并由implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a`的exact provider artifact `9506913562`复验。TASK-P3-09又以additive方式新增`export-manifest.v2`/`export-job.v2`且保留全部v1 bytes；TASK-P3-10只实现HTTP绑定，不修改任何Schema。

| Document | Stable `$id` | compatibility | 主要consumer |
|---|---|---|---|
| `schedule-version.schema.json` / `schedule-version.v1` | `urn:plantnexus:aps:schema:schedule-version:v1` | 新文档；不与PlanningSolution互换 | P3-03～10、11～13 |
| `workspace-query.schema.json` / `workspace-query.v1` | `urn:plantnexus:aps:schema:workspace-query:v1` | 新文档；strict query/result envelope | P3-05、10～13 |
| `workspace-command.schema.json` / `workspace-command.v1` | `urn:plantnexus:aps:schema:workspace-command:v1` | 新文档；strict discriminated command | P3-06～10、13 |
| `schedule-version-comparison.schema.json` / `schedule-version-comparison.v1` | `urn:plantnexus:aps:schema:schedule-version-comparison:v1` | 新文档；不是ChangeReport | P3-05、10、12 |
| `audit-event.schema.json` / `audit-event.v1` | `urn:plantnexus:aps:schema:audit-event:v1` | 新文档；append-only carrier | P3-03、06～10、13 |
| `publication-result.schema.json` / `publication-result.v1` | `urn:plantnexus:aps:schema:publication-result:v1` | 新文档；internal publish result | P3-08、10、13 |
| `export-job.schema.json` / `export-job.v1` | `urn:plantnexus:aps:schema:export-job:v1` | P3-02历史carrier；bytes保留 | P3-03与显式v1 consumer |
| `export-job-v2.schema.json` / `export-job.v2` | `urn:plantnexus:aps:schema:export-job:v2` | P3-09 additive carrier；不等于ExportManifest | P3-09、10、13 |

所有对象必须`additionalProperties=false`、显式version/plane/provenance、拒绝unknown state/code/version且不提供Production业务默认值。P2 Schema/URN/bytes和`state-machines.v1`保持不变。

## Endpoint inventory

总规既有route保持：

| Method / route | 类型 | application owner | 结果合同 |
|---|---|---|---|
| `GET /api/v1/planning-runs/{id}` | read | P2/P3 read service | versioned PlanningRun/Solver/Validation摘要 |
| `GET /api/v1/schedule-versions/{id}` | read | P3-05 | `schedule-version.v1` + allowed actions |
| `POST /api/v1/schedule-versions/{id}/validate` | command | P3-04/06 | fresh validation result；不跳过DRAFT |
| `POST /api/v1/schedule-versions/{id}/approve` | command | P3-07 | approved decision/audit result |
| `POST /api/v1/schedule-versions/{id}/reject` | command | P3-07 | rejected decision/audit result |
| `POST /api/v1/schedule-versions/{id}/publish` | command | P3-08 | `publication-result.v1` |

P3新增route template：

| Method / route | 类型 | payload/result | capability |
|---|---|---|---|
| `GET /api/v1/workspace/data-health` | read | `workspace-query.v1` Data Health | `view` |
| `GET /api/v1/workspace/import-runs` | read | paged Import run projection | `view` |
| `GET /api/v1/workspace/planning-runs` | read | paged PlanningRun projection | `view` |
| `GET /api/v1/schedule-versions/{id}/workspace/{view}` | read | strict view enum/result for orders, operations, resources, calendars, Gantt, load, KPI, diagnostics, locks, audit | `view`; audit view需`audit` |
| `POST /api/v1/schedule-version-comparisons` | read-query | base/compare IDs + filters → comparison v1 | `view` |
| `POST /api/v1/schedule-versions/{id}/commands` | command | `workspace-command.v1` → new DRAFT result | `edit`或`lock` |
| `GET /api/v1/schedule-versions/{id}/audit-events` | read | paged `audit-event.v1` | `audit` |
| `POST /api/v1/schedule-versions/{id}/exports` | command | export request → `export-job.v1` | `export` |
| `GET /api/v1/export-jobs/{id}` | read | `export-job.v1` | `view`/`export` |
| `POST /api/v1/export-jobs/{id}/retry` | command | expected failed attempt → updated job | `export` |
| `POST /api/v1/export-jobs/{id}/cancel` | command | allowed ExportJob pair result | `export` |

`{view}`必须是TASK-P3-02机器enum，不能成为任意repository/table selector。P4的`/replan-requests`和`/execution-events`即使在总规inventory中存在，也不得由P3 router装配。

## Read query envelope

query至少携带`workspace_query_version`、`data_plane`、resource/view identity、version/content precondition、stable sort、filters、page size和opaque cursor。response至少包含：

- contract/result version、query fingerprint、server correlation ID；
- authoritative `schedule_version_id/state/content_fingerprint`和完整lineage引用；
- stable ordered items、`next_cursor`和server-observed count；
- server计算的`allowed_actions`，其值由authorization/state/target共同决定；
- freshness/stale marker与生成时间；空集合与not-found分开表达。

同一Version fingerprint、query fingerprint和cursor的重放必须保持内容与排序；实时审计追加造成页面变化时必须返回新cursor/fingerprint，不能静默混页。

## Command envelope

所有命令共享：

| 字段 | 语义 |
|---|---|
| `workspace_command_version` / `command_type` | strict version/discriminator |
| `idempotency_key` | action scope内exact replay；HTTP header/body必须一致 |
| `source_id` / `expected_state` / `expected_content_fingerprint` | CAS与stale保护 |
| `data_plane` / `target` | Production/Simulation与副作用隔离；不允许隐式default |
| `reason` | 所有人工状态/内容改变必填 |
| `correlation_id` | trace/audit关联；不得作为authority |
| `payload` | command-specific strict object |

认证principal/claims由transport security context提供，不允许客户端在body中自报“角色”。application通过[`authorization-and-audit.md`](authorization-and-audit.md)解析capability，并在任何状态或副作用前fail closed。

## 状态与副作用

- content edit/lock永远copy-on-write产生新DRAFT；source Version content/state不变。
- DRAFT/REJECTED不能publish；只有APPROVED可`APPROVED → PUBLISHED`。
- PUBLISHED content immutable；新current publication才可原子触发旧PUBLISHED→SUPERSEDED。
- Export只从PUBLISHED创建ExportJob；ExportJob状态不改变ScheduleVersion状态或current reference。
- 每次成功command必须原子提交业务结果、idempotency result和append-only audit；无法保证原子性则整体失败。

允许pair仍只由`state-machines.v1`授权，本合同不新增state/self-transition。

## HTTP/error映射计划

现有顶层七类product error category保持不变。TASK-P3-02的workspace response carrier必须显式区分`product_error`与`workspace_control_error`；P3 module-local reason不得被强塞进不相符的product category，也不得被误写为已经加入`error-code-registry.v2`。

| category / reason | HTTP | 责任层与边界 |
|---|---:|---|
| `DATA_ERROR` request shape/reference | `422`；资源ID不存在可用`404` | transport/contract/domain；副作用前拒绝 |
| `MODEL_INVALID` | `422`；若已持久化权威artifact损坏则sanitized `500` | contract/model invariant；不等于INFEASIBLE |
| `VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED` | `422` | fresh independent Validator；不产生成功Version/transition |
| `INVALID_STATE_TRANSITION` | `409` | application state guard、expected-state mismatch |
| `AUTHORIZATION_DENIED`（`workspace-control.v1`） | `403` | capability/default-deny；缺失认证由未来transport返回`401`，当前identity provider未决定 |
| `IDEMPOTENCY_CONFLICT`（`workspace-control.v1`） | `409` | same key/different fingerprint或stale content precondition |
| `EXPORT_FAILED`（`workspace-control.v1`） | `500` | Export attempt失败；底层causal product error可为sanitized `SYSTEM_ERROR`，job保持可审计失败且不改变publish |
| unexpected exception | `500` | sanitized correlation only；不返回SQL、stack、credential |

Solver `UNKNOWN`继续映射`NO_SOLUTION_WITHIN_LIMIT`并且没有candidate；API不得把它改成`INFEASIBLE`、Validation PASS或可发布ScheduleVersion。

错误response至少包含version、error namespace/discriminator、product category/code或control reason、sanitized message/details、correlation ID、retryable和相关resource/version reference；不得返回raw credential、Secret、SQL、filesystem绝对目标或内部stack。Frontend不得以英文`message`作为业务判断；本地化选择顺序是namespace→`product_error.code`或`workspace_control_error.reason`→`details.reason`，安全message只作诊断fallback。

## Idempotency 与事务

action scope至少包含data plane、action、resource/version、target和key；request fingerprint覆盖contract version、expected preconditions、payload、reason与target。

- same key + same fingerprint返回同一logical result和`replayed=true`；
- same key + different fingerprint返回`409`且不产生新副作用；
- timeout后的客户端先查询原result，不换key盲重试；
- approve/reject、publish/current/supersede、ExportJob create/retry分别拥有独立scope，Export retry不得触发publish；
- DB unique/CAS/transaction和索引需求由TASK-P3-03实现，本文件不构成migration。

## Authorization、audit 与observability

每个route的server guard和audit字段遵循[`authorization-and-audit.md`](authorization-and-audit.md)。日志记录contract/action/resource reference、result、duration、correlation和sanitized error；不得把audit当普通可变日志，也不得把结构化日志当成audit persistence。

## 测试分配

TASK-P3-01只形成文档合同；TASK-P3-02以`test_p3_workspace_contracts.py`形成`TEST-CONTRACT-001`与`TEST-WORKSPACE-CONTRACT-001`的machine carrier slice，并复验`TEST-STATE-TRANSITION-001`/`TEST-ERROR-MAPPING-001`既有集合未漂移。P3-05～10形成read/command/API behavior，P3-13形成用户可见E2E，P3-14复验Gate；P3-16 display-only本地化与P3-17最终独立Audit均为`done`且双提交provider完整闭环。P3-15为治理支持，不是API/Audit实现。

## TASK-P3-02 machine carrier realization

七份Schema都使用Draft 2020-12、strict object/no default、exact `2.6.0`与stable URN。`workspace-query.v1`把REQUEST/RESULT、14个允许view、sort/filter/page、query fingerprint、authoritative Version、lineage、items/cursor/count/allowed-actions/freshness固定为单一carrier；`workspace-command.v1`把11类P3 intent、derived capability、CAS、plane/environment/target、reason、idempotency scope/key与request fingerprint固定为discriminated carrier，且body明确不含principal/role。

`app.domain.workspace_contracts`只计算canonical projection和跨值precheck；它不读取认证上下文、不推进state、不写repository，也不产生HTTP/result side effect。CI的`p3-workspace-contract-report.v1`固定7/7 positive、24个Schema negative、6个fingerprint negative、P2 34 artifact preservation和P3/P4/Production边界。

## P4/Production边界

本合同不包含ExecutionEvent、ReplanRequest、freeze、OBJ-002、ChangeReport、Execution Simulator、真实RBAC/SSO、MES/ERP/storage adapter或Production deployment。OPEN-002/010/015继续开放，Production command/target default-deny。

## TASK-P3-05 read application semantics

P3-05已在HTTP边界之前形成solver-neutral read application：Data Health、Import/Planning Runs、Orders、Operations、Resources、Calendars、Gantt、Resource Load、KPI、Diagnostics、Locks、Audit与Version Comparison。Schedule-scoped请求必须带exact Version reference；不存在返回`found=false`，存在但结果为空返回`found=true/items=[]`，state/content变化为`STALE_VERSION`，plane/environment、lineage或cursor不匹配均fail closed。Cursor绑定过滤、排序、page size、Version precondition及不可变source collection；comparison显式绑定base/compared两个Version。

这不是HTTP endpoint实现：没有FastAPI/Pydantic/OpenAPI、identity/capability解析或前端payload。P3-10必须适配这里的carrier+payload结果，不得绕过precondition、重新计算Solver/Validator事实或把comparison升级成P4 ChangeReport。

## TASK-P3-06 command application semantics

HTTP之前的command application已形成：接受`workspace-command.v1`的Move/Assign/Set/Remove Lock四类content command及空payload `SUBMIT_FOR_REVIEW`，逐项复验strict字段、derived capability、exact source state/content、server-derived idempotency scope、plane/environment/synthetic provenance和`WORKSPACE_INTERNAL` target。Raw idempotency key只在调用内使用；AuditEvent仅保存hashed key reference与request fingerprint。Content成功结果固定source/new Version reference、new state DRAFT、fresh ValidationReport reference、audit ID、correlation及replay flag；submit只接受本Task生成的manual/lock DRAFT，经第二次fresh PASS与CAS返回同ID/content的READY reference。

Same key/same request可在source后续state变化后通过既有audit/new immutable content重放原logical result；same key/different request、stale source、missing source、authorization、Validator或persistence failure均fail closed。该服务不是HTTP endpoint、OpenAPI或RBAC实现；P3-10只能做transport/error映射，不能在router复制command mutation或Validator逻辑。Production在OPEN-010关闭前无论carrier capability如何都default-deny。

## TASK-P3-07 decision application boundary

Approve/Reject application现消费冻结`workspace-command.v1`的空payload `APPROVE|REJECT`，要求`expected_state=READY_FOR_REVIEW`、exact content fingerprint、`WORKSPACE_INTERNAL`、server-derived scope/key reference及non-empty sanitized reason。返回logical result包含command/type/request fingerprint、READY source reference、APPROVED或REJECTED new reference、audit ID、correlation和replay flags；它不返回credential、role或raw key。

该行为仍不是上述两个`POST` endpoint：未新增router、request model、OpenAPI、401/403 challenge或HTTP status adapter。P3-10只能调用`ApprovalDecisionService`并映射既有module-local failure，不能绕过authorization-before-lookup、在router重复CAS/audit逻辑，或把APPROVED解释为PUBLISHED。P3-08～13、真实RBAC/SSO与Production authority均未形成。

## TASK-P3-08 publication application boundary

`PublicationService`现消费冻结PUBLISH carrier：`expected_state=APPROVED`、exact content fingerprint、`SIMULATION_INTERNAL`、payload中的exact previous-current reference或null、server-derived scope/key和sanitized reason。成功返回`publication-result.v1`及current/superseded logical references；same-key replay把`replayed=true`并重算result fingerprint，但不重复transition、audit或current CAS。Stale previous/current、different fingerprint、double publish与并发loser均fail closed。

该行为不是`POST .../publication` endpoint：没有router、request/response model、OpenAPI、HTTP status或Frontend。P3-10只能组合application service，不能在transport重写authorization、state/current CAS或把internal Simulation result外推为external/Production publish；P3-09 ExportJob仍是独立服务。

P3-09现形成transport-neutral `ExportJobService`与`export-job.v2`结果，仍没有HTTP route/OpenAPI/response model。P3-10如获授权只能组合create/read/retry/cancel，不得把raw role、absolute storage path、external target、Publish调用或Production fallback塞入API；下载/状态必须以v2 manifest/job fingerprints为authority。

## TASK-P3-10 executable HTTP surface

`create_app` 以显式注入的`PlanningWorkspaceApplicationPort`组装上述17个operation；默认facade为unavailable，不得在router中直接读repository或复制Solver、Validator、state-machine逻辑。GET route以URL-encoded canonical JSON `query`参数承载strict query carrier；POST command使用strict body，`Idempotency-Key`必须与body精确一致，传入的`X-Correlation-Id`也必须与carrier一致，缺失时由server生成并在response回传。Comparison显式绑定base/compared Version header与body。所有响应使用`Cache-Control: no-store`。

Transport只有在server-derived principal/capability/resource scope通过后才委托application。缺失/非法Bearer为401，capability/scope拒绝为403，resource missing为404，state/stale/idempotency为409，strict carrier/validation为422，sanitized unexpected/persistence为500，unavailable composition为503；响应只暴露稳定namespace/reason、safe details和correlation。Production在provider lookup前固定拒绝，Simulation必须同时开启显式API flag和Simulation data plane。

OpenAPI固定17个operation ID和`x-plantnexus-*`边界；P3-10 artifact `9550224090`复验17 paths/17 successful delegations、8类error mapping、Production provider/application调用均0、router business transition与Solver/Validator调用均0。P3-11只消费其read subset；这不形成external adapter、真实RBAC/SSO、P4 endpoint或Production readiness。

## TASK-P3-11 read-only HTTP consumer

Frontend现只调用`getPlanningRun`、`getScheduleVersion`及获授权的workspace GET route；query参数是canonical compact JSON经`URLSearchParams`编码的单一`query`值。Schedule-scoped页面必须先读取Version并把exact ID/state/content fingerprint放入query carrier；409只进入`stale`状态，不使用旧缓存继续显示ready。

Implementation `567e8693db881ea3dfffa011de9021fef9641361` / artifact `9552386549`已复验GET-only consumer、query/Version/reference边界与13-route inventory；没有修改P3-10 API、Schema或server authority，也未形成P3-12/13 control、P4或Production能力。

Response adapter逐字段检查version、view、result、unknown state、raw UTC、lineage、carrier item与完整payload item reference；query fingerprint由canonical projection复验。Payload fingerprint保留server authority并与carrier/reference逐字对齐，不从JSON.parse后的JavaScript number重新定义后端canonical lexical bytes。401/403、404/422、409、500/503/network分别进入authorization、contract、stale和server failure；任何失败均不伪造empty/ready。

Session只来自注入provider且默认null；client不持久化/记录token、不发POST、不装配command/idempotency/action route。此consumer不改变17个operation、Schema/OpenAPI、Backend semantics或Production authority。

## TASK-P3-12 visualization consumer

Frontend现消费既有`GANTT`、`RESOURCE_LOAD`、`KPI`、`DIAGNOSTICS`和`VERSION_COMPARISON`投影。每个完整payload在runtime重新canonicalize并核对server `payload_fingerprint`，Gantt严格校验UTC/tick/duration与operation/order/resource/topology引用，load严格校验seconds/count/utilization，comparison严格校验version/reference/change kind/KPI delta/summary/fingerprint。Unknown enum、invalid timestamp、reference或fingerprint mismatch均进入contract error，不丢row或推断fallback业务事实。

Two-Version consumer先GET compared Version，再以base/compared exact ID/state/content fingerprint调用既有`POST /api/v1/schedule-version-comparisons`；它不发送`Idempotency-Key`且不调用任何command/action route。P3-10的17 operations、OpenAPI fingerprint `sha256:fbabcc5b9005f5ec22f3a6e8b6351bcf0469dbaa176682caa954191c0d697b36`、Schema、router/application authority均零变化；P3-12 artifact `9555196470`精确复验该consumer，仍不形成new endpoint、P4 ChangeReport或Production API readiness。
