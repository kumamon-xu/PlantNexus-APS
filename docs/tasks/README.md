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
| [TASK-P2-01](P2/TASK-P2-01-planning-problem-v2-contract-gap-closure.md) | PlanningProblem v2合同缺口闭环 | P2-00 | `done` |
| [TASK-P2-02](P2/TASK-P2-02-planning-machine-contracts-and-status.md) | Planning机器合同与status | P2-01 | `done` |
| [TASK-P2-03](P2/TASK-P2-03-ortools-backend-foundation.md) | OR-Tools与Backend foundation | P2-02 | `done` |
| [TASK-P2-04](P2/TASK-P2-04-formal-independent-schedule-validator.md) | 正式独立ScheduleValidator | P2-01/02 | `in_progress` |
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

TASK-P2-00～03已`done`。P2-03的Diff base固定为`f73f8c90af94d3c9b05ecc10b6c999594a3b7d66`，ADR-0011先于dependency变更接受；implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的required run/job/artifact均success。用户已授权TASK-P2-04；它以clean/provider-verified `4c66dce3b919a53816005c4aebf4983db19a6108`为Diff base并进入`in_progress`。P2-05～14继续`planned`且未获启动授权。

P2-04限定为正式Problem/Solution独立C-001～C-011判定、stable ValidationReport/Error、mutation/property/independence machine evidence及CI handoff；不得修改Backend、合同Schema、fixture历史bytes、dependency、objective、Benchmark或P3。P2-05及以后不会由本Task自动启动。

P2-04本地实现已通过6/6 machine checks、13个mutation、11个C-ID、14个hard violations及6个duration/order examples；Task在完整local Gate与exact implementation provider artifact闭环前仍为`in_progress`。P2-05依赖本Task=`done`且必须另获用户授权。

P2-03本地39 focused、319 full、Ruff/Pyright、6/6 foundation、5/5 P2-02 compatibility及6/6 historical Engineering均PASS；provider artifact再次证明6/6与50 paths/9 rows/0 issues，因此索引状态为`done`。
