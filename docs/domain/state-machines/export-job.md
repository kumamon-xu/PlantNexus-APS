---
doc_id: DOC-STATE-003
title: ExportJob 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [34, 65, 66, 67]
last_reviewed: 2026-08-19
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

`EXPORTED` 与 `CANCELLED` 为终态。`EXPORT_FAILED` 不是成功也不是永久终态；只有显式 retry 才能回到 EXPORTING。任何其他 pair 返回 `INVALID_STATE_TRANSITION`。Worker lease/heartbeat、存储提交、外部发布副作用和真实 retry 实现仍由 TASK-P0-08/P3 负责。

机器来源为 [`state-machines.v1`](../../../schemas/rules/state-machines.v1.yaml)，名称 envelope 为 [`state-transition.v1`](../../../schemas/json/state-transition.schema.json)，TEST-STATE-TRANSITION-001 只验证纯合同。
