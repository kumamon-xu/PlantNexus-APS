---
doc_id: DOC-CONTRACT-011
title: P3 Authorization Capability 与 Audit 合同
status: baseline
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 60, 66, 78, 94, 95]
last_reviewed: 2026-08-26
---

# P3 Authorization Capability 与 Audit 合同

## TASK-P3-14 authorization/audit Gate

两轮Gate复验authority-neutral capability、default-deny、actor/reason/correlation/idempotency与append-only audit link，并检查四类exact rejection的stage/category/code。它不创建真实identity或Production approval/publish authority；OPEN-010及全部PROD_OPEN保持未关闭，任何旁路或raw evidence不一致均阻断Gate。

## TASK-P3-13 action/download authorization

Browser从不构造role/actor/Production binding；只依据server返回的`allowed_actions`决定是否呈现control，最终authorization仍由HTTP层和application层执行。Download在任何repository/package lookup前要求authenticated `export` capability、Job scope和non-Production binding；unauthorized resource不能通过404或timing暴露存在性。随后还须验证Job plane/target/state、attempt、ScheduleVersion、synthetic provenance、artifact/storage/package hash及completion audit lineage。

UI reason、error、trace和download evidence不得包含Bearer、raw idempotency key、absolute storage path或stack。Unknown outcome只能保留内存中的exact command并在authority refresh后same-key retry；没有local/session storage。OPEN-010仍为`OPEN`，本Task没有真实RBAC/SSO、Production approver/publisher或SIEM evidence。

本合同定义authority-neutral capability、default-deny判定和append-only audit语义。它不选择真实用户、岗位、组织、identity provider或Production责任人，也不关闭OPEN-010。

## 判定模型

一次授权决定必须同时消费：

```text
authenticated principal reference
+ environment
+ data plane
+ capability
+ resource / ScheduleVersion / ExportJob identity
+ current state and content fingerprint
+ target
→ ALLOW or DENY
```

客户端自报role/capability、UI按钮、Simulation fixture或数据库owner均不是授权来源。Production缺少明确principal→capability mapping、resource scope或target时必须DENY；不得使用“admin”“planner”等猜测角色作为fallback。

## Capability vocabulary

| capability | 允许的语义 | 不允许的扩张 |
|---|---|---|
| `view` | 读取已授权workspace/version/job投影 | 不隐含audit或任何command |
| `edit` | 提交copy-on-write人工内容command | 不原地UPDATE，不调用Solver/Replan |
| `lock` | 提交version-local SET/RELEASE lock command | 不移动execution facts，不定义freeze |
| `approve` | READY_FOR_REVIEW→APPROVED | 不隐含publish/export |
| `reject` | READY_FOR_REVIEW→REJECTED | 不删除或改写Version |
| `publish` | APPROVED→internal PUBLISHED/current switch | 不授权外部MES/Production target |
| `export` | 从允许的PUBLISHED Version创建/重试/cancel ExportJob | 不改变ScheduleVersion publish state |
| `audit` | 读取有scope限制的append-only audit projection | 不修改、删除或补写历史event |

capability名称是应用合同，不是现有Solver `capability-registry.v1`中的工厂建模能力；TASK-P3-02必须避免两个namespace混淆。

## Action guard matrix

| Action | resource guard | state guard | target/data-plane guard | audit requirement |
|---|---|---|---|---|
| read workspace | `view` + resource scope | any visible state | same plane | access log；敏感读取是否升格audit留待retention policy |
| edit/lock | `edit`/`lock` + source scope | copy-on-write；source不可原地修改 | same plane | attempt/result、reason、old/new Version |
| approve/reject | exact capability + Version scope | only READY_FOR_REVIEW | same plane | decision、actor ref、reason、before/after |
| publish | `publish` + Version/target scope | only APPROVED | P3仅`SIMULATION_INTERNAL`；Production deny | request/result/current/supersession |
| export/retry/cancel | `export` + Version/Job/target scope | only允许的ScheduleVersion/ExportJob pair | P3 internal target；same plane | job/attempt/artifact/result |
| read audit | `audit` + aggregate scope | not a transition | same plane | security access log，不能递归写业务event |

