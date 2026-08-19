---
doc_id: DOC-ARCH-003
title: 模块边界与依赖规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [12, 13, 14, 30, 41, 47, 51, 65, 70]
last_reviewed: 2026-08-19
---

# 模块边界与依赖规则

V1 使用 Modular Monolith：一个 FastAPI 应用、PostgreSQL、Redis、独立 Solver Worker 和 React Frontend。Solver 计算不得运行在 API Process 中。

## 后端模块职责

| 模块 | 职责 | 禁止依赖/行为 |
|---|---|---|
| `api/` | HTTP contract、认证上下文、DTO 调用 | CP-SAT 建模、业务规则复制 |
| `application/` | 用例编排、事务和状态迁移 | OR-Tools 对象 |
| `domain/` | 实体、值对象、不变量和协议 | ORM、FastAPI、Celery、OR-Tools |
| `infrastructure/` | DB、消息、外部 Adapter | 决定业务权威和约束语义 |
| `importers/` | 读取版本化输入 | 绕过 staging/validation |
| `normalization/` | 单位/字段规范化 | 猜缺失业务值 |
| `data_validation/` | 输入质量和能力预检 | 静默忽略 unsupported capability |
| `snapshots/` | immutable Snapshot 与 hash | 引入求解器类型 |
| `planning/problem/` | 构建 Solver-neutral Problem | OR-Tools 类型 |
| `planning/strategies/` | 组织求解方式 | 将策略固化到 Controller/UI |
| `planning/backends/cp_sat/` | CP-SAT 模型和映射 | 向 domain 泄漏 OR-Tools 对象 |
| `planning/validation/` | 独立验证计划 | 导入/复用 CpSatBackend 约束实现 |
| `simulation/` | Profile、Scenario、Generator、Execution、Benchmark | 直接构造 CpModel 或绕过正式入口 |

## 跨模块不变量

- ORM Model 不承载 Solver 建模逻辑。
- React Component 不复制约束或直接修改发布计划。
- Validator 可以共享领域数据类型和规范化时间工具，但不能共享产生同源缺陷的 CP-SAT 约束构建器。
- Reference Scheduler 实现位于 simulation/baselines 或独立规划基线模块，必须标记非生产 Solver。

TASK-P0-05 已在 `simulation/profiles`、`simulation/scenarios`、`simulation/generators` 落地纯合同。七层 generator Protocol 的最终输出类型是 `GeneratedScenarioPackage`（Standard Import v1 + ScenarioManifest + canonical bytes/hash）；代码扫描与 contract tests 禁止 `app.planning`/OR-Tools import。`execution`、`baselines`、`benchmarks` 仍为空边界，不存在行为实现。

## TASK-P0-08 engineering boundaries

- `api/app.py` 只装配 `/health/live` 与 `/health/ready`，不接触 Domain、Planning、Import、Export 或发布；OpenAPI/docs UI 在该 health-only app 中禁用。
- `infrastructure/` 持有环境配置、日志、SQLAlchemy/Redis adapter、health probe 和 machine contract check。构建 client 不连接外部服务；只有 readiness probe 或未来 repository 调用才访问网络。
- `jobs/` 持有 business-neutral immutable JobRecord、lease/heartbeat/attempt/STALLED 纯转移、idempotency protocol/process-local reference store 与 Celery adapter；不注册任何业务 task，不改变 ExportJob/PlanningRun/ScheduleVersion 状态合同。
- API Process 与 Worker 使用同一 package/image但不同启动命令；P0-08 没有 Solver Worker task。未来 Solver 必须继续位于独立 Worker process 且不得在 health API 执行。
- `backend/migrations` 的两张表只保存通用工程 job/idempotency metadata，不是 Domain ORM 或业务权威来源；真实 distributed repository/transaction semantics 仍为后续 Task。

## TASK-P1-03 Raw Staging boundaries

- `importers/contracts.py`只定义frozen raw batch/row、synthetic provenance、data plane和稳定staging error；`staging.py`只把opaque row iterable冻结为tuple；`repository.py`只暴露`stage/get` protocol。
- `infrastructure/import_staging_repository.py`使用SQLAlchemy Core实现plane-scoped insert/read、idempotent replay/conflict与单事务batch+rows落库；它不决定字段权威、不解析业务值，也不提供update/delete。
- migration只创建internal `raw_import_batches/raw_import_rows`；ORM/Domain/API/Celery business task均未新增。
- `TEST-IMPORT-STAGING-001`以AST import scan确认上述实现不导入`app.domain.canonical_records`、`app.snapshots`或`app.planning`。因此当前没有Raw→Canonical/Snapshot/Problem/Solver捷径；正式consumer仍必须经过P1-04～08的Adapter/Normalization/DataValidation/Expansion/Snapshot链。
