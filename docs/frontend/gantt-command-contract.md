---
doc_id: DOC-FRONTEND-002
title: P3 Gantt Command 与新版本合同
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 35, 47, 48, 50, 69, 77, 78, 94]
last_reviewed: 2026-08-27
---

# P3 Gantt Command 与新版本合同

## TASK-P3-16 localization boundary

Move/Assign/Set Lock/Remove Lock等用户可见名称已依据[`official-zh-cn-terminology.v1`](official-zh-cn-terminology-map.md)显示中文或英文，但`MOVE_OPERATION`、`ASSIGN_RESOURCE`、`SET_LOCK`、`REMOVE_LOCK`、payload keys、state、Idempotency-Key与canonical fingerprint逐字保持英文。格式化时间保留raw UTC，未知command/state/reason显示raw值；UI不从localized label解析或生成machine value。Zero-wire-drift与双语Gantt browser evidence已由exact implementation provider复验；command行为、Schema和state pair零变化，最终由TASK-P3-17独立审计。

## TASK-P3-14 command Gate

Gate两轮复验UI command→server validation→new DRAFT→formal Validator链、copy-on-write/immutable source与same-key replay，并在聚合层拒绝对PUBLISHED内容的任何mutation。该检查不增加command类型、状态转移、客户端权威或P4 replan；若raw report或semantic projection漂移则非零退出。

## TASK-P3-13 implemented command surface

DRAFT Gantt现把selection映射为四种既有server command：Move发送operation/resource/start/end，Assign只发送operation/resource，Set Lock发送完整HARD/SOFT lock tuple，Remove Lock发送lock/operation identity。Drag只是5分钟量化且±24小时有界的Move intent；keyboard/table表单提供等价路径。Client canonicalize `workspace-command.v1`并绑定source Version ID/state/content fingerprint、capability、target、reason、correlation和同一header/body idempotency key。

Server返回new authoritative DRAFT后，UI导航到该Version；validation/state/stale/idempotency错误不会乐观改变原Version。PUBLISHED timeline仍可选择和查看，但`draggable=false`且不渲染move/assign/lock button。以上不修改P3-06 copy-on-write/fresh Validator语义，也不是P4 dynamic replan。

本文件固定UI提交人工编辑/lock的command语义。TASK-P3-01不实现command、Schema、API或UI；机器carrier由TASK-P3-02发布，application pipeline由TASK-P3-06实现。

## 唯一允许的链

```text
UI intent
→ versioned command envelope
→ authentication/capability/data-plane precheck
→ idempotency + expected-state/content precondition
→ server semantic validation
→ copy-on-write candidate
→ fresh independent ScheduleValidator
→ atomic new DRAFT + lineage + audit + idempotency result
```

任何失败均不得修改source Version、创建成功状态或返回伪成功。UI不得直接写repository/DB，也不得在浏览器运行Solver、Validator或KPI公式。

## Command types

| `command_type` | Intent payload | 必需capability | 结果 |
|---|---|---|---|
| `MOVE_OPERATION` | operation ID、建议start/end或duration-preserving start、reason | `edit` | assignment变更后的新DRAFT |
| `ASSIGN_RESOURCE` | operation ID、candidate resource ID、reason | `edit` | 资源/时长合同校验后的新DRAFT |
| `SET_LOCK` | operation ID、lock type、resource/start/end、reason | `lock` | version-local lock投影后的新DRAFT |
| `RELEASE_LOCK` | operation ID、lock identity、reason | `lock` | 显式移除version-local lock后的新DRAFT |

`SET_LOCK/RELEASE_LOCK`不创建P4 freeze window，不移动RUNNING/COMPLETED事实，不弱化既有HARD lock，也不把SOFT lock升级为Production稳定性策略。

## Command envelope

TASK-P3-02必须将下列语义发布为strict、versioned、`additionalProperties=false`的机器合同；字段名可在Schema review中保持等价但不得减少语义。

