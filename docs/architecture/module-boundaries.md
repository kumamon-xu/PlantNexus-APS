---
doc_id: DOC-ARCH-003
title: 模块边界与依赖规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [12, 13, 14, 30, 41, 47, 51, 65, 70]
last_reviewed: 2026-09-01
---

# 模块边界与依赖规则

## TASK-P6-06 duration runtime module boundary

`app.duration_prediction.runtime`单向消费既有P6-04 safe model loader/pure predictor与P6-05 Gate validator，拥有exact runtime-policy、request/standard-authority precheck、candidate/confidence/fallback决策及P6-02 prediction identity。它不导入Application、PlanningProblem/Solver/Validator、Infrastructure、Simulation orchestrator、API、SQLAlchemy、network client或host configuration；provider实例不可变，无cache、thread、queue、database或业务state write。

Caller仍拥有operation/resource-option与标准工时authority；runtime只返回独立advisory carrier，不改FeatureRecord、model、standard duration或P0～P5对象。`p6_duration_runtime_check.py`是唯一machine composition root，可读取tracked synthetic feature/model与P6-05 aggregate report并生成safe evidence，但不得成为Planning/API入口。P6-07才可拥有后继ingress/invariant adapter。

## TASK-P4-12 API module ownership

`app.api.replanning_contracts`拥有HTTP-only query/action/response合同与P4-02 carrier consumer precheck；`app.api.routers.dynamic_replanning`只拥有FastAPI binding、correlation、plane、authorization与delegation；`app.api.replanning_check`是machine composition root。Router只依赖API contract/authorization/config，禁止导入Application、Domain、Repository、Planning/Solver/Validator、Simulation或Exporter owner。

## TASK-P4-11 module ownership

`app.application.change_report_queries`拥有authorization-before-lookup、query preconditions、stable filtering/paging与read projection；它只依赖domain contract和repository ports，不导入Solver。`app.domain.export_job`拥有v2/v3 carrier identity和既有transition语义；`app.exporters.change_report_package`拥有canonical package/verify/load/archive/write；`app.jobs.change_report_export_job`只编排claim/materialize/complete/fail；Infrastructure只持久化/加载version-aware完整carrier。

P3 `standard_package`保持独立owner和冻结行为，P4 exporter只复用其verified package及安全序列化原语。Download application通过package-store port验证结果，不暴露absolute path。没有API/UI、external adapter、Replan orchestration或Simulator反向依赖。

## TASK-P4-10 module boundary

`simulation/scenarios/disruption_replay.py`拥有strict asset parsing、五步coverage/order、P4-09 schedule/config projection、checkpoint partition与downstream evidence validation；`disruption_replay_check.py`是machine composition root，可调用P4-04/P4-08/P4-09 owner checks并生成raw evidence。Runtime orchestrator只依赖pure contract/Simulation execution surface，不导入Infrastructure、API、OR-Tools/CP-SAT、SQLAlchemy或wall clock。

`ContinuousReplanPort`是唯一downstream composition boundary；fact/Snapshot、freeze、Solver/Validator、repository、DRAFT与ChangeReport语义继续由原owner负责。Scenario层不写repository、不推进业务state、不提供P5/Production adapter。

## TASK-P4-09 module boundary

`backend/app/simulation/execution/contracts.py`拥有immutable Simulation run/event-schedule/clock/checkpoint inputs；`simulator.py`只拥有compile、queue、canonical Event、prefix restart与manifest projection；`simulator_check.py`是machine composition root，可用真实P4-04 service证明端口，但不属于core import boundary。Core可以消费pure domain event/capability/provenance/hash helpers，禁止导入Infrastructure、Planning/Solver、API或Application service。

唯一side-effect port为`ExecutionEventIngressPort.ingest_event(Mapping)`；P4-04 `ExecutionFactProjectionService`结构化满足该端口。Scenario/disruption generation留在P4-10 owner，fact/Snapshot/Replan/ScheduleVersion state仍由既有模块负责。

## TASK-P4-08 implemented dependency edge

`app.application.replan_application`只编排既有domain、Snapshot/Problem builder、freeze projection、Strategy、fresh Validator、ChangeReport与plane-scoped repositories；domain builder负责Simulation-only授权、DRAFT identity/content/lineage，repositories负责caller-owned transaction和existing-table immutable result envelope。Application不导入API/UI/Simulator/export adapter，Solver/Validator/ChangeReport均不反向依赖Application。

