---
doc_id: MILESTONE-P3
title: P3 — Planning Workspace
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [68, 69, 77, 78]
last_reviewed: 2026-08-19
---

# P3 — Planning Workspace

## Outcome

实现 Gantt、Resource Load、Order View、ScheduleVersion、Comparison、Lock、Approval、Reject、Publish、Export 和 Audit 工作区。

## Gate

DRAFT/REJECTED 不可发布，仅 APPROVED 可发布；PUBLISHED immutable；export idempotent。Gantt 编辑使用 UI Command→Server Validation→New Draft→Validator，不能直接更新 published schedule。

详细页面、API payload、权限矩阵在实现前形成；审批责任受 OPEN-010 约束。
