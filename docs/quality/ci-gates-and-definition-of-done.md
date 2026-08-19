---
doc_id: DOC-QUAL-006
title: CI Gate 与 Definition of Done
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 72, 74, 76, 78, 80, 89, 100, 101]
last_reviewed: 2026-08-19
---

# CI Gate 与 Definition of Done

## 常规验收命令目标

Backend：Ruff、type check、unit/contract/integration tests。Frontend：test 和 production build。P2 后增加 golden/simulation；涉及 Solver 的任务增加 PR Benchmark。

具体命令以仓库脚本和 lockfile 落地为准；在这些文件不存在前不宣称已运行。

文档一致性自动检查的实现合同见 `documentation-consistency-checks.md`；其目标实现任务为 TASK-P0-02。

## Task Done

任务完成至少满足：

- Task Card 的目标、允许范围和明确排除项均遵守；
- Requirement/NFR/ENG 追踪已更新；
- Schema/Contract/ADR 影响已处理；
- Task Card 已填写文档影响、明确文档路径和追踪更新；
- change-impact matrix 要求的文档均已更新，或存在经审查的 `Documentation impact: none` 理由；
- 成功、错误、边界和回滚行为有测试证据；
- 没有新增未登记 PROD_OPEN/SIM_ASSUMPTION；
- 文档与实现一致；
- 文档一致性检查通过；
- 验收命令实际通过并记录结果。

## Phase Done

只有对应 Milestone 的全部 Exit Gate 有真实 Artifact 证明时才能更新 `current_phase.md`。任务全部关闭不自动等于 Phase 通过，未经确认不得进入下一阶段。
