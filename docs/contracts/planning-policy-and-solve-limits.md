---
doc_id: DOC-CONTRACT-004
title: PlanningPolicy 与 SolveLimits 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [13, 28, 29, 35, 57, 96]
last_reviewed: 2026-08-19
---

# PlanningPolicy 与 SolveLimits 合同

## PlanningPolicy

PlanningPolicy 描述业务允许的计划策略，例如目标层级、交期权重来源、Replan 稳定性、freeze/lock 语义。V1 目标按词典序执行：Delivery → Stability（Replan）→ Makespan。

Policy 不得包含随意混合的 `0.6/0.3/0.1` 权重，不得允许关闭硬约束。未确认的业务优先级/冻结窗口分别引用 OPEN-006/005。

## SolveLimits

SolveLimits 描述计算预算，例如 wall time、worker/resource limit 和允许的求解参数。它可以终止搜索，但不能改变业务事实、候选设备、duration 或 Constraint。

## 可追溯性

每次运行必须记录 Policy version、limits、Solver exact version 和完整参数。相同 Problem/Policy/Limits 不保证相同 Gantt 排序，但必须满足相同合同和可重放诊断。

## 状态语义

Limits 到期且 Solver 不能给出认证结论时返回 UNKNOWN，并映射 `NO_SOLUTION_WITHIN_LIMIT`。有已认证可行解时可以返回 FEASIBLE，但不得描述为最优。
