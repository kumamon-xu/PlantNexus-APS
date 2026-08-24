---
doc_id: DOC-QUAL-001
title: 测试策略与 Test Matrix
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [31, 57, 72, 74, 76, 78, 80, 86, 87, 88, 89, 100]
last_reviewed: 2026-08-24
registry_version: 1.0.0
---

# 测试策略与 Test Matrix

## 测试层

| 层 | 目的 |
|---|---|
| Unit | 局部纯逻辑和错误边界 |
| Contract | Schema、状态、API/adapter 语义 |
| Integration | DB/queue/import/export 和模块协作 |
| Golden | 小规模、人工/暴力可验证 correctness |
| Mutation | 证明 Validator 能拒绝人工错误计划 |
| Property | 随机合法 Problem 的通用不变量 |
| Simulation | 可重放场景、覆盖与动态异常 |
| Benchmark | correctness、quality、runtime、memory regression |

## 必需 Test IDs

| Test ID | Purpose | Earliest phase | Evidence status |
|---|---|---|---|
| TEST-TRACEABILITY-VALIDATOR | Registry、reference、Task、diff/impact，以及 clean-tree committed range regression | P0 | [`backend/tests/unit/test_check_docs.py`](../../backend/tests/unit/test_check_docs.py) |
| TEST-PHASE-GOVERNANCE-001 | Current/prior/future Phase Task policy与 CI changed-task handoff | P1 | [`test_check_docs.py`](../../backend/tests/unit/test_check_docs.py) phase/range/discovery negative paths + [`test_ci_contract.py`](../../backend/tests/integration/test_ci_contract.py) generic workflow/no-stale-P0 handoff formed |
| TEST-OBS-001 | 日志、运行标识与 Observability 关联 | P0 | [`test_logging.py`](../../backend/tests/integration/test_logging.py) JSON/context/trace-ID/redaction P0 slice formed；PlanningRun metrics/audit retention PLANNED |
| TEST-CONTRACT-001 | Schema meta/positive/negative、版本、UTC/duration/reference、isolation 与 round-trip | P0-P3 | Existing schema suite + [`test_p2_output_contracts.py`](../../backend/tests/contract/test_p2_output_contracts.py) + [`test_p3_workspace_contracts.py`](../../backend/tests/contract/test_p3_workspace_contracts.py)；preserved artifacts/additive `2.6.0` workspace carrier与cross-document negatives formed |
| TEST-IMPORT-STAGING-001 | Raw batch/row provenance、transaction、migration与 idempotent replay | P1 | [`test_import_staging.py`](../../backend/tests/unit/test_import_staging.py) + [`test_raw_import_staging.py`](../../backend/tests/integration/test_raw_import_staging.py) + [`test_migrations_and_infrastructure.py`](../../backend/tests/integration/test_migrations_and_infrastructure.py) formed / TASK-P1-03 |
| TEST-IMPORT-ADAPTER-001 | CSV/XLSX/ReferenceFileAdapter semantic parity与文件安全拒绝 | P1 | [`test_input_adapters.py`](../../backend/tests/contract/test_input_adapters.py) + [`test_reference_file_adapter.py`](../../backend/tests/integration/test_reference_file_adapter.py) formed / TASK-P1-04 |
| TEST-NORMALIZATION-001 | ID/time/unit mapping、canonical bytes、unit error与 missing duration | P1 | [`test_normalization.py`](../../backend/tests/unit/test_normalization.py) formed / TASK-P1-05；`cycle_seconds_per_unit` explicit-unit regression added / TASK-P1-10 |
| TEST-DATA-QUALITY-001 | DAG/reference/capability/quality report与四类 P1 exact rejection | P1 | [`test_data_validation.py`](../../backend/tests/unit/test_data_validation.py) + [`test_import_validation.py`](../../backend/tests/contract/test_import_validation.py) formed / TASK-P1-06；[common-ingress exact rejection](../../backend/tests/contract/test_p1_exit_rejections.py) added / TASK-P1-11 |
| TEST-ORDER-EXPANSION-001 | Order/Lot/Routing到 OperationInstance/edge deterministic expansion | P1 | [`test_order_expansion.py`](../../backend/tests/unit/test_order_expansion.py) + [`test_order_expansion_properties.py`](../../backend/tests/property/test_order_expansion_properties.py) formed / TASK-P1-07；provider run `32265257468` PASS |
| TEST-SNAPSHOT-REPLAY-001 | Snapshot canonical bytes/hash/ID、immutability与 repository replay | P1 | TASK-P1-08 suites formed/provider `32310098594` PASS；[P1 pipeline full-byte replay](../../backend/tests/simulation/test_p1_pipeline_replay.py) added / TASK-P1-11 |
| TEST-PROBLEM-REPLAY-001 | Solver-neutral Problem builder/bytes/hash deterministic replay | P1 | TASK-P1-09 unit/property/Golden formed/provider `32315513504` PASS；[P1 pipeline full-byte replay](../../backend/tests/simulation/test_p1_pipeline_replay.py) added / TASK-P1-11 |
| TEST-P1-COMMON-INGRESS | Reference/Synthetic共同 staging→Problem链路与 Gate report | P1 | [`test_p1_common_ingress.py`](../../backend/tests/integration/test_p1_common_ingress.py) + [`test_p1_pipeline_replay.py`](../../backend/tests/simulation/test_p1_pipeline_replay.py) + [`test_p1_exit_rejections.py`](../../backend/tests/contract/test_p1_exit_rejections.py) formed / TASK-P1-11 |
| TEST-RULE-SHEET-001 | C-001～C-018 唯一/完整、input/formula/example/violation/Test ID 与 registry cross-check | P0 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) + [`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) + [TASK-P0-04 Acceptance PASS](../tasks/P0/TASK-P0-04-constraints-states-errors-capabilities.md#completion-evidence) |
| TEST-STATE-TRANSITION-001 | 三套 state enum、42 个 allowed pair、terminal/negative transitions | P0-P3 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) + [`test_p3_workspace_contracts.py`](../../backend/tests/contract/test_p3_workspace_contracts.py) + [`state-machines.v1`](../../schemas/rules/state-machines.v1.yaml) formed；P3 carrier alignment formed，persistence/behavior PLANNED |
| TEST-ERROR-MAPPING-001 | 七类 error、global code/category与namespace isolation | P0-P3 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) + [`test_p3_workspace_contracts.py`](../../backend/tests/contract/test_p3_workspace_contracts.py)；global registry preserved、workspace-control separation formed；HTTP behavior PLANNED |
| TEST-CAPABILITY-001 | 20 capability registry 与 supported declaration/unsupported/unknown/duplicate precheck | P0 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) registry contract + [`test_data_validation.py`](../../backend/tests/unit/test_data_validation.py) platform rejection/ordinary resource matching formed；Solver capability implementation PLANNED |
| TEST-GOLDEN-JSSP | 人工可验证 JSSP | P2 | [`P2-GOLDEN-JSSP@1.0.0`](../../backend/tests/golden/test_p2_golden_solver.py) fixed Solver→Validator optimum/hash replay formed / TASK-P2-09 |
| TEST-GOLDEN-FJSP | 人工可验证 FJSP | P0-P2 | [`SIM-MINIMAL-001` positive Golden](../../backend/tests/golden/test_sim_minimal_001.py) + [`P2-GOLDEN-FJSP@1.0.0` Solver integration](../../backend/tests/golden/test_p2_golden_solver.py) formed |
| TEST-INF-NO-RESOURCE | 无候选资源明确拒绝 | P0-P2 | P0/P1 input slices + formal wrong-resource + [Solver-candidate exact C-003 mutation](../../backend/tests/validation/test_p2_solver_mutations.py) formed |
| TEST-INF-LOCK | Lock 导致的不可行性 | P0-P2 | P0/formal/P2-07 infeasible slices + [P2 Hard Lock positive and exact C-008 mutation](../../backend/tests/validation/test_p2_solver_mutations.py) formed |
| TEST-INF-HORIZON | Horizon 不允许静默截断 | P0-P2 | P0/formal horizon slices + [Solver-candidate exact C-011 mutation](../../backend/tests/validation/test_p2_solver_mutations.py) formed |
| TEST-CALENDAR | 设备日历约束 | P0-P2 | Golden/formal slices + [`P2-CALENDAR@1.0.0` Solver replay](../../backend/tests/simulation/test_p2_scenario_matrix.py) and C-005 mutation formed |
| TEST-MATERIAL | material_ready_at gate | P0-P2 | Golden/formal slices + [`P2-MATERIAL-DELAY@1.0.0` Solver replay](../../backend/tests/simulation/test_p2_scenario_matrix.py) and C-006 mutation formed |
| TEST-RUNNING | 运行中事实保护 | P0-P2 | P0/P1/formal/P2-07 slices + [`P2-RUNNING@1.0.0` Solver replay](../../backend/tests/simulation/test_p2_scenario_matrix.py) and C-007 mutation formed |
| TEST-CROSS-WORKSHOP | 跨车间 precedence/transport lag | P0-P2 | Golden/formal slices + [`P2-CROSS-WORKSHOP@1.0.0` Solver replay](../../backend/tests/simulation/test_p2_scenario_matrix.py) and C-009 mutation formed |
| TEST-MAX-LAG | max_lag 不被忽略 | P0-P2 | Golden/formal inclusive min/max lag + P2 versioned JSSP/Scenario complete-edge Solver replay formed |
| TEST-VALIDATOR-MUTATION | 独立 Validator 拒绝人工错误计划 | P0-P2 | P0/formal suites + [11 formula-free mutations of Solver-produced candidates](../../backend/tests/validation/test_p2_solver_mutations.py) formed；performance integration PLANNED |
| TEST-REPLAN | Replan 事实、锁与变化报告 | P4 | PLANNED |
| TEST-OUTPUT | 标准成果包合同 | P2-P3 | [`test_p2_output_contracts.py`](../../backend/tests/contract/test_p2_output_contracts.py) + [`test_p2_export_package.py`](../../backend/tests/integration/test_p2_export_package.py) internal synthetic profile/schema/hash/count/lineage/tamper/atomic boundary formed；P3 publish PLANNED |
| TEST-IDEMPOTENCY | Import/Planning/Export/Publish/Event 幂等 | P0-P3 | generic primitive + durable Import staging + P2 internal package + TASK-P3-03 Audit/Publication/ExportJob unique exact replay/conflict and current-reference CAS formed；business approval/publish/export/worker/external side effects PLANNED |
| TEST-SCENARIO-REPLAY | Scenario/Profile/Generator/seed 重放 | P0-P2 | empty/P0 + P1 ingress + [seven versioned Solver/Validator replays](../../backend/tests/property/test_p2_solver_properties.py) with fixed hashes and row-order invariance formed |
| TEST-SIM-ISOLATION | Synthetic/Production 隔离 | P0-P3 | generator/common-ingress + Raw/Snapshot + TASK-P3-03 plane-scoped repository/cross-plane/internal-only publication-export guards formed；separate Production DB/API/auth/publish target PLANNED |
| TEST-REFERENCE-SCHEDULER | Reference Scheduler baseline | P2 | [five algorithms / 35 complete candidates / explicit failure](../../backend/tests/unit/test_reference_schedulers.py) and [shrinkable properties](../../backend/tests/property/test_reference_scheduler_properties.py) provider-verified |
| TEST-BENCHMARK | BenchmarkReport/profile 回归 | P2 | [`test_benchmark_contract.py`](../../backend/tests/contract/test_benchmark_contract.py) + [`test_benchmark_runner.py`](../../backend/tests/integration/test_benchmark_runner.py) strict Profile/Report/Baseline、XS/S/M replay、Global/Reference/Validator/KPI、warning/threshold与required CI XS artifact provider-verified |
| TEST-PROPERTY | 合法 Problem 的通用不变量 | P2 | Problem v2/formal/Solver properties + [Reference gate/duration/due and authoritative Problem properties](../../backend/tests/property/test_reference_scheduler_properties.py) + [generated XS/S/M formal pipeline replay](../../backend/tests/integration/test_benchmark_runner.py) formed |
| TEST-SOLVER-UPGRADE | Solver 升级 replay/status contract | P2+ | Benchmark baseline固定Python/OR-Tools/environment signature并拒绝profile/problem/complexity drift的P2 development slice formed；实际upgrade重建新版本baseline/compatibility evidence仍PLANNED |
| TEST-WORKSPACE-CONTRACT-001 | P3页面/API/permission/state/error/audit/idempotency合同一致性 | P3 | TASK-P3-01 human baseline + TASK-P3-02 seven strict machine carriers/pure fingerprints/negative vectors formed；persistence/application/API/UI behavior PLANNED |
| TEST-SCHEDULE-VERSION-REPOSITORY-001 | ScheduleVersion/Audit/ExportJob migration、immutability、transaction与replay | P3 | FORMED / TASK-P3-03 provider-verified storage slice |
| TEST-SCHEDULE-VERSION-LIFECYCLE-001 | Validated Solution→DRAFT→READY_FOR_REVIEW与非法状态拒绝 | P3 | PLANNED / TASK-P3-04、07～08 |
| TEST-WORKSPACE-READ-MODEL-001 | Gantt、Resource Load、Order View与Version Comparison lineage/KPI一致性 | P3 | PLANNED / TASK-P3-05 |
| TEST-GANTT-COMMAND-001 | Edit/Lock command→server validation→new DRAFT→formal Validator | P3 | PLANNED / TASK-P3-06 |
| TEST-APPROVAL-AUTHORIZATION-001 | authority-neutral capability、default-deny、approve/reject guards | P3 | PLANNED / TASK-P3-07、10、13 |
| TEST-PUBLISH-IDEMPOTENCY-001 | APPROVED-only publish、same-key replay、conflict与supersession | P3 | PLANNED / TASK-P3-08 |
| TEST-EXPORT-JOB-001 | ExportJob transition、package integrity、atomic/idempotent export与失败恢复 | P3 | persistence state/lease/attempt slice FORMED / TASK-P3-03 provider-verified；package/export behavior PLANNED / TASK-P3-09 |
| TEST-AUDIT-TRAIL-001 | append-only actor/reason/correlation/before-after/version audit完整性 | P3 | append/replay/trigger/index slice FORMED / TASK-P3-03 provider-verified；business action completeness PLANNED / TASK-P3-07～10 |
| TEST-WORKSPACE-API-001 | HTTP payload/error/auth/idempotency/OpenAPI与application boundary | P3 | PLANNED / TASK-P3-10 |
| TEST-WORKSPACE-FRONTEND-001 | read/action UI、状态可见性、accessibility与no-client-authority E2E | P3 | PLANNED / TASK-P3-11～13 |
| TEST-P3-VERTICAL-SLICE-001 | P3完整workspace→review→approve→publish→export双重replay与拒绝门 | P3 | PLANNED / TASK-P3-14～15 |

Test ID 一经分配不得复用。链接到真实测试路径才是已形成证据；`PLANNED` 只登记合同。表结构或状态语义变化必须提升 `registry_version`。

TASK-P2-09未新增或复用Test ID；它把TEST-GOLDEN-JSSP/FJSP、CALENDAR/MATERIAL/RUNNING/CROSS-WORKSHOP/INF类、VALIDATOR-MUTATION、SCENARIO-REPLAY与PROPERTY链接到四个新focused files。Focused=45 passed、full repository=427 passed，覆盖2 Golden、5 matrix、7 row-order/fresh Validator properties、11 exact Solver-candidate mutations及CI machine contract；`p2-correctness-report.v1`为8/8。XS/S/M、Reference、Export、P2 Gate与Production测试仍为`PLANNED`，registry format version保持`1.0.0`。

Implementation provider run `32442651322` / artifact `9432982306`精确复现上述427 tests与8/8 correctness report；TASK-P2-09=`done`。这不改变Test ID集合或表结构，XS/S/M、Reference、Export、P2 Gate与Production测试仍为`PLANNED`，registry format version保持`1.0.0`。

TASK-P2-10不新增或复用Test ID；它把TEST-REFERENCE-SCHEDULER与TEST-PROPERTY链接到五个exact algorithm identity、unit/property/integration tests和`reference-scheduler-report.v1`。新增Task-specific tests=`13 passed`，full repository=`441 passed`，machine report为7/7、35 complete/fresh Validator/deterministic、5 explicit failures；Ruff/Pyright均0问题。Implementation provider run `32449742281` / artifact `9435264655`精确复现上述441 tests、reference 7/7及38-path治理，故TASK-P2-10=`done`；TEST-BENCHMARK、Export、P2 Gate与Production继续PLANNED，registry format version保持`1.0.0`。

TASK-P2-11不新增或复用Test ID；它把TEST-OUTPUT、TEST-CONTRACT-001与TEST-IDEMPOTENCY的internal slice链接到两份新focused files和`p2-output-contract-report.v1`。Contract tests覆盖KPI/manifest Schema/sample、KPI v1 byte preservation、metric formulas、SolverReport freeze及mixed/Validator failures；integration覆盖same-input bytes、file/hash/count/CSV lineage、tamper/missing、synthetic provenance、exact replay/conflict与partial-write cleanup。P3 ExportJob/publish side effects和P2-12 TEST-BENCHMARK继续PLANNED，registry format version保持`1.0.0`。

本地指定验收=`49 passed`、full repository=`455 passed`，其中新增task-specific测试13项；Ruff/Pyright为0问题，output machine report为8/8。首次full准确暴露3个旧global schema-set断言并在先扩allow-list后修正为`2.5.0`，其document-level版本与历史fingerprint断言保持。Implementation provider run `32454693799` / artifact `9436863185`精确复现455 tests、output 8/8、18/18 reports及58-path治理，故TASK-P2-11=`done`；TEST-BENCHMARK、P2 Gate与Production测试继续PLANNED，registry format version保持`1.0.0`。

TASK-P2-12不新增或复用Test ID；它把TEST-BENCHMARK、TEST-REFERENCE-SCHEDULER、TEST-SCENARIO-REPLAY、TEST-PROPERTY和TEST-SOLVER-UPGRADE的P2 development slice链接到strict `benchmark-profile-set/report/baseline.v1`、两份新focused test及真实CI XS命令。本地指定验收=`27 passed`、full repository=`466 passed`，XS/S/M三份report均为8/8且所有Global/Reference candidate经fresh formal Validator；全部历史machine reports、Ruff/Pyright、Compose/build和治理diff均PASS。Implementation provider run `32460861563` / artifact `9438899443`精确复现19/19 reports、XS 8/8与49-path治理，故TASK-P2-12=`done`；S/M保留local policy evidence。L/XL、Production SLA/capacity、P2 Gate/audit与P3继续PLANNED，registry format version保持`1.0.0`。

## 原则

- 测试失败不能通过删除硬约束或修改断言规避；
- Solver 与 Validator 必须有不同实现路径；
- Golden 关注 feasibility、objective 和约束，不比较完整 Gantt JSON；
- 多个同质量解可能都正确，Property/Golden 不固定无意义排序；
- Benchmark 正确性失败优先于性能结果。

实际测试路径和结果在文件创建后写入追踪矩阵。TEST-CONTRACT-001 已形成 P0 data Schema skeleton 证据；TASK-P0-04 的四项 contract tests 只形成 rule/state/error/capability 合同证据。Rule-sheet completeness 不能替代 schedule correctness；TEST-VALIDATOR-MUTATION 当前只形成 P0 fixture-local slice，不能外推为 P2 production completion。

TASK-P0-05 新增 10 项 Simulation tests，覆盖三份 Draft 2020-12 Schema/sample、strict version/seed/unknown-field rejection、Profile range semantic check、same-input canonical Import/hash replay、generated-at exclusion、seed/version/capability declaration order、命名 layer seed、Production/unknown/duplicate/unsupported rejection，以及 Generator 不导入 Planning/Solver 的边界。其 `records={}`，因此只形成 TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION 的 P0 contract slice；Golden、non-empty generator、DB/API isolation、Benchmark/Execution/Reference Scheduler 仍为 `PLANNED`。

TASK-P0-06 新增 5 项 Golden tests：四份既有 Schema + pure contract、15-record non-empty Import hash replay、2/2/3 topology/profile/assumption trace、C-001～C-011 独立直接计算、Delivery/Planning/Resource KPI 与 objective lower bound、loader 无 Planning/Solver/evaluator import boundary。它形成 TEST-GOLDEN-FJSP 和 TEST-SCENARIO-REPLAY 的 P0 correctness slice，以及 TEST-CALENDAR/MATERIAL/CROSS-WORKSHOP/MAX-LAG 的 positive slice；negative mutation、正式 Validator/Solver/Problem/KPI、TEST-PROPERTY 和性能证据仍 `PLANNED`。

TASK-P0-07 新增 18 项 Validator tests：positive Golden PASS；13 个 mutation 的 exact C-ID/report/error 与 v2 Schema；max-lag/calendar/running/transport/duration/horizon 手算；deep-copy/materializer formula separation；Rule Sheet metadata/11 C-ID/13 mutation-class coverage；candidate envelope rejection和 validation package backend/OR-Tools dependency scan。它形成 13 cases/15 hard violations 的 TEST-VALIDATOR-MUTATION P0 evidence；正式 PlanningProblem/candidate、Solver comparison、random Property、Benchmark 和 READY_FOR_REVIEW integration 仍 `PLANNED`。Test registry 格式与 ID 生命周期未变，`registry_version` 保持 `1.0.0`。

TASK-P0-08 新增 26 项 integration tests：environment-only/malformed-value/Production fail-closed config、health live/ready 200/503 与 no-leak、JSON context/OpenTelemetry enable-disable/redaction、job owner/lease/heartbeat/attempt/STALLED/completion、atomic idempotent replay/conflict、Alembic empty-DB upgrade/downgrade、lazy DB/Redis client、JSON-only Celery/no business task、exact dependency/Compose/Dockerfile/CI/machine report contract。它形成 TEST-OBS-001 与 TEST-IDEMPOTENCY 的 P0 engineering slice；真实 PostgreSQL/Redis network、distributed repository/scanner、PlanningRun metrics、business Import/Planning/Export/Publish/Event idempotency、production security/UAT/Benchmark 均继续 `PLANNED`。Test registry format/version 未变。

TASK-P0-09 没有增加或修改测试、断言、Test ID 或 registry format；它独立重跑 unit/contract/simulation/golden/validation/integration 共 90 tests，27 个已登记 Test ID 的 formed/`PLANNED` 边界保持不变。五类 machine reports 与 no-Solver gate均 PASS，但 workflow 的旧 Task diff step在 P0-09 commit 上 `FAIL` 且当时 external provider execution `NOT_RUN`，所以该次 CI Gate与 P0 Exit Gate不能通过；两项缺口由 TASK-P0-10 承接，`registry_version` 保持 `1.0.0`。

TASK-P0-10 不新增 Test ID、test function、fixture 或 assertion 豁免；它在既有 `test_ci_runs_all_p0_gates_and_keeps_benchmark_as_a_hook` 中加强 workflow handoff 断言：exact TASK-P0-10 diff command 与 `p0-exit-gate-evidence-${{ github.run_id }}` 必须存在，任何 `TASK-P0-08` workflow 残留必须失败。测试总数仍为 90，已登记 27 个 Test ID 与既有 formed/`PLANNED` 边界不变；provider run/artifact/required-check 是 CI Gate artifact，不是新业务测试。

本地 90-test suite 及 GitHub run `32228647627` 的 P0 test/machine-contract steps 均 PASS，且 clean implementation commit 的目标 integration file为 5 passed。该结果只关闭 CI handoff/provider evidence gap；不新增 Solver/Property/Benchmark 或 P1 能力证据，`registry_version` 保持 `1.0.0`。

## P1 allocation and TASK-P1-01 evidence

用户于 2026-08-19授权进入 P1后，新增上述9个稳定 Test ID并分配到 TASK-P1-01/03～09/11；TASK-P1-02复用 TEST-CONTRACT-001，TASK-P1-10复用 TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION，TASK-P1-12重跑全部 P1证据。TEST-PHASE-GOVERNANCE-001、TEST-IMPORT-STAGING-001、TEST-IMPORT-ADAPTER-001、TEST-NORMALIZATION-001与TEST-DATA-QUALITY-001已按TASK-P1-01/03～06形成；其他新增行仍为`PLANNED`，没有测试文件、结果或artifact时不得改写为formed。

TASK-P1-01扩展治理单测覆盖 current P1/prior terminal P0/future phase/alignment、任意 phase range、唯一 changed Task、stale historical/multiple card、完整 event-base Git range；CI integration contract验证中性 workflow/report/artifact、PR/push base来源、full+diff governance、全部既有 gates、无 P0-08/P0-10 Task残留及无 `continue-on-error`。这些只证明治理/CI contract，不证明 provider执行、P1数据链或 Benchmark/Solver。

P1 Exit Gate至少要求 TEST-P1-COMMON-INGRESS组合证明 same scenario+seed的 Import/Snapshot/Problem bytes/hash一致，并由 TEST-DATA-QUALITY-001分别证明 `ROUTE_CYCLE`、`MISSING_RESOURCE`、`UNIT_CONVERSION_ERROR`、`MISSING_DURATION`。这些都是 data pipeline证据，不能外推为 Solver、ScheduleValidator、Benchmark或 Production readiness。

## TASK-P1-02 contract evidence

TEST-CONTRACT-001新增canonical/Import v2/Snapshot v2的Draft 2020-12跨URN `$ref` registry、synthetic positive samples/JSON round-trip、v1/v2 non-interchangeability、v1 byte fingerprint、unknown/no-default、Production/Synthetic conditional、UTC/unit/duration/source/reference/count及expanded option copy负例，并以Pyright/Ruff覆盖pure JSON-compatible types/prechecks。固定sample不做随机generation/shrinking，sentinel digest不验证hash builder，单异常precheck不替代TASK-P1-06 multi-error quality evaluator。

本Task不新增Test ID或改变registry表结构，`registry_version`保持`1.0.0`。TEST-IMPORT-STAGING-001、TEST-NORMALIZATION-001、TEST-DATA-QUALITY-001、TEST-ORDER-EXPANSION-001、TEST-SNAPSHOT-REPLAY-001、TEST-PROBLEM-REPLAY-001与TEST-P1-COMMON-INGRESS继续`PLANNED`。

## TASK-P1-03 Raw Staging evidence

TEST-IMPORT-STAGING-001现覆盖frozen batch/row/provenance、opaque non-UTF-8 bytes、deterministic request fingerprint、missing source/version/digest/UTC/path与duplicate row identity拒绝、Production/Simulation conditional、raw-not-canonical AST boundary、SQLAlchemy round-trip、exact replay/conflict、真实transaction rollback/no-leak、plane-scoped read/write，以及empty/populated Alembic upgrade/downgrade/re-upgrade。TEST-IDEMPOTENCY因此获得durable Import staging slice。

定向suite为23 passed，full repository regression为121 passed；测试数据库/records均为显式synthetic，migration downgrade删除1 batch/1 row的开发数据。没有真实PostgreSQL race/outage、Adapter file security、Normalization/DataValidation、Snapshot/Problem/Solver、Property或Benchmark evidence。Test ID/表结构未变，`registry_version`保持`1.0.0`。

## TASK-P1-04 Reference Adapter evidence

TEST-IMPORT-ADAPTER-001现以31项定向tests覆盖manifest ID/version/non-production binding、CSV/XLSX semantic row parity与truthful file/location provenance、strict UTF-8/BOM/dialect、unknown/missing/duplicate/reordered header、file/row/column/cell/sheet/archive limits、path traversal、legacy/macro-enabled extension、formula/non-text cell、VBA/external link/DTD/entity，以及通过TASK-P1-03 repository的create/exact replay/conflict和CSV/XLSX durable parity。

全部文件在pytest temporary directory动态生成，不提交workbook/客户数据；2-row sample不构成Scenario/Benchmark或Production scale。测试不解析`payload_json`业务语义，不证明Normalization/DataValidation/canonical Import/Snapshot/Problem/common ingress、malware/auth或真实system binding。Test ID/表结构未变，`registry_version`保持`1.0.0`。

本地最终证据为Adapter自身31 passed、Task focused suite 42 passed、full repository 152 passed，Task/full Ruff与Pyright均PASS，full/diff docs治理为124 docs、36 Test IDs、42 changed paths、8 impact rows、0 issues，build成功。Implementation commit`9391ec021afa9e6f4f881b1538b276c84584df0e`由GitHub run [`32247079996`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32247079996)的required `validate`成功重放；这些结果只关闭TEST-IMPORT-ADAPTER-001的P1-04 slice，不外推后续Test ID或Production能力。

## TASK-P1-05 Normalization evidence

TEST-NORMALIZATION-001覆盖stable namespaced IDs、explicit offset/DST→UTC Z、integer `s/min/h` conversion、nested intervals、required/unmapped field、duplicate JSON/ID、profile/source/version/data-plane/provenance conflict、Production/Simulation boundary、canonical ordering、volatile transport metadata replay、mapping-version hash mutation，以及unit missing/unknown/float/non-integral/overflow exact rejection。Schema validator与domain precheck证明合法minimal package；missing reference例同时证明producer不会吞并TASK-P1-06边界。

TEST-CONTRACT-001扩展覆盖registry exact keys/rules/no-default、data dictionary/app/pyproject `2.1.0`一致性、Import v2 document仍固定`2.0.0`、canonical/import Schema SHA-256不变，以及MappingProfile required/optional field集与canonical-records.v1逐collection对齐。当前不形成Hypothesis property suite、ImportQualityReport、Snapshot/Problem或Production evidence；registry format version保持`1.0.0`。

本地证据为Task-focused `66 passed`、full repository `189 passed`，Task/full Ruff与Pyright均0问题，`uv sync --locked`无lock漂移且build成功。Full/diff docs治理为124 docs、49 changed paths、8 impact rows、0 issues。Immutable implementation commit `d52aa62d36e8d89eba318cb5fc586311680e030f`对应GitHub Actions run `32252308695`，required `validate` job `96065907901`=`success`；artifact `9364897397`的provider与下载ZIP digest均为`sha256:5db1ccbb242b555d8a95d36ac9cc1b1373dab95d482dbde17ab7fb369cce2966`，其中Task report精确匹配该SHA并为`PASS`。因此TASK-P1-05测试/CI证据已闭环并标记`done`；其Data Validation后继现由下节TASK-P1-06 evidence形成。

## TASK-P1-06 Data Validation evidence

TEST-DATA-QUALITY-001现覆盖合法Import PASS/0、四项P1 exact `DATA_ERROR`、route SCC/self-edge、all-collection orphan/lineage、duplicate ID/logical edge/option、resource capability eligibility、unsupported platform capability、UTC/calendar overlap、lag/duration/unit、execution fact/lock、malformed structure multi-error、rich source/action detail、report count/status/content ID和collection-order invariant。TEST-INF-NO-RESOURCE获得canonical input-gate slice，TEST-CAPABILITY-001获得ordinary machine matching与unsupported/deferred runtime precheck slice。

TEST-CONTRACT-001扩展验证Draft 2020-12 Error v3/ImportQualityReport跨URN显式registry、registry v2与Python映射、v1 19项保留、Error v1/v2/v3不互换、PASS/FAIL samples exact evaluator replay、global/document/registry版本分层及六份immutable artifact fingerprint。固定mutations不是Hypothesis Property或candidate ScheduleValidator；Expansion/Snapshot/Problem/common-ingress/P2 Solver和Production evidence继续`PLANNED`，Test registry format/version保持`1.0.0`。

本地证据为Task-focused `50 passed`、full repository `210 passed`，Task/full Ruff与Pyright均0问题，`uv sync --locked`无lock漂移、`git diff --check`与build成功。Full/diff docs治理为124 docs、63 changed paths、9 impact rows、0 issues。Implementation commit `c1ac1077fdd92e012f4050f30bab2aec4638f6ec`对应GitHub Actions run `32257767495`、required `validate` job `96083426251`=`success`；artifact `9366988617`的provider/download digest均为`sha256:a2e38cf942e672a073f5044b936dd2b7b7450204f5d353251566ed8b7352ca98`，其中Task report精确匹配该SHA并为`PASS`。Data Validation只消费canonical Import并生成deterministic report，不导入Planning/ScheduleValidator/Solver，也不形成Order Expansion、Snapshot/Problem或P2证据；TASK-P1-06据此闭环为`done`。

## TASK-P1-07 Order Expansion evidence

TEST-ORDER-EXPANSION-001现由7项unit与2项Hypothesis property tests形成：serial与branch/merge DAG、cross-workshop transport、multi-candidate exact copy、explicit multi-lot cardinality、stable versioned IDs/order/bytes/hash、Import/quality/synthetic/source lineage、RUNNING/COMPLETED/locks，以及quality mismatch、missing lot/route/option/duration、duplicate fact、SPLIT_MERGE与version拒绝。Expanded payload还注入Snapshot v2 pure precheck验证既有shape，不构建Snapshot hash。

Property使用fixed seeds`20260819/20260820`、64 positive与24 negative max examples，生成1～3 lots、4-op branch/merge、2 workshops/resources、1～2 candidates、fact/lock组合并验证重排不变量和可收缩exact rejection。本地为7 unit + 2 property + 5 CI contract=`14 passed`，full repository=`219 passed`，Ruff/Pyright均0问题。Implementation commit `5a3dbc14c12a107abf4052cca935e3ef59009d3d`对应GitHub Actions run `32265257468`、required `validate` job `96108055149`=`success`；artifact `9369917400`的provider/download digest均为`sha256:8aeb7416516f7932436bbf406d800cdbdeb8313ba9249f2709b7df71647e566e`，其中Task report精确匹配该SHA并为`PASS`。TASK-P1-07测试/CI证据据此闭环为`done`。

TEST-RUNNING获得P1 expansion projection slice：RUNNING/COMPLETED绑定唯一fact且COMPLETED保留，NOT_STARTED不引用fact；它不验证未来occupancy/resource immutability或P2 candidate ScheduleValidator。P2 TEST-PROPERTY仍`PLANNED`，因为本Task生成canonical expansion而非合法PlanningProblem/candidate schedule；Test registry表结构/ID不变，`registry_version`保持`1.0.0`。

## TASK-P1-08 PlanningSnapshot evidence

TEST-SNAPSHOT-REPLAY-001现由9项unit、4项fixed-seed Hypothesis properties、5项repository integration与migration suite中的Snapshot upgrade/downgrade形成。覆盖固定hash vector、same-input complete bytes/hash/ID、all collection/candidate/lock ordering、self/received/generated noise exclusion、cutoff/fact/rule/version mutation、fresh-copy immutability、FAIL/stale/mismatch/tamper/invalid-cutoff拒绝、Production/Synthetic conditional、insert/exact replay/read、identity-content conflict，以及application/database update/delete拒绝。

Task-focused suite为`25 passed`，full repository regression为`238 passed`，Ruff/Pyright均0问题。Implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`对应GitHub Actions run `32310098594`、required `validate` job `96251145353`=`success`；artifact `9386127863`的provider/download digest均为`sha256:69d68183bad614631df07234a3ca88508379ab89ec715f811ee7f529d6f17e0c`，Task report精确匹配该SHA并为41 paths/6 rows/0 issues。TEST-SIM-ISOLATION获得Snapshot application/table plane guard slice，但同库临时SQLite不等于独立Production/Simulation database。Schema/Test ID/registry表结构未改，P1-09 Problem replay现由下节形成；P1-11 common ingress和P2 TEST-PROPERTY/Solver继续`PLANNED`，`registry_version`保持`1.0.0`。

## TASK-P1-09 PlanningProblem evidence

TEST-PROBLEM-REPLAY-001由10项unit、3项fixed-seed Hypothesis properties与2项Golden tests形成，覆盖fixed Snapshot→Problem/hash/bytes vector、same-input replay、self/order/runtime noise、Snapshot fact/tick/horizon/builder version sensitivity、RUNNING projection、COMPLETED过滤、edge/calendar/candidate/tick ceiling、immutable/tamper、content-hashed active DAG cycle、active lock/completed-active boundary明确拒绝及no-OR-Tools/ORM/API scan。扩展TEST-CONTRACT-001继续回归published Problem v1 Schema与pure reference/time/duration precheck。

本地Task-focused suite=`34 passed`、full repository=`253 passed`，Ruff/Pyright均0问题。Problem vector为`sha256:6e4afffebf464de5c156094c894dccb5fe3efc712449f8583bcd91e1694dff72`，canonical bytes digest=`sha256:1f00ad7a856395328e9eb2c70afe8fe5878d69c3d8618ae7ef45bca34ef08645`。Implementation commit `e8c59547857d2eeace1c9f8b453a5a294cca5ef7`对应GitHub Actions run `32315513504`、required `validate` job `96266776018`=`success`；artifact `9387907707`的provider/download digest均为`sha256:1ede296252bb04e9015240e13222eaf4ee783bc6e7582012cac0a441fd624568`，Task report精确匹配该SHA并为30 paths/5 rows/0 issues。该证据只形成builder/hash和input projection，不形成P2 candidate schedule、TEST-PROPERTY、Solver/Validator/Benchmark或common-ingress；Test ID/registry表结构不变，`registry_version`保持`1.0.0`。

## TASK-P1-10 Synthetic Generator evidence

`test_p1_synthetic_generator.py`现有8项测试覆盖Profile/Scenario Schema与pure contract、frozen context、16个非空collection/49 records/PASS-0、same-input bytes/hash与generated-at exclusion、seed/profile/version guard、七层pure/call-order independence、Production/unsupported/mismatch/unsupported shape、Normalization/DataValidation结构化失败及AST no-Application/Snapshot/Planning/Solver/ORM import。`test_normalization.py`另有`cycle_seconds_per_unit`显式`min→second`直接回归；既有P0 simulation contracts继续通过。

当前聚焦suite为`18 passed`，no-import单测为`1 passed`，full repository为`262 passed`，Ruff/Pyright均0问题；machine check为7/7 PASS、16 collections、49 records、hash `sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`。Implementation commit `5ac08183dd03049ad02c77e6cba80c4621847e0f`对应GitHub Actions run `32319530217`、required `validate` job `96278754755`=`success`；artifact `9389283489`的provider/download digest均为`sha256:2b04b7bd134810c7d37d6130a2ba84911b6f672fb8a95ef83c761496370b73cf`，Task report精确匹配该SHA并为52 paths/7 rows/0 issues。TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION获得P1 generator slice，但TEST-P1-COMMON-INGRESS、P2 TEST-PROPERTY/Solver/Benchmark仍`PLANNED`。Test ID和registry表结构不变，`registry_version`保持`1.0.0`。

## TASK-P1-11 Common Ingress evidence

`test_p1_common_ingress.py`覆盖ReferenceFileAdapter/Synthetic不staging后完整artifact parity、expected-plane拒绝与Application AST no-API/Infrastructure/Backend/Strategy/Validator/OR-Tools/SQLAlchemy shortcut；`test_p1_pipeline_replay.py`覆盖公开Generator staging、固定Import/Snapshot/Problem bytes/hash向量、Generator legacy output一致性与14-check report边界；`test_p1_exit_rejections.py`独立构造四类source mutation并用monkeypatch证明失败stage不调用下游。

聚焦回归=`17 passed`、exact rejection=`4 passed`、full repository=`271 passed`，Ruff/Pyright均0问题；pipeline machine report=`14/14 PASS`，rule sheet、generator、Golden、mutation、engineering既有machine checks与Docker/docs/build亦全部PASS。固定Import/Snapshot/Problem hashes分别为`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`、`sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`、`sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da`。Implementation commit `fa6c4c1159972a30ea683ad4e6eba98342d3c344`对应GitHub Actions run `32322511227`、required `validate` job `96287321281`=`success`；artifact `9390250284`的provider/download digest均为`sha256:77e0389e2902021c419e8ec2fcf99d88c02c19d96a69304791693b822498bd6e`，Task report精确匹配该SHA并为43 paths/7 rows/0 issues。Test ID与registry表结构不变，`registry_version=1.0.0`，P2 TEST-PROPERTY、Solver/Validator/Benchmark和Production evidence仍`PLANNED`。

## TASK-P1-12 independent audit replay

P1-12不新增或修改test代码/Test ID；它独立执行全部已登记目录，实际结果为`271 passed`，并执行`test_migrations_and_infrastructure.py + test_p1_exit_rejections.py`得到`11 passed`。P1 pipeline报告14/14、Generator 7/7、Rule/Golden/13-class Mutation/6-check Engineering报告均PASS，四类exact rejection的stage/category/code与P1-11保持一致。

Audit还核验P1-01～11各CI artifact内`traceability-report.v1`的Task/head/path/impact/issues，并确认required `validate`成功。该evidence关闭P1 Data & Snapshot Exit Gate，不将P2 `TEST-PROPERTY`、Solver/Validator comparison、Benchmark或Production test标为完成；Test registry仍为36项，`registry_version=1.0.0`。

## P2 allocation baseline

用户于2026-08-20批准P1→P2后，既有36个Test ID不新增、不复用，只把P2 planned slices分配到TASK-P2-01～14：P2-01/02覆盖contract/problem replay；P2-03覆盖solver upgrade/status boundary；P2-04覆盖formal Validator/mutation/property；P2-05～08覆盖C-001～C-011与OBJ-001；P2-09覆盖Golden JSSP/FJSP及Cross/Calendar/Material/Running/Hard Lock；P2-10覆盖Reference Scheduler；P2-11覆盖Output；P2-12覆盖Benchmark/XS/S/M；P2-13形成vertical Gate；P2-14独立重跑audit。

TASK-P2-00本身只扩展TEST-PHASE-GOVERNANCE-001与TEST-TRACEABILITY-VALIDATOR，验证合法phase-planning batch及existing/active-member拒绝；targeted=22 passed、full=273 passed，implementation `3298229fae89a54e0641f5907ad90c4fa81569bf`的provider run `32332003608` / artifact `9393345593`成功。没有业务测试、Solver运行或P2 artifact。TEST-GOLDEN-JSSP、TEST-REFERENCE-SCHEDULER、TEST-BENCHMARK、TEST-PROPERTY、TEST-SOLVER-UPGRADE及所有P2 integration slice继续`PLANNED`，直到对应Task存在真实路径、结果与provider artifact。Registry表结构/状态语义不变，`registry_version=1.0.0`。

## TASK-P2-01 PlanningProblem v2 evidence

扩展TEST-CONTRACT-001、TEST-PROBLEM-REPLAY-001与TEST-PROPERTY，覆盖v2 Draft 2020-12 strict/non-interchangeable Schema、priority正反与source、capacity=1、Resource topology、COMPLETED→active anchor/lag、expired/active/cross-horizon HARD/SOFT locks、same-input/order/noise replay、due/priority/resource/anchor/lock mutation、tamper/verify及v1 bytes/hash preservation。Golden v2 vector为Problem hash`sha256:9927418a446dd046ddd1d835643da03fbf5cdcf8ca246ba22c3700563a17e9e8`、canonical bytes digest`sha256:2dbe06907952d6aba303977d67a7f5d7a6ef89c4be5ac5a6ac8d74e3f95d720a`。

Task-focused八文件suite=`89 passed`，full repository=`286 passed`，Ruff/Pyright均0问题；`planning-problem-contract-report.v1`为4/4 PASS并记录v1/v2 fingerprints/vectors及no-Solver边界。Implementation `c64284685f37ef0d03eacade5699076146653333`的provider run `32336812748` / required job `96327855244` / artifact `9394931377`均success，artifact Task report为60 paths/10 rows/0 issues且Problem report绑定同一SHA；Task据此`done`。本slice不形成TEST-GOLDEN-JSSP、formal Validator、Solver Upgrade、Reference Scheduler或Benchmark；registry table/status与`registry_version=1.0.0`不变。

## TASK-P2-02 planning-machine contract evidence

扩展TEST-CONTRACT-001与TEST-ERROR-MAPPING-001，覆盖四份Draft 2020-12 Schema的stable URN离线解析、strict/no-default、sample round-trip、Policy C-001～C-011/OBJ-001、显式Limits、七种status到PlanningRun/product error的总映射、candidate/non-candidate组合、OPTIMAL/FEASIBLE objective-bound-gap、duration seconds/ticks/UTC还原、timing/model/memory、parameter/version/code-commit provenance、canonical order/fingerprint与cross-document drift。Integration contract还要求CI生成5/5 planning-machine report并上传artifact。

负向测试覆盖missing objective/limit、boolean limit、non-candidate assignment、伪optimal/错误relative gap、stage budget、UTC/tick和duration不一致、Policy/Limits跨plane、Solution/Report evidence-kind、limit参数与timing漂移、negative timing、非法commit与fingerprint mismatch。Source/dependency scan证明新增代码无OR-Tools/CpModel/IntervalVar/ORM/API/later validator import。Task指定suite=`54 passed`、full repository=`311 passed`、Ruff/Pyright为0问题、machine report=5/5 PASS；implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`的provider artifact `9396828326`再次记录5/5及Task diff 63 paths/11 rows/0 issues。这仍不是formal ScheduleValidator mutation、Solver Upgrade、Golden、Reference Scheduler或Benchmark evidence；Test registry结构和`registry_version=1.0.0`不变。

## TASK-P2-03 solver foundation local evidence

TEST-SOLVER-UPGRADE与TEST-CONTRACT-001新增slice覆盖exact pin/lock/wheels、identity/version drift、Protocol re-export、native五状态+CANCELLED/FAILED、未知native code、SolveLimits四参数、empty/model-invalid smoke、JSON serialization、real `solve()` bounded refusal及全`backend/app` AST namespace isolation。CI integration还要求6/6 `solver-backend-foundation-report.v1`和non-continue step。

本地聚焦suite=`39 passed`、full repository=`319 passed`，Ruff/Pyright均0问题，foundation report=`6/6 PASS`；P2-02 report继续`5/5 PASS`，P0-08 historical report继续`6/6 PASS`。Implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的run `32346208046` / job `96355386111` / artifact `9398128763`均success，artifact再次记录6/6及50 paths/9 rows/0 issues。没有新增Test ID或改变registry版本；formal Validator mutation、C-ID/OBJ-001、Golden/Reference/Benchmark tests仍PLANNED。

## TASK-P2-04 formal Validator evidence

P2-04新增`test_problem_schedule_validator.py`与`test_schedule_validator_properties.py`，并扩展CI integration contract。Formal suite覆盖schema-valid positive、declared status independence、13 exact mutations/14 violations/C-001～C-011、malformed/reference、RUNNING remainder、ValidationReport/Error v2、AST import/token isolation、fixed asset hashes和6-check machine report；Hypothesis seeds `20260820/21/22`覆盖legal duration/horizon、sampled corruption与collection ordering。

本地formal+P0 validation/golden focused=`50 passed`，CI integration=`9 passed`，Task指定合并suite=`59 passed`，full repository=`343 passed`，Ruff/Pyright均0问题，formal machine report=`6/6 PASS`。P0 mutation CLI仍为13 cases/15 violations PASS，固定Problem/Solution/Validation Schema、P0 assets、Backend与lockfile无差异。Implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的run `32350068318` / job `96367085099` / artifact `9399519368`精确复现6/6 formal与38-path/6-row/0-issue Task report，故Task=`done`。没有新增Test ID或改变registry版本；Solver C-ID implementation、OBJ-001、Golden/Reference/Benchmark/P3继续PLANNED。

## TASK-P2-05 core Solver test slices

`test_cp_sat_core_model.py`覆盖exact five-C-ID model shape/no objective、tight JSSP、alternative-duration FJSP、native OPTIMAL→business FEASIBLE、unary overload、zero/overflow build rejection、future-fact fail-closed、formal Validator mutation与machine report。`test_cp_sat_core_properties.py`用三个固定seed及独立穷举oracle覆盖feasibility、duration和horizon invariants；既有P2-03 contract测试改为验证历史smoke与当前consumer兼容，CI integration固定core CLI/report路径和完整boundary。

本Task复用TEST-GOLDEN-JSSP/FJSP、TEST-INF-NO-RESOURCE/HORIZON、TEST-PROPERTY、TEST-VALIDATOR-MUTATION、TEST-CONTRACT-001与TEST-SOLVER-UPGRADE的新增slice，不新增Test ID或改变36项registry。验收必须同时运行focused、全仓pytest、Ruff、Pyright、core/formal machine CLI、治理、compose与build；实际总数和provider evidence仅在运行后回填。

本地实际验收为focused `64 passed`、full repository `360 passed`、Ruff/Pyright 0问题、core/formal machine report各6/6 PASS。Core counts为5个C-ID、2个candidate、1个infeasible、2个precheck、2个Validator mutation与4个oracle cases；immutable contracts/rules/Validator/fixtures/benchmarks保持无差异。Exact provider evidence待implementation SHA生成后回填。

Exact provider已复现：implementation `df706786e0ec1c54bf60cd43261a92ef6aa53cc7`的run `32354050257` / required job `96379299455`全步骤success；artifact `9400957897`中的core/formal报告各6/6，Task report为49 committed/0 working、6 rows、19 checks、0 issues。TASK-P2-05测试证据闭环为`done`。

## TASK-P2-06 temporal Solver test slices

`test_cp_sat_temporal_model.py`覆盖signed rounding、calendar projection/merge、exact min ceil/max floor、impossible window、release/material、half-open calendar、independent non-summed transport、same-workshop、historical anchor、formal mutations及sub-second/overflow precheck。`test_cp_sat_temporal_properties.py`用固定seed和独立oracle覆盖rounding/lag/calendar；integration contract固定temporal CLI/report及boundary。

本Task复用TEST-MAX-LAG、TEST-CALENDAR、TEST-MATERIAL、TEST-CROSS-WORKSHOP、TEST-PROPERTY、TEST-VALIDATOR-MUTATION、TEST-CONTRACT-001与TEST-SOLVER-UPGRADE，不新增Test ID或改变36项registry。本地实际验收为focused `87 passed`、full repository `367 passed`、Ruff/Pyright 0；foundation/core/formal/temporal分别6/6、6/6、6/6、7/7 PASS。Temporal counts为4个C-ID、5 candidate、3 infeasible、2 precheck、4 Validator mutation和8 oracle cases；治理53 paths/6 rows/19 checks/0 issues，compose/build/immutable PASS。Exact provider结果仍待implementation SHA。

Exact provider已复现：implementation `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`的run `32432482739` / required job `96626844156`全步骤success；artifact `9429579311`中的temporal/core/formal报告为7/7、6/6、6/6，Task report为53 committed/0 working paths、6 rows、19 checks、0 issues。TASK-P2-06测试证据闭环为`done`。

## TASK-P2-07 test evidence

本Task复用TEST-RUNNING、TEST-INF-LOCK、TEST-PROPERTY、TEST-VALIDATOR-MUTATION、TEST-CONTRACT-001与TEST-SOLVER-UPGRADE，不新增Test ID或改变36项registry。新增unit/property/integration覆盖COMPLETED anchor exclusion、RUNNING resource/remainder、HARD exact tuple、SOFT movement、grid/duration/multi-source self-conflict、calendar/resource/horizon INFEASIBLE、stable lock references与formal mutations。

`cp-sat-fact-lock-model-report.v1`当前为7/7：2个C-ID、4 candidate、3 infeasible、4 precheck、2 Validator mutation及6 oracle cases；foundation/core/temporal/formal历史machine reports保持6/6、6/6、7/7、6/6。本地focused=`93 passed`、full repository=`382 passed`且Ruff/Pyright为0问题。Exact provider evidence仍待implementation SHA形成；P2-09 Golden integration、P2-12 Benchmark和Production仍未形成。

Exact provider已复现：implementation `5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`的run `32435395744` / required job `96635463577`全步骤success；artifact `9430579117`中的fact-lock/temporal/core/formal报告分别7/7、7/7、6/6、6/6，Task report为54 committed/0 working paths、6 rows、19 checks、0 issues。TASK-P2-07测试证据闭环为`done`；P2-08及以后不自动启动。

## TASK-P2-08 objective/strategy coverage

`test_global_cp_sat_strategy.py`覆盖approved/no-default Simulation Policy/Limits、priority sequence、zero tardiness、hard INFEASIBLE、受控UNKNOWN/FEASIBLE、Validator FAIL、Production/data-plane/limits-source/priority-source rejection、int64 overflow、single global call与SolverReport replay；`test_delivery_objective_properties.py`覆盖16个exhaustive scheduling examples、12个priority scaling examples及non-grid due。既有Solver namespace、formal Validator与全部历史suite保持回归。

`objective-strategy-report.v1`固定7/7 checks、4 tiny optimality、4 Validator PASS、1 certified INFEASIBLE、7 status与1 Production rejection；CI integration contract固定CLI、report counts/boundaries与artifact路径。本地focused=`70 passed`、full repository=`395 passed`、Ruff/Pyright=0，全部历史machine reports亦PASS。Implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`的required run `32438785162` / artifact `9431673977`精确复现全部报告，故Task=`done`；这不是P2-09 Golden/scenario integration或P2-12 Benchmark。

## TASK-P2-13 vertical Gate coverage

本Task不新增或复用Test ID；它把TEST-GOLDEN-JSSP/FJSP、全部C-specific、TEST-VALIDATOR-MUTATION/PROPERTY/OUTPUT/SCENARIO-REPLAY/REFERENCE-SCHEDULER/BENCHMARK/SOLVER-UPGRADE及CI contract链接到`test_p2_vertical_slice.py`、`test_p2_exit_rejections.py`和`p2-vertical-slice-report.v1`。实际Gate两次重跑全部公开边界，而非读取stale build report。

Integration覆盖完整链、七Scenario/C-ID、XS/S/M status/objective/model/timing/memory、五Reference、fresh Validator、KPI/Export、semantic projection和no-Exit/P3边界；contract覆盖unsupported/invalid/limit与repeat<2非零失败；CI contract固定required workflow命令、report counts和artifact路径。P1 application AST test只新增唯一`p2_gate_report.py → app.exporters.contract_check` exact evidence例外，其他捷径禁令不变。既有36个Test ID和registry format version保持不变；P2-14仍须独立重跑audit。

本地30 focused/476 full与provider required run全部PASS；artifact Gate复现2 replays、11/11、14 scenarios、108 Benchmark Validator passes、4 rejections和0 gaps。TASK-P2-13测试DoD已闭环；P2-14仍须独立审计而不能复用本Task结论。

## TASK-P2-14 independent audit replay

本Task不新增、删除、修改或复用Test ID/test assertion；它独立重跑全部registered unit/contract/simulation/golden/validation/integration/property目录，结果为`476 passed in 52.66s`，Ruff/Pyright均0问题。P2 Gate重新执行两轮且11/11；独立XS/S/M各8/8、0 warning。为确保总规§76每个correctness case的model/build/first/objective/bound/gap/memory/Validator字段可直接审计，另通过公开P2 correctness执行边界生成14条两轮measurement observation，全部PASS。

该evidence与P2-01～13的26个exact provider artifacts共同支持P2 Gate=`READY`，且audit implementation run `32677741558` / artifact `9503227240`再次精确通过476项测试与Gate 11/11，故TASK-P2-14=`done`。36个Test ID、registry format version或Production测试状态不变；P3 approval/publish、L/XL与Production capacity/SLA tests继续`PLANNED`。

## P3 planning allocation baseline

TASK-P3-00只登记12个P3 Test ID，registry从36项增加到48项；没有创建测试文件、修改断言或把任一P3 evidence标为formed。P3-01先形成合同/ADR，P3-02～13按repository/lifecycle/read-command/authorization/publish/export/API/frontend顺序形成证据，P3-14聚合vertical slice，P3-15独立重放Exit Audit。

所有P3测试必须保留P2 formal Validator与immutable artifacts，明确DRAFT/REJECTED publish拒绝、APPROVED-only publish、PUBLISHED immutability、command产生new DRAFT、same-key幂等和default-deny authorization。P4 ExecutionEvent/Replan/OBJ-002/ChangeReport/Execution Simulator及Production identity/deployment/SLA测试不属于P3；48个ID的生命周期仍为注册或历史证据状态，`registry_version=1.0.0`格式不变。

TASK-P3-00本地治理回归为`35 passed`，implementation required run `32681493976`的完整repository suites与20份artifact JSON均PASS。该结果只验证规划/registry/历史回归；12个P3新Test ID全部继续`PLANNED`，没有测试断言或P3行为证据形成。

## TASK-P3-01 contract-test boundary

TASK-P3-01形成三份Frontend规范、两份语义合同和accepted ADR-0012，并用现有TEST-WORKSPACE-CONTRACT-001/TEST-STATE-TRANSITION-001/TEST-ERROR-MAPPING-001建立planned矩阵。现有`test_rule_contracts.py`只复验三套state enum/42 pairs及旧error registry不漂移；`test_check_docs.py`只复验front matter、链接、trace/Impact治理。它们不能证明P3 Schema、authorization、idempotency、state persistence、API或UI行为。

## TASK-P3-02 workspace carrier test slice

`test_p3_workspace_contracts.py`与`p3-workspace-contract-report.v1`形成七份Draft 2020-12 Schema/URN的offline `$ref`、strict/no-default、7 synthetic positive、24个unknown/version/plane/non-interchangeable negative、6个canonical fingerprint drift、key-order replay、query/command authority separation、comparison/publication/export cross-value、no-secret audit以及Schedule/Export exact state pair证据。四份既有contract tests只把current set metadata/dictionary覆盖提升到`2.6.0`；P2 document const、bytes、URN与行为断言不变。

本地受影响contract=`73 passed`、CI integration focused=`4 passed`、全仓=`493 passed`、machine checks=`8/8`。Implementation run `32689832111` / artifact `9506913562`再次通过全仓suite并精确绑定workspace/Task报告。这些只形成TEST-CONTRACT-001与TEST-WORKSPACE-CONTRACT-001的carrier slice，并复验TEST-STATE-TRANSITION-001与TEST-ERROR-MAPPING-001 preservation；不形成auth decision、repository transaction、transition behavior、HTTP/UI/E2E、external side effect或Production readiness。

因此P3新Test ID总数仍为48且behavior lifecycle保持`PLANNED`；本Task不得新增/修改测试断言。后续P3-02必须先形成strict Schema/round-trip evidence，P3-03～13按卡片形成repository/application/API/UI evidence，P3-14/15再聚合和独立审计。

## TASK-P3-03 persistence test slice

`test_p3_persistence_state.py`与`test_p3_persistence.py`覆盖既有pair、content/identity mutation、stale CAS、top-level carrier rejection、audit exact replay/conflict/DB trigger、caller transaction rollback、publication result+current atomic replay、ExportJob claim/heartbeat/wrong owner/failure/retry及Production plane拒绝；既有migration suite新增五表检查和populated `0004` destructive downgrade/re-upgrade。CI contract要求`p3-persistence-report.v1`为Task P3-03、8/8、5 tables、4 repositories并绑定exact SHA。

这些形成TEST-SCHEDULE-VERSION-REPOSITORY-001及TEST-IDEMPOTENCY/SIM-ISOLATION的storage slice，并只部分形成TEST-EXPORT-JOB-001/AUDIT-TRAIL-001；真实PostgreSQL concurrency/capacity、business audit completeness、package/side-effect与Production仍PLANNED。Test ID总数48、registry version`1.0.0`不变。

Implementation provider run `32694644036` / artifact `9508445635`通过完整repository suite并下载复核22/22 JSON顶层PASS；`ci-p3-persistence.json`绑定exact SHA且8/8，Task report为52 committed/0 working paths、7 rows、19 checks、0 issues。因此上述storage slice为provider-verified，TASK-P3-03可闭环；未形成的TEST-EXPORT-JOB-001/TEST-AUDIT-TRAIL-001 business部分及P3-04+测试状态不提升。

TASK-P3-01本地治理/规则回归为`27 passed`，implementation required run `32684713630`的完整repository suites与20份artifact JSON均PASS。该结果只验证合同文档、registry与既有state/error preservation；48个Test ID及全部P3 behavior lifecycle不因此提升，P3-02仍需新的明确授权。
