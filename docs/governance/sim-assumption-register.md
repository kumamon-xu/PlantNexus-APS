---
doc_id: DOC-GOV-007
title: SIM_ASSUMPTION 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [37, 38, 39, 43, 44, 49, 59, 62, 96]
last_reviewed: 2026-08-19
registry_version: 1.0.0
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

本注册表的稳定 ID 前缀为 `SIM-ASSUMPTION-NNN`。总规示例中的 `SIM_ASSUMPTION-003` 是同类标记的上游拼写，校验时规范化为 `SIM-ASSUMPTION-003`；新引用必须使用本表前缀。条目只能为 `ACTIVE` 或 `RETIRED`，不得出现 `OPEN`/`CLOSED` 生产问题状态，也不得用于关闭任何 `OPEN-NNN`。

修改表结构、ID 前缀或状态语义必须提升 `registry_version`；具体 Scenario/Profile 参数变化由对应资产版本管理。

TASK-P0-03 review：`schemas/samples/*.synthetic.json` 使用显式 `synthetic=true` 和 `SCHEMA-SAMPLE-P0-03`，只验证 Schema，不定义 workshop/resource 数、概率或正式 Scenario/Profile。没有新增或修改 SIM-ASSUMPTION，五项状态继续为 `ACTIVE`。

TASK-P0-04 review：C-012～C-018 与 unsupported/deferred capability 的 expected result 可以是 `UNSUPPORTED_CAPABILITY`，但本 Task 没有创建 Scenario/Profile、概率、工厂参数或 synthetic fixture。规则正反例只是合同文字，不是 Simulation 事实。没有新增/修改 SIM-ASSUMPTION，五项状态继续为 `ACTIVE`，registry format version 不变。
