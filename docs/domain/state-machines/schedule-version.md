---
doc_id: DOC-STATE-002
title: ScheduleVersion 状态机
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [30, 33, 35, 66, 69, 78]
last_reviewed: 2026-08-19
---

# ScheduleVersion 状态机

```text
DRAFT
→ READY_FOR_REVIEW
→ APPROVED
→ PUBLISHED
→ SUPERSEDED

READY_FOR_REVIEW
→ REJECTED
→（通过新 Planning/Editing command 产生新 DRAFT Version）
```

## 转移门

| 转移 | 必须满足 |
|---|---|
| DRAFT → READY_FOR_REVIEW | 独立 Validator PASS，硬违反数为 0，provenance 完整 |
| READY_FOR_REVIEW → APPROVED | 有权限的人工作出审批并记录 audit |
| READY_FOR_REVIEW → REJECTED | 记录 actor、reason；原版本保留 |
| APPROVED → PUBLISHED | 发布操作幂等、目标明确、没有 synthetic/production 混用 |
| PUBLISHED → SUPERSEDED | 新版本已成为当前生产参考；旧版本仍不可变 |

## 不变量

- DRAFT 和 REJECTED 不可发布；仅 APPROVED 可发布。
- PUBLISHED Version 不可修改或删除。
- Reject、Gantt 编辑、Replan 都产生新版本，不复用旧 ID。
- 发布重试不能 double publish。
- “Rollback”只表示选择历史版本作为新计划的参考输入；不得直接把历史 PUBLISHED 行改回当前。
