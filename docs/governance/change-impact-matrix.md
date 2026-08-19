---
doc_id: DOC-GOV-010
title: 变更影响与必审文档矩阵
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 97, 98, 99, 100, 101, 102, 103, 104, 111]
last_reviewed: 2026-08-19
---

# 变更影响与必审文档矩阵

本矩阵用于在 Task 开始前确定文档影响。表中的文档是“必须审查”，不代表每次都必须修改；如果审查后不修改，Task 完成证据必须逐项说明理由。

## 使用规则

1. 根据计划修改的路径和行为类型匹配所有适用行；
2. 把匹配到的文档写入 Task Card 的 `Documents to update`；
3. 把 Requirement/Test/Artifact/Registry 变化写入 `Traceability updates`；
4. 将这些文档路径加入 `Files allowed to change`；
5. 实施中出现新影响时先修订 Task Card；
6. 完成时按实际 diff 再匹配一次，防止计划与实际偏离。

## 路径与行为映射

| 变更区域或行为 | 必须审查的文档 | 必须检查的追踪/版本 | 额外门 |
|---|---|---|---|
| `schemas/**`、领域 DTO/值对象 | 对应 `contracts/*.md`、`contracts/schema-index.md`、`contracts/schema-versioning.md`、`domain/domain-model.md` | Schema version、REQ/NFR、contract tests、fixtures | 不兼容变更需 migration/compatibility rule |
| `domain/**` 的实体关系或不变量 | `domain/domain-model.md`、相关领域专题、`core/glossary.md`、`architecture/data-authority.md` | REQ、Schema、state/constraint refs | 语义变化可能需要 ADR |
| `importers/**`、`normalization/**`、`data_validation/**` | `contracts/import-and-normalization.md`、`architecture/data-authority.md`、`domain/error-model.md` | REQ-001～003、OPEN-002/013/015、contract tests | 禁止补猜生产默认值 |
| `snapshots/**`、snapshot hash | `contracts/planning-snapshot.md`、`architecture/provenance-and-versioning.md`、`quality/property-tests.md` | Snapshot/schema/rule version、replay tests | hash 语义变化需兼容说明 |
| `planning/problem/**` | `contracts/planning-problem.md`、`planning/constraint-catalog.md`、`architecture/provenance-and-versioning.md` | Problem version/hash、Golden/Scenario/Benchmark | 必须 ADR 与 replay |
| `planning/policy/**`、目标层级/权重语义 | `contracts/planning-policy-and-solve-limits.md`、`planning/objective-policy.md`、`domain/kpi-contract.md` | OBJ IDs、OPEN-005/006、solver reports | 目标层级变化必须 ADR |
| `planning/strategies/**` | `planning/planning-strategies.md`、`planning/solver-backend-contract.md`、`simulation/performance-gates.md` | REQ-004、Benchmark baseline | 分解/滚动策略必须 ADR 与证据门 |
| `planning/backends/**`、OR-Tools 参数/版本 | Solver contract、strategy、constraint/objective、benchmark regression、technology stack | Solver exact version、lock、Golden/Scenario/Benchmark | Backend/升级必须 ADR |
| `planning/validation/**` | `planning/schedule-validator.md`、`planning/constraint-catalog.md`、`quality/validator-mutation-tests.md`、test matrix | C-ID、REQ-005、Mutation/Property tests | 禁止复用 backend constraint builder |
| `planning/diagnostics/**`、状态映射 | `planning/infeasibility-diagnostics.md`、`domain/error-model.md`、Solver contract | error/status contract tests | UNKNOWN 不得变成 INFEASIBLE |
| PlanningRun/ScheduleVersion/ExportJob 状态或迁移 | 对应 `domain/state-machines/*.md`、相关 Contract、audit/release 文档 | transition tests、migration、REQ-007 | 状态机修改必须 ADR |
| `simulation/profiles/**` | `simulation/factory-profile.md`、scenario matrix、SIM assumption register、versioning | profile version、scenario compatibility | 不得成为生产默认值 |
| `simulation/scenarios/**` | Scenario/provenance、scenario library、performance gates | scenario version、expected behavior、replay | expected result 变化需解释 |
| `simulation/generators/**` | generator/determinism、dual-channel architecture、versioning | generator version、dataset hash、replay tests | 禁止绕过 Standard Import |
| `simulation/execution/**` | execution simulator、ExecutionEvent/Replan contract、`planning/replanning.md` | simulator version、event idempotency、P4 scenarios | 事实保护与 lock tests |
| `simulation/benchmarks/**`、`benchmarks/**` | benchmark harness、performance gates、benchmark regression、KPI contract | profile/baseline version、hardware/environment | 不得生成生产 SLA |
| `fixtures/**`、Golden/Mutation/Property 数据 | fixtures/golden、mutation/property docs、traceability matrix | Fixture/version/seed、Test IDs、expected artifacts | 不覆盖历史 baseline |
| `api/**`、HTTP 状态或 payload | 对应 API contract（形成后）、error model、security/authorization 文档 | OpenAPI/schema version、contract tests、REQ | 当前受实现阶段和 OPEN-002/010 约束 |
| `frontend/**` 的计划编辑/审批/发布 | Frontend 专题、ScheduleVersion state machine、replanning/validator contract | E2E tests、REQ-007/008、audit events | UI 不复制 Solver Logic |
| `exporters/**`、publish | export package、ExportJob/ScheduleVersion state、provenance、release docs | package schema、idempotency、audit/artifact | 仅 APPROVED 可发布 |
| `jobs/**`、Worker、retry/lease | ExportJob state、Operations reliability 文档、error model | idempotency/heartbeat tests、NFR-REL-001 | 禁止 double publish/event |
| `infrastructure/**`、配置、Secret、环境 | configuration/isolation、technology stack、Operations/Runbook（形成后） | NFR-SEC/ISO/OBS、deployment artifacts | 生产变更需安全/回滚证据 |
| dependency/lockfile，尤其 OR-Tools | technology stack、solver contract、benchmark regression、ADR index | dependency version、upgrade replay | OR-Tools 升级强制 ADR/Gate |
| `milestones/**`、`current_phase.md` | Milestone index、task index、traceability matrix、document inventory | Gate artifacts、Task status | 需用户确认才进入下一 Phase |
| 只修改文档 | document inventory、被引用文档、必要的 supersedes/ADR links | doc metadata、links、source sections | 运行文档一致性检查 |

## `Documentation impact: none` 的允许条件

只有同时满足以下条件才可声明 `none`：

- 实际 diff 未触发上表任何语义/路径行，或所有匹配文档经审查确认无需修改；
- 没有对外合同、状态、错误、配置、运维、测试口径或用户行为变化；
- 没有新增/关闭 PROD_OPEN、SIM_ASSUMPTION 或 ADR；
- 完成证据列出已审查的矩阵行和不修改理由。

纯格式化也需要记录影响判断，但可以在理由充分时声明 `none`。
