---
doc_id: DOC-SIM-004
title: Scenario Library 与复杂度矩阵
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [43, 44, 45, 46, 56]
last_reviewed: 2026-08-19
---

# Scenario Library 与复杂度矩阵

## 初始工厂画像

| Profile | 主要特征 | 验证目标 |
|---|---|---|
| PROFILE-A Flexible Job Shop | 多工序、多候选设备、多车间、设备速度不同 | V1 主模型 |
| PROFILE-B Bottleneck Factory | 关键设备高负荷、高交期压力、多订单竞争 | Weighted tardiness、scaling |
| PROFILE-C High-Mix Setup | 高频切换、Setup Matrix | 当前期望 `UNSUPPORTED_CAPABILITY` |
| PROFILE-D Assembly DAG | parallel branch、merge、secondary resource | DAG；Secondary Capacity 可明确拒绝 |
| PROFILE-E Cross-Workshop | Cutting→Machining→Treatment→Assembly 等 | precedence、transport lag、calendar |

## Scenario 矩阵

场景覆盖应组合 Factory Size、Routing Complexity、Candidate Resources、Bottleneck、Due Pressure、Calendar Fragmentation、Material Delay、WIP、Lock、Cross-workshop 和 Failure Frequency，而不是只扩大 operation count。

## Complexity Metrics

至少记录 order/lot/operation/edge/resource counts、avg candidates、optional intervals、routing depth、cross-workshop ratio、calendar fragments、WIP/lock/material-delay ratios、bottleneck utilization 和 horizon ticks。

## Profile 级别

XS/S/M/L/XL 在 `benchmarks/profiles.yaml` 中定义 operation/resource target、candidate/calendar density 和 routing complexity。它们只用于相对复杂度与回归，不代表生产容量。

## P0-05 status

ScenarioSpec v1 已固定上述矩阵所需的 factory size、routing complexity、candidate density、bottleneck、due pressure、calendar fragmentation、material/WIP/lock/cross-workshop ratios 和 failure frequency 字段；FactoryProfile v1 固定生成范围与 capability/rejection 边界。当前仅有 `SCHEMA-*` samples，五类 Profile、XS/S/M/L/XL baseline 与正式 Scenario catalog 尚未创建，不得把 sample 的单值范围写入本表作为批准参数。

TASK-P0-06 才创建 `SIM-MINIMAL-001` correctness fixture；未来 Profile/Scenario asset 必须各自升 version 并引用 SIM_ASSUMPTION。P0-05 没有关闭 OPEN-003/011/012，也没有产生容量或性能结论。
