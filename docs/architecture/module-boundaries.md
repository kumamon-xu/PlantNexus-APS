---
doc_id: DOC-ARCH-003
title: 模块边界与依赖规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [12, 13, 14, 30, 41, 47, 51, 65, 70]
last_reviewed: 2026-08-24
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
- 当前没有`application/**` common-ingress orchestration、Worker task、API、ScheduleVersion或Solver；这些边界分别留给TASK-P1-11及后续Phase。

## TASK-P1-09 PlanningProblem boundaries

- `planning/problem/contracts.py`只定义JSON TypedDict、module-local error和immutable bytes value；`hashing.py`拥有canonical ordering/hash/integrity与pure precheck，`builder.py`只编排verified immutable Snapshot→Problem；
- Problem模块不读取Snapshot repository、Import/Expansion producer、DB、environment、API或Job，不持久化、不创建migration，也不导入OR-Tools/CpModel/IntervalVar；
- Builder保留Snapshot的content-derived ID和可由v1表达的future facts；遇到active lock、multi-factory或completed-active edge明确拒绝，不向Solver藏字段、不把输入错误转成INFEASIBLE；
- TASK-P1-09未实现Backend、Strategy、ScheduleValidator或candidate solution。P2 consumer只能从canonical Problem继续，不能回读上游对象绕过此边界。

## TASK-P1-10 Synthetic Generator boundaries

- `simulation/generators`七个layer只消费frozen GenerationContext和上游JSON-compatible source collections，不访问repository、Settings、API、Worker或数据库；package layer负责稳定组合。
- Package layer构造ReferenceFileAdapter-v1形状Raw rows与Simulation staging provenance，然后只调用公开`normalize_import`和`validate_import_package`；它不调用Snapshot/Problem builder，不伪造canonical source/package ID/report。
- AST isolation test禁止Generator导入`app.application`、`app.planning`、`app.snapshots`、OR-Tools或SQLAlchemy；Normalization只做`cycle_seconds_per_unit`既有duration分类修复，没有反向依赖Generator。
- 本Task不实现P1-11 common-ingress application orchestration、Execution Simulator、Benchmark、Solver或Production connector；后续consumer不得直接读取layer source records绕过Import quality Gate。

## TASK-P1-11 Application boundaries

- `application/import_pipeline.py`只编排已有public函数，不复制ID/unit/DAG/duration/expansion/hash规则，也不导入API、Infrastructure、Solver Backend/Strategy、ScheduleValidator、OR-Tools或SQLAlchemy。
- `simulation/generators.prepare_batch()`只暴露既有source-shaped Staging边界；Generator仍禁止导入Application/Snapshot/Planning，所以依赖方向为Application向内编排而非Generator反向调用。
- `application/p1_gate_report.py`是验收CLI，使用temporary reference CSV与ignored machine report；它不是产品API、Worker、repository或Production connector。
- AST边界测试覆盖上述禁止依赖，链路在immutable PlanningProblem终止。

## TASK-P2-03 CP-SAT Backend boundaries

- `planning/backends/contracts.py`只提供solver-neutral Protocol re-export、稳定Backend错误和JSON-compatible evidence types，不导入OR-Tools；canonical `app.planning.contracts.SolverBackend`签名不变。
- `planning/backends/cp_sat/`是唯一允许导入OR-Tools的namespace，拥有exact identity、native status适配、SolveLimits参数转换及engineering smoke；AST检查覆盖整个`backend/app`并拒绝越界import。
- `CpSatBackend.solve()`在验证Problem/Policy/Limits后以稳定`MODEL_BUILDER_NOT_IMPLEMENTED`停止，不构造C-001～C-011、OBJ-001，不返回candidate，也不调用Validator。
- `contract_check.py`只读repository、构造empty与intentional-invalid native model并写ignored JSON；它不访问DB/API/Worker、fixture/benchmark/export或Production配置。

## TASK-P2-04 formal Validator boundaries

- `planning/validation/problem_schedule_validator.py`只依赖solver-neutral domain/Problem合同，直接从Problem v2与candidate assignment重算C-001～C-011；不得导入`planning.backends`、OR-Tools或constraint builder。
- Solver status、expected mutation outcome和P0 fixture-local evaluator均不是判定输入；candidate缺失、重复、非法reference与每个C-ID violation按稳定顺序输出。
- `problem_validator_check.py`拥有fresh synthetic formal vector、声明式mutation、schema/error replay、固定fingerprints与AST isolation evidence，但不复用expected artifact作为oracle。
- Validator不构造CP-SAT model、objective、KPI、Benchmark、DB/API/Worker或P3 state。后继Solver consumer必须把candidate交给该独立边界，不能以Backend status替代验证。

