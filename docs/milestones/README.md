---
doc_id: DOC-MILESTONE-INDEX
title: Milestone 索引
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84]
last_reviewed: 2026-08-19
---

# Milestone 索引

项目沿用总规 P0～P7，不建立 M0～M7 平行编号。

| Phase | 名称 | 主要结果 |
|---|---|---|
| P0 | Executable Specification | 固定排什么、什么算正确 |
| P1 | Data & Snapshot | 正式/仿真输入走同一确定性数据链 |
| P2 | CP-SAT Vertical Slice | C-001～C-011 + OBJ-001 闭环 |
| P3 | Planning Workspace | 版本、比较、审批、发布和导出 |
| P4 | Dynamic Replanning | 执行异常、事实保护、稳定性与 ChangeReport |
| P5 | Advanced Capabilities | 仅按证据逐项增加高级能力 |
| P6 | AI Duration Prediction | 核心稳定后的版本化预测接口 |
| P7 | Reality Calibration | 历史重放、现实差距与生产边界 |

Milestone 定义 outcome 和 exit gate，不等同 Sprint。只有当前 Phase 创建详细 Task Card；更新 `current_phase.md` 需要 Gate 的真实证据和用户确认。

P0 当前进度：TASK-P0-01～08 已完成 executable contracts、Simulation/Golden/Validator 和 engineering/CI skeleton；TASK-P0-09 的原 [独立审计](P0-exit-gate-audit-report.md) 忠实发现旧 Task diff handoff/provider evidence 缺口。TASK-P0-10 已交接 workflow/test，并以 implementation commit `036bc23bc0ac4d60aab131c0d44eda5508e844d4`、GitHub run `32228647627`、artifact `9356432918` digest 和 protected `main` required `validate` 证据关闭两项 gap。superseding audit 的 Schema、Golden、Validator Rule Sheet、Scenario replay、Repository Build、CI 和 PROD_OPEN registration 全部 `PASS`，P0 Gate 为 `READY`。P0 Milestone 仍保持 `active`、P1～P7 保持 `planned`，直到用户另行确认 phase transition；不自动进入 P1。
