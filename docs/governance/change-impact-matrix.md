---
doc_id: DOC-GOV-010
title: 变更影响与必审文档矩阵
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 97, 98, 99, 100, 101, 102, 103, 104, 111]
last_reviewed: 2026-08-21
registry_version: 1.0.0
---

# 变更影响与必审文档矩阵

本矩阵用于在 Task 开始前确定文档影响。表中的文档是“必须审查”，不代表每次都必须修改；如果审查后不修改，Task 完成证据必须逐项说明理由。

## 使用规则

1. 根据计划修改的路径和行为类型匹配所有适用行；
2. 把匹配到的文档写入 Task Card 的 `Documents to update`；
3. 把 Requirement/Test/Artifact/Registry 变化写入 `Traceability updates`；
4. 将这些文档路径加入 `Files allowed to change`；
5. 实施中出现新影响时先修订 Task Card；
6. Task 进入 `in_progress` 时记录完整 HEAD SHA 为 `Diff base`；完成时按 `Diff base..HEAD` 已提交路径与 working tree 路径并集再匹配一次，防止计划、提交前验收和提交后验收相互偏离。

`Change-impact matrix rows reviewed` 必须使用下方稳定 Rule ID。校验器忽略纯 `.gitkeep`，其他 changed path 可以同时命中多条规则；每条命中的 Rule ID 都必须在当前 Task 声明，其 `Required documentation` 必须进入 `Documents to update`。

## Machine-checkable rules

