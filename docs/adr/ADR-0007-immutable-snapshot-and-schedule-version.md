---
doc_id: ADR-0007
title: 不可变 Snapshot 与版本化计划发布
status: accepted
spec_version: 0.3.0
phase: P1-P4
normative: true
source_sections: [23, 33, 35, 69, 78]
last_reviewed: 2026-08-19
---

# ADR-0007 — 不可变 Snapshot 与版本化计划发布

## Decision

PlanningSnapshot 创建后不可修改。计划的编辑、驳回修订和 Replan 均产生新 ScheduleVersion；PUBLISHED Version 不可修改，仅 APPROVED 可发布。

## Consequences

审计、重放和比较清晰，但存储和版本管理成本增加。Rollback 表示以历史版本为新 Draft/Replan 的参考，不直接改写历史发布记录。Publish/Export 必须幂等。