## TASK-P2-05 core Backend boundary

- `planning/backends/cp_sat/core_constraints.py`拥有P2-05输入预检，只允许C-001/003/004/010/011所需事实；`model.py`拥有master/optional interval、exact-one与capacity-1 `NoOverlap`；`solution_mapper.py`只把完整native candidate映射到solver-neutral合同。
- `CpSatBackend`负责exact-pinned求解、状态降级、telemetry与调用formal Validator；Validator仍不得反向导入Backend、OR-Tools或模型变量。Validator FAIL时Backend必须丢弃assignments并返回FAILED边界。
- `core_model_check.py`拥有独立tiny choice/load枚举oracle、固定hash和机器报告，不是Production Scheduler或Benchmark runner。C-002/005～009、OBJ-001搜索、Strategy、DB/API/Worker及P3均不进入这些模块。

## TASK-P2-06 temporal Backend boundary

- `temporal_constraints.py`独占signed seconds→ticks取整、calendar grid projection/merge、precedence、historical anchor、release/material和conditional transport表达；`core_constraints.py`只负责输入可表示性和deferred-fact fail-closed，`model.py`只负责组合core与temporal bindings。
- min lag与transport各自条件化后形成独立下界，cross-workshop的有效下界为二者最大值而非相加；max lag使用独立上界。Calendar fixed intervals只进入对应resource的`NoOverlap`。
- `solution_mapper.py`仍只映射完整candidate，formal Validator仍不导入Backend/OR-Tools。`temporal_model_check.py`拥有in-memory oracle、mutation和telemetry；不拥有Problem builder/hash、规则公式、objective、Strategy、Benchmark或Production入口。

## TASK-P2-07 fact/lock Backend boundary

- `fact_lock_constraints.py`独占RUNNING future master interval/resource固定与HARD lock resource/start/end等式；它不读取环境、freeze policy或objective，也不把SOFT lock转成constraint/hint。
- `core_constraints.py`在CP-SAT对象创建前区分unrepresentable/self-conflicting fact/lock的MODEL_INVALID，与calendar/resource/horizon等合法约束冲突的certified INFEASIBLE；`model.py`只组合core/temporal/fact-lock bindings。
- `solution_mapper.py`使用RUNNING `remaining_seconds`映射duration，并稳定回写该operation全部lock IDs；Problem v2未暴露RUNNING execution fact ID，因此不得猜造`execution_fact_ids`，历史事实由Problem hash与actual/resource/remainder字段保持。
- Formal Validator继续独立重算C-007/C-008且不导入Backend/OR-Tools。`fact_lock_model_check.py`拥有synthetic oracle、mutation、model delta与telemetry，不拥有Problem builder/hash、rule formula、OBJ-001、Strategy、dynamic Replan、Benchmark或Production入口。

## TASK-P2-08 Strategy/objective boundary

- `planning/policy/delivery.py`拥有唯一批准的versioned Simulation Delivery Policy、无默认值SolveLimits factory与priority source/data-plane gate；不创建native Solver对象。
- `planning/strategies/global_cp_sat.py`拥有单PlanningRun编排、显式run/commit provenance和SolverReport组装；每次只调用一次`solve_delivery_with_evidence`，不分解、不rolling、不fallback、不批准或发布。
- `planning/backends/cp_sat/objectives.py`是新增OR-Tools import的唯一目标模块，拥有每Demand completion max、exact tardiness seconds、priority integer sum、int64 precheck与`Minimize`；C-ID builder、Problem、Policy和Validator均不依赖它。
- `backend.py`保留P2-07 feasibility-only diagnostic入口，并为Global Strategy新增objective-aware evidence入口；两条路径都强制formal independent Validator，candidate FAIL即丢弃。`objective_strategy_check.py`只拥有tiny correctness/provenance evidence，不是BenchmarkRunner。

## TASK-P2-09 Scenario orchestration boundary

`simulation/scenarios/p2_correctness.py`只拥有fixture-local blueprint解析、Raw row assembly、正式pipeline编排、expected/hash核验、row-order property与formula-free candidate mutation。它调用公开Normalization/Data Validation/Expansion/Snapshot/Problem/Strategy/Validator接口，不直接构造PlanningProblem或CpModel，也不复用Backend/Validator公式。`simulation/scenarios/__init__.py`以lazy export避免CLI module预加载。

