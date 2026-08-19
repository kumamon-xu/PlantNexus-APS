---
doc_id: DOC-ARCH-005
title: 数据权威边界
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [15, 22, 59, 61, 90]
last_reviewed: 2026-08-19
---

# 数据权威边界

| 数据 | 权威来源 | 当前注意事项 |
|---|---|---|
| Order | ERP | 字段级权威仍受 OPEN-015 约束 |
| BOM | ERP | V1 不负责自动 MRP |
| Purchase Promise | ERP | 与 material readiness 的关系待确认 |
| Execution | MES | 已完成/运行中事实不可被计划覆盖 |
| Machine Runtime State | MES | 故障/恢复成为执行事实或事件 |
| Physical Inventory | WMS | V1 不做完整库存平衡 |
| CAM Processing Feature | CAM | V1 不做联合优化 |
| Planning Decision | APS | 必须经过 Validator 和人工审批 |

## AI 边界

AI 可以输出 `duration`、`risk`、`confidence` 及版本信息。AI 不能成为 routing、resource compatibility、hard constraint、schedule state 或业务权重的权威来源。

## Material Readiness

V1 接受上游提供的 `material_ready_at`，并执行 `operation.start >= material_ready_at`。Solver 不猜库存齐套时间。若上游不能直接提供，应通过 `MaterialReadinessProvider` 扩展，并由 OPEN-007/OPEN-015 关闭其权威问题。

## 冲突处理

来源冲突不得由最后写入或 AI 推断解决。应在 Raw Staging/Normalization 阶段保留来源、版本和冲突诊断，根据字段权威规则拒绝或等待业务决策。
