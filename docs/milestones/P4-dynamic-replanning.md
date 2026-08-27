---
doc_id: MILESTONE-P4
title: P4 — Dynamic Replanning
status: active
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-27
---

# P4 — Dynamic Replanning

## Activation

用户于2026-08-27在P3 Exit双提交provider与clean synchronized closure baseline精确通过后批准P3→P4。TASK-P4-00 phase-planning implementation `c94af400392418f9bb69509331fa8d1dff046184`的exact required provider/artifact已成功，本closure把P4-00标为`done`；P4-01～15均为`planned`成员且不会自动启动。P4-15是最后一项独立Exit Gate Audit。

## Outcome

实现 ExecutionEvent、ReplanRequest、Freeze Window、HARD/SOFT LOCK、OBJ-002、ChangeReport 和 Execution Simulator。

## Gate

连续模拟 Urgent Order、Machine Failure、Material Delay、Processing Delay、Early Completion；证明 facts/locks preserved、Validator PASS、ChangeReport complete，并比较重排前后 tardiness/stability。

生产 freeze window 由 OPEN-005 关闭；Simulation 值必须显式登记。

## Task allocation

| Task | Owner outcome | Depends on |
|---|---|---|
| TASK-P4-00 | Phase transition与完整规划治理 | P3-17 |
| TASK-P4-01 | Dynamic Replanning合同与三份具名P4 ADR（stable ID在Task启动时分配） | P4-00 |
| TASK-P4-02 | ExecutionEvent/Replan/ChangeReport等机器合同 | P4-01 |
| TASK-P4-03 | Event/Replan持久化与状态事务 | P4-02 |
| TASK-P4-04 | ExecutionEvent→事实→新Snapshot | P4-02/03 |
| TASK-P4-05 | Freeze Window与effective locks | P4-01/02/04 |
| TASK-P4-06 | OBJ-002 Stability与ChangeReport | P4-01/02 |
| TASK-P4-07 | Delivery→Stability→Makespan Solver/Validator | P4-04/05/06 |
| TASK-P4-08 | ReplanRequest应用与new DRAFT lineage | P4-03～07 |
| TASK-P4-09 | Deterministic Execution Simulator core | P4-02/04 |
| TASK-P4-10 | 五类连续disruption场景 | P4-05/08/09 |
| TASK-P4-11 | ChangeReport read/export integration | P4-06/08 |
| TASK-P4-12 | Dynamic Replanning HTTP API | P4-02/03/04/08/11 |
| TASK-P4-13 | Replanning Workspace UI/browser E2E | P4-09～12 |
| TASK-P4-14 | P4 Vertical Slice Gate | P4-01～13 |
| TASK-P4-15 | Independent P4 Exit Gate Audit | P4-14 |

P4 Gate必须连续而非单点地模拟Urgent Order、Machine Failure/Recovery、Material Delay、Processing Delay和Early Completion；每一步保存raw event/replan/change evidence并证明completed/running/HARD/freeze facts、independent Validator和ChangeReport completeness。TASK-P4-14的PASS不替代P4-15 fresh independent audit。

## P4/P5/Production boundary

P4不得引入secondary resource、batching、sequence setup、tool/fixture capacity、多Factory、替代工艺、rolling/decomposed/hybrid strategy等P5 advanced capabilities。真实Production freeze、priority/KPI authority、identity/approval角色、external adapter/target、deployment/UAT、容量和SLA继续由OPEN项阻塞；Simulation policy/scenario/actor/API/UI证据不得外推Production。