本Task没有修改`application/**`、`planning/**`、`simulation/generators/**`、Schema、DB/API/Worker或Export/Benchmark边界；P2-10 Reference Schedulers保持未启动。

## TASK-P2-10 Reference Scheduler boundary

- `simulation/baselines/contracts.py`独占五个algorithm identity、policy/result/report版本与honest status；没有Production fallback或最优性status。
- `simulation/baselines/reference_schedulers.py`只依赖solver-neutral Problem/assignment types、Problem hash precheck、UTC helpers和formal Validator；AST/source tests禁止直接导入`planning.backends`或native Solver package。
- 共享feasibility helper拥有deterministic ready/resource scan、RUNNING/HARD fixed tuple与C-001～C-011 candidate construction，但formal acceptance仍只来自fresh Validator；失败必须丢弃partial state。
- Evidence CLI仅在`run_reference_checks`内部使用P2-09公开orchestrator取得冻结Problem，明确不读取其solution/report；它不实现BenchmarkRunner、Global comparison、Export、API/DB/Worker或P3。

PlanningProblem/Solution Schema、Backend/Strategy/Validator公式与P2-09 assets均未修改。P2-11～14不会由该模块导入或自动启动。

## TASK-P2-11 reporting and exporter boundary

`app.planning.reporting`位于Planning output consumer层：只依赖solver-neutral contracts、formal Validator与Snapshot/Problem pure verification，负责冻结SolverReport和构建KPI；它不导入API/ORM/Worker或修改Backend/Strategy。`app.exporters`再单向依赖reporting并把已验证document编码成immutable package；Planning/Domain不得反向导入exporter。

Exporter核心不依赖`jsonschema`或外部I/O服务；Schema validation只存在于tests和CI machine check。目录writer是有界filesystem adapter，不是ExportJob repository/publisher。该分层保持Modular Monolith与Solver-neutral边界，无需新ADR。

## TASK-P2-12 benchmark boundary

`app.simulation.benchmarks`位于Simulation evidence层，单向依赖versioned Profile/Scenario assembler、public Planning Strategy/Problem/Reporting、Reference Scheduler和internal Exporter。它不得被Domain/Planning/Backend/Validator反向导入，不接触API/ORM/Worker/DB/queue，也不直接导入OR-Tools；solver identity经`planning.backends.cp_sat`公共常量和SolverReport取得。

Planning reporting新增的`calculate_schedule_kpi_metrics`只提取已有pure schedule公式，继续不依赖Simulation。Benchmark用它交叉Global KPI v2和Reference carrier，不复制KPI公式。该拓扑已由P2总规预留`simulation/benchmarks`模块，无新依赖或架构决策，ADR不新增。

## TASK-P2-13 evidence orchestrator boundary

`application/p2_gate_report.py`是唯一跨越到`app.exporters.contract_check`的application文件，且只为TASK-P2-13 machine evidence重跑既有公开output boundary；它不导入Exporter实现、API、Infrastructure、Backend/Strategy/Validator native modules、OR-Tools或SQLAlchemy，不承载产品用例、事务或持久化。P1 CommonIngress仍终止于Problem，其他`application/*.py`继续禁止Exporter及Solver/Validator/API/Infrastructure捷径。

该例外由AST integration test按“精确文件→精确module”固定为`p2_gate_report.py → app.exporters.contract_check`，不能扩展为通配或dynamic import。Gate对Simulation correctness/benchmark/export的依赖方向仍是evidence consumer单向下游；Domain/Planning/Validator/Exporter均不反向依赖Gate，因此无需新ADR。

Required run `32465737712`的Lint/Type/full tests、Gate与artifact全部success，provider精确复验该单文件例外及其余application禁令；未出现API/ORM/Worker/native反向依赖。TASK-P2-13据此闭环，不改变P2-14/P3架构边界。

## P3 planned module chain

P3依赖方向固定为domain contracts/state→infrastructure repositories→application services/read models→API/jobs/exporters→frontend；router、worker和UI不得直接写repository状态、复制Validator/Solver规则或决定authority。P3-01用ADR固定边界，P3-03/04～10逐层落地，P3-11～13只通过HTTP/application合同消费。P4 execution/replan模块不得被P3引用为实现捷径。
