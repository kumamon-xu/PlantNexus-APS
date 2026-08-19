---
doc_id: DOC-GOV-003
title: NFR 与工程需求注册表
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [4, 6, 16, 23, 24, 29, 30, 42, 58, 62, 65, 66, 89, 93, 95]
last_reviewed: 2026-08-19
registry_version: 1.0.0
---

# NFR 与工程需求注册表

以下 ID 是对总规已有非功能要求的稳定化登记，不引入尚未确认的性能数值。

| ID | ID status | 要求 | 可验证标准 |
|---|---|---|---|
| NFR-COR-001 | ALLOCATED | 进入评审的计划无硬约束违反 | `hard_violation_count == 0` |
| NFR-DET-001 | ALLOCATED | Snapshot、Problem 和 Synthetic Dataset 可确定性重放 | 同输入、版本和 seed 得到同 hash |
| NFR-TRC-001 | ALLOCATED | 全链路可追溯 | 成果 manifest 包含所需版本和来源 |
| NFR-ISO-001 | ALLOCATED | Production 与 Simulation 数据隔离 | 独立数据库；生产禁用 Simulation API |
| NFR-REL-001 | ALLOCATED | 长任务故障可检测、可重试 | heartbeat、lease、attempt、STALLED、idempotency |
| NFR-SEC-001 | ALLOCATED | 导入、Secret 和外部执行安全 | 格式/大小限制，不执行宏/公式，不拼接 SQL/shell |
| NFR-OBS-001 | ALLOCATED | PlanningRun 可观测 | 记录模型规模、耗时、目标、bound、gap、内存和验证时间 |
| NFR-PER-001 | ALLOCATED | 性能通过分级 Benchmark 管理 | PR/ Nightly/ Release profiles；当前不设生产 SLA |
| NFR-HUM-001 | ALLOCATED | 发布受人工控制 | 仅 APPROVED 可发布，自动发布禁止 |
| ENG-ARCH-001 | ALLOCATED | 采用 Modular Monolith | Solver Worker 与 API Process 分离 |
| ENG-SOL-001 | ALLOCATED | 领域层 Solver-neutral | OR-Tools 类型不进入 domain/PlanningProblem |
| ENG-VAL-001 | ALLOCATED | Validator 独立实现 | 不导入/复用 CpSatBackend 约束代码 |
| ENG-ERR-001 | ALLOCATED | 错误语义可区分 | DATA_ERROR 等七类错误不统一映射 500 |
| ENG-VER-001 | ALLOCATED | Schema、Solver、Simulation 版本化 | 修改触发 lock/replay/migration/contract test |
| ENG-LOG-001 | ALLOCATED | 结构化日志可关联到运行与来源 | 日志携带稳定 run/correlation 标识且不成为唯一 provenance 载体 |

`NFR-PER-001` 只规定测量机制。生产运行时间、内存和规模阈值属于 `OPEN-012`，在 P7 以前不得填入承诺值。

`ENG-LOG-001` 补齐总规追踪示例和 Observability/Provenance 对日志关联能力的既有要求，不表示 logging 实现已经形成。与 REQ 相同，`ALLOCATED` 仅表示 ID 稳定；删除、复用或改变 ID 含义必须保留历史并提升 `registry_version`。

TASK-P0-03 review：NFR-DET-001/NFR-TRC-001 与 ENG-SOL-001/ENG-VER-001 已链接 Schema `1.0.0`、纯类型和 TEST-CONTRACT-001；canonical hash/replay、run manifest、Problem builder 和 Solver 仍为 `PLANNED`。其余 NFR/ENG 含义和全部 `ALLOCATED` 状态不变。

TASK-P0-04 review：NFR-COR-001/ENG-VAL-001 获得 C-001～C-011 rule metadata、validation-report.v2 与独立 import-boundary/completeness tests，但没有 schedule evaluator/mutation PASS；NFR-REL-001/NFR-HUM-001 只获得 ExportJob/ScheduleVersion transition contract，不是 Worker/审批/发布实现；ENG-ERR-001 获得七类/19 code 唯一映射；ENG-VER-001 获得 additive schema set `1.1.0`、v1 preservation 和 contract tests。全部根 ID 仍为 `ALLOCATED`，registry format version 不变。
