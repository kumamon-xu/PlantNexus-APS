---
doc_id: DOC-STATE-003
title: ExportJob 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [34, 65, 66, 67]
last_reviewed: 2026-08-24
---

# ExportJob 状态机

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

P3-02形成ExportJob carrier，P3-03形成repository/migration，P3-09实现既有pair、atomic package、same-key replay/conflict与显式FAILED retry。EXPORTED/CANCELLED终态不可复活，Job状态不得改变ScheduleVersion publication；P3-10/13只调用application service，P3-14/15复验。Production external target继续受OPEN-002/010/015阻止。
