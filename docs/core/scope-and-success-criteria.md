---
doc_id: DOC-CORE-001
title: V1 范围与成功标准
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [0, 3, 4, 7, 8, 105, 106, 107, 112, 113]
last_reviewed: 2026-09-04
---

# V1 范围与成功标准

## 产品目标

PlantNexus APS V1 是面向单工厂、多车间、多产线、多设备的统一计划排程底座。最终Headless产品只接收宿主平台提交的versioned canonical JSON，并完成从合同/数据校验、不可变快照、统一问题构建、求解、独立验证、计划版本、人工审批到发布和异常重排的闭环。第三方采集、vendor字段映射与结果展示归宿主平台，APS不直接对接ERP、MES、WMS或CAM。

V1 的交付单位不是一个 OR-Tools 脚本，而是一组可以持续吸收制造约束、独立证明结果正确并可追溯重放的产品能力。

## V1 成功标准

| 维度 | 必须达到 |
|---|---|
| Correctness | 任何进入 `READY_FOR_REVIEW` 的 ScheduleVersion 必须满足 `hard_violation_count == 0` |
| Feasibility | 代表性仿真场景能在配置预算内得到业务可用的可行方案 |
| Traceability | 结果可追溯到 Snapshot、规则、PlanningProblem、Solver、参数、Scenario/Generator、代码提交 |
| Human Control | 计划员可以查看、比较、锁定、驳回、批准、发布和引用历史版本 |
| Interoperability | Canonical JSON是唯一外部输入；宿主与可选独立Frontend使用同一版本化API和标准结果/read model |

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
- Headless API、独立Solver Worker与APS自有持久化的产品化目标；可选独立Frontend只作为同一API consumer。

## V1 明确不支持

- 多工厂网络优化；
- 自动 MRP、完整库存流、替代料优化和自动采购；
- 强化学习排程、数字孪生、APS+CAM 联合优化；
- 自动发布；
- LLM 自动修改硬约束、工艺、资源兼容性或业务权重。
- APS内置ERP/MES/WMS/CAM专用连接器、vendor payload API或共享宿主数据库；
- 为宿主平台与独立Frontend维护两套业务后端。

高级能力如 Secondary Capacity、Sequence-dependent Setup、Batch、Split/Merge、Material Competition、Preemption、Buffer Capacity、Alternative Material 和 Multi-factory 必须显式返回 `UNSUPPORTED_CAPABILITY`，禁止静默近似。

这些尚未实现的高级能力不作为P8基础封装与Headless工程Exit的阻塞项；后续只能通过独立Task、兼容API/Schema扩展和对应验证逐项增加，不能改变已封装核心的默认语义。

## 生产就绪边界

生产上线至少需要P7真实匿名历史快照、Historical Replay、计划员评审、Reality Gap Report与性能边界，同时需要P8 canonical API、可靠worker、host identity、安全、发布封装、备份恢复、监控与Runbook Exit通过，并关闭关键`PROD_OPEN`、完成UAT。P7和P8任一未通过都必须`NOT_READY`；Synthetic Benchmark只能证明当前测试场景与当前硬件下的行为。
