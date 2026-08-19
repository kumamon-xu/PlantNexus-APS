---
doc_id: DOC-TASK-INDEX
title: Task Card 索引
status: living
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [2, 6, 71, 98, 99, 100]
last_reviewed: 2026-08-19
---

# Task Card 索引

当前只允许建立和执行 P0 Task。P1～P7 只有 Milestone，不提前创建 Task Card。

| Task | 目标 | 依赖 | 状态 |
|---|---|---|---|
| TASK-P0-01 | Repository/document governance skeleton | 文档基线 | `done` |
| TASK-P0-02 | Requirements、NFR/ENG 与追踪机制 | P0-01 | `done` |
| TASK-P0-03 | Domain contract 与 Schema skeleton | P0-01/02 | `done` |
| TASK-P0-04 | Constraint、State、Error、Capability contracts | P0-02/03 | `done` |
| TASK-P0-05 | Simulation contracts 与 module skeleton | P0-03/04 | `done` |
| TASK-P0-06 | SIM-MINIMAL-001 与人工 Golden Schedule | P0-05 | `planned` |
| TASK-P0-07 | Illegal Fixtures 与 Validator Rule Sheet | P0-04/06 | `planned` |
| TASK-P0-08 | CI、logging、DB、worker、health skeleton | P0-01/02 | `planned` |
| TASK-P0-09 | P0 Exit Gate 审计 | P0-01～08 | `planned` |

状态由 Task front matter 记录：`planned`、`ready`、`in_progress`、`blocked`、`done`、`cancelled`。只有真实验收证据存在时才能标记 done。

Task 进入 `in_progress` 时必须把切换前的完整 40 字符 HEAD commit SHA 写入 `Diff base`。验收器用 `Diff base..HEAD` 与 working tree 的路径并集检查范围和文档影响，使同一 Task 在提交前后都能复验。

每张 Task Card 必须在开始前完成文档影响分析：填写 `Documentation impact`、明确的 `Documents to update`、理由、匹配的 change-impact matrix 行和 `Traceability updates`。禁止使用“相关 docs”作为路径；没有文档变化也必须提交有依据的 `none` 结论。

本表是导航摘要；发生差异时以对应 Task Card front matter 为准。完成一个 Task 不会自动把下一个 Task 改为 `ready` 或开始执行。