`SqlAlchemyScheduleVersionRepository`在不新增table/migration的前提下同时识别冻结v1与公开v2 carrier；`replan_results.record_json`保存内部envelope但不成为新业务Schema或状态机。P4-08没有复制P4-07公式、改变P3 lifecycle或建立P5/Production edge。

既有application AST guard现以逐字文件→逐字module集合登记该获批边：runtime文件只可静态引用P4-03 persistence values/errors、P4-07 Strategy/fresh Validator、ChangeReport precheck及SQLAlchemy transaction types/errors；machine checker只可装配逐字列出的repositories、SQLite engine与P4-07 fixture入口。该例外禁止通配，其他application文件仍保持原禁令，且不授权API、Exporter、Simulator、OR-Tools对象或具体CP-SAT backend进入runtime service。

## TASK-P4-07 implemented dependency edge

CP-SAT变量、effective HARD constraints、Hint和六轮objective orchestration只位于`app.planning.backends.cp_sat`；`app.planning.strategies.lexicographic_replan`只验证lineage并组装SolverReport。`app.planning.validation.replan_candidate_validator`不导入OR-Tools/backend/reporting calculator，独立调用formal public validator并重算P4算术。三者均不依赖repository/application/API/UI/Simulator，不写状态；machine checker只负责组合fixture与证据。

## TASK-P4-05 implemented pure dependency edge

`app.planning.policy.freeze_window`只依赖既有pure contracts/Snapshot verification；`app.planning.problem.freeze_projection`消费policy、Snapshot、Problem和workspace/P4 carriers；`app.planning.validation.freeze_window_precheck`独立重算而不导入projector、CP-SAT Backend或formal `ProblemScheduleValidator`。Machine checker/tests可以组装versioned Simulation向量，但runtime projector没有repository/application/Simulator/API/UI依赖，也不创建ScheduleVersion。

## TASK-P4-04 implemented dependency edge

依赖方向现为`domain/execution_fact_projection`纯规则 ← `snapshots/projection` canonical finalizer ← `application/execution_fact_projection`事务编排 → P4-03 repositories；`importers/urgent_demand`只携带既有Normalization inputs。Domain不导入SQLAlchemy、repository、Solver或wall clock；application不复制event/fact规则；repositories不解释payload。后继freeze/solver/application/Simulator仍不可反向进入本边界。


## TASK-P4-03 implemented dependency edge

`app.domain.execution_contracts → app.infrastructure.replan_persistence/execution_event_repository/replan_repository`已形成单向consumer edge；repositories只依赖纯carrier precheck和既有SQLAlchemy/Alembic primitives。它们暴露caller-owned transaction与CAS，不导入Application、Planning、Solver、Validator、Simulation、API、Frontend或Exporter。P4-04只能消费这些ports完成projection，不能绕过ledger；P4-08只能消费attempt/result references完成application。

## TASK-P4-02 module boundary

新增实现仅位于domain pure contracts/check CLI；它可解析JSON/YAML与校验Schema，但不导入repository、application service、OR-Tools、Simulator、API或Frontend。两处existing application/domain machine checker只同步current global metadata，不改变P3业务路径。后继consumer不得把pure precheck当作transaction或authority provider。

## TASK-P4-01 accepted module allocation

ADR-0013～0015固定依赖方向：contract/domain event+fact semantics → plane-scoped ledger/repositories → fact/Snapshot projector → replan application → existing Strategy/Backend + independent Validator → Version/ChangeReport persistence → read/export/API/UI。TASK-P4-02只发布carrier；P4-03不实现业务projection；P4-04不直接solve/apply；P4-05/06只提供pure freeze/stability/report边界；P4-07不写repository；P4-08不复制Solver/Validator；P4-09/10只生成标准Event；P4-11/12/13只消费application/read authority。

禁止Simulator直写fact/Snapshot/Version、API/router/worker复制transaction或objective、Frontend计算authority/OBJ-002/ChangeReport。Evidence orchestrator只能调用公开边界并保留raw report。本Task没有源码、目录或依赖变化；后继Task须在激活时把上述目录责任收紧为exact file allow-list。

## TASK-P3-17 audit conclusion

Domain/application ports、SQLAlchemy adapters、thin HTTP router、Frontend consumer、export worker与formal Validator依赖方向经source/machine/full tests复验；router/UI无business transition或Solver调用，publication与export worker保持分离。Audit没有改变模块或依赖锁。

## TASK-P3-14 evidence-orchestrator boundary

