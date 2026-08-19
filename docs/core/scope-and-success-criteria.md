---
doc_id: DOC-CORE-001
title: V1 范围与成功标准
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 3, 4, 7, 8, 105, 106, 107, 112]
last_reviewed: 2026-08-19
---

# V1 范围与成功标准

## 产品目标

PlantNexus APS V1 是面向单工厂、多车间、多产线、多设备的统一计划排程底座。它必须完成从版本化输入、规范化、不可变快照、统一问题构建、求解、独立验证、计划版本、人工审批到发布和异常重排的闭环。

V1 的交付单位不是一个 OR-Tools 脚本，而是一组可以持续吸收制造约束、独立证明结果正确并可追溯重放的产品能力。

## V1 成功标准

| 维度 | 必须达到 |
|---|---|
| Correctness | 任何进入 `READY_FOR_REVIEW` 的 ScheduleVersion 必须满足 `hard_violation_count == 0` |
| Feasibility | 代表性仿真场景能在配置预算内得到业务可用的可行方案 |
| Traceability | 结果可追溯到 Snapshot、规则、PlanningProblem、Solver、参数、Scenario/Generator、代码提交 |
| Human Control | 计划员可以查看、比较、锁定、驳回、批准、发布和引用历史版本 |
| Interoperability | 至少支持 JSON、CSV、Excel 和 MES Adapter 成果输出 |

`FEASIBLE` 不等于全局最优，`UNKNOWN` 不等于无解。没有真实历史数据前，不承诺秒级排程、固定运行时间、全局最优比例或任意规模工厂。

## V1 范围内

- 单工厂、多车间、多产线、多设备；
- Flexible Job Shop 与 DAG 工艺；
- 跨车间工艺与运输 lag；
- 候选设备和设备差异化工时；
- Capacity=1 设备互斥；
- 班次、休息、维护和停机日历；
- release time、`material_ready_at`；
- COMPLETED、RUNNING、HARD_LOCK、SOFT_LOCK；
- ScheduleVersion、审批、发布、导出和 Replan；
- Simulation、Scenario Library、Reference Scheduler、Benchmark Harness 和 Execution Simulator。

## V1 明确不支持

- 多工厂网络优化；
- 自动 MRP、完整库存流、替代料优化和自动采购；
- 强化学习排程、数字孪生、APS+CAM 联合优化；
- 自动发布；
- LLM 自动修改硬约束、工艺、资源兼容性或业务权重。

高级能力如 Secondary Capacity、Sequence-dependent Setup、Batch、Split/Merge、Material Competition、Preemption、Buffer Capacity、Alternative Material 和 Multi-factory 必须显式返回 `UNSUPPORTED_CAPABILITY`，禁止静默近似。

## 生产就绪边界

生产上线至少需要真实匿名历史快照、Historical Replay、计划员评审、Reality Gap Report、性能边界、关键 `PROD_OPEN` 关闭、安全审查、备份恢复测试、监控、Runbook 和 UAT。Synthetic Benchmark 只能证明当前测试场景与当前硬件下的行为。
