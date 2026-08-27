---
doc_id: DOC-STATE-003
title: ExportJob 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [34, 65, 66, 67]
last_reviewed: 2026-08-27
---

# ExportJob 状态机

## TASK-P3-16 display-label review

`official-zh-cn-terminology.v1`为CREATED/EXPORTING/EXPORTED/EXPORT_FAILED/CANCELLED提供双语展示label；Schema、API、repository、worker、manifest、transition与error中的machine value保持英文。未知Job state显示raw值并fail visibly，中文“已导出”不从文件存在推断，也不等同Publish或external transfer。TASK-P3-16已形成该display-only mapping与本地zero-wire-drift evidence，exact provider待形成；state pair、package、migration与后端测试零变化，TASK-P3-17最终独立复验。

## TASK-P3-14 state Gate

Gate两轮消费P3-09公开report，核对PENDING/RUNNING/EXPORTED/FAILED既有pair、terminal immutability、same-key replay与显式retry，并单独证明unpublished source返回`STALE_SOURCE`。不增加worker、queue、external target或状态pair。

## TASK-P3-13 EXPORTED retrieval review

第18个HTTP operation只从已有EXPORTED terminal事实读取verified artifact；它不claim、heartbeat、complete、fail、retry或cancel，也不新增self-transition。Download要求v2 Job=`SIMULATION`/`SIMULATION_INTERNAL`/`EXPORTED`、positive attempt与exact artifact/audit lineage；其他state返回显式conflict/failure。5 states、6 pairs、lease/attempt/CAS和worker completion语义保持不变，Export仍不等于Publish或external transfer。

```text
CREATED
→ EXPORTING
→ EXPORTED

CREATED / EXPORTING
→ CANCELLED

EXPORTING
→ EXPORT_FAILED
```

## 合同

ExportJob 必须幂等、可重试并有 audit trail。至少持久化：

```text
id
idempotency_key
schedule_version_id
target
status
attempt
heartbeat / lease
started_at
finished_at
artifact_manifest
error
```

## 重试语义

- 同一个 idempotency key 和等价输入返回相同逻辑成果；
- 内容 hash/manifest 用于检测重复或不一致生成；
- Worker 崩溃不能造成永久 EXPORTING，应被 lease/heartbeat 检测；
- 失败重试不得重新触发一次业务发布；导出与外部发布副作用必须明确分开或共同受幂等控制。

## 成功条件

只有所有必需文件生成、manifest 可校验且存储提交成功后，才能进入 EXPORTED。部分文件不得以成功成果包对外暴露。

## P0 versioned transition table

| From | Allowed to | Guard |
|---|---|---|
| CREATED | EXPORTING、CANCELLED | 接受 idempotency key/attempt，或在开始前取消 |
| EXPORTING | EXPORTED、EXPORT_FAILED、CANCELLED | 全部 artifact+manifest 原子提交才成功；失败/取消不得暴露部分成功 |
| EXPORT_FAILED | EXPORTING | 显式 retry、attempt 递增、保持同一幂等合同与 audit |

`EXPORTED` 与 `CANCELLED` 为终态。`EXPORT_FAILED` 不是成功也不是永久终态；只有显式 retry 才能回到 EXPORTING。任何其他 pair 返回 `INVALID_STATE_TRANSITION`。

机器来源为 [`state-machines.v1`](../../../schemas/rules/state-machines.v1.yaml)，名称 envelope 为 [`state-transition.v1`](../../../schemas/json/state-transition.schema.json)，TEST-STATE-TRANSITION-001 只验证纯合同。

## TASK-P0-08 worker primitive boundary

P0-08 形成 business-neutral `JobRecord` pure transitions：新任务 QUEUED，claim 后 RUNNING/attempt+1/lease，合法 owner heartbeat 延长 lease，lease 到期由 scanner-style `mark_stalled` 变为 STALLED，STALLED 可被新 worker claim 且 attempt 再增；成功/失败 completion 需要未过期 owner lease。owner mismatch、expired lease、invalid transition 和 failure-code 缺失均为不同 Python exception/validation path。

`IdempotencyStore` protocol 与 thread-safe process-local reference implementation 固定 replay/conflict 语义；Alembic baseline 建立 generic metadata tables。但当前没有 ExportJob repository、`CREATED/EXPORTING/EXPORTED/EXPORT_FAILED/CANCELLED` persistence、manifest/storage commit、distributed lock、crash scanner、retry scheduler、Export/Publish task 或业务副作用。因此 P0-08 只形成 NFR-REL-001/TEST-IDEMPOTENCY 的 primitive slice，不能宣称 ExportJob 实现；`state-machines.v1` 未改变。

## TASK-P2-02 review

PlanningSolution/SolverReport v1没有ExportJob字段、storage side effect或publish action。P2-02不创建internal Export package、不执行任何ExportJob transition，也不修改`state-machines.v1`；P2-11和P3的export/publish边界继续`PLANNED`。

## TASK-P2-11 internal package boundary

`p2-internal-export.v1`只提供纯内存构建和本地同文件系统原子目录materialization。Manifest固定`export_job=NOT_CREATED`、`publication=NOT_STARTED`与`publishable=false`；实现没有ExportJob ID/idempotency key/attempt/lease/heartbeat、repository、storage target或外部副作用，也没有执行`CREATED → EXPORTING → EXPORTED`。

