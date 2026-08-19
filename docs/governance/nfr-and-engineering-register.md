---
doc_id: DOC-GOV-003
title: NFR 与工程需求注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [4, 6, 16, 23, 24, 29, 30, 42, 58, 62, 65, 66, 89, 93, 95]
last_reviewed: 2026-08-19
---

# NFR 与工程需求注册表

以下 ID 是对总规已有非功能要求的稳定化登记，不引入尚未确认的性能数值。

| ID | 要求 | 可验证标准 |
|---|---|---|
| NFR-COR-001 | 进入评审的计划无硬约束违反 | `hard_violation_count == 0` |
| NFR-DET-001 | Snapshot、Problem 和 Synthetic Dataset 可确定性重放 | 同输入、版本和 seed 得到同 hash |
| NFR-TRC-001 | 全链路可追溯 | 成果 manifest 包含所需版本和来源 |
| NFR-ISO-001 | Production 与 Simulation 数据隔离 | 独立数据库；生产禁用 Simulation API |
| NFR-REL-001 | 长任务故障可检测、可重试 | heartbeat、lease、attempt、STALLED、idempotency |
| NFR-SEC-001 | 导入、Secret 和外部执行安全 | 格式/大小限制，不执行宏/公式，不拼接 SQL/shell |
| NFR-OBS-001 | PlanningRun 可观测 | 记录模型规模、耗时、目标、bound、gap、内存和验证时间 |
| NFR-PER-001 | 性能通过分级 Benchmark 管理 | PR/ Nightly/ Release profiles；当前不设生产 SLA |
| NFR-HUM-001 | 发布受人工控制 | 仅 APPROVED 可发布，自动发布禁止 |
| ENG-ARCH-001 | 采用 Modular Monolith | Solver Worker 与 API Process 分离 |
| ENG-SOL-001 | 领域层 Solver-neutral | OR-Tools 类型不进入 domain/PlanningProblem |
| ENG-VAL-001 | Validator 独立实现 | 不导入/复用 CpSatBackend 约束代码 |
| ENG-ERR-001 | 错误语义可区分 | DATA_ERROR 等七类错误不统一映射 500 |
| ENG-VER-001 | Schema、Solver、Simulation 版本化 | 修改触发 lock/replay/migration/contract test |

`NFR-PER-001` 只规定测量机制。生产运行时间、内存和规模阈值属于 `OPEN-012`，在 P7 以前不得填入承诺值。
