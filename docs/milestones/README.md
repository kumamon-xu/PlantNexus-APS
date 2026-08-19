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

P0 当前状态：TASK-P0-01～10 全部完成；[superseding audit](P0-exit-gate-audit-report.md) 的 Schema、Golden、Validator Rule Sheet、Scenario replay、Repository Build、CI 和 PROD_OPEN registration全部 `PASS`，P0 Gate=`READY`。用户于 2026-08-19 明确批准 phase transition后，P0转为 `completed`，历史失败/修复/provider evidence继续保留。

P1当前状态：[`P1 — Data & Snapshot`](P1-data-and-snapshot.md)为`active`，已创建TASK-P1-01～12；TASK-P1-01=`done`、TASK-P1-02=`in_progress`、TASK-P1-03～12=`planned`，最后一项是P1 Exit Gate Audit。P1-02工作版本已形成schema set`2.0.0`合同候选，但须本地验收、commit/provider CI闭环后才可标记done；当前不启动pipeline或P2。