新增`app.application.p3_gate_report`只编排P3-02～10既有公开machine boundaries、P2 Gate和Frontend Gate文件，不得从Gate层实现repository、state、Solver/Validator、API或UI行为。既有application import guard为该文件逐字允许`app.api.planning_workspace_check`与`app.infrastructure.workspace_persistence_check`两个只读machine-check入口，除此之外仍全部禁止；该窄例外与P2 Gate同属evidence orchestration，不是业务依赖。Frontend Node脚本只解析Playwright与P3-13 evidence并生成稳定报告；没有反向业务依赖、Schema、migration或runtime service增加。

## TASK-P3-13 bounded dependency additions

Frontend依赖方向固定为`api canonical/contracts/client → useHumanControlAction → feature controls → pages`；feature只提交carrier并渲染server authority。Backend download依赖方向固定为`HTTP adapter → application download service ports → read-only Job repository/package store → standard package verifier/archive`，router与store都不持有business transition。Worker与download共用root-confined attempt destination identity，避免两套path语义。

无Frontend→domain/backend import、无router→repository/Solver/Validator shortcut、无package store→external network。Schema、migration、dependency/lock、P3-06～09 domain/application语义与P4目录均不变；若以后加入object storage、streaming gateway或Production identity，必须另立Task/ADR。

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

ADR-0012已接受该方向并补充：domain定义versioned command/query/state/error语义；repository只提供plane-scoped immutable/append-only/CAS/idempotency原语；application是capability/state/transaction/fresh Validator的唯一owner；API/jobs/exporters只适配；React只消费HTTP并显示server authority。P3-02发布carrier、P3-03持久化、P3-04～09应用服务、P3-10 API、P3-11～13 frontend，不允许任一层反向成为第二权威。

本Task没有创建module或代码。任何需要API→repository直写、UI/client solver、shared Solver/Validator、outbox/external adapter或P4 module引用的实现必须停止并先行新ADR/Task授权。

## TASK-P3-03 repository layer formed

`app.domain.state_machines.schedule_version|export_job`只包含pure CAS/attempt/lease不变量；`app.infrastructure.workspace_persistence`及四个SQLAlchemy repository只负责plane、canonical integrity、unique/FK/index、append-only、CAS和caller-owned transaction。依赖保持domain→infrastructure，且import package不建连接。Application/API/jobs/exporters/frontend均零差异，router/worker/UI仍不能直接写repository。

未引入outbox、event bus、external adapter或新topology，因此无需新ADR；P3-04～09必须通过公开`*_in_transaction`原语由application组合capability/state/Validator/audit，不能把repository成功当成业务Gate成功。

## TASK-P3-04 application composition

`app.domain.schedule_version`只依赖domain state/types/workspace pure contracts；AST evidence禁止其反向导入Infrastructure、Planning或Simulation。`app.application.schedule_versions`声明repository ports与transaction factory注入，只调用P2 public reporting/Validator consumer，不静态导入SQLAlchemy/Infrastructure、CP-SAT Backend、Strategy或Simulation，且源文件无`.solve(`调用。Machine CLI是唯一executable composition root，以延迟runtime装配既有adapter并复用冻结P2 correctness test input；报告明确service Solver调用为0，既有P1 application-boundary AST Gate继续PASS。

Application是本slice唯一transaction owner：repository仍不知道fresh Validator、COMPLETED gate、actor reason或audit业务动作；API/UI/Worker不得直接调用repository。没有新outbox/topology/dependency，若未来需跨事务side effect仍须新ADR。

## TASK-P3-05 read composition

`app.domain.workspace`只依赖domain types/contracts并拥有pure bind/projection/filter/sort/cursor/comparison；`app.application.workspace_queries`与`schedule_comparison`声明read-only repository ports并组合权威Version/audit，既不静态导入Infrastructure、Simulation或CP-SAT，也没有write/transition/Solver port。`workspace_read_model_check`是测试composition root，才可延迟装配既有SQLite adapters和冻结P2 fixture。

完整payload与published carrier分层是既有Schema约束下的application return value，不是cache/materialized view或新transport Schema。若后续引入持久化read store、异步物化或跨进程cache，必须先建ADR并重新确认authority/freshness。

## TASK-P3-06 command composition

`app.domain.schedule_commands`只依赖domain types/workspace pure contracts，负责strict carrier、semantic guard、copy-on-write DRAFT及显式review submission的READY/audit documents；它不导入Planning Validator、Infrastructure、Simulation、CP-SAT或HTTP。`app.application.schedule_commands`只声明Schedule get/insert/CAS、Audit、transaction和Validator ports，Validator factory必须由外部显式注入；它不静态导入Planning Validator、SQLAlchemy、Infrastructure、Backend/Strategy或Solver API。`schedule_command_check`是唯一executable composition root，才装配公开`ProblemScheduleValidator`、临时SQLite adapters与冻结synthetic inputs。