同一目标的exact byte replay仅验证文件级确定性；目标内容不同则返回conflict，I/O失败清理临时目录且不留下成功manifest。这是NFR-REL-001的P2 internal consistency slice，不等于business ExportJob retry或double-publish控制。状态机和`state-machines.v1`保持不变，P3实现仍须提供持久化、audit、target、lease/retry与发布隔离。

## P3 implementation allocation

P3-02形成ExportJob carrier，P3-03形成repository/migration，P3-09实现既有pair、atomic package、same-key replay/conflict与显式FAILED retry。EXPORTED/CANCELLED终态不可复活，Job状态不得改变ScheduleVersion publication；P3-10/13只调用application service，P3-14 Gate与P3-17 Audit复验，P3-16仅处理label。Production external target继续受OPEN-002/010/015阻止。

## TASK-P3-01 guard baseline

Export合同确认P3只从PUBLISHED ScheduleVersion创建ExportJob，并把Publish与Export分成独立idempotency scope和副作用。`CREATED→EXPORTING→EXPORTED/EXPORT_FAILED/CANCELLED`及`EXPORT_FAILED→EXPORTING`仍是唯一允许pair；same key/same fingerprint返回同一Job/artifact result，不重复package或Publish，不同fingerprint冲突。显式retry增加attempt并保持audit，不能复活EXPORTED/CANCELLED。

TASK-P3-01未创建`export-job.v1`、repository、lease/heartbeat/attempt、storage或worker；`state-machines.v1`不变。外部target、Production容量/SLA和side effect继续受OPEN-002/010/012/015阻止。
## TASK-P3-02 carrier alignment

`export-job.v1`只允许`CREATED/EXPORTING/EXPORTED/EXPORT_FAILED/CANCELLED`并按state约束attempt、lease/heartbeat、artifact/error和timestamps。Machine report复验既有六个allowed pair；idempotent replay不表示self-transition。Source必须是PUBLISHED ScheduleVersion，target仅`SIMULATION_INTERNAL`。

本Task不建表、不抢lease、不执行retry/cancel、不写artifact，也不改变ScheduleVersion state。Repository/CAS由TASK-P3-03形成，worker/package behavior由TASK-P3-09形成。

## TASK-P3-03 persistence primitive

`export_jobs`只接受`SIMULATION`/`SIMULATION_INTERNAL`且source必须匹配同plane的PUBLISHED ScheduleVersion。Creation以scope/key/request fingerprint和creation bytes exact-replay；state CAS只接受既有六个pair，claim/retry必须把attempt恰好加一，非claim transition保持attempt。Heartbeat是同一`EXPORTING` lease上的operational CAS，不登记为state self-transition；错误owner、expired lease、stale revision全部fail closed。

DB中的`lease_expires_at_utc`是调用者显式提供、不可由默认值补猜的storage coordination metadata，不进入`export-job.v1` carrier或job fingerprint；若未来需要对API暴露它，必须先发布新Schema版本。当前没有Celery business task、package writer、artifact manifest、external storage或自动retry；P3-09仍负责真实export行为。

## TASK-P3-04 zero-impact review

Validated output lifecycle在READY_FOR_REVIEW停止，`decision/publication`保持null，AuditEvent的`export_job_id`保持null；代码不导入ExportJob repository、exporter或worker，也不创建package/target/lease/attempt。ExportJob state、pair、carrier、table和P3-03持久化语义均无变化，P3-09仍是唯一business export owner。

## TASK-P3-06 zero-impact review

Edit/lock content command只创建DRAFT与command AuditEvent；review submit只执行ScheduleVersion既有DRAFT→READY pair。两者`export_job_id=null`且不导入ExportJob repository、worker或exporter。ExportJob state/pair/lease/attempt、PUBLISHED-only source gate和package contract均无变化；P3-09仍是唯一export behavior owner。

## TASK-P3-07 zero-impact review

APPROVE/REJECT AuditEvent继续固定`export_job_id=null`；decision service不导入ExportJob repository、worker、exporter或publication current reference。APPROVED不自动创建或排队ExportJob，REJECTED不可export。ExportJob五states/七pairs、lease/attempt/idempotency与PUBLISHED-only gate均无变化，P3-09仍是唯一export behavior owner。

## TASK-P3-08 zero-impact review

PUBLISH AuditEvent继续固定`export_job_id=null`；publication service不导入ExportJob repository、worker、exporter、manifest或storage。PUBLISHED只成为P3-09的source gate，不自动创建/排队ExportJob；SUPERSEDED历史版本不可作为新current export source。ExportJob五states/七pairs、lease/attempt/idempotency均无变化，P3-09仍是唯一export behavior owner。

P3-09现执行machine authority中的六个distinct allowed pair：CREATED→EXPORTING/CANCELLED、EXPORTING→EXPORTED/EXPORT_FAILED/CANCELLED、EXPORT_FAILED→EXPORTING；exact replay不是self-pair。Claim/retry递增attempt并创建future-expiry lease；heartbeat必须同owner/active lease且延长expiry；terminal释放lease。过期EXPORTING仅允许受审计恢复为FAILED或CANCELLED，再显式retry。EXPORTED/CANCELLED终态，artifact只在manifest完整写入后提交。

## TASK-P3-10 transport-only review

HTTP只暴露create/read/retry/cancel并传递exact Job/Schedule scope、v2 reference、idempotency与correlation；claim/heartbeat/fail/complete仍属worker/application边界，不由router执行。Retry/cancel的state failure仅映射为409，transport不增加state/self-pair/attempt/lease规则，也不把Export解释为Publish或external transfer。
