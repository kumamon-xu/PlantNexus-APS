---
doc_id: MILESTONE-P4
title: P4 — Dynamic Replanning
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80]
last_reviewed: 2026-08-19
---

# P4 — Dynamic Replanning

## Outcome

实现 ExecutionEvent、ReplanRequest、Freeze Window、HARD/SOFT LOCK、OBJ-002、ChangeReport 和 Execution Simulator。

## Gate

连续模拟 Urgent Order、Machine Failure、Material Delay、Processing Delay、Early Completion；证明 facts/locks preserved、Validator PASS、ChangeReport complete，并比较重排前后 tardiness/stability。

生产 freeze window 由 OPEN-005 关闭；Simulation 值必须显式登记。
