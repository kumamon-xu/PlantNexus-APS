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

| Task | 目标 | 依赖 |
|---|---|---|
| TASK-P0-01 | Repository/document governance skeleton | 文档基线 |
| TASK-P0-02 | Requirements、NFR/ENG 与追踪机制 | P0-01 |
| TASK-P0-03 | Domain contract 与 Schema skeleton | P0-01/02 |
| TASK-P0-04 | Constraint、State、Error、Capability contracts | P0-02/03 |
| TASK-P0-05 | Simulation contracts 与 module skeleton | P0-03/04 |
| TASK-P0-06 | SIM-MINIMAL-001 与人工 Golden Schedule | P0-05 |
| TASK-P0-07 | Illegal Fixtures 与 Validator Rule Sheet | P0-04/06 |
| TASK-P0-08 | CI、logging、DB、worker、health skeleton | P0-01/02 |
| TASK-P0-09 | P0 Exit Gate 审计 | P0-01～08 |

状态由 Task front matter 记录：`planned`、`ready`、`in_progress`、`blocked`、`done`、`cancelled`。只有真实验收证据存在时才能标记 done。

每张 Task Card 必须在开始前完成文档影响分析：填写 `Documentation impact`、明确的 `Documents to update`、理由、匹配的 change-impact matrix 行和 `Traceability updates`。禁止使用“相关 docs”作为路径；没有文档变化也必须提交有依据的 `none` 结论。
