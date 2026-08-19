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

P0 当前进度：TASK-P0-01～03 已完成 repository/governance/traceability 与 Schema set `1.0.0` 数据合同；TASK-P0-04 已完成 additive `1.1.0` rule/state/error/capability contracts；TASK-P0-05 已完成 additive `1.2.0` Simulation contracts/skeleton、empty Import replay 与 isolation tests；TASK-P0-06 已完成 `SIM-MINIMAL-001@1.0.0` deterministic correctness fixture、人工 Golden 与 non-empty replay；TASK-P0-07 已完成 fixture-local 独立 C-001～C-011 evaluator/13 类 mutation；TASK-P0-08 已完成 engineering/CI skeleton 与 90-test local acceptance。TASK-P0-09 与 P1～P7 保持 `planned`；外部 CI provider run 仍为 `NOT_RUN`，该进度不等于 P0 Exit Gate PASS。