| Rule ID | Changed path globs | Required documentation |
|---|---|---|
| IMPACT-SCHEMA | `schemas/**` | `docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-DOMAIN | `backend/app/domain/**` | `docs/domain/domain-model.md`、`docs/core/glossary.md`、`docs/architecture/data-authority.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-APPLICATION | `backend/app/application/**` | `docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/domain/error-model.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-IMPORT | `backend/app/importers/**`、`backend/app/normalization/**`、`backend/app/data_validation/**` | `docs/contracts/import-and-normalization.md`、`docs/architecture/data-authority.md`、`docs/domain/error-model.md`、`docs/governance/prod-open-register.md` |
| IMPACT-SNAPSHOT | `backend/app/snapshots/**` | `docs/contracts/planning-snapshot.md`、`docs/architecture/provenance-and-versioning.md`、`docs/quality/property-tests.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-PROBLEM | `backend/app/planning/problem/**` | `docs/contracts/planning-problem.md`、`docs/planning/constraint-catalog.md`、`docs/architecture/provenance-and-versioning.md`、`docs/adr/README.md` |
| IMPACT-PLANNING-CONTRACTS | `backend/app/planning/contracts.py`、`backend/app/planning/contracts/**` | `docs/contracts/planning-problem.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/planning/solver-backend-contract.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-POLICY | `backend/app/planning/policy/**` | `docs/contracts/planning-policy-and-solve-limits.md`、`docs/planning/objective-policy.md`、`docs/domain/kpi-contract.md`、`docs/adr/README.md` |
| IMPACT-STRATEGY | `backend/app/planning/strategies/**` | `docs/planning/planning-strategies.md`、`docs/planning/solver-backend-contract.md`、`docs/simulation/performance-gates.md`、`docs/adr/README.md` |
| IMPACT-REPORTING | `backend/app/planning/reporting/**` | `docs/domain/kpi-contract.md`、`docs/planning/solver-backend-contract.md`、`docs/contracts/export-package.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-BACKEND | `backend/app/planning/backends/**` | `docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/quality/benchmark-regression.md`、`docs/architecture/technology-stack.md`、`docs/adr/README.md` |
| IMPACT-VALIDATOR | `backend/app/planning/validation/**` | `docs/planning/schedule-validator.md`、`docs/planning/constraint-catalog.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-DIAGNOSTICS | `backend/app/planning/diagnostics/**` | `docs/planning/infeasibility-diagnostics.md`、`docs/domain/error-model.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-STATE | `backend/app/domain/state_machines/**`、`docs/domain/state-machines/**` | `docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/adr/README.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-SIM-PROFILE | `backend/app/simulation/profiles/**`、`schemas/scenario/factory-profile*` | `docs/simulation/factory-profile.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/architecture/provenance-and-versioning.md` |
| IMPACT-SIM-SCENARIO | `backend/app/simulation/scenarios/**`、`schemas/scenario/scenario*` | `docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/performance-gates.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-SIM-GENERATOR | `backend/app/simulation/generators/**` | `docs/simulation/synthetic-generator-and-determinism.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/provenance-and-versioning.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-SIM-EXECUTION | `backend/app/simulation/execution/**` | `docs/simulation/execution-simulator-and-disruptions.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/planning/replanning.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-BENCHMARK | `backend/app/simulation/benchmarks/**`、`benchmarks/**`、`scripts/run_benchmark.py` | `docs/simulation/benchmark-harness.md`、`docs/simulation/performance-gates.md`、`docs/quality/benchmark-regression.md`、`docs/domain/kpi-contract.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-REFERENCE-SCHEDULER | `backend/app/simulation/baselines/**` | `docs/planning/reference-schedulers.md`、`docs/planning/schedule-validator.md`、`docs/planning/objective-policy.md`、`docs/domain/kpi-contract.md`、`docs/simulation/benchmark-harness.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-FIXTURE | `fixtures/**` | `docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-API | `backend/app/api/**` | `docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/governance/prod-open-register.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-FRONTEND | `frontend/**` | `docs/frontend/README.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-EXPORT | `backend/app/exporters/**` | `docs/contracts/export-package.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/schedule-version.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-JOBS | `backend/app/jobs/**` | `docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/architecture/module-boundaries.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-INFRA | `infra/**`、`backend/app/infrastructure/**`、`backend/migrations/**`、`alembic.ini`、`.env.example`、`.github/workflows/**`、`docker-compose.yml` | `docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/governance/nfr-and-engineering-register.md` |
| IMPACT-DEPENDENCY | `pyproject.toml`、`uv.lock` | `docs/architecture/technology-stack.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/benchmark-regression.md`、`docs/adr/README.md` |
| IMPACT-VERSION-METADATA | `backend/app/__init__.py`、`pyproject.toml` | `docs/contracts/schema-versioning.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-PHASE | `docs/milestones/**`、`docs/current_phase.md` | `docs/milestones/README.md`、`docs/tasks/README.md`、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md` |
| IMPACT-GOVERNANCE-REGISTRY | `docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md` | `docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md` |
| IMPACT-GOVERNANCE-VALIDATOR | `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py` | `README.md`、`docs/README.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/repository-layout.md`、`docs/governance/document-control.md`、`docs/governance/traceability-rules.md`、`docs/governance/change-impact-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/TASK_TEMPLATE.md` |
| IMPACT-TESTS | `backend/tests/**` | `docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-DOCS | `docs/**`、`README.md`、`AGENTS.md` | `docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md` |

## 路径与行为映射

| 变更区域或行为 | 必须审查的文档 | 必须检查的追踪/版本 | 额外门 |
|---|---|---|---|
| `schemas/**`、领域 DTO/值对象 | 对应 `contracts/*.md`、`contracts/schema-index.md`、`contracts/schema-versioning.md`、`domain/domain-model.md` | Schema version、REQ/NFR、contract tests、fixtures | 不兼容变更需 migration/compatibility rule |
| `domain/**` 的实体关系或不变量 | `domain/domain-model.md`、相关领域专题、`core/glossary.md`、`architecture/data-authority.md` | REQ、Schema、state/constraint refs | 语义变化可能需要 ADR |
| `application/**` 的跨模块用例/事务编排 | `architecture/end-to-end-planning-flow.md`、`architecture/module-boundaries.md`、`architecture/data-authority.md`、`domain/error-model.md` | REQ/NFR/ENG、integration tests、artifact provenance | 不得复制领域规则或绕过阶段门 |
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

## TASK-P2-10 matrix review

完整Diff base范围命中`IMPACT-REFERENCE-SCHEDULER`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Baseline代码触发Reference必审文档；unit/property/integration触发test matrix/docs/trace；workflow触发configuration/technology/operations/NFR；Task lifecycle与SIM-ASSUMPTION-012触发Phase/registry/docs行。

Schema、Planning/Validator、P2-09 Scenario/fixture、dependency/lock、Benchmark implementation/profile、API/DB/Worker、Export与P3路径均为零差异，因此不声明对应Rule ID。Machine rule表无需新增glob或改变`registry_version`；最终path/count以Task governance report真实结果为准。

Implementation artifact `9435264655`已绑定`8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`并复现38 committed/0 working paths、上述六行、19 checks与0 issues；TASK-P2-10据此关闭为`done`。Schema/Planning/Validator/Scenario/Dependency/Benchmark/Export规则继续未命中，P2-11不自动启动。

## TASK-P0-04 matrix review

本 Task 实际路径预期命中 `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-VALIDATOR`、`IMPACT-STATE`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`schemas/rules/**` 由 IMPACT-SCHEMA 覆盖；rule completeness CLI 位于 `backend/app/planning/validation/**`，由 IMPACT-VALIDATOR 覆盖，不需要无边界新 glob。

PlanningProblem、Backend、Fixture、API、Export/Job implementation 路径均不修改，因此不声明对应 Rule ID。本段记录审查结论，不改变 machine rule 表结构或 registry version；最终以 Task diff report 的真实 matched rows 为准。

## TASK-P0-05 matrix review

本 Task 实际路径预期命中 `IMPACT-SCHEMA`、`IMPACT-VALIDATOR`、`IMPACT-SIM-PROFILE`、`IMPACT-SIM-SCENARIO`、`IMPACT-SIM-GENERATOR`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`pyproject.toml` 只更新 schema metadata但仍按 dependency 行审查；`rule_sheet.py` 只解除旧 set exact-value check但仍按 Validator 行审查。

Fixture、Simulation execution/baseline/benchmark implementation、PlanningProblem/Backend、API、Infra/DB、Export/Job 均不修改，因此不声明对应 Rule ID。现有 machine glob/required-document 表无需改变，registry format version 保持 `1.0.0`；最终以 TASK-P0-05 diff report 的真实 matched rows 为准。

## TASK-P0-06 matrix review

本 Task 预期命中 `IMPACT-SIM-SCENARIO`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/simulation/scenarios/golden_fixture.py` 只做 artifact/provenance/hash replay，`backend/tests/golden/**` 承担 test-local direct calculation；没有修改 `planning/validation/**`，因此不声明 `IMPACT-VALIDATOR`。

FactoryProfile artifact 位于 `fixtures/**` 而非 profile code/schema，故由 `IMPACT-FIXTURE` 覆盖，不虚报 `IMPACT-SIM-PROFILE`。Schema、Generator、PlanningProblem、Backend、Benchmark、API、Infra/DB、Export/Job 均不修改；machine rule 表和 registry format version 保持 `1.0.0`，最终以 TASK-P0-06 diff report 的真实 matched rows 为准。

## TASK-P0-07 matrix review

本 Task 预期命中 `IMPACT-VALIDATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/planning/validation/**` 只新增 fixture-local independent evaluator/mutation runner；`fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/**` 与 `backend/tests/validation/**` 固定 negative evidence；阶段/注册表只同步 P0-07 状态和真实追踪。

Schema、Domain、PlanningProblem、Backend、Simulation code、Golden/其他 tests、dependency/version metadata、Benchmark、API、Infra/DB、Export/Job 均禁止修改，因此不声明对应 Rule ID。现有 machine globs/required-document 列无需改变，registry format version 保持 `1.0.0`；最终以 TASK-P0-07 diff report 的真实 matched rows 为准。

## TASK-P0-08 matrix review

本 Task 预期命中 `IMPACT-API`、`IMPACT-JOBS`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`pyproject.toml` 同时触发 dependency/version review；更新 `export-job.md` 触发完整三套 state/ADR/trace review，即使 machine state artifacts 保持只读。首次 diff check 暴露 Alembic/migrations、`.env.example` 与 CI workflow 没有规则覆盖，因此在同一稳定 `IMPACT-INFRA` 行加入这些有界工程路径；required documentation 不变且均已列入 Task。

Schema、Domain、Import/Normalization/Snapshot、Planning/Validator/Backend、Simulation、Exporter、Fixture、Benchmark、Frontend、governance validator 均禁止修改，因此不声明相应 Rule ID。新增路径覆盖没有创建新 Rule ID、没有改变 required-document column/registry table format，`registry_version` 保持 `1.0.0`。最终以 TASK-P0-08 diff report 的真实 matched rows 为准。

## TASK-P0-09 matrix review

本 Task 只修改明确列出的 P0 phase/milestone、governance registry、quality/index/task/audit documents 和 `docs/milestones/P0-exit-gate-evidence-manifest.json`，实际预期命中 `IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。新建 TASK-P0-10 仅为 planned remediation card；没有执行后续任务或外部操作。

Schema、Domain、Constraint/Validator、Simulation、Fixture、Test、Benchmark、API、Infrastructure/workflow、dependency/version metadata、governance validator 和 P1 path均保持只读，因此不声明对应 Rule ID。machine rule table/required-document column 未修改，`registry_version` 保持 `1.0.0`；最终以 TASK-P0-09 diff report 的真实 matched rows 为准。

## TASK-P0-10 matrix review

本 Task 实际路径命中 `IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`.github/workflows/ci.yml` 只交接当前 Task diff/report 和 artifact 引用；`backend/tests/integration/test_ci_contract.py` 增加 exact handoff/no-stale-reference 断言；phase/audit/registry/docs 只同步 GitHub provider 真实证据与 Gate 状态。

Schema、Domain、Import/Snapshot/Planning/Validator implementation、Simulation code/Fixture、Benchmark、API/Job/DB、dependency/version metadata、governance validator、Solver/P1 path 均禁止修改，因此不声明其他 Rule ID。machine rule table/required-document column 与 registry format 不变，`registry_version` 保持 `1.0.0`；最终以 TASK-P0-10 diff report 的真实 matched rows 为准。

## P1 planning baseline review

2026-08-19 的用户授权使 current phase进入 P1并创建 TASK-P1-01～12。本次 planning baseline只修改 phase/milestone/task/governance/quality/index文档，以及为跨阶段校验所必需的 `scripts/check_docs.py` 与 `backend/tests/unit/test_check_docs.py`；不执行任何 P1业务实现。实际路径预期命中 `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

P1-11首次计划在 `backend/app/application/**` 形成 common-ingress orchestration，因此增加稳定 `IMPACT-APPLICATION` 行，避免未来 application path无机器影响规则。该行只建立治理覆盖，不实现 pipeline，也不改变总规模块边界。Schema、Import、Snapshot、Problem、Simulation、Fixture、Infrastructure workflow和dependency均未在本次 planning baseline中修改。

## TASK-P1-01 matrix review

本 Task实际命中 `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。治理脚本/单测实现 phase policy与CI Task discovery；workflow/integration test移除P0-10 handoff并保留原 gates；阶段/注册表/文档只同步 TASK-P1-01 状态和真实追踪。

Schema、Domain、Import/Snapshot/Planning/Validator/Simulation/Fixture、dependency/version metadata、API/Job/DB、Solver/P2均未修改，因此不声明其他 Rule ID。现有 machine globs与required-document列足够覆盖，无需新 Rule ID或 `registry_version`提升；最终以 TASK-P1-01 diff report真实 matched rows为准。

## TASK-P1-02 matrix review

本Task实际路径命中`IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`pyproject.toml`仅改变schema metadata但仍按dependency/version行审查；Schema、data dictionary、domain pure types、contract tests及所有required docs均在有界清单内。

Adapter/Staging/Normalization/DataValidation/Expansion/Snapshot/Problem builder、Migration/DB、API/Job、Simulation Generator/Fixture、Validator、Backend/Solver、Benchmark、Frontend与governance validator均未修改，因此不声明其Rule ID。现有machine globs/required-document列足够覆盖，无需新Rule或`registry_version`提升；最终以TASK-P1-02 diff report真实matched rows为准。

## TASK-P1-03 matrix review

本Task实际路径预期命中`IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/importers/**`只形成Raw Staging pure contract/protocol/assembler；Infrastructure与migration只形成SQLAlchemy insert-only persistence；测试/阶段/注册表同步真实证据。

首次diff check准确暴露原Task卡遗漏的5份phase/governance必审文档，现已先修订卡片并纳入完整review。Schema、Domain、Application orchestration、Adapter reader、Normalization/DataValidation、Snapshot/Problem、Simulation、Fixture、API/Job/Worker、dependency/version metadata、Solver/Benchmark和governance validator均不修改，因此不声明其他Rule ID。machine rule表无需改变，`registry_version`保持`1.0.0`；最终以TASK-P1-03 diff report真实matched rows为准。

## TASK-P1-04 matrix review

本Task实际路径命中`IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/importers/**`形成reader/protocol/Reference Adapter，`pyproject.toml/uv.lock`精确增加openpyxl/defusedxml，限定test文件形成contract/integration evidence；既有Infrastructure machine contract/CI dependency assertion仅同步exact pin集合并保留solver-free断言，阶段、注册表和文档同步真实边界。

启动前检查准确发现原卡遗漏`change-impact-matrix.md`、`traceability-rules.md`、`sim-assumption-register.md`、`milestones/README.md`与`TASK_TEMPLATE.md`，已在激活前加入Documents/allowed scope；首次实际diff检查又发现`pyproject.toml`同时命中`IMPACT-VERSION-METADATA`，因此在继续验收前补入该Rule ID和`schema-versioning.md`。全仓回归随后忠实暴露P0 exact dependency baseline过期，故再次先扩卡，纳入`infrastructure/contract_check.py`、`test_ci_contract.py`、`IMPACT-INFRA`及其configuration/Operations必审文档。Schema、Domain、Application/migration、Normalization/DataValidation、Snapshot/Problem、Simulation/Fixture、API/Job、Solver/Benchmark和governance validator均未修改；machine rule表和`registry_version`保持`1.0.0`，最终以TASK-P1-04 diff report真实matched rows为准。

## TASK-P1-05 matrix review

本Task实际路径命中`IMPACT-SCHEMA`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前先把受global schema断言影响的既有contract tests，以及dependency/phase/governance矩阵强制文档和三份直接architecture说明补入Task Card允许范围；Diff base保持`d63926f84d9d2b7bc46bbcaff5704612af120a34`。

Schema变化只新增unit registry并同步set metadata/data dictionary；Import v2/canonical-records v1原文件、DB/migration、Adapter/Infrastructure、DataValidation/Expansion/Snapshot/Problem、Simulation、API/Job、Solver/Benchmark均未改。`pyproject.toml`无dependency变化，`uv.lock`不变；machine impact rows和registry format version不变，最终以TASK-P1-05 diff report真实matched rows为准。

## TASK-P1-06 matrix review

本Task实际命中`IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡遗漏`IMPACT-DOMAIN/DEPENDENCY/VERSION-METADATA/PHASE/GOVERNANCE-REGISTRY`的若干强制文档、两个受global schema version影响的既有contract tests和Task已要求但未分配路径的ImportQualityReport samples，均已在任何业务实现前补入范围；Diff base固定为`75d761332204ec779477ba7242c98517cce1b68b`。

本Task只新增error registry v2、error.v3、ImportQualityReport v1和`backend/app/data_validation/**`，同步domain pure error/types、schema set metadata与限定测试；旧error/import/canonical/unit artifacts由固定SHA-256证明只读。`pyproject.toml`只改schema metadata、dependency与`uv.lock`不变。Planning ScheduleValidator/constraint formula、Adapter/Staging/Normalization、Expansion/Snapshot/Problem、Simulation、API/HTTP、Solver/Benchmark实现均未修改，因此不声明其他Rule ID；最终以TASK-P1-06 diff report真实changed paths/九行matched/0 issues为准。

## TASK-P1-07 matrix review

本Task实际命中`IMPACT-DOMAIN`、`IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡遗漏domain/dependency/version/tests/phase/governance/docs行的强制文档与root README，并在任何业务实现前补入范围；全仓回归随后发现workflow未收集property tests，故在修改CI前再次扩卡加入INFRA文件及configuration/Operations必审文档。Diff base始终固定`97728521e187f9f50715de4b04a09098bef62ddf`。

实际实现只新增pure domain production contract、normalization order expansion、unit/property tests和dev-only Hypothesis lock，并在既有workflow/integration contract追加phase-neutral property suite路径；`pyproject.toml`的schema/code metadata与runtime dependencies不变。Schema/error registry、Adapter/Staging/unit-time Normalizer、DataValidation、Snapshot/Problem、Simulation/API/DB/Worker、Constraint/ScheduleValidator、Solver/Benchmark均未修改，因此不声明其他Rule ID；最终以TASK-P1-07 diff report真实changed paths/九行matched/0 issues为准。

## TASK-P1-08 matrix review

本Task实际路径命中`IMPACT-SNAPSHOT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡遗漏root/docs入口、端到端当前态及TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS行的强制文档，均已在任何Snapshot业务实现前补入允许范围；Diff base固定为`8b4fb4c027305d3e3aa68eec0baaf73cd0598189`。

实际实现只修改`app.snapshots`、新增Infrastructure repository/`0003` migration及限定unit/property/integration/migration tests。Snapshot v1/v2 Schema、Import/Adapter/Normalization/DataValidation/Expansion、dependency/lock/version metadata、Application/Planning/Solver/Simulation/API/Job均不修改，因此不声明SCHEMA/IMPORT/DEPENDENCY/VERSION/APPLICATION等其他Rule ID；machine rule表和`registry_version`保持`1.0.0`。Implementation artifact内TASK-P1-08 diff report精确记录SHA `72670d18a29c9a10cb70f7a263c981a2b660e0ee`、41 changed paths、六行matched、0 issues并由run `32310098594`重放成功。

## TASK-P1-10 matrix review

本Task实际路径命中`IMPACT-IMPORT`、`IMPACT-SIM-GENERATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前已先补入验收所需contract check和各行强制文档；真实生成调用发现`cycle_seconds_per_unit`既有duration合同与normalizer分类矛盾后，按治理规则先停并扩卡加入唯一normalizer/unit regression及IMPORT强制文档。Diff base始终为`11c6ca97882a3be5bf6eb25bab84f69d1dfe469c`。

实际实现仅修复该字段transform分类、新增七层Generator/package/contract check、一个versioned synthetic asset和限定unit/simulation tests。Schema、domain DTO、Adapter/Staging/DataValidation、Snapshot/Problem、Application/API/DB/Worker、dependency/version metadata、Solver/Benchmark及governance validator均不修改；machine rule表和`registry_version`保持`1.0.0`，最终以TASK-P1-10 diff report真实changed paths/七行matched/0 issues为准。

## TASK-P1-11 matrix review

本Task实际路径预期命中`IMPACT-APPLICATION`、`IMPACT-SIM-GENERATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡缺少Generator公开Raw Staging路径及INFRA/PHASE/GOVERNANCE行强制的`technology-stack.md`、`milestones/README.md`、`TASK_TEMPLATE.md`，均在任何业务代码前扩入允许范围；Diff base固定为`ea56c3867651c0f03306e66936fd649526049319`。

实现只新增application orchestration/report、Generator公开`prepare_batch()`、限定contract/integration/simulation tests和CI report命令，不改Schema/registry、Domain/Import/Normalization/DataValidation/Expansion/Snapshot/Problem语义、migration/dependency、API/Worker、Solver/Validator/Benchmark/P2。Machine impact rules和`registry_version`不变，最终以TASK-P1-11 diff report真实paths/7 rows/0 issues为准。

## TASK-P1-12 matrix review

本Task实际路径只命中`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`：新增P1 audit report/JSON manifest并同步current phase、Milestone/Task索引、合同/架构/质量审计结论、根注册表、traceability和文档清单。JSON manifest位于`docs/milestones/**`，由PHASE行覆盖但按文档清单规则不作为Markdown inventory条目。

业务代码、Schema/fixture、test、migration、workflow/infra、dependency/version metadata、governance validator、Solver/P2路径均保持只读，因此不声明其他Rule ID。Machine rule table/required-document列与`registry_version=1.0.0`不变；最终以TASK-P1-12 diff report的actual paths/3 matched rows/0 issues为准。

## TASK-P2-01 matrix review

本Task实际路径预期命中`IMPACT-SCHEMA`、`IMPACT-PROBLEM`、`IMPACT-DOMAIN`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Dependency row是强制review而非lock变化：`pyproject.toml`只提升schema metadata，runtime/dev pins与`uv.lock`必须无diff。INFRA只新增通用CI machine command，不改变service/Compose/deployment。

Schema/Problem/Domain实现限定为additive Problem v2、version-specific APIs、pure precheck与tests；v1 bytes/default API保留。Phase/Governance在exact implementation provider成功后只把P2-01闭环为`done`并同步formed/PLANNED边界，不激活P2-02。Machine rule table/required-document columns与`registry_version=1.0.0`不变；implementation provider Task report为60 paths、10 matched rows和0 issues，最终docs-overview有界更正使完整Task range为61 unique paths并保持相同10 rows/0 issues。

## TASK-P2-02 matrix review

本Task实际路径预期命中`IMPACT-SCHEMA`、`IMPACT-PLANNING-CONTRACTS`、`IMPACT-POLICY`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Dependency row只因`pyproject.toml`提升schema metadata触发；runtime/dev pins和`uv.lock`无diff。INFRA只增加CI contract-report step，不改变service/deployment。实现中含current schema-set值的glossary在修改前已扩入allow-list；planning-run mapping审查触发STATE后也在修改其余state文档前补齐Rule与required docs。

实现限定为四份Schema/sample、pure JSON-compatible contracts/status/fingerprint checks、测试和CI report；Problem v1/v2、Backend/Constraint/Validator/DB/API/Worker/P3均只读。STATE只同步既有status mapping并确认ScheduleVersion/ExportJob无行为变化。Phase/Governance在exact implementation provider成功后把P2-02闭环为`done`，不激活P2-03/P2-04。Machine rule table/required-document columns与`registry_version=1.0.0`不变；implementation artifact内TASK-P2-02 diff report为63 actual paths、11 matched rows、19 checks和0 issues。

## TASK-P2-03 matrix review

本Task实际命中`IMPACT-POLICY/BACKEND/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`九行。实现限定exact dependency/lock、CP-SAT namespace、historical report compatibility、tests/workflow和Task声明文档；Problem/Policy/Solution/Report Schema/sample及canonical合同、Strategy/C-ID/objective/Validator/fixture/benchmark/export/DB/API/Worker/P3均无差异。

首次solver依赖由ADR-0011和dependency/security review闭环；RISK-011是登记未消除的风险，不改变registry格式。Implementation provider artifact `9398128763`内Task report确认50 actual paths、9 matched rows、19 checks、0 issues，故Task=`done`；P2-04不自动激活。

本地Task diff实际为50 paths、9 matched rows、19 checks和0 issues；provider必须对exact implementation SHA复现该范围。

## TASK-P2-04 matrix review

本Task实际预期命中`IMPACT-VALIDATOR/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行。VALIDATOR覆盖formal evaluator、machine CLI和公开导出；INFRA仅增加CI machine command；TESTS覆盖contract/mutation/property/integration；其余三行同步Task/Milestone/trace/register/inventory及说明文档。

Problem/Solution/Validation/Error Schema、fixture历史bytes、`pyproject.toml`/`uv.lock`、Backend/Strategy/constraint model、objective、Benchmark、migration、DB/API/Worker和P3均无差异，故不声明SCHEMA/DEPENDENCY/BACKEND等其他Rule ID。Machine rule table、required-document columns与`registry_version=1.0.0`不变；implementation provider artifact已记录actual paths/checks，TASK-P2-04据此为`done`。

本地Task diff实际为38 paths、6 matched rows、19 checks和0 issues；implementation artifact `9399519368`对exact SHA复现38 committed/0 working paths、相同6 rows/19 checks/0 issues，故影响治理闭环。

## TASK-P2-05 impact review

实际范围必须命中`IMPACT-BACKEND`（CP-SAT model/mapper/consumer）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-PHASE`（唯一active Task与边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（合同/规划/质量/运维同步）六行。Problem/Policy/Solution Schema、rule sheet、formal Validator、dependency/lock、fixture/benchmark、migration、DB/API/Worker和P3无差异，因此不命中SCHEMA/DEPENDENCY/MIGRATION等额外Rule ID。

最终path/check/issue计数必须由TASK-P2-05 diff report和exact provider artifact回填；在验收前不得预写。Registry table与`registry_version=1.0.0`均不修改。

本地TASK-P2-05 report实际为49 paths、6 matched rows、19 checks、0 issues，六行与上方预期完全一致。该数字仍须由exact implementation provider artifact重放后才能闭环。

Implementation artifact `9400957897`已对exact SHA重放49 committed/0 working paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/TESTS`六行、19 checks与0 issues，影响治理闭环。未出现额外SCHEMA/DEPENDENCY/MIGRATION影响。

## TASK-P2-06 impact review

实际范围必须命中`IMPACT-BACKEND`（temporal builder/model/mapper/consumer）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-PHASE`（唯一active Task与阶段边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（合同/规划/质量/运维同步）六行。

Problem/Policy/Solution Schema、rule sheet、formal Validator、Problem builder/hash、dependency/lock、fixture/benchmark、migration、DB/API/Worker和P3无差异，因此不命中SCHEMA/DEPENDENCY/MIGRATION等额外Rule ID。最终path/check/issue计数必须由TASK-P2-06 diff report与exact provider artifact回填；registry tables及`registry_version=1.0.0`保持不变。

本地TASK-P2-06 report实际为53 paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/TESTS`六行、19 checks与0 issues，和预期完全一致；exact provider artifact通过前只作为local evidence。

Implementation artifact `9429579311`已对exact SHA `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`重放53 committed/0 working paths、六行、19 checks与0 issues，影响治理闭环。未出现额外SCHEMA/DEPENDENCY/MIGRATION影响。

## TASK-P2-07 impact review

实际范围必须命中`IMPACT-BACKEND`（fact/lock builder、precheck、model/mapper/consumer）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-PHASE`（唯一active Task与边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（合同/领域/规划/质量/运维同步）六行。

Problem/Policy/Solution Schema、rule sheet、formal Validator、Problem builder/hash、dependency/lock、fixture/benchmark implementation、migration、DB/API/Worker和P3无差异，因此不命中SCHEMA/VALIDATOR/PROBLEM/DEPENDENCY/MIGRATION等额外Rule ID。最终path/check/issue计数必须由TASK-P2-07 diff report与exact provider artifact回填；registry tables及`registry_version=1.0.0`保持不变。

本地Task diff已精确命中上述六行：54 changed paths、19 checks、0 issues；禁止路径相对Diff base无变化。Exact provider artifact仍需在implementation SHA push后复现同一range与Impact Rule集合，Task才可关闭。

Implementation artifact `9430579117`已绑定`5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`并复现54 paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/TESTS`六行、19 checks、0 issues；Task据此关闭为`done`。Schema/Validator/Problem/Dependency/Migration Rule继续未命中，P2-08不自动启动。

## TASK-P2-08 impact review

实际范围必须命中`IMPACT-POLICY`（versioned Simulation Delivery Policy/explicit limits）、`IMPACT-STRATEGY`（single global orchestration）、`IMPACT-BACKEND`（OBJ-001 builder、objective-aware solve/mapper/report）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-PHASE`（唯一active Task与边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（架构/合同/领域/规划/质量/运维同步）八行。

Planning Schema/contracts、Problem builder/hash、formal Validator、core model/C-ID formulas、dependency/lock、fixture/benchmark implementation、migration、DB/API/Worker和P3/P4无差异，因此不命中SCHEMA/PLANNING-CONTRACTS/PROBLEM/VALIDATOR/DEPENDENCY/MIGRATION等额外Rule ID。最终path/check/issue计数必须由TASK-P2-08 diff report与exact provider artifact回填；registry tables及`registry_version=1.0.0`保持不变。

本地machine report已形成7/7 objective/strategy checks与70 focused/395 full tests；最终Task diff精确为52 changed paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/POLICY/STRATEGY/TESTS`八行、19 checks、0 issues。禁止路径相对Diff base无变化；exact provider artifact绑定implementation SHA前TASK-P2-08保持`in_progress`，P2-09不自动启动。

Implementation artifact `9431673977`已绑定`b1ec83ed96120357ecadd41d3f520181838f17c6`并复现52 committed/0 working paths、上述八行、19 checks与0 issues；TASK-P2-08据此关闭为`done`。Schema/Planning contracts/Problem/Validator/Dependency/Migration Rule继续未命中，P2-09不自动启动。

## TASK-P2-09 local impact review

实际差异命中`IMPACT-SIM-SCENARIO/FIXTURE/TESTS/INFRA/PHASE/GOVERNANCE-REGISTRY/DOCS`七行；Task卡已在首个asset产生前展开全部实际路径，并在activation提交后、实现前切换为完整Impact Rule。发布Schema、Planning/Application/Generator、Dependency/Version Metadata、Migration、Benchmark/Reference/Export/API/Jobs均未命中，故对应规则不得虚报。

所有七行required documents已进入本Task `Documents to update`并同步review。本地`TASK-P2-09-report.json`精确为58 paths、7 rows、19 checks、0 issues；provider artifact须重现58 committed/0 working paths并绑定implementation SHA，provider前Task保持`in_progress`。

Implementation artifact `9432982306`已绑定`20e49c92306128b47313059fabe31534814dbe3d`并复现58 committed/0 working paths、上述七行、19 checks与0 issues；TASK-P2-09据此关闭为`done`。Schema/Planning/Application/Generator/Dependency/Migration/Benchmark/Reference/Export规则继续未命中，P2-10不自动启动。

## TASK-P2-11 impact review

完整Diff base范围必须命中`IMPACT-SCHEMA`（KPI/manifest/data dictionary）、`IMPACT-REPORTING`（KPI/SolverReport）、`IMPACT-EXPORT`（internal package）、`IMPACT-STATE`（明确零ScheduleVersion/ExportJob transition）、`IMPACT-TESTS`、`IMPACT-INFRA`（CI machine step）、`IMPACT-DEPENDENCY`与`IMPACT-VERSION-METADATA`（`pyproject.toml`仅schema metadata）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`十一行。

Dependency行是强制review，runtime/dev pins及`uv.lock`必须零差异；State行只审查状态合同且`state-machines.v1`/migration/persistence不得修改。Planning/Strategy/Backend/Validator/Problem/Snapshot/Import/Simulation/P2-09 assets、Benchmark/API/DB/Worker/P3+保持零差异。Machine rule table和`registry_version=1.0.0`不变，最终path/count以Task report为准。

Implementation artifact `9436863185`已绑定`546292831c3bd52185687a4c646c10ae10541ae2`并复现58 committed/0 working paths、上述十一行、19 checks与0 issues；TASK-P2-11据此关闭为`done`。Runtime/dev dependency、`uv.lock`、state persistence、Planning/Strategy/Backend/Validator/Scenario/Benchmark/API/DB/Worker/P3+禁止边界保持零差异，P2-12不自动启动。

## TASK-P2-12 impact review

完整Diff base范围命中`IMPACT-BENCHMARK`（profiles/baselines/runner/CLI）、`IMPACT-REPORTING`（只抽公共schedule KPI pure calculation）、`IMPACT-TESTS`、`IMPACT-INFRA`（CI XS及artifact）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`七行。所有required documents均已列入Task allow-list并同步review。

Schema/global set、Planning Problem/Policy/Strategy/Backend/Validator、Reference算法、P2-09 assets、P2-11 Exporter、dependency/lock、migration/DB/API/Worker和P3+零差异，故不声明对应Rule ID。Machine rule table与`registry_version=1.0.0`不变；最终path/check/issue计数须由Task diff report和exact provider artifact回填，provider前Task保持`in_progress`。

Implementation artifact `9438899443`已绑定`01e7f4bdca88fc903e7caa771f875fc1a70ff357`并复现49 committed/0 working paths、上述七行、19 checks与0 issues；TASK-P2-12据此关闭为`done`。Schema/dependency、Planning/Strategy/Backend/Validator/Reference/Scenario/Exporter/API/DB/Worker/P3+禁止边界保持零差异，P2-13不自动启动。

## TASK-P2-13 impact review

完整Diff base范围命中`IMPACT-APPLICATION`（新增只读Gate orchestrator及精确Exporter合同检查例外）、`IMPACT-TESTS`（Gate/exit/CI与既有application boundary）、`IMPACT-INFRA`（required validate新增Gate命令）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`六行。所有实现和文档路径必须在Task allow-list内，P2-14/P3不得因Gate PASS自动激活。

Schema/global set、migration/database、runtime/dev dependency与`uv.lock`、ADR、Planning/Strategy/Backend/Validator/Reference/Scenario/Benchmark/Exporter实现、API/Worker/P3+均零差异，故不声明对应Rule ID。Gate只消费这些冻结的公开能力；`backend/tests/integration/test_p1_common_ingress.py`的例外只能允许`p2_gate_report.py`直接导入`app.exporters.contract_check`，不得扩大application→exporter反向依赖。Machine rule table与`registry_version=1.0.0`不变；最终path/check/issue计数由Task diff report与exact provider artifact回填。

本地完整Diff治理已实际覆盖37 paths（activation 8 committed、当前37 working-tree union）、上述六行、19 checks与0 issues并PASS。Implementation exact provider artifact形成前不得把该本地结果写成外部required evidence或关闭Task。

Implementation artifact `9440650646`已绑定`dc2e5cd41080603606090ebfc4bc6162941c5f7f`并复现37 committed/0 working paths、上述六行、19 checks与0 issues；TASK-P2-13据此关闭为`done`。Schema/migration/dependency/lock/ADR及冻结业务实现边界保持零差异，P2-14/P3不自动启动。

## TASK-P2-14 impact review

完整Diff base范围只允许命中`IMPACT-PHASE`（audit report/manifest、current phase、Milestone/Task索引）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk/matrix review）和`IMPACT-DOCS`（合同/规划/质量/清单同步）三行。Ignored `build/validation/TASK-P2-14-*`和`build/traceability/TASK-P2-14-report.json`不进入Git diff或Markdown inventory。

Backend/application、Schema/global set、fixture/benchmark baseline、test assertions、scripts/workflow、dependency/lock、migration/database、ADR、API/Worker、P3+均相对Diff base零差异，故不声明其他Rule ID。Machine rule table、required-document列和`registry_version=1.0.0`不变；最终本地Task diff report已覆盖30 paths（8 committed-range / 30 working-tree union）、上述3 rows、19 checks、0 issues并PASS。Exact implementation provider仍须复现该范围，形成前不得关闭Task。