Application拥有atomic insert+append与CAS+append transaction；repository不决定command capability/semantics，API/UI不得直接写repository或复制mutation/Validator逻辑。没有新outbox、cache、queue、dependency或topology；若未来跨事务记录失败attempt或异步command，必须先建ADR。

## TASK-P3-07 approval boundary

`app.domain.authorization`只依赖domain types/workspace pure contracts，负责strict APPROVE/REJECT carrier、server context guard、deterministic identity、same-content decision candidate及success/denial AuditEvent；它不导入Infrastructure、Planning、Simulation、HTTP或identity SDK。`app.application.approval`只声明Schedule get/CAS、Audit get/append与transaction ports，并拥有authorization-before-lookup、replay/conflict和atomicity编排；它不导入SQLAlchemy、repository adapter、Solver、Validator、API或Frontend。

`approval_decision_check`才作为executable composition root装配既有SQLAlchemy repositories、临时SQLite和P3-04 frozen lifecycle input。Repository只执行durability/CAS/append，不选择capability或Production role；未来HTTP、RBAC/SSO、publish/export adapter不得复制或绕过application guard。没有新dependency、outbox、queue、service或deployment topology。

## TASK-P3-08 publication module boundary

`app.domain.publication`只依赖domain types/workspace pure contracts，负责strict PUBLISH carrier、server context guard、deterministic identities、published/superseded/result/audit documents；不导入Infrastructure、Planning、Simulation、HTTP、Exporter或identity SDK。`app.application.publication`只声明Schedule/Audit/Publication repository与transaction ports，拥有authorization-before-lookup、historical replay、current CAS和atomicity编排；不导入SQLAlchemy adapter、Solver、Validator、API或Frontend。

`publication_check`作为executable composition root装配既有repositories与临时SQLite。Repository仍只提供durability，不能授权或自动publish/export。没有新dependency、outbox、queue、worker、network、service或deployment topology。

P3-09依赖方向为`domain.export_job`→ports-only`application.export_jobs`→SQLAlchemy repositories；`exporters.standard_package`只消费冻结contracts/openpyxl，`jobs.export_job`是thin composition且不注册Celery business task。Domain/application/exporter/job均不依赖publication application service、API/frontend、network/external adapter或P4。

## TASK-P3-10 API boundary

`app.api.routers.planning_workspace` 只依赖API contracts、authorization dependency和由composition root注入的application port；禁止导入`app.application.*`具体service、`app.domain.*`业务state、repository、Solver或Validator。`app.api.app` 是唯一组装点，默认使用unavailable facade/provider以fail closed。Machine/static tests验证17个operation全部只委托一次、business transition和Solver/Validator invocation为0；无新service topology或ADR。

## TASK-P3-11 Frontend boundary

依赖方向固定为`pages/components/app → api client/query/types`，再通过HTTP读取P3-10；Frontend不导入Backend source、Schema interpreter、Solver、Validator、repository或state transition。API client只发GET并从注入的ephemeral session provider取得token；默认provider返回null，任何server/contract/auth/stale failure都映射成明确非成功状态。

Frontend只比较carrier reference和server完整payload item的一致性，保留server fingerprint authority；它不依据payload重算KPI/Resource Load或授权动作。TanStack Query只是transport cache，server state/precondition/error覆盖缓存。P3-12/13不得把Gantt/control逻辑塞回P3-11模块。

## TASK-P3-12 Frontend visualization boundary

`frontend/src/api`只扩展strict visualization types/query/parser与comparison read-query transport；`app/useWorkspaceView`集中Version precondition、query state和七类页面状态；`features/gantt`、`features/resource-load`、`features/version-comparison`只做presentation、server filter与navigation。`GanttTimeline`拥有windowing/pixel layout和可访问table，但不拥有duration、feasibility、KPI、load或delta算法。

Comparison唯一POST仍属于read operation且明确无Idempotency-Key；feature不得导入command/action模块。Playwright只经mock network验证browser consumer并不连接repository/application service。Dependency方向、P3-10 backend API、state machine和24个pins/lock均不变；P3-13 control不得反向把mutation塞入这些read-only模块，P4与Production adapters仍不存在。

P3-11 artifact `9552386549`先以source boundary scan、GET/client tests和9/9 machine checks复验foundation依赖方向；P3-12 artifact `9555196470`再以strict transport tests、4/4 Chromium及12/12 machine checks复验visualization依赖方向。两项Task均`done`；这仍不形成command/action、external、P4或Production边界。
