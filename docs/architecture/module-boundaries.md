---
doc_id: DOC-ARCH-003
title: 模块边界与依赖规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [12, 13, 14, 30, 41, 47, 51, 65, 70]
last_reviewed: 2026-08-20
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

## TASK-P1-04 ReferenceFileAdapter boundaries

- `importers/adapter.py`定义version/capability/source manifest、stable DATA_ERROR和format-neutral reference rows；`csv_reader.py`与`excel_reader.py`只负责bounded transport decoding。
- `reference_file_adapter.py`验证source root/path、读取一次bounded bytes、计算文件SHA-256并调用TASK-P1-03 assembler；它不持久化、不导入Infrastructure、Domain canonical types、Normalization、Snapshot、Problem或Solver。
- CSV/XLSX只共享三列transport validation与opaque row serialization；XLSX通过read-only openpyxl读取，macro/formula/external relationship不执行。
- persistence/idempotency仍由`ImportStagingRepository`承担；TASK-P1-04 integration只证明prepared batch可exact replay/conflict，不把Adapter变成repository或application orchestration。

## TASK-P1-05 Normalization boundaries

- `normalization/contracts.py`定义frozen profile/input/result和sanitized DATA_ERROR；`ids.py`、`time.py`、`units.py`分别拥有单一pure转换；`normalizer.py`只消费`StagedImportBatch`并生产JSON-compatible Import v2 bytes/hash。
- Runtime unit registry通过mapping注入，不读取文件或数据库；MappingProfile必须精确绑定source/version和registry version，不访问Adapter路径、repository或环境配置。
- 模块不导入`app.data_validation`、`app.snapshots`、`app.planning`或OR-Tools；测试以source scan固定这一边界。跨实体precheck只在测试中证明后续validator仍能拒绝missing reference，producer本身不调用。
- Transport metadata继续由`importers`/Infrastructure拥有，Normalization不持久化、不创建migration/API/Job，也不生成Lot/OperationInstance/Snapshot/Problem。

## TASK-P1-06 Data Validation boundaries

- `data_validation/contracts.py`只定义report/version、canonical serializer和有序issue collector；`references.py`建立非位置化view并检查structure/source/reference/lineage；`routing.py`检查DAG/time/calendar/unit/duration/fact/lock；`capabilities.py`检查platform declaration与resource eligibility；
- evaluator只读Import v2 Mapping并总是返回Error v3/ImportQualityReport v1，不修改Normalization output、不访问Raw repository、DB、API、Job或环境配置；
- package source scan禁止`app.planning`、OR-Tools、CpSat与ScheduleValidator依赖。Input-quality DAG/resource规则不复用P0 fixture-local schedule evaluator或C-001～C-011公式；
- 本模块不展开订单、不创建Snapshot/Problem、不持久化报告、不映射HTTP。TASK-P1-07 consumer只能接收PASS report与原canonical Import，不能绕过本Gate。

## TASK-P1-07/08 Expansion and Snapshot boundaries

- `domain.production`只定义solver-neutral expansion contract/identity/error，`normalization.order_expansion`只把validated Import/PASS report展开为pure artifact；两者不访问数据库、Snapshot repository、Planning或API。
- `snapshots.canonical`拥有Import/Snapshot排序、dataset digest、Snapshot hash projection/ID和integrity verification；`snapshots.builder`只编排已存在的Import/report/Expansion并返回immutable bytes value，不读取Raw repository、环境或数据库。
- `snapshots.repository`只定义insert/replay/read protocol；`infrastructure.snapshot_repository`单独拥有SQLAlchemy transaction、plane query和storage integrity，migration只建立internal content-addressed table/trigger。
- `app.snapshots`保持无ORM/FastAPI/Celery/OR-Tools/PlanningProblem依赖；Infrastructure adapter不得反向成为领域权威或绕过builder接受任意JSON。
- 当前没有`application/**` common-ingress orchestration、PlanningProblem builder、Worker task、API、ScheduleVersion或Solver；这些边界分别留给TASK-P1-09/11及后续Phase。