状态、capability和target任一失败都必须在副作用前拒绝。是否记录拒绝audit由action policy固定：高风险approve/reject/publish/export和Production default-deny attempt必须记录sanitized拒绝event；普通not-found不得泄漏资源是否存在。

## Simulation test policy

P3 test可以在显式Development/Test/Benchmark环境、`SIMULATION` plane和隔离数据库中绑定stable test principal reference与capability set。该policy必须：

- 名称包含test/simulation语义且`production_binding=false`；
- 只作用于synthetic resource和`SIMULATION_INTERNAL` target；
- 在Production配置中不存在或始终DENY；
- 不被写入真实组织role mapping、OPEN closure或Production approval evidence。

本合同不新增定量SIM_ASSUMPTION。

## AuditEvent v1语义

TASK-P3-02已发布strict `audit-event.v1` carrier；TASK-P3-03才可append-only持久化。event至少包含：

| Field group | Required meaning |
|---|---|
| identity | `audit_event_id`、event version、UTC `occurred_at` |
| actor | stable pseudonymous `actor_ref`、resolved capability、auth policy version；不含token/credential |
| context | environment、data plane、action、aggregate type/ID、target |
| intent | sanitized reason、command/decision type、request fingerprint、idempotency reference |
| lineage | PlanningRun/Snapshot/Problem/Solution/Validation/ScheduleVersion/ExportJob references as applicable |
| state | before/after state；content改变时source/new Version和fingerprint |
| result | ALLOWED/DENIED/SUCCEEDED/FAILED、stable category/code、retry/replay flag |
| trace | correlation ID、parent event/attempt reference、code/schema/policy versions |

raw idempotency key可以被视为operational identifier但不得包含credential；持久化/日志应保存稳定reference或hash，避免把用户输入key扩散到artifact。自由文本reason需长度/字符/敏感信息策略，审计必须保存其批准后的sanitized representation。

## Append-only 与transaction

- audit event禁止UPDATE/DELETE；纠正只能追加新event引用旧event。
- state-changing result、idempotency result和成功audit必须处于同一事务/一致性边界；写audit失败即业务state不得成功。
- 外部副作用尚未形成；未来outbox/adapter若需要新transaction topology必须新ADR，不能在P3-01假定exactly-once network delivery。
- structured log/trace是观测carrier，不替代durable audit；audit retention、SIEM、legal hold和Production backup仍未决定。
- replay同一请求返回原logical result，不重复业务audit；允许追加单独的read/operational replay observation时必须与业务event类型区分。

## Redaction 与no-leak

不得写入audit、日志、HTTP error或CI artifact：password、token、cookie、authorization header、Secret、raw database DSN、SQL/stack trace、未清洗文件内容或未经批准的PII。actor使用稳定reference而非显示名/邮箱；UI需要显示名时由未来identity adapter按权限解析，不写回历史event。

## Error contract

- 未授权/default-deny使用`workspace-control.v1` module-local `AUTHORIZATION_DENIED`，HTTP计划为`403`；它与product error category显式分namespace，尚未加入global registry。
- state不允许使用既有`INVALID_STATE_TRANSITION`，HTTP `409`。
- same key/different fingerprint使用module-local `IDEMPOTENCY_CONFLICT`，HTTP `409`。
- audit/persistence失败归sanitized `SYSTEM_ERROR`，业务state不改变。

缺失认证的`401`行为、challenge header和identity provider选择留给独立安全/API决定；不能用`403`合同反向声明真实认证已形成。

## Version、Schema 与迁移边界

TASK-P3-02的`audit-event.v1`、`workspace-command.v1`与共享`workspace-control.v1` reason carrier现已形成：actor只允许`actor:<stable-ref>`，resolved capability来自固定应用词汇，intent reason受长度/控制字符约束，idempotency只扩散key reference/hash而非credential。PRODUCT与WORKSPACE_CONTROL是互斥namespace；`AUTHORIZATION_DENIED/IDEMPOTENCY_CONFLICT/EXPORT_FAILED`仍未加入`error-code-registry.v2`。

