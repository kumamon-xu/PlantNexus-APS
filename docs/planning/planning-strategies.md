---
doc_id: DOC-PLAN-002
title: PlanningStrategy 规则
status: baseline
spec_version: 0.3.0
phase: P0-P5
normative: true
source_sections: [14, 75, 81, 82]
last_reviewed: 2026-08-19
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
