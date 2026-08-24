---
doc_id: DOC-CONTRACT-010
title: P3 Planning Workspace API 语义合同
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 63, 65, 66, 68, 69, 77, 78, 91, 94]
last_reviewed: 2026-08-24
---

# P3 Planning Workspace API 语义合同

本文件是P3 read/command HTTP的先行人类语义合同。TASK-P3-01不创建JSON Schema、Pydantic/FastAPI、OpenAPI、数据库或行为；TASK-P3-02发布机器carrier，TASK-P3-05～10实现read/application/API，TASK-P3-11～13消费。

## 合同版本与Schema分配

当前全局schema set为additive `2.6.0`。下表文件和URN已由TASK-P3-02新增；机器文件、offline `$ref`、sample、canonical fingerprint和machine report已经形成，并由implementation `aff27d3d6b63fb9f216c9a2687408a6c676fa96a`的exact provider artifact `9506913562`复验。Read/application/API行为仍留给P3-05～10。

| Document | Stable `$id` | compatibility | 主要consumer |
|---|---|---|---|
| `schedule-version.schema.json` / `schedule-version.v1` | `urn:plantnexus:aps:schema:schedule-version:v1` | 新文档；不与PlanningSolution互换 | P3-03～10、11～13 |
| `workspace-query.schema.json` / `workspace-query.v1` | `urn:plantnexus:aps:schema:workspace-query:v1` | 新文档；strict query/result envelope | P3-05、10～13 |
| `workspace-command.schema.json` / `workspace-command.v1` | `urn:plantnexus:aps:schema:workspace-command:v1` | 新文档；strict discriminated command | P3-06～10、13 |
| `schedule-version-comparison.schema.json` / `schedule-version-comparison.v1` | `urn:plantnexus:aps:schema:schedule-version-comparison:v1` | 新文档；不是ChangeReport | P3-05、10、12 |
| `audit-event.schema.json` / `audit-event.v1` | `urn:plantnexus:aps:schema:audit-event:v1` | 新文档；append-only carrier | P3-03、06～10、13 |
| `publication-result.schema.json` / `publication-result.v1` | `urn:plantnexus:aps:schema:publication-result:v1` | 新文档；internal publish result | P3-08、10、13 |
| `export-job.schema.json` / `export-job.v1` | `urn:plantnexus:aps:schema:export-job:v1` | 新文档；不等于ExportManifest | P3-03、09、10、13 |

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

错误response至少包含version、error namespace/discriminator、product category/code或control reason、sanitized message/details、correlation ID、retryable和相关resource/version reference；不得返回raw credential、Secret、SQL、filesystem绝对目标或内部stack。

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

TASK-P3-01只形成文档合同；TASK-P3-02现以`test_p3_workspace_contracts.py`形成`TEST-CONTRACT-001`与`TEST-WORKSPACE-CONTRACT-001`的machine carrier slice，并复验`TEST-STATE-TRANSITION-001`/`TEST-ERROR-MAPPING-001`既有集合未漂移。P3-05～10才形成read/command/API behavior，P3-13形成用户可见E2E，P3-14/15复验Gate/Audit。

## TASK-P3-02 machine carrier realization

七份Schema都使用Draft 2020-12、strict object/no default、exact `2.6.0`与stable URN。`workspace-query.v1`把REQUEST/RESULT、14个允许view、sort/filter/page、query fingerprint、authoritative Version、lineage、items/cursor/count/allowed-actions/freshness固定为单一carrier；`workspace-command.v1`把11类P3 intent、derived capability、CAS、plane/environment/target、reason、idempotency scope/key与request fingerprint固定为discriminated carrier，且body明确不含principal/role。

`app.domain.workspace_contracts`只计算canonical projection和跨值precheck；它不读取认证上下文、不推进state、不写repository，也不产生HTTP/result side effect。CI的`p3-workspace-contract-report.v1`固定7/7 positive、24个Schema negative、6个fingerprint negative、P2 34 artifact preservation和P3/P4/Production边界。

## P4/Production边界

本合同不包含ExecutionEvent、ReplanRequest、freeze、OBJ-002、ChangeReport、Execution Simulator、真实RBAC/SSO、MES/ERP/storage adapter或Production deployment。OPEN-002/010/015继续开放，Production command/target default-deny。

## TASK-P3-05 read application semantics

P3-05已在HTTP边界之前形成solver-neutral read application：Data Health、Import/Planning Runs、Orders、Operations、Resources、Calendars、Gantt、Resource Load、KPI、Diagnostics、Locks、Audit与Version Comparison。Schedule-scoped请求必须带exact Version reference；不存在返回`found=false`，存在但结果为空返回`found=true/items=[]`，state/content变化为`STALE_VERSION`，plane/environment、lineage或cursor不匹配均fail closed。Cursor绑定过滤、排序、page size、Version precondition及不可变source collection；comparison显式绑定base/compared两个Version。

这不是HTTP endpoint实现：没有FastAPI/Pydantic/OpenAPI、identity/capability解析或前端payload。P3-10必须适配这里的carrier+payload结果，不得绕过precondition、重新计算Solver/Validator事实或把comparison升级成P4 ChangeReport。