这只是strict serialization与pure no-secret/cross-reference precheck。真实principal→capability mapping、default-deny执行、append-only repository/transaction、拒绝事件策略、retention/SIEM及HTTP transport仍未实现；OPEN-002/010/015不变。

本Task没有Schema/migration。TASK-P3-02新增carrier必须保留P2 bytes，TASK-P3-03负责plane-scoped表、unique/CAS/index和append-only enforcement。字段不足必须发布新document version，禁止在数据库私加无法序列化的authority默认值。

## 追踪与测试

`REQ-007/009 + NFR-TRC/ISO/SEC/HUM + ENG-ERR/VER → TASK-P3-01 → TEST-WORKSPACE-CONTRACT-001/TEST-STATE-TRANSITION-001/TEST-ERROR-MAPPING-001`当前只形成文档合同。authorization/audit behavior由P3-03/07～10/13验证，Gate/Audit由P3-14/15复验。

## P4/Production边界

ExecutionEvent、Replan、freeze、OBJ-002、ChangeReport和Execution Simulator不在本合同。真实RBAC/SSO、role责任、external publish/export target、retention/SIEM和Production approval保持OPEN-002/010/015或后续治理，P3 default-deny不得被test actor绕过。

## TASK-P3-04 submit-for-review audit slice

P3-04首次把成功的DRAFT→READY_FOR_REVIEW与一条append-only `SUBMIT_FOR_REVIEW` AuditEvent放入同一数据库事务。Event固定actor reference、upstream auth-policy context、resolved `edit` capability、sanitized reason、correlation、request fingerprint、key reference、完整P2 lineage、DRAFT/READY source/new reference与exact code commit；repository/audit任一冲突会回滚本次ScheduleVersion变化。Exact replay返回原event，event内`result.replayed=false`保持历史事实，调用结果另行标记replay，不能通过改写event伪造第二次执行。

本Task不实现principal/role→capability解析，也不声称`auth_policy_version`是Production授权；调用者提供的resolved context只满足carrier/audit可追踪边界。未授权/default-deny、approve/reject/publish/export authority仍由P3-07+和OPEN-010治理；测试actor不得外推真实责任人。无raw key、credential、SQL、stack trace或secret进入carrier/error/machine report。

## TASK-P3-05 audit read boundary

Audit view只通过plane-scoped append-only repository读取指定ScheduleVersion的event，按`occurred_at_utc/audit_event_id`稳定排序，并输出fingerprinted `AUDIT_REFERENCE` payload；query本身不追加、改写或重放业务event。Carrier中的`allowed_actions`来自权威Version状态集合，仅供后续authorization适配器裁剪，不能证明当前principal具有任何capability；P3-05没有identity/RBAC、approve/reject/publish/export授权行为。

## TASK-P3-06 edit/lock audit slice

Command context只接受server-resolved `edit`或`lock` capability、sanitized actor reference、auth-policy version、UTC、code commit及可选parent audit reference；客户端carrier中的`required_capability`必须等于command-derived值，但不获得授权权威。Production没有真实mapping时在任何source读取或idempotent replay前default-deny。

成功new DRAFT与`EDIT_SCHEDULE`/`SET_LOCK`/`REMOVE_LOCK` AuditEvent在同一transaction提交。显式`SUBMIT_FOR_REVIEW`在第二次fresh PASS后把同一manual DRAFT CAS为READY，并在同一transaction追加独立event。Event记录actor/capability/reason、request fingerprint、hashed key reference、source/new Version、before/after state、fresh validation lineage、correlation、parent及成功result；raw key、credential、SQL、payload全文和stack均不进入event。Same request replay返回原event且不改写`result.replayed=false`历史事实。TASK-P3-06不持久化失败Version或拒绝audit；若后续需要attempt audit，必须单独定义失败event policy并保持成功历史不可改写。

## TASK-P3-07 approval/rejection authorization slice

