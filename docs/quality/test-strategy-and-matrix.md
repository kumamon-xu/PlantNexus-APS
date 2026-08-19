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
| TEST-OBS-001 | 日志、运行标识与 Observability 关联 | P0 | [`test_logging.py`](../../backend/tests/integration/test_logging.py) JSON/context/trace-ID/redaction P0 slice formed；PlanningRun metrics/audit retention PLANNED |
| TEST-CONTRACT-001 | Schema meta/positive/negative、版本、UTC/duration/reference、isolation 与 round-trip | P0 | [`backend/tests/contract/test_schema_contracts.py`](../../backend/tests/contract/test_schema_contracts.py) + data/rule Schema baselines formed；Simulation Schema validation also covered by TEST-SCENARIO-REPLAY |
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
| TEST-IDEMPOTENCY | Import/Planning/Export/Publish/Event 幂等 | P0-P3 | [`test_job_reliability.py`](../../backend/tests/integration/test_job_reliability.py) generic replay/conflict/lease/STALLED P0 primitive formed；业务 durable side effects PLANNED |
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
