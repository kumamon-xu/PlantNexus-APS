---
doc_id: DOC-PLAN-008
title: 动态重排设计合同
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [21, 28, 35, 47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-19
---

# 动态重排设计合同

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
