---
doc_id: DOC-PLAN-002
title: PlanningStrategy 规则
status: baseline
spec_version: 0.3.0
phase: P0-P5
normative: true
source_sections: [14, 75, 81, 82]
last_reviewed: 2026-09-11
---

# PlanningStrategy 规则

## P5 strategy Task final retirement

用户于2026-09-11最终退役TASK-P5-17～20及同批TASK-P5-03～16；这些`cancelled`卡现在为`FINAL_RETIRED/NOT_EXECUTED`，不得恢复或用于形成DecomposedStrategy、RollingHorizonStrategy或任何相关fallback。本轮P5定制高级策略方案作废，Global/`global-lexicographic-replan-cp-sat.v1`继续是唯一已形成策略。

未来可以重新审定Decomposition或Rolling Horizon，但必须从届时的真实需求、Benchmark、quality budget与运行边界重新建立versioned决策和全新Task/Test/Gate；不得继承TASK-P5-17～20的授权、参数、Diff base、依赖或Provider身份。下述P5段落保留为历史证据，不再构成可执行入口。

## TASK-P5-22 Exit audit strategy boundary

Exit审计fresh重放P5 qualification与portfolio Gate，确认selected strategy owner集合仍为空，Global/`global-lexicographic-replan-cp-sat.v1`仍是唯一已形成策略。Decomposition、Rolling Horizon和Hybrid均未进入执行图；空组合不会生成fallback、参数、registry或Feature Flag变更。

历史READY及双exact Provider不授权P6 strategy、Production选策、deployment或capacity/SLA；TASK-P5-22已完成，但不改变顶部最终退役决定。

## TASK-P5-21 Global-only aggregate replay

P5 portfolio的selected strategy集合为空。Gate fresh调用既有objective/strategy public machine boundary，继续得到`ONE_GLOBAL_CP_SAT_MODEL_NO_DECOMPOSITION_OR_FALLBACK`；Decomposition和Rolling Horizon没有被调用，空组合的advanced-strategy fallback为`NOT_APPLICABLE_EMPTY_SELECTED`。这里的“Global default”不是新增fallback逻辑，也没有参数、公式、Strategy registry或Feature Flag变更。

Gate PASS只是Simulation/development重放，不建立Hybrid、P6+、Production选策或capacity/SLA。

## TASK-P5-01 strategy decision

Decomposition与Rolling Horizon均为`DEFERRED`。冻结的XS/S/M replay全部PASS且没有触发§82 scaling/memory/model-explosion必要性；同时没有真实portfolio分布、可接受quality-loss预算、partition/merge政策或rolling window/step/overlap/handoff政策。Global/`global-lexicographic-replan-cp-sat.v1`继续是唯一已形成策略，不能因DEFERRED而推导Decomposed、Rolling或Hybrid实现。

## Historical P5 evidence-gated strategy allocation

P5历史执行期内，Global/`global-lexicographic-replan-cp-sat.v1`是唯一已形成策略。TASK-P5-01只评价Decomposition与Rolling Horizon必要性，TASK-P5-02只保留selected链；不存在因phase激活自动选择新strategy的路径。

该历史计划原把Decomposition分配给TASK-P5-17/18、Rolling Horizon分配给TASK-P5-19/20；四张卡现已最终退役，分配不再可执行。未来全新计划仍须重新评估scaling/memory/model-explosion、Global comparison、partition/merge、whole-horizon validation、quality impact、default-off及P4 regression，但这些条件不能复活原Task。Hybrid未形成且不得由历史组合推导。

## TASK-P4-07 implemented strategy

`global-lexicographic-replan-cp-sat.v1`是P4当前唯一已实现的Simulation replan strategy。它先验证PUBLISHED synthetic base、Policy/Limits、ReplanRequest、new Problem和effective-lock projection的exact lineage，再调用一个全局CP-SAT模型完成六轮词典序求解；base assignment只作为搜索Hint。strategy只组装SolverReport和raw evidence，无repository、state、API或Simulator副作用。

P2 single-stage strategy保持可回滚且未修改；P5 decomposition、rolling/hybrid、多工厂、alternative route、secondary resource、batch及sequence setup仍不支持。

