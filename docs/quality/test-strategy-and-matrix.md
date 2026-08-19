---
doc_id: DOC-QUAL-001
title: 测试策略与 Test Matrix
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [31, 57, 72, 74, 76, 78, 80, 86, 87, 88, 89, 100]
last_reviewed: 2026-08-19
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
| TEST-CONTRACT-001 | Schema meta/positive/negative、版本、UTC/duration/reference、isolation 与 round-trip | P0-P1 | Existing schema suite + [`test_unit_conversion_registry.py`](../../backend/tests/contract/test_unit_conversion_registry.py) + preserved Import/canonical hashes and additive `2.1.0` unit registry formed；Data Validation/builder仍PLANNED |
| TEST-IMPORT-STAGING-001 | Raw batch/row provenance、transaction、migration与 idempotent replay | P1 | [`test_import_staging.py`](../../backend/tests/unit/test_import_staging.py) + [`test_raw_import_staging.py`](../../backend/tests/integration/test_raw_import_staging.py) + [`test_migrations_and_infrastructure.py`](../../backend/tests/integration/test_migrations_and_infrastructure.py) formed / TASK-P1-03 |
| TEST-IMPORT-ADAPTER-001 | CSV/XLSX/ReferenceFileAdapter semantic parity与文件安全拒绝 | P1 | [`test_input_adapters.py`](../../backend/tests/contract/test_input_adapters.py) + [`test_reference_file_adapter.py`](../../backend/tests/integration/test_reference_file_adapter.py) formed / TASK-P1-04 |
| TEST-NORMALIZATION-001 | ID/time/unit mapping、canonical bytes、unit error与 missing duration | P1 | [`test_normalization.py`](../../backend/tests/unit/test_normalization.py) formed / TASK-P1-05 |
| TEST-DATA-QUALITY-001 | DAG/reference/capability/quality report与四类 P1 exact rejection | P1 | PLANNED / TASK-P1-06 |
| TEST-ORDER-EXPANSION-001 | Order/Lot/Routing到 OperationInstance/edge deterministic expansion | P1 | PLANNED / TASK-P1-07 |
| TEST-SNAPSHOT-REPLAY-001 | Snapshot canonical bytes/hash/ID、immutability与 repository replay | P1 | PLANNED / TASK-P1-08 |
| TEST-PROBLEM-REPLAY-001 | Solver-neutral Problem builder/bytes/hash deterministic replay | P1 | PLANNED / TASK-P1-09 |
| TEST-P1-COMMON-INGRESS | Reference/Synthetic共同 staging→Problem链路与 Gate report | P1 | PLANNED / TASK-P1-11 |
| TEST-RULE-SHEET-001 | C-001～C-018 唯一/完整、input/formula/example/violation/Test ID 与 registry cross-check | P0 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) + [`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) + [TASK-P0-04 Acceptance PASS](../tasks/P0/TASK-P0-04-constraints-states-errors-capabilities.md#completion-evidence) |
| TEST-STATE-TRANSITION-001 | 三套 state enum、42 个 allowed pair、terminal/negative transitions | P0 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) + [`state-machines.v1`](../../schemas/rules/state-machines.v1.yaml) formed；persistence/P3 behavior PLANNED |
| TEST-ERROR-MAPPING-001 | 七类 error、19 code/category 唯一映射与 v1/v2 isolation | P0 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) + [`error-code-registry.v1`](../../schemas/rules/error-code-registry.v1.yaml) formed；HTTP mapping PLANNED |
| TEST-CAPABILITY-001 | 20 capability registry 与 supported declaration/unsupported/unknown/duplicate precheck | P0 | [`test_rule_contracts.py`](../../backend/tests/contract/test_rule_contracts.py) + [`capability-registry.v1`](../../schemas/rules/capability-registry.v1.yaml) formed；capability implementation PLANNED |
| TEST-GOLDEN-JSSP | 人工可验证 JSSP | P2 | PLANNED |
| TEST-GOLDEN-FJSP | 人工可验证 FJSP | P0-P2 | [`SIM-MINIMAL-001` positive Golden](../../backend/tests/golden/test_sim_minimal_001.py) formed；P2 Solver/Problem integration PLANNED |
| TEST-INF-NO-RESOURCE | 无候选资源明确拒绝 | P0-P2 | [P0 wrong-resource/multiple-selection mutation](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；zero-option Problem/Solver infeasibility P2 PLANNED |
| TEST-INF-LOCK | Lock 导致的不可行性 | P0-P2 | [P0 HARD_LOCK movement mutation](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；Solver infeasibility P2 PLANNED |
| TEST-INF-HORIZON | Horizon 不允许静默截断 | P0-P2 | [P0 horizon-overflow mutation](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；Solver integration P2 PLANNED |
| TEST-CALENDAR | 设备日历约束 | P0-P2 | Golden positive + [calendar-overlap negative mutation](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；Solver integration PLANNED |
| TEST-MATERIAL | material_ready_at gate | P0-P2 | Golden positive + [material-early negative mutation](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；Solver integration PLANNED |
| TEST-RUNNING | 运行中事实保护 | P0-P2 | [completed/running fact negative mutations](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；P1 fact contract/P2 integration PLANNED |
| TEST-CROSS-WORKSHOP | 跨车间 precedence/transport lag | P0-P2 | Golden positive + [transport-lag negative mutation](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；Solver integration PLANNED |
| TEST-MAX-LAG | max_lag 不被忽略 | P0-P2 | Golden inclusive-boundary positive + [2700>1800 negative mutation](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；Solver integration PLANNED |
| TEST-VALIDATOR-MUTATION | 独立 Validator 拒绝人工错误计划 | P0-P2 | [`test_schedule_validator_mutations.py`](../../backend/tests/validation/test_schedule_validator_mutations.py) + [`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/coverage-matrix.json) P0 fixture-local slice formed；production/performance P2 PLANNED |
| TEST-REPLAN | Replan 事实、锁与变化报告 | P4 | PLANNED |
| TEST-OUTPUT | 标准成果包合同 | P2-P3 | PLANNED |
| TEST-IDEMPOTENCY | Import/Planning/Export/Publish/Event 幂等 | P0-P3 | [`test_job_reliability.py`](../../backend/tests/integration/test_job_reliability.py) generic primitive + P1 [`test_raw_import_staging.py`](../../backend/tests/integration/test_raw_import_staging.py) durable Import staging replay/conflict/rollback formed；Worker/Planning/Export/Publish/Event side effects PLANNED |
| TEST-SCENARIO-REPLAY | Scenario/Profile/Generator/seed 重放 | P0-P2 | empty Import [`test_simulation_contracts.py`](../../backend/tests/simulation/test_simulation_contracts.py) + non-empty committed [`SIM-MINIMAL-001`](../../backend/tests/golden/test_sim_minimal_001.py) canonical hash replay formed；Snapshot/Problem replay PLANNED |
| TEST-SIM-ISOLATION | Synthetic/Production 隔离 | P0-P1 | [`test_simulation_contracts.py`](../../backend/tests/simulation/test_simulation_contracts.py) formed for Schema/pure context/Import envelope；separate DB/API/publish guards PLANNED |
| TEST-REFERENCE-SCHEDULER | Reference Scheduler baseline | P2 | PLANNED |
| TEST-BENCHMARK | BenchmarkReport/profile 回归 | P2 | PLANNED |
| TEST-PROPERTY | 合法 Problem 的通用不变量 | P2 | PLANNED |
| TEST-SOLVER-UPGRADE | Solver 升级 replay/status contract | P2+ | PLANNED |

Test ID 一经分配不得复用。链接到真实测试路径才是已形成证据；`PLANNED` 只登记合同。表结构或状态语义变化必须提升 `registry_version`。

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

用户于 2026-08-19授权进入 P1后，新增上述9个稳定 Test ID并分配到 TASK-P1-01/03～09/11；TASK-P1-02复用 TEST-CONTRACT-001，TASK-P1-10复用 TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION，TASK-P1-12重跑全部 P1证据。除 TEST-PHASE-GOVERNANCE-001 已由 TASK-P1-01形成外，其余新增行仍为 `PLANNED`，没有测试文件、结果或 artifact时不得改写为 formed。

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

提交前本地证据为Task-focused `66 passed`、full repository `189 passed`，Task/full Ruff与Pyright均0问题，`uv sync --locked`无lock漂移且build成功。Full/diff docs治理为124 docs、49 changed paths、8 impact rows、0 issues；provider结果仍须绑定immutable implementation commit后才能把TASK-P1-05标记`done`。
