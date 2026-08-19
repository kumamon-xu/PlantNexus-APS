---
doc_id: DOC-GOV-008
title: 项目风险注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: false
source_sections: [0, 8, 10, 30, 42, 57, 59, 62, 89, 90, 105]
last_reviewed: 2026-08-19
registry_version: 1.0.0
---

# 项目风险注册表

| ID | Status | 风险 | 早期信号 | 当前控制 |
|---|---|---|---|---|
| RISK-001 | MONITORED | 无真实数据导致模型与业务脱节 | 大量 `PROD_OPEN` 长期无关闭证据 | Simulation-First、P7 Reality Gap、禁止生产猜测 |
| RISK-002 | MONITORED | 仿真走测试捷径，未验证真实链路 | Generator 直接构造 CpModel/Problem | 强制 Standard Import → Snapshot → Problem |
| RISK-003 | MONITORED | Solver 与 Validator 共用逻辑导致共同缺陷 | Validator 导入 backend/constraint builder | 模块隔离、Mutation Tests、独立 Rule Sheet |
| RISK-004 | MONITORED | 未支持能力被静默忽略 | Scenario 可运行但缺少对应约束 | Capability Matrix、`UNSUPPORTED_CAPABILITY` |
| RISK-005 | MONITORED | Solver 规模失控 | optional interval、日历碎片、内存快速增长 | Complexity Metrics、XS/S/M gates、分解 ADR 门 |
| RISK-006 | MONITORED | 结果状态被错误解释 | UNKNOWN 被显示成 INFEASIBLE | 状态 Contract 和错误分类测试 |
| RISK-007 | MONITORED | Synthetic 数据污染生产 | 共库、生产启用 sim API | 独立 Database、生产 404/disabled |
| RISK-008 | MONITORED | 重试导致重复发布或事件 | Worker crash 后重复副作用 | idempotency key、lease、audit trail |
| RISK-009 | MONITORED | 过早性能或最优性承诺 | 没有历史数据却设置 SLA | OPEN-012、Benchmark 环境声明、P7 Gate |
| RISK-010 | MONITORED | P5 高级能力大爆炸 | 多个高级约束同时进入一个迭代 | 每能力独立 ADR/Schema/Validator/Fixture/Benchmark |

风险状态、责任人和日期将在团队角色与仓库工作流确认后补充，当前不猜测人员归属。

状态仅允许 `MONITORED`、`MITIGATED`、`CLOSED`。状态变化必须给出可验证控制或关闭证据；未知责任人继续留空，不能为了表格完整而猜测。修改表结构或状态语义必须提升 `registry_version`。