## P4 planned strategy boundary

P4-07在既有Global Strategy上增加有界replan solve path，并可使用base schedule作为Hint，但Hint不构成事实、freeze或lock保护；独立Validator仍是acceptance authority。P4不引入P5 decomposition、rolling/hybrid、多工厂、alternative route、batch、secondary resource或sequence-dependent setup策略。本次没有策略实现或默认参数变化。

V1 默认且唯一批准的生产策略为：

```text
GlobalCpSatStrategy
```

一个 PlanningRun 对 PlanningSnapshot 中全部 V1 OperationInstance 统一建模，覆盖跨车间 precedence、候选资源、日历、release/material gates、execution facts 和 locks。

未来可能重新提案`DecomposedStrategy`、`RollingHorizonStrategy`，但只能使用重新审定后的全新计划与Task ID；原P5证据门控Task已最终退役。`HybridStrategy`未形成，不能由历史P5范围推导或实现。

## Decomposition 进入门

只有以下证据之一存在时才允许提案：

- Synthetic large benchmark 显示不可接受 scaling；
- Historical benchmark 显示不可接受 scaling；
- 模型内存超过部署预算；
- 高级约束导致模型爆炸。

提案必须包含 ADR、与 Global strategy 的比较 Benchmark、合并 Validator、质量影响报告和回滚策略。不能为了代码结构便利提前分解业务计划。

## TASK-P2-03 foundation boundary

本Task只建立`CpSatBackend` adapter，不创建`GlobalCpSatStrategy`、decomposition、rolling horizon或任何Reference Scheduler。Empty/model-invalid smoke不选择策略、不消费业务Problem facts，也不产生可比较schedule。P2-08仍负责唯一Global strategy与OBJ-001接线；任何分解策略仍需独立ADR和同口径Validator/Benchmark证据。

## TASK-P2-05 no-strategy core execution

Backend现可直接执行bounded core feasibility model，但仍未创建或选择`GlobalCpSatStrategy`，也没有decomposition、rolling horizon、warm start或Reference Scheduler。该直接调用只验证底层可行域与solution mapping，不构成策略层入口。P2-08继续独占Global strategy与OBJ-001搜索接线；P2-05不得被上层发布流程调用。

## TASK-P2-06 no-strategy temporal execution

Temporal约束直接组合进同一bounded Backend model，没有创建`GlobalCpSatStrategy`、分解、rolling horizon、warm start或Reference Scheduler。Calendar/precedence/material/transport correctness只证明底层可行域，不能作为策略选择或上层发布入口。

P2-08继续独占Global strategy与OBJ-001搜索接线；P2-06不得被Production workflow调用，也不提供策略质量比较。

## TASK-P2-07 strategy boundary

C-007/C-008直接组合进同一bounded Backend model，没有创建`GlobalCpSatStrategy`、freeze/replan strategy、warm start或Reference Scheduler。HARD lock是可行域等式，SOFT lock不被用作hint或cost；因此本Task不产生稳定性策略或计划变更比较。

P2-08继续独占Global strategy与OBJ-001搜索接线；P2-07不得被Production workflow调用，也不提供策略质量、动态Replan或publishability声明。

## TASK-P2-08 GlobalCpSatStrategy

`GlobalCpSatStrategy@global-cp-sat-strategy.v1`现为唯一可执行P2策略：先验证完整Problem与approved Simulation Policy/Limits/priority source，再对全部active operations调用一次complete C-001～C-011 Backend+OBJ-001模型，最后要求formal independent Validator PASS并组装SolverReport。不得按order/workshop/resource拆分，不存在rolling、fallback、warm start或Reference Scheduler。

Hard constraints定义可接受域且不能由目标放宽；OBJ-001只在该域内选择候选。当前Strategy是internal Simulation correctness入口，不批准、不发布、不创建ScheduleVersion；OPEN-006/011/012关闭和后续Gate前不得用于Production。任何decomposition/rolling/hybrid仍需新ADR与同口径Benchmark/merge Validator证据。
