---
doc_id: DOC-PLAN-002
title: PlanningStrategy 规则
status: baseline
spec_version: 0.3.0
phase: P0-P5
normative: true
source_sections: [14, 75, 81, 82]
last_reviewed: 2026-08-21
---

# PlanningStrategy 规则

V1 默认且唯一批准的生产策略为：

```text
GlobalCpSatStrategy
```

一个 PlanningRun 对 PlanningSnapshot 中全部 V1 OperationInstance 统一建模，覆盖跨车间 precedence、候选资源、日历、release/material gates、execution facts 和 locks。

未来可选 `DecomposedStrategy`、`RollingHorizonStrategy`、`HybridStrategy`，但当前不得实现。

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
