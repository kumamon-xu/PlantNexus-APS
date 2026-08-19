---
doc_id: DOC-GOV-006
title: PROD_OPEN 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [16, 59, 60, 61, 105, 106]
last_reviewed: 2026-08-19
---

# PROD_OPEN 注册表

未关闭的 `PROD_OPEN` 不阻止开发、仿真和 Benchmark，但阻止依赖该事实的生产发布。关闭必须附业务权威来源、决策日期、影响范围和验证证据。

| ID | 待确认问题 | 当前状态 | 主要影响 |
|---|---|---|---|
| OPEN-001 | Factory timezone | OPEN | Production 时间显示与边界；未知时 `BLOCK_PRODUCTION` |
| OPEN-002 | ERP/MES/WMS/CAM interfaces | OPEN | Adapter、字段、版本和错误处理 |
| OPEN-003 | Real factory topology | OPEN | Workshop/Line/Resource 建模与规模 |
| OPEN-004 | Calendar processing semantics | OPEN | 班次、休息、维护、跨日语义 |
| OPEN-005 | Freeze window | OPEN | Replan 锁定与稳定性 |
| OPEN-006 | Priority/tardiness business meaning | OPEN | 权重与 OBJ-001 业务含义 |
| OPEN-007 | material_ready_at authority | OPEN | MaterialReadinessProvider 和数据权威 |
| OPEN-008 | Lot splitting policy | OPEN | ProductionLot 展开；V1 不近似 Split/Merge |
| OPEN-009 | Cross-workshop transport rule | OPEN | transport_lag 来源和日历语义 |
| OPEN-010 | Approval responsibility | OPEN | 角色、权限和审计 |
| OPEN-011 | Historical benchmark data | OPEN | P7 Reality Calibration |
| OPEN-012 | Production runtime threshold | OPEN | 生产性能边界和部署预算 |
| OPEN-013 | Unit conversion | OPEN | Import/Normalization 拒绝与转换规则 |
| OPEN-014 | Duration fallback | OPEN | 标准工时/预测低置信度回退 |
| OPEN-015 | Field authority | OPEN | 字段级来源冲突解决 |

## 关闭记录要求

关闭一项问题时必须记录：权威人/系统、原始证据、决策值或规则、适用版本、受影响 Contract/Schema/ADR/Task/Test，以及是否需要迁移或历史重放。
