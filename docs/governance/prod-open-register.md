---
doc_id: DOC-GOV-006
title: PROD_OPEN 注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [16, 59, 60, 61, 105, 106]
last_reviewed: 2026-08-19
registry_version: 1.0.0
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

关闭记录必须在本文件使用以下机器可检查的字段；表中状态只有在记录完整且引用路径存在后才能从 `OPEN` 改为 `CLOSED`：

```text
### OPEN-NNN closure
Authority: person-role or authoritative-system
Evidence: repository path or approved external reference
Decision date: YYYY-MM-DD
Decision: approved value or rule
Applies to: version/scope
Affected artifacts: Contract/Schema/ADR/Task/Test paths or IDs
Migration/replay: required with path | none with reason
```

不得以会议印象、Coding Agent 推断或 `SIM_ASSUMPTION` 作为关闭证据。`registry_version` 在字段结构、状态机或关闭证据语义变化时递增；关闭单个条目不改变格式版本。

TASK-P0-03 review：Schema/data dictionary 只引用 OPEN-001/002/003/004/007/013/015 等既有问题来标明未知生产事实；没有提供外部权威、closure record 或生产默认值。OPEN-001～015 全部继续为 `OPEN`，registry version 不变。

TASK-P0-04 review：rule sheet 显式引用 OPEN-004（日历）、OPEN-005（lock/freeze）、OPEN-007（material authority）、OPEN-009（transport）并在 state guard 中保留 OPEN-010（审批角色）；OPEN-006/008 只作为相邻业务政策审查，未写入权重或 lot 默认值。没有权威来源、closure record、生产值或状态变化，OPEN-001～015 全部继续为 `OPEN`，registry format version 不变。

TASK-P0-05 review：FactoryProfile/Scenario Schema sample 的 count/range/calendar/complexity 值全部标识 synthetic-only，不成为 OPEN-003/004 的真实拓扑或日历答案；empty Import records 不提供 OPEN-002/013/015 字段权威；manifest/hash 不提供 OPEN-011 历史数据或 OPEN-012 生产阈值。没有权威来源或 closure record，OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-06 review：本 Task 注册的 synthetic-only assumptions 和 `SIM-MINIMAL-001@1.0.0` 的 2/2/3 topology、900 秒 tick、maintenance、duration/lag、due/weight 都不能作为本注册表的权威证据。fixture-local `records` 不回答 OPEN-002/013/015，数值不回答 OPEN-001/003/004/006/007/009/014，correctness runtime 不回答 OPEN-011/012。没有权威来源或 closure record；OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-07 review：calendar/material/transport/lock/duration/horizon mutation 只是在 `SIM-MINIMAL-001@1.0.0` synthetic facts 上制造明确非法反例，不提供 OPEN-004/005/007/009/014 的生产语义或权威值；fixture evaluator runtime 也不回答 OPEN-011/012。没有外部权威、closure record、production default 或迁移结论；OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-08 review：environment/data-plane/Production config guard、development Compose database name/credentials placeholder、health timeout、heartbeat=30/lease=120 与 conditional PR Benchmark hook 全是工程/本地测试值，不回答 OPEN-001/002/003/010/011/012/015，也不是生产 topology、SLA、角色、接口或字段权威。没有 CI provider、Production deployment、外部权威或 closure record；OPEN-001～015 全部继续 `OPEN`，registry format version 不变。

TASK-P0-09 review：P0 registration gate 确认 OPEN-001～015 共 15 项全部存在，且没有任何条目被 SIM_ASSUMPTION、本地测试值、Compose/config 或 audit 推断关闭；因此“全部登记”Gate 为 `PASS`。本审计没有 authority、closure record、生产值或 migration/replay 决定，15 项全部继续 `OPEN`，registry format version不变；`P0-GAP-001/002` 是 CI 审计缺口，不是新的生产业务开放项。
