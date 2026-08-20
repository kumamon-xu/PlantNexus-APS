---
doc_id: DOC-TASK-INDEX
title: Task Card 索引
status: living
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [2, 6, 73, 74, 75, 76, 98, 99, 100]
last_reviewed: 2026-08-20
---

# Task Card 索引

当前Phase为P2。P0/P1 Task作为terminal历史保留；只有当前P2允许详细Task Card，P3～P7继续只保留Milestone。

## Completed history

- TASK-P0-01～10全部`done`，P0 Milestone=`completed`。
- [TASK-P1-01～12](P1/)全部`done`；[P1 audit](../milestones/P1-exit-gate-audit-report.md)=`READY`且用户已批准transition，P1 Milestone=`completed`。

## P2 execution order

| Task | 目标 | 依赖 | 状态 |
|---|---|---|---|
| [TASK-P2-00](P2/TASK-P2-00-phase-transition-and-task-planning-governance.md) | Phase transition、Task plan与batch CI治理 | P1-12 | `done` |
| [TASK-P2-01](P2/TASK-P2-01-planning-problem-v2-contract-gap-closure.md) | PlanningProblem v2合同缺口闭环 | P2-00 | `planned` |
| [TASK-P2-02](P2/TASK-P2-02-planning-machine-contracts-and-status.md) | Planning机器合同与status | P2-01 | `planned` |
| [TASK-P2-03](P2/TASK-P2-03-ortools-backend-foundation.md) | OR-Tools与Backend foundation | P2-02 | `planned` |
| [TASK-P2-04](P2/TASK-P2-04-formal-independent-schedule-validator.md) | 正式独立ScheduleValidator | P2-01/02 | `planned` |
| [TASK-P2-05](P2/TASK-P2-05-cp-sat-core-assignment-resource-model.md) | CP-SAT core assignment/resource | P2-03/04 | `planned` |
| [TASK-P2-06](P2/TASK-P2-06-cp-sat-temporal-calendar-material-model.md) | temporal/calendar/material | P2-05 | `planned` |
| [TASK-P2-07](P2/TASK-P2-07-execution-facts-and-hard-lock-model.md) | execution facts/HARD lock | P2-06 | `planned` |
| [TASK-P2-08](P2/TASK-P2-08-delivery-objective-and-global-strategy.md) | OBJ-001与Global Strategy | P2-02/05/06/07 | `planned` |
| [TASK-P2-09](P2/TASK-P2-09-golden-scenario-property-integration.md) | Golden/scenario/property integration | P2-04～08 | `planned` |
| [TASK-P2-10](P2/TASK-P2-10-reference-schedulers.md) | 五个Reference Schedulers | P2-01/02/04 | `planned` |
| [TASK-P2-11](P2/TASK-P2-11-kpi-solver-report-and-export-closure.md) | KPI/report/internal Export | P2-08/09 | `planned` |
| [TASK-P2-12](P2/TASK-P2-12-benchmark-runner-xs-s-m.md) | BenchmarkRunner与XS/S/M | P2-08～11 | `planned` |
| [TASK-P2-13](P2/TASK-P2-13-p2-vertical-slice-gate-evidence.md) | Vertical Slice Gate evidence | P2-01～12 | `planned` |
| [TASK-P2-14](P2/TASK-P2-14-p2-exit-gate-audit.md) | P2 Exit Gate Audit | P2-01～13 | `planned` |

## Lifecycle and planning-batch rules

状态使用`planned`、`ready`、`in_progress`、`blocked`、`done`、`cancelled`。进入`in_progress`前必须确认全部依赖`done`、用户授权、允许范围与文档影响，再把即时完整40字符HEAD写入Diff base；P2 Task还必须明确Start gate、Dependency changes、ADR impact和Provider evidence。

普通CI event range仍只能变更一张current-phase Task Card。唯一例外是初始phase-planning batch：必须由新建`TASK-Pn-00`、`Task batch role: phase-planning-owner`、有效Diff base且`in_progress/done`的唯一owner归属；其他卡必须同range新建、role=`phase-plan-member`、保持`planned/ready`且不得预填implementation SHA。历史卡、既有成员、多个owner或active/done成员均硬失败。选择owner后仍按owner Diff base检查全部scope/Impact Rule。

TASK-P2-00只完成本次治理工作，implementation `3298229fae89a54e0641f5907ad90c4fa81569bf` / run `32332003608` / artifact `9393345593`已闭环；P2-01～14未获本次实现授权且均为`planned`。建议首先另行授权P2-01。每个后续Task完成本地验收、提交并直接push当前`main`后，必须核验exact required `validate`和artifact；失败run保留且阻断closure。
