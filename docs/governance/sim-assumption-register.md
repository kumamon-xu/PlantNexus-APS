---
doc_id: DOC-GOV-007
title: SIM_ASSUMPTION 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [37, 38, 39, 43, 44, 49, 59, 62, 96]
last_reviewed: 2026-08-19
---

# SIM_ASSUMPTION 注册表

Simulation 用于模拟 APS Planning Reality，不代表真实物理工厂。每个定量假设必须在 FactoryProfile 或 ScenarioSpec 中版本化，并可追溯到本注册表。

| ID | 仿真假设边界 | 状态 | 约束 |
|---|---|---|---|
| SIM-ASSUMPTION-001 | 虚拟工厂拓扑可以为测试覆盖而构造 | ACTIVE | `synthetic_only=true`，不能成为生产默认值 |
| SIM-ASSUMPTION-002 | 场景随机性由显式 seed 控制 | ACTIVE | Scenario+Profile+Generator version+seed 必须可重放 |
| SIM-ASSUMPTION-003 | 设备故障、延迟、急单等概率只属于 Scenario | ACTIVE | 不得进入 Production Business Policy |
| SIM-ASSUMPTION-004 | 初始场景库覆盖 Flexible Job Shop、Bottleneck、High-Mix Setup、Assembly DAG、Cross-Workshop | ACTIVE | 不支持能力必须得到明确拒绝结果 |
| SIM-ASSUMPTION-005 | XS/S/M/L/XL 只表示 Benchmark 复杂度画像 | ACTIVE | 不代表真实生产容量承诺 |

具体 workshop 数、resource 数、候选设备密度、故障概率、到期压力等数值尚未在本阶段批准。它们应由后续版本化 FactoryProfile/ScenarioSpec 明确，不能在本文中给出“通用默认工厂”。