`ApprovalDecisionContext`只接收server-resolved authenticated flag、stable actor reference、capability set、exact ScheduleVersion scope、test-policy version、Production binding flag、UTC/code commit和可选parent event；`workspace-command.v1`仍不允许client声明actor/role/capability authority。Simulation只接受名称显式包含test/simulation、`production_binding=false`且resource为synthetic的policy；Production即使carrier/context声称`approve`或`reject`也在任何source/result lookup前固定`PRODUCTION_AUTHORITY_UNAVAILABLE`，OPEN-010保持`OPEN`。

APPROVE/REJECT必须分别精确匹配`approve`/`reject`与resource scope。授权通过后才读取durable audit/source；成功仅把同一ID/content的READY carrier以CAS推进APPROVED或REJECTED，并在同一transaction追加一条`DECISION` AuditEvent。Same scope/key/request从原audit重放，different fingerprint冲突；audit失败回滚state。高风险capability/scope/authentication/Production拒绝只追加无source/lineage/before/after引用的sanitized `DENIED` event且不读取resource；非法actor、空reason或credential-like reason因无法形成安全carrier而在audit前拒绝。DENIED event的`resolved_capability`表示本次被评估的server-derived capability，不代表grant。

本slice不选择identity provider或真实role，不关闭OPEN-010，不形成HTTP/UI、publish/export、retention/SIEM或Production approval/readiness。`p3-approval-decision-report.v1`本地8/8仅是Simulation/Test与临时SQLite行为证据；exact provider仍是Task closure前置条件。

## TASK-P3-08 publication authorization and audit slice

PUBLISH使用独立scope=`plane/PUBLISH/ScheduleVersion/SIMULATION_INTERNAL`与hashed raw-key reference。Server context必须先验证authenticated、`publish` capability、exact ScheduleVersion scope、显式Simulation/Test policy、synthetic resource和`production_binding=false`，然后才允许读取success audit、source或current reference。Production在任何resource/replay lookup前以`PRODUCTION_AUTHORITY_UNAVAILABLE`拒绝，只能追加`WORKSPACE_INTERNAL`、无source/lineage/state reference的sanitized DENIED audit；OPEN-002/010保持OPEN。

成功event固定`intent_type=PUBLICATION`、APPROVED source/PUBLISHED new reference、完整既有lineage、actor/policy/capability/reason/request/key/correlation/code与SUCCEEDED result，并与publish/supersede/current/result同事务。Same request只重放历史logical result且不改写event；different fingerprint冲突。该slice不选择真实RBAC/SSO、external target、HTTP/UI、ExportJob、retention/SIEM或Production authority/readiness。

Export authorization由server context提供authenticated actor、`export` capability、Schedule/Job scope与policy；在Job/source/replay lookup前执行，Production提前default-deny。Denied Simulation request只append sanitized audit，不保存raw key或泄露resource existence。CREATE/attempt/retry/fail/cancel/complete的ExportJob CAS与对应append-only AuditEvent处于同一事务；heartbeat是同lease operational CAS。冻结audit action enum不新增pair，lifecycle phase由deterministic event ID、before/after/result表达。

## TASK-P3-10 HTTP authorization adapter

HTTP层只从Bearer解析器获得stable principal reference、policy version、capability与resource scopes，并为17个operation在application委托前计算唯一required capability。Client body/header不得提升role、capability、actor或Production binding。缺失/非法Bearer为401；未授权capability/scope为403；provider异常收敛为可重试sanitized 503，denial audit sink异常收敛为sanitized 500，两者都不进入application；Production在principal provider lookup和application调用前恒为403且对应调用计数为0。

高风险拒绝使用sanitized `PlanningWorkspaceAuthorizationDenial`记录operation、actor reference、resource scope、policy、reason、correlation和UTC；Bearer/raw credential、SQL、stack、资源内容和绝对路径不得进入sink。默认provider/sink不形成真实identity或SIEM，OPEN-010保持OPEN；本地security/contract/integration和8/8 machine report通过，exact provider待提交后复验。
