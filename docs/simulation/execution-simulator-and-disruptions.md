---
doc_id: DOC-SIM-005
title: Execution Simulator 与异常模型
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-19
---

# Execution Simulator 与异常模型

ExecutionSimulator 输入 PUBLISHED ScheduleVersion，模拟生产时间推进并输出标准 `ExecutionEvent[]`。它不得直接修改计划数据库或调用特殊 Replan 入口。

## 事件

`OPERATION_STARTED`、`OPERATION_COMPLETED`、`OPERATION_DELAYED`、`MACHINE_DOWN`、`MACHINE_RECOVERED`、`MATERIAL_DELAYED`、`URGENT_ORDER_CREATED`、`LOCK_CREATED`、`LOCK_RELEASED`。

## Disruption 配置

设备故障、processing delay、urgent order、material delay 等开关和概率均为版本化 `SIM_ASSUMPTION`。相同 base schedule、simulator version、Scenario 和 seed 必须产生相同事件序列。

## 验证

动态重排至少检查：

- completed operation unchanged；
- running resource unchanged；
- HARD_LOCK unchanged；
- changed operation、machine change、time deviation 被记录；
- before/after tardiness 可比较；
- 新 ScheduleVersion Validator PASS。

P4 Gate 需要连续模拟 Urgent Order、Machine Failure、Material Delay、Processing Delay 和 Early Completion，而非仅单事件单元测试。
