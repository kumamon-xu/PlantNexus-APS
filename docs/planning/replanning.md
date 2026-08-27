---
doc_id: DOC-PLAN-008
title: 动态重排设计合同
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [21, 28, 35, 47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-27
---

# 动态重排设计合同

## TASK-P3-17 phase boundary

P3 Exit本地READY只覆盖Planning Workspace；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport和Execution Simulator仍属于P4且未授权、未创建详细Task、未实现。任何P3编辑仍是显式command→new DRAFT，不是dynamic replan。

## TASK-P3-16 localization / P4 boundary

双语展示只本地化现有P3 workspace术语，没有新增ExecutionEvent、ReplanRequest、freeze window、OBJ-002、ChangeReport、Execution Simulator或任何P4 route/action。中文“移动/重新分配/锁定”仍只是P3 copy-on-write command label，不是dynamic replan。TASK-P3-16 implementation已取得exact provider；TASK-P3-17最终审计后P3也不会自动进入P4，当前P4仍完全未启动。

## TASK-P3-14 boundary Gate

P3 Gate只重放P3 copy-on-write manual command与publication链，并证明PUBLISHED不能原地mutation；它不消费ExecutionEvent、不生成ReplanRequest/ChangeReport、不实现freeze/OBJ-002或ExecutionSimulator。最终TASK-P3-17已完成本地独立审计并等待provider闭环，P4只有另行phase transition授权后才能启动。

## TASK-P3-13 P3/P4 boundary review

Gantt drag/move/assign/lock是对单一immutable ScheduleVersion的人工command proposal，经既有P3-06 fresh Validator产生new DRAFT；它不读取ExecutionEvent、不生成ReplanRequest、不计算freeze window/OBJ-002/Stability/ChangeReport，也不调用Solver。UI的“refresh authority”仅重读Version/Job，不是replan trigger。

P3-14已完成有界Gate，P3-15已完成修订治理，P3-16已完成双语实现双提交provider复验；P3-17已完成本地独立Audit但在自身provider闭环前仍不能形成可关闭的P3 Exit。P4 dynamic replanning完全未启动；PUBLISHED immutable且rollback只能以新Version/command表达，不能修改执行事实或历史发布。

## 输入

ReplanRequest 引用 base ScheduleVersion、新 PlanningSnapshot、reason 和 freeze window。执行事实必须先进入权威事实层和新 Snapshot，不能作为 Solver 的临时隐藏参数。

## 约束与目标

1. COMPLETED 保持不变；
2. RUNNING resource 与历史事实保持不变，未来剩余占用固定；
3. HARD_LOCK 保持不变；
4. SOFT_LOCK/旧计划变化通过 OBJ-002 计价；
5. 旧计划可作为 Hint，但 Hint 不保证稳定；
6. Delivery 优先于 Stability，Makespan 最后；
7. 结果必须经过同一独立 Validator。

## ChangeReport

至少比较：changed operation count、resource changes、start shifts、lock/fact preservation、before/after tardiness 和不可避免变化原因。报告引用 base/new version 和两个 Snapshot/Problem hash。

## Dynamic Gate

Execution Simulator 连续注入 Urgent Order、Machine Failure、Material Delay、Processing Delay、Early Completion，检查 Facts Preserved、Locks Preserved、Validator PASS 和 ChangeReport Complete。

freeze window 的生产语义由 OPEN-005 决定；仿真值必须标记 SIM_ASSUMPTION。

## TASK-P2-07 static fact/lock boundary

本Task只在单次immutable Problem求解中保护COMPLETED/RUNNING facts与HARD lock；SOFT lock只保留metadata reference。它不接收ExecutionEvent，不生成ReplanRequest/ChangeReport，不执行freeze window或稳定性目标，也不改变ScheduleVersion。

因此C-007/C-008 correctness不能声明动态Replan已形成。P4事件幂等、事实演进、lock policy与change comparison仍须独立Task/Scenario/ADR证据；OPEN-005及现有SIM assumptions保持不变。

## P3/P4 boundary

P3 version comparison只比较两个immutable ScheduleVersion的既有assignment/KPI/lineage；Gantt edit/lock是人工新DRAFT命令，不是ExecutionEvent驱动的Replan。ExecutionEvent、ReplanRequest、freeze、OBJ-002 stability、ChangeReport和Execution Simulator全部继续属于P4，P3 Task/Schema/API/UI不得预埋可执行P4语义。

## TASK-P3-06 enforced P3/P4 boundary

形成的Move/Assign/Lock及manual review-submit service仅消费一个immutable Problem和source Version，不读ExecutionEvent、不构建Problem/Snapshot、不调用Solver，也不计算freeze window、OBJ-002或ChangeReport。SOFT lock仍是metadata，HARD lock只保护Version tuple；READY只表示通过fresh review gate，不是执行态或Replan结果。Machine report固定`solver_replan_obj002=NOT_IMPLEMENTED`和`p4_capabilities=NOT_IMPLEMENTED`；这些边界不得因“人工重排”名称而解释为动态Replan。
