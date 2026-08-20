---
doc_id: DOC-PLAN-004
title: Objective Policy
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [28, 35, 50, 52, 53]
last_reviewed: 2026-08-19
---

# Objective Policy

硬约束可行性优先于所有目标。目标采用词典序分轮，禁止用未经论证的浮点权重混合。

## OBJ-001 Delivery

首先最小化 weighted tardiness。权重和迟交业务含义受 OPEN-006 约束；在关闭前可用明确版本化的 Simulation Policy 测试，但不能称为生产规则。

## OBJ-002 Stability

仅 Replan 阶段使用，在 Delivery 等价的候选中最小化计划变化，包括：

- resource change；
- start time deviation；
- changed operation count/movement。

HARD_LOCK 是约束，不属于 OBJ-002；SOFT_LOCK 通过本目标体现。旧计划 Hint 不保证稳定性。

## OBJ-003 Makespan

只在 Delivery 和 Stability 等价时作为 tie breaker。

## 报告

SolverReport 必须分阶段记录每一轮目标值、bound、停止原因和求解预算，不能只输出一个无法解释的混合分数。Reference Scheduler 比较至少报告 feasibility、weighted tardiness、makespan 和 runtime。

## TASK-P2-01 OBJ-001 input contract

`planning-problem.v2.delivery_demands`现在为每个active DemandOrder显式保存`due_at_utc`及其source三元组、非boolean正整数`priority_weight`及独立priority source三元组。Builder要求priority mapping与active demand集合精确相等；缺失、额外、零/负、boolean或无版本来源均拒绝，不猜Production weight。

该字段使OBJ-001输入可表达，但本Task不计算tardiness、weighted sum、lexicographic stages或SolverReport，也不宣称目标形成。P2-08才可实现Delivery objective；OPEN-006关闭前Production policy仍阻断。SOFT_LOCK不会借本合同启用OBJ-002，OBJ-003也未实现。

## TASK-P2-02 objective-stage contract

PlanningPolicy v1在当前P2 slice只允许一个stage：`stage_index=1`、`OBJ-001`、`WEIGHTED_TARDINESS`、`MINIMIZE`。PlanningSolution/SolverReport逐字引用该stage，并按status约束objective/bound/gap；非负整数Delivery objective使用`(objective-best_bound)/max(1, objective)`报告relative gap。SolveLimits的显式wall-time是该stage预算上限。此处固定的是报告和consumer machine contract，不是tardiness计算或CP-SAT objective实现。

总规的Delivery→Stability（Replan）→Makespan顺序继续有效，但OBJ-002/OBJ-003在本合同版本中explicit deferred，不能作为额外stage或混合权重加入。P2-08实现OBJ-001时必须消费此版本合同；未来启用OBJ-002/003需要独立Task/version，且OPEN-006关闭前仍不得生成Production权重。

## TASK-P2-03 no-objective review

Foundation不调用`Minimize`/`Maximize`，不读取OBJ-001 weight，也不计算objective/bound/gap。Empty native model的OPTIMAL没有业务objective，不能作为OBJ-001 execution或quality evidence。P2-08边界、OBJ-002/003 deferred状态和OPEN-006均不变。
