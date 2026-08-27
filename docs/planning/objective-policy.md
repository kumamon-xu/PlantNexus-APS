---
doc_id: DOC-PLAN-004
title: Objective Policy
status: baseline
spec_version: 0.3.0
phase: P0-P4
normative: true
source_sections: [28, 35, 50, 52, 53]
last_reviewed: 2026-08-28
---

# Objective Policy

## TASK-P4-06 pure OBJ-002 measurement

本Task实现的calculator只从immutable base/new assignments、complete active universe与priority-4 SOFT lock projection复算`(soft violations, changed existing, resource changes, absolute start shift seconds)`。全部分量使用integer seconds并保持signed delta与absolute aggregate分离；same inputs产生相同bytes/vector，禁止float、Big-M或私有权重。Metadata-only变化不计movement，ADDED为零movement，REMOVED必须有completion fact。

这只是PlanningPolicy v2的reporting/completeness consumer，不修改Policy carrier，也不进入CP-SAT objective builder/strategy。Delivery→Stability→Makespan的多阶段冻结、value/bound/stop evidence和fresh candidate validation仍由TASK-P4-07负责；本地向量PASS不能声明Solver stage已形成。

## TASK-P4-05 objective boundary

PlanningPolicy v2 carrier继续声明Delivery→Stability→Makespan顺序，但本Task只解析freeze section并输出SOFT与非冻结base分类；没有构造OBJ-002整数向量、调用多阶段Solver、应用hint或计算objective value/bound。显式/derived HARD永不通过objective放松，SOFT的偏离和movement成本仍由TASK-P4-06/07实现。

## TASK-P4-02 PlanningPolicy v2 contract

Machine carrier现固定三阶段exact lexicographic顺序：OBJ-001 Delivery、OBJ-002四元Stability、OBJ-003 Makespan；每阶段保留sense/value/bound/budget/stop evidence。任何weighted blend、隐式优先级或Production默认均不可表示。此处只形成Policy/Report Schema和sample，P4-07才执行求解。

## TASK-P4-01 accepted OBJ-002 allocation

ADR-0014已固定TASK-P4-06拥有Stability/ChangeReport pure calculation，TASK-P4-07实施`hard feasibility → Delivery/OBJ-001 → Stability/OBJ-002 → Makespan`。OBJ-002不是单一加权分数，而是`soft_lock_violation_count → changed_existing_operation_count → resource_changed_count → total_absolute_start_shift_seconds`的整数词典序向量；每层value/bound/stop reason/provenance必须独立报告。当前OBJ-001机器合同与实现不变，P4行为仍未形成。

硬约束可行性优先于所有目标。目标采用词典序分轮，禁止用未经论证的浮点权重混合。

## OBJ-001 Delivery

首先最小化 weighted tardiness。权重和迟交业务含义受 OPEN-006 约束；在关闭前可用明确版本化的 Simulation Policy 测试，但不能称为生产规则。

## OBJ-002 Stability

仅 Replan 阶段使用，在 Delivery 等价的候选中最小化计划变化，包括：

- resource change；
- start time deviation；
- changed operation count/movement。

HARD_LOCK 是约束，不属于 OBJ-002；SOFT_LOCK 通过本目标体现。旧计划 Hint 不保证稳定性。

比较只覆盖base与candidate共有且在new Snapshot仍active的operation。resource/start/end任一改变使`changed_existing_operation_count += 1`；resource不同另计，start UTC差值按整数秒绝对值求和。新urgent operation无base assignment，OBJ-002贡献为0但ChangeReport必须标记ADDED；由COMPLETED fact移出future Problem的operation只报告事实，不成为Solver可选收益。SOFT lock偏离作为向量第一分量，HARD/freeze-derived lock仍是约束。Hint不影响score或正确性。

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

## TASK-P2-05 feasibility-only objective boundary

Core model仍不调用`Minimize`/`Maximize`，不按OBJ-001引导搜索。为满足既有PlanningSolution stage shape，只在candidate产生后计算weighted tardiness，记录通用0 lower bound、相应gap与`OBJECTIVE_NOT_OPTIMIZED` stop reason；native OPTIMAL降级为业务FEASIBLE。

因此OBJ-001 execution仍由P2-08形成，OBJ-002/003继续deferred，不能比较候选质量或声称最优。OPEN-006及objective policy版本均不变。

## TASK-P2-06 objective boundary

Temporal constraints只收紧可行域；模型仍不调用`Minimize`/`Maximize`，precedence/calendar/material/transport telemetry也不是objective component。Candidate产生后仍按既有合同测量weighted tardiness、使用通用0 lower bound并明确`OBJECTIVE_NOT_OPTIMIZED`。

OBJ-001 execution继续由P2-08形成，OBJ-002/003保持deferred；不得把native OPTIMAL、temporal feasibility或较小makespan表述为目标最优。OPEN-006与Policy版本不变。

## TASK-P2-07 objective boundary

RUNNING与HARD lock只收紧可行域；SOFT lock明确不进入本Task模型、hint或post-solve stability cost。Candidate仍只后测weighted tardiness、使用通用0 lower bound并标记`OBJECTIVE_NOT_OPTIMIZED`。

OBJ-001 execution继续由P2-08形成，OBJ-002 Stability与OBJ-003保持deferred；不得把native OPTIMAL、fact/lock preservation或SOFT metadata reference表述为目标最优。OPEN-005/006与Policy版本不变。

## TASK-P2-08 OBJ-001 execution

OBJ-001现在以每个Demand全部active operation的最大`end_tick`作为completion，并计算`max(0, completion_tick*tick_seconds-due_offset_seconds)`；因此非tick-grid due也保留exact迟交秒数。每项乘显式正整数`priority_weight`后求和，单位固定为`priority_weighted_tardiness_seconds`，并在建模前检查CP-SAT int64上界。

模型只调用一次`Minimize`且不混入makespan、SOFT lock movement或浮点权重。OPTIMAL必须有value=bound/gap=0，FEASIBLE不得称最优，UNKNOWN不得称无解；4个tiny exhaustive cases与generated properties复核数值。Policy仍为`objective-policy.v1`单stage，OBJ-002/003继续deferred；OPEN-006未关闭，只有approved versioned Simulation source可执行。

## TASK-P2-10 Reference measurement boundary

Reference Scheduler不执行或声称OBJ-001优化；它在完整candidate通过formal Validator后，复用同一公式按Demand最大`end_tick`、exact due offset和Problem显式正整数priority计算`weighted_tardiness_seconds`，同时报告`max(end_tick) * tick_seconds` makespan与runtime。五种ordering只决定heuristic选择，不增加目标stage、浮点混合权重、SOFT stability或makespan优化。

因此`FEASIBLE`只表示Validator接受的完整candidate，`optimality_claim=NONE`；`HEURISTIC_FAILURE`也不得解释为不可行证明。Reference与Global Strategy的质量比较、warning及回归阈值仍由TASK-P2-12负责。SIM-ASSUMPTION-012只固定Simulation tie-break，OPEN-006仍OPEN，Production weight与dispatch policy没有形成。