| 字段 | 要求 |
|---|---|
| `workspace_command_version` | 精确document version；未知版本fail closed |
| `command_id` | 客户端生成的可追踪ID，不承担幂等唯一性 |
| `command_type` | 上表固定enum |
| `idempotency_key` | scope内非空；raw credential不得作为key |
| `source_schedule_version_id` | 唯一source Version；旧内容只读 |
| `expected_state` | 客户端读取时的state；server必须CAS/比较 |
| `expected_content_fingerprint` | source content/precondition指纹 |
| `data_plane` | `SIMULATION`或`PRODUCTION`；禁止跨plane |
| `payload` | command-type discriminated strict object |
| `reason` | 非空、用户可审计且按日志规则清洗 |
| `correlation_id` | 贯穿HTTP/application/audit/provider的trace carrier |

transport可以另带认证principal和`Idempotency-Key` header；credential/token绝不能进入payload、audit或artifact。application只消费已认证principal解析出的capability context，不能信任客户端自报授权。

## Source 与不可变性

- source Version内容在任何state下都不可原地更新；command结果必须有新的`schedule_version_id`、父版本引用和新的content fingerprint。
- `DRAFT`或`READY_FOR_REVIEW`可作为工作source；`APPROVED`、`REJECTED`、`PUBLISHED`或`SUPERSEDED`若被选作历史参考，也只能copy-on-write派生新DRAFT，绝不能改变原state/content/current publication。
- PUBLISHED Version没有“保存到当前版本”的路径。若实现无法证明copy-on-write，必须拒绝而不是退化为UPDATE。
- source state不会因编辑自动转移；新DRAFT进入READY仍须TASK-P3-04的fresh ValidationReport PASS/hard=0 guard。

## Server validation

server在持久化成功结果前至少检查：

1. principal/capability、environment、data plane和source identity；
2. exact state/content precondition与idempotency fingerprint；
3. operation/resource/lock reference存在且属于同一Problem/ScheduleVersion lineage；
4. UTC、整数秒、duration、calendar、candidate resource和execution fact不可变边界；
5. command不得移动COMPLETED/RUNNING事实或违反HARD lock；
6. copy-on-write candidate具有完整assignment与provenance；
7. fresh、solver-independent Validator对C-001～C-011返回PASS且hard violation count为0。

Validator FAIL时返回`VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED`及sanitized details，不发布新成功DRAFT。实现Task必须明确失败candidate是完全不持久化，还是作为不可评审的失败attempt evidence单独保存；两者都不得伪装成功ScheduleVersion。

## Idempotency 与并发

幂等scope至少包括`data_plane + action + source_schedule_version_id + idempotency_key`，request fingerprint覆盖command version/type、source identity/preconditions、payload和reason。

- same scope/key + same fingerprint：返回相同logical result/new Version ID，不重复audit或写入；
- same scope/key + different fingerprint：`IDEMPOTENCY_CONFLICT`；
- source state/content已变化：HTTP `409`并返回稳定precondition错误；
- 并发两个不同key可各自产生独立DRAFT，但不得覆盖彼此或改变source。

## Result contract

成功结果至少包含command/version、source/new ScheduleVersion ID、new state=`DRAFT`、parent/content fingerprint、fresh ValidationReport reference、audit event ID、idempotent replay flag和correlation ID。客户端只能在收到成功结果后切换到新Version；optimistic preview不得作为权威状态。

## Error/UI mapping

| 情况 | 责任层 | 计划HTTP | UI行为 |
|---|---|---|---|
| payload/reference/time/data-plane错误 | contract/domain | `422` | 标出字段，不提交成功状态 |
| stale state/content或key冲突 | application/idempotency | `409` | 刷新Version，保留用户intent供显式重试 |
| unauthorized/default-deny | authorization | `403` | 隐藏/禁用动作并显示拒绝；不请求Production override |
| independent Validator FAIL | validation | `422` | 展示C-ID/details；不得显示已保存成功 |
| unexpected persistence/system failure | infrastructure | `500` | 显示可追踪correlation ID，不泄漏异常 |

`UNKNOWN` Solver status不是command验证结果，绝不能转换成`INFEASIBLE`或“可编辑成功”。

## 审计

成功和允许记录的拒绝attempt须使用[`authorization-and-audit.md`](../contracts/authorization-and-audit.md)的append-only字段，至少关联actor reference/capability、reason、command/request fingerprint、source/new Version、before/after state、ValidationReport、correlation和result。raw token、payload中的敏感自由文本和stack trace不得进入审计。

## P4 与Production边界

本合同不定义ExecutionEvent、ReplanRequest、freeze window、OBJ-002、ChangeReport、Execution Simulator或真实调度员角色。Simulation test actor只验证contract；Production authority未知时所有command default-deny，OPEN-005/010继续开放。

## TASK-P3-06 executable command boundary

`ScheduleCommandService`现严格消费`MOVE_OPERATION`、`ASSIGN_RESOURCE`、`SET_LOCK`、Schema中的实际名称`REMOVE_LOCK`及`SUBMIT_FOR_REVIEW`；此前表格中的`RELEASE_LOCK`仅为早期人类措辞，机器与应用权威名称统一为`REMOVE_LOCK`。服务先校验server-resolved capability、plane/environment、source state/content precondition、scope/key/request fingerprint及operation/resource/time/lock引用，再构造copy-on-write candidate；`MOVE_OPERATION`要求tick-aligned interval与candidate resource duration一致，`ASSIGN_RESOURCE`保持start并按候选duration重算end，HARD lock必须与assignment精确一致。

每次成功都创建不同ID、parent reference、`MANUAL_EDIT`或`LOCK_CHANGE`、fresh `validation-report.v2`引用和append-only AuditEvent的新DRAFT；source在DRAFT、READY_FOR_REVIEW、REJECTED或PUBLISHED等状态下均逐字不变。Same scope/key+same fingerprint重放原logical result，同key+不同fingerprint冲突。Validator FAIL、stale、unauthorized、mixed plane、invalid reference/time/lock及transaction failure都不保留失败ScheduleVersion；本slice选择“discard candidate、无成功audit”，未来若记录拒绝attempt必须独立版本化且不得伪装成功。

该application boundary没有HTTP/UI或真实principal→capability解析。Simulation carrier只证明test policy；Production command始终`DEFAULT_DENY_OPEN_010`。新DRAFT不会隐式进入READY；当前已形成独立空payload `SUBMIT_FOR_REVIEW`，仅接受`MANUAL_EDIT|LOCK_CHANGE` DRAFT，第二次fresh PASS后以同ID/content CAS到READY并原子audit。它不等于approve/reject；approval/publish/export和P4均未形成。

## TASK-P3-10 command transport

`POST /api/v1/schedule-versions/{id}/commands`与validate/approve/reject/publish路由只处理strict body、path/header绑定、server authorization、correlation和error mapping，然后委托application port。Router不重算Gantt mutation、lock、Validator或state transition。HTTP已形成不等于UI已形成；drag/confirmation/accessibility/browser E2E仍由P3-11～13完成，P4 replan/freeze和Production command继续排除。

## TASK-P3-12 visualization-only boundary

当前Gantt实现只有zoom、server filter、selection、cross-highlight和navigation link；timeline/bar/table均没有drag/drop、resize、lock toggle、optimistic mutation、command endpoint或Idempotency-Key。Resource Load和Version Comparison也只显示server事实；comparison POST是P3-10定义的双Version read-query，不是command，不生成新DRAFT或状态转换。

Read-only Chromium覆盖120-row virtualization/table fallback、load→Gantt link、comparison no-idempotency/server classification及authorization denial；artifact `9555196470`已精确复验4/4 specs及no-command边界。该证据不形成上表任何human command；P3-13必须另行授权并继续遵循copy-on-write、fresh Validator、explicit confirmation和server state authority，P4 replan/change report与Production authority仍排除。
