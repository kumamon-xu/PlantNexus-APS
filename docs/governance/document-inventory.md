---
doc_id: DOC-GOV-009
title: 文档清单
status: living
spec_version: 0.3.0
phase: cross-phase
normative: false
source_sections: []
last_reviewed: 2026-08-21
registry_version: 1.0.0
---

# 文档清单

本清单列出当前仓库已经实际存在的Markdown文档。P0/P1均已归档为completed；P2现为active，TASK-P2-00～10已done，TASK-P2-11已获授权并为in_progress。P2-12～14仍为planned且未获启动授权。产品API与Production Runbook正文尚未形成并继续由相应索引登记。

| Path | Doc ID | Status | Title |
|---|---|---|---|
| [adr/ADR_TEMPLATE.md](../adr/ADR_TEMPLATE.md) | TEMPLATE-ADR | baseline | ADR Template |
| [adr/ADR-0001-simulation-first-common-ingress.md](../adr/ADR-0001-simulation-first-common-ingress.md) | ADR-0001 | accepted | Simulation-First 使用共同数据入口 |
| [adr/ADR-0002-modular-monolith-and-solver-worker.md](../adr/ADR-0002-modular-monolith-and-solver-worker.md) | ADR-0002 | accepted | Modular Monolith 与独立 Solver Worker |
| [adr/ADR-0003-solver-neutral-planning-problem.md](../adr/ADR-0003-solver-neutral-planning-problem.md) | ADR-0003 | accepted | Solver-neutral PlanningProblem |
| [adr/ADR-0004-global-cp-sat-strategy-for-v1.md](../adr/ADR-0004-global-cp-sat-strategy-for-v1.md) | ADR-0004 | accepted | V1 使用 Global CP-SAT Strategy |
| [adr/ADR-0005-independent-schedule-validator.md](../adr/ADR-0005-independent-schedule-validator.md) | ADR-0005 | accepted | 独立 ScheduleValidator |
| [adr/ADR-0006-lexicographic-objectives.md](../adr/ADR-0006-lexicographic-objectives.md) | ADR-0006 | accepted | 词典序目标层级 |
| [adr/ADR-0007-immutable-snapshot-and-schedule-version.md](../adr/ADR-0007-immutable-snapshot-and-schedule-version.md) | ADR-0007 | accepted | 不可变 Snapshot 与版本化计划发布 |
| [adr/ADR-0008-utc-seconds-and-solver-ticks.md](../adr/ADR-0008-utc-seconds-and-solver-ticks.md) | ADR-0008 | accepted | UTC、整数秒与可配置 Solver Tick |
| [adr/ADR-0009-production-simulation-data-isolation.md](../adr/ADR-0009-production-simulation-data-isolation.md) | ADR-0009 | accepted | Production 与 Simulation 数据隔离 |
| [adr/ADR-0010-planning-problem-v2-contract-evolution.md](../adr/ADR-0010-planning-problem-v2-contract-evolution.md) | ADR-0010 | accepted | PlanningProblem v2 合同演进 |
| [adr/ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md](../adr/ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md) | ADR-0011 | accepted | OR-Tools 9.15 CP-SAT Backend 与版本策略 |
| [adr/README.md](../adr/README.md) | DOC-ADR-INDEX | baseline | Architecture Decision Records |
| [agents/AGENTS.md](../agents/AGENTS.md) | DOC-AGENT-001 | baseline | PlantNexus APS Coding Agent 规则 |
| [agents/reading-order-and-context-policy.md](../agents/reading-order-and-context-policy.md) | DOC-AGENT-002 | baseline | Agent 读取顺序与上下文策略 |
| [agents/review-checklists.md](../agents/review-checklists.md) | DOC-AGENT-005 | living | Agent 审查清单 |
| [agents/role-and-module-boundaries.md](../agents/role-and-module-boundaries.md) | DOC-AGENT-004 | baseline | Agent 角色与模块边界 |
| [agents/task-execution-protocol.md](../agents/task-execution-protocol.md) | DOC-AGENT-003 | baseline | Task 执行协议 |
| [architecture/configuration-environments-and-isolation.md](../architecture/configuration-environments-and-isolation.md) | DOC-ARCH-008 | baseline | 配置、环境与数据隔离 |
| [architecture/data-authority.md](../architecture/data-authority.md) | DOC-ARCH-005 | baseline | 数据权威边界 |
| [architecture/end-to-end-planning-flow.md](../architecture/end-to-end-planning-flow.md) | DOC-ARCH-002 | baseline | 端到端计划链路 |
| [architecture/module-boundaries.md](../architecture/module-boundaries.md) | DOC-ARCH-003 | baseline | 模块边界与依赖规则 |
| [architecture/provenance-and-versioning.md](../architecture/provenance-and-versioning.md) | DOC-ARCH-009 | baseline | Provenance 与版本规则 |
| [architecture/repository-layout.md](../architecture/repository-layout.md) | DOC-ARCH-007 | baseline | 目标仓库结构 |
| [architecture/simulation-first-dual-channel.md](../architecture/simulation-first-dual-channel.md) | DOC-ARCH-004 | baseline | Simulation-First 双通道架构 |
| [architecture/system-context.md](../architecture/system-context.md) | DOC-ARCH-001 | baseline | 系统上下文 |
| [architecture/technology-stack.md](../architecture/technology-stack.md) | DOC-ARCH-006 | baseline | 推荐技术栈与锁定规则 |
| [contracts/execution-events-and-replan-request.md](../contracts/execution-events-and-replan-request.md) | DOC-CONTRACT-006 | baseline | ExecutionEvent 与 ReplanRequest 合同 |
| [contracts/export-package.md](../contracts/export-package.md) | DOC-CONTRACT-007 | baseline | 标准成果包合同 |
| [contracts/import-and-normalization.md](../contracts/import-and-normalization.md) | DOC-CONTRACT-001 | baseline | Import 与 Normalization 合同 |
| [contracts/planning-policy-and-solve-limits.md](../contracts/planning-policy-and-solve-limits.md) | DOC-CONTRACT-004 | baseline | PlanningPolicy 与 SolveLimits 合同 |
| [contracts/planning-problem.md](../contracts/planning-problem.md) | DOC-CONTRACT-003 | baseline | PlanningProblem 合同 |
| [contracts/planning-snapshot.md](../contracts/planning-snapshot.md) | DOC-CONTRACT-002 | baseline | PlanningSnapshot 合同 |
| [contracts/planning-solution-and-schedule-version.md](../contracts/planning-solution-and-schedule-version.md) | DOC-CONTRACT-005 | baseline | PlanningSolution 与 ScheduleVersion 合同 |
| [contracts/README.md](../contracts/README.md) | DOC-CONTRACT-INDEX | living | 合同文档索引 |
| [contracts/schema-index.md](../contracts/schema-index.md) | DOC-CONTRACT-008 | living | Schema 计划索引 |
| [contracts/schema-versioning.md](../contracts/schema-versioning.md) | DOC-CONTRACT-009 | baseline | Schema 版本与兼容规则 |
| [core/APS_IMPLEMENTATION_SPEC.md](../core/APS_IMPLEMENTATION_SPEC.md) | SOURCE-SPEC | implementation_ready | PlantNexus APS 模块 Vibe Coding 开发技术框架与实施规格 |
| [core/capability-matrix.md](../core/capability-matrix.md) | DOC-CORE-004 | baseline | 能力矩阵 |
| [core/engineering-principles-and-invariants.md](../core/engineering-principles-and-invariants.md) | DOC-CORE-002 | baseline | 工程原则与不可破坏不变量 |
| [core/glossary.md](../core/glossary.md) | DOC-CORE-003 | living | 术语表 |
| [core/scope-and-success-criteria.md](../core/scope-and-success-criteria.md) | DOC-CORE-001 | baseline | V1 范围与成功标准 |
| [current_phase.md](../current_phase.md) | DOC-PHASE-CURRENT | living | 当前阶段 |
| [domain/domain-model.md](../domain/domain-model.md) | DOC-DOM-001 | baseline | APS 领域模型 |
| [domain/error-model.md](../domain/error-model.md) | DOC-DOM-006 | baseline | 错误与求解状态模型 |
| [domain/execution-facts-locks-and-replan.md](../domain/execution-facts-locks-and-replan.md) | DOC-DOM-004 | baseline | 执行事实、锁定与重排边界 |
| [domain/kpi-contract.md](../domain/kpi-contract.md) | DOC-DOM-005 | baseline | KPI 合同 |
| [domain/operation-instance-and-resource-options.md](../domain/operation-instance-and-resource-options.md) | DOC-DOM-002 | baseline | OperationInstance 与候选资源语义 |
| [domain/state-machines/export-job.md](../domain/state-machines/export-job.md) | DOC-STATE-003 | baseline | ExportJob 状态机 |
| [domain/state-machines/planning-run.md](../domain/state-machines/planning-run.md) | DOC-STATE-001 | baseline | PlanningRun 状态机 |
| [domain/state-machines/schedule-version.md](../domain/state-machines/schedule-version.md) | DOC-STATE-002 | baseline | ScheduleVersion 状态机 |
| [domain/time-calendar-and-material-boundaries.md](../domain/time-calendar-and-material-boundaries.md) | DOC-DOM-003 | baseline | 时间、日历与物料边界 |
| [frontend/README.md](../frontend/README.md) | DOC-FRONTEND-INDEX | planned | Frontend 文档形成计划 |
| [governance/change-impact-matrix.md](../governance/change-impact-matrix.md) | DOC-GOV-010 | baseline | 变更影响与必审文档矩阵 |
| [governance/document-control.md](../governance/document-control.md) | DOC-GOV-001 | baseline | 文档控制规则 |
| [governance/document-inventory.md](../governance/document-inventory.md) | DOC-GOV-009 | living | 文档清单 |
| [governance/nfr-and-engineering-register.md](../governance/nfr-and-engineering-register.md) | DOC-GOV-003 | living | NFR 与工程需求注册表 |
| [governance/prod-open-register.md](../governance/prod-open-register.md) | DOC-GOV-006 | living | PROD_OPEN 注册表 |
| [governance/requirements-register.md](../governance/requirements-register.md) | DOC-GOV-002 | baseline | 核心需求注册表 |
| [governance/risk-register.md](../governance/risk-register.md) | DOC-GOV-008 | living | 项目风险注册表 |
| [governance/sim-assumption-register.md](../governance/sim-assumption-register.md) | DOC-GOV-007 | living | SIM_ASSUMPTION 注册表 |
| [governance/traceability-matrix.md](../governance/traceability-matrix.md) | DOC-GOV-005 | living | 追踪矩阵 |
| [governance/traceability-rules.md](../governance/traceability-rules.md) | DOC-GOV-004 | baseline | 需求追踪规则 |
| [milestones/P0-executable-specification.md](../milestones/P0-executable-specification.md) | MILESTONE-P0 | completed | P0 — Executable Specification |
| [milestones/P0-exit-gate-audit-report.md](../milestones/P0-exit-gate-audit-report.md) | MILESTONE-P0-AUDIT-001 | baseline | P0 Exit Gate Audit Report |
| [milestones/P1-data-and-snapshot.md](../milestones/P1-data-and-snapshot.md) | MILESTONE-P1 | completed | P1 — Data & Snapshot |
| [milestones/P1-exit-gate-audit-report.md](../milestones/P1-exit-gate-audit-report.md) | MILESTONE-P1-AUDIT-001 | baseline | P1 Exit Gate Audit Report |
| [milestones/P2-cp-sat-vertical-slice.md](../milestones/P2-cp-sat-vertical-slice.md) | MILESTONE-P2 | active | P2 — CP-SAT Vertical Slice |
| [milestones/P3-planning-workspace.md](../milestones/P3-planning-workspace.md) | MILESTONE-P3 | planned | P3 — Planning Workspace |
| [milestones/P4-dynamic-replanning.md](../milestones/P4-dynamic-replanning.md) | MILESTONE-P4 | planned | P4 — Dynamic Replanning |
| [milestones/P5-advanced-capabilities.md](../milestones/P5-advanced-capabilities.md) | MILESTONE-P5 | planned | P5 — Advanced Capabilities |
| [milestones/P6-ai-duration-prediction.md](../milestones/P6-ai-duration-prediction.md) | MILESTONE-P6 | planned | P6 — AI Duration Prediction |
| [milestones/P7-reality-calibration.md](../milestones/P7-reality-calibration.md) | MILESTONE-P7 | planned | P7 — Reality Calibration |
| [milestones/README.md](../milestones/README.md) | DOC-MILESTONE-INDEX | baseline | Milestone 索引 |
| [operations/observability-and-audit.md](../operations/observability-and-audit.md) | DOC-OPS-002 | baseline | P0 Observability 与 Audit 边界 |
| [operations/README.md](../operations/README.md) | DOC-OPS-INDEX | baseline | Operations 索引与形成边界 |
| [operations/security.md](../operations/security.md) | DOC-OPS-001 | baseline | P0 工程安全边界 |
| [operations/worker-reliability-and-idempotency.md](../operations/worker-reliability-and-idempotency.md) | DOC-OPS-003 | baseline | P0 Worker Reliability 与 Idempotency |
| [planning/constraint-catalog.md](../planning/constraint-catalog.md) | DOC-PLAN-003 | baseline | V1 Constraint Catalog |
| [planning/infeasibility-diagnostics.md](../planning/infeasibility-diagnostics.md) | DOC-PLAN-006 | baseline | 无解与失败诊断 |
| [planning/objective-policy.md](../planning/objective-policy.md) | DOC-PLAN-004 | baseline | Objective Policy |
| [planning/planning-strategies.md](../planning/planning-strategies.md) | DOC-PLAN-002 | baseline | PlanningStrategy 规则 |
| [planning/reference-schedulers.md](../planning/reference-schedulers.md) | DOC-PLAN-007 | baseline | Reference Scheduler 基线 |
| [planning/replanning.md](../planning/replanning.md) | DOC-PLAN-008 | baseline | 动态重排设计合同 |
| [planning/schedule-validator.md](../planning/schedule-validator.md) | DOC-PLAN-005 | baseline | 独立 ScheduleValidator 合同 |
| [planning/solver-backend-contract.md](../planning/solver-backend-contract.md) | DOC-PLAN-001 | baseline | SolverBackend 合同 |
| [quality/benchmark-regression.md](../quality/benchmark-regression.md) | DOC-QUAL-005 | baseline | Benchmark Regression 规则 |
| [quality/ci-gates-and-definition-of-done.md](../quality/ci-gates-and-definition-of-done.md) | DOC-QUAL-006 | baseline | CI Gate 与 Definition of Done |
| [quality/documentation-consistency-checks.md](../quality/documentation-consistency-checks.md) | DOC-QUAL-007 | baseline | 文档一致性自动检查合同 |
| [quality/fixtures-and-golden-tests.md](../quality/fixtures-and-golden-tests.md) | DOC-QUAL-002 | baseline | Fixture 与 Golden Test 规范 |
| [quality/property-tests.md](../quality/property-tests.md) | DOC-QUAL-004 | baseline | Property Test 规范 |
| [quality/test-strategy-and-matrix.md](../quality/test-strategy-and-matrix.md) | DOC-QUAL-001 | baseline | 测试策略与 Test Matrix |
| [quality/validator-mutation-tests.md](../quality/validator-mutation-tests.md) | DOC-QUAL-003 | baseline | Validator Mutation Test 规范 |
| [README.md](../README.md) | DOC-INDEX-001 | baseline | PlantNexus APS 文档中心 |
| [runbooks/README.md](../runbooks/README.md) | DOC-RUNBOOK-INDEX | planned | Runbook 形成计划 |
| [simulation/benchmark-harness.md](../simulation/benchmark-harness.md) | DOC-SIM-006 | baseline | Benchmark Harness 合同 |
| [simulation/execution-simulator-and-disruptions.md](../simulation/execution-simulator-and-disruptions.md) | DOC-SIM-005 | baseline | Execution Simulator 与异常模型 |
| [simulation/factory-profile.md](../simulation/factory-profile.md) | DOC-SIM-001 | baseline | FactoryProfile 合同 |
| [simulation/performance-gates.md](../simulation/performance-gates.md) | DOC-SIM-007 | baseline | 性能与现实校准门 |
| [simulation/README.md](../simulation/README.md) | DOC-SIM-INDEX | baseline | Simulation 子系统 |
| [simulation/scenario-library-and-matrix.md](../simulation/scenario-library-and-matrix.md) | DOC-SIM-004 | baseline | Scenario Library 与复杂度矩阵 |
| [simulation/scenario-spec-and-provenance.md](../simulation/scenario-spec-and-provenance.md) | DOC-SIM-002 | baseline | ScenarioSpec 与 Provenance |
| [simulation/synthetic-generator-and-determinism.md](../simulation/synthetic-generator-and-determinism.md) | DOC-SIM-003 | baseline | Synthetic Generator 与确定性 |
| [tasks/P0/TASK-P0-01-documentation-and-repository-governance.md](../tasks/P0/TASK-P0-01-documentation-and-repository-governance.md) | TASK-P0-01 | done | Documentation and Repository Governance |
| [tasks/P0/TASK-P0-02-requirements-and-traceability.md](../tasks/P0/TASK-P0-02-requirements-and-traceability.md) | TASK-P0-02 | done | Requirements and Traceability |
| [tasks/P0/TASK-P0-03-domain-and-schema-skeleton.md](../tasks/P0/TASK-P0-03-domain-and-schema-skeleton.md) | TASK-P0-03 | done | Domain and Schema Skeleton |
| [tasks/P0/TASK-P0-04-constraints-states-errors-capabilities.md](../tasks/P0/TASK-P0-04-constraints-states-errors-capabilities.md) | TASK-P0-04 | done | Constraints States Errors and Capabilities |
| [tasks/P0/TASK-P0-05-simulation-contracts-and-skeleton.md](../tasks/P0/TASK-P0-05-simulation-contracts-and-skeleton.md) | TASK-P0-05 | done | Simulation Contracts and Skeleton |
| [tasks/P0/TASK-P0-06-minimal-scenario-and-golden-schedule.md](../tasks/P0/TASK-P0-06-minimal-scenario-and-golden-schedule.md) | TASK-P0-06 | done | SIM-MINIMAL-001 and Golden Schedule |
| [tasks/P0/TASK-P0-07-invalid-fixtures-and-validator-rules.md](../tasks/P0/TASK-P0-07-invalid-fixtures-and-validator-rules.md) | TASK-P0-07 | done | Invalid Fixtures and Validator Rules |
| [tasks/P0/TASK-P0-08-engineering-and-ci-skeleton.md](../tasks/P0/TASK-P0-08-engineering-and-ci-skeleton.md) | TASK-P0-08 | done | Engineering and CI Skeleton |
| [tasks/P0/TASK-P0-09-p0-exit-gate-audit.md](../tasks/P0/TASK-P0-09-p0-exit-gate-audit.md) | TASK-P0-09 | done | P0 Exit Gate Audit |
| [tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md](../tasks/P0/TASK-P0-10-ci-provider-evidence-remediation.md) | TASK-P0-10 | done | CI Workflow Handoff and Provider Evidence Remediation |
| [tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md](../tasks/P1/TASK-P1-01-phase-governance-and-ci-handoff.md) | TASK-P1-01 | done | P1 Phase Governance and CI Handoff |
| [tasks/P1/TASK-P1-02-canonical-import-contracts.md](../tasks/P1/TASK-P1-02-canonical-import-contracts.md) | TASK-P1-02 | done | Canonical Import Contracts |
| [tasks/P1/TASK-P1-03-raw-staging-and-import-provenance.md](../tasks/P1/TASK-P1-03-raw-staging-and-import-provenance.md) | TASK-P1-03 | done | Raw Staging and Import Provenance |
| [tasks/P1/TASK-P1-04-csv-excel-reference-adapter.md](../tasks/P1/TASK-P1-04-csv-excel-reference-adapter.md) | TASK-P1-04 | done | CSV Excel and Formal Reference Adapter |
| [tasks/P1/TASK-P1-05-normalization-and-unit-time-rules.md](../tasks/P1/TASK-P1-05-normalization-and-unit-time-rules.md) | TASK-P1-05 | done | Normalization and Unit Time Rules |
| [tasks/P1/TASK-P1-06-data-quality-and-routing-validation.md](../tasks/P1/TASK-P1-06-data-quality-and-routing-validation.md) | TASK-P1-06 | done | Data Quality and Routing Validation |
| [tasks/P1/TASK-P1-07-deterministic-order-expansion.md](../tasks/P1/TASK-P1-07-deterministic-order-expansion.md) | TASK-P1-07 | done | Deterministic Order Expansion |
| [tasks/P1/TASK-P1-08-immutable-snapshot-and-hash.md](../tasks/P1/TASK-P1-08-immutable-snapshot-and-hash.md) | TASK-P1-08 | done | Immutable PlanningSnapshot and Hash |
| [tasks/P1/TASK-P1-09-planning-problem-builder-and-hash.md](../tasks/P1/TASK-P1-09-planning-problem-builder-and-hash.md) | TASK-P1-09 | done | PlanningProblem Builder and Hash |
| [tasks/P1/TASK-P1-10-synthetic-generator-records.md](../tasks/P1/TASK-P1-10-synthetic-generator-records.md) | TASK-P1-10 | done | Synthetic Generator Canonical Records |
| [tasks/P1/TASK-P1-11-common-ingress-pipeline-and-gate-evidence.md](../tasks/P1/TASK-P1-11-common-ingress-pipeline-and-gate-evidence.md) | TASK-P1-11 | done | Common Ingress Pipeline and P1 Gate Evidence |
| [tasks/P1/TASK-P1-12-p1-exit-gate-audit.md](../tasks/P1/TASK-P1-12-p1-exit-gate-audit.md) | TASK-P1-12 | done | P1 Exit Gate Audit |
| [tasks/P2/TASK-P2-00-phase-transition-and-task-planning-governance.md](../tasks/P2/TASK-P2-00-phase-transition-and-task-planning-governance.md) | TASK-P2-00 | done | P2 Phase Transition and Task Planning Governance |
| [tasks/P2/TASK-P2-01-planning-problem-v2-contract-gap-closure.md](../tasks/P2/TASK-P2-01-planning-problem-v2-contract-gap-closure.md) | TASK-P2-01 | done | PlanningProblem v2 Contract Gap Closure |
| [tasks/P2/TASK-P2-02-planning-machine-contracts-and-status.md](../tasks/P2/TASK-P2-02-planning-machine-contracts-and-status.md) | TASK-P2-02 | done | Planning Machine Contracts and Status |
| [tasks/P2/TASK-P2-03-ortools-backend-foundation.md](../tasks/P2/TASK-P2-03-ortools-backend-foundation.md) | TASK-P2-03 | done | OR-Tools and SolverBackend Foundation |
| [tasks/P2/TASK-P2-04-formal-independent-schedule-validator.md](../tasks/P2/TASK-P2-04-formal-independent-schedule-validator.md) | TASK-P2-04 | done | Formal Independent ScheduleValidator |
| [tasks/P2/TASK-P2-05-cp-sat-core-assignment-resource-model.md](../tasks/P2/TASK-P2-05-cp-sat-core-assignment-resource-model.md) | TASK-P2-05 | done | CP-SAT Core Assignment and Resource Model |
| [tasks/P2/TASK-P2-06-cp-sat-temporal-calendar-material-model.md](../tasks/P2/TASK-P2-06-cp-sat-temporal-calendar-material-model.md) | TASK-P2-06 | done | CP-SAT Temporal Calendar and Material Model |
| [tasks/P2/TASK-P2-07-execution-facts-and-hard-lock-model.md](../tasks/P2/TASK-P2-07-execution-facts-and-hard-lock-model.md) | TASK-P2-07 | done | Execution Facts and Hard Lock Model |
| [tasks/P2/TASK-P2-08-delivery-objective-and-global-strategy.md](../tasks/P2/TASK-P2-08-delivery-objective-and-global-strategy.md) | TASK-P2-08 | done | Delivery Objective and Global Strategy |
| [tasks/P2/TASK-P2-09-golden-scenario-property-integration.md](../tasks/P2/TASK-P2-09-golden-scenario-property-integration.md) | TASK-P2-09 | done | Golden Scenario and Property Integration |
| [tasks/P2/TASK-P2-10-reference-schedulers.md](../tasks/P2/TASK-P2-10-reference-schedulers.md) | TASK-P2-10 | done | Reference Schedulers |
| [tasks/P2/TASK-P2-11-kpi-solver-report-and-export-closure.md](../tasks/P2/TASK-P2-11-kpi-solver-report-and-export-closure.md) | TASK-P2-11 | in_progress | KPI SolverReport and Export Closure |
| [tasks/P2/TASK-P2-12-benchmark-runner-xs-s-m.md](../tasks/P2/TASK-P2-12-benchmark-runner-xs-s-m.md) | TASK-P2-12 | planned | BenchmarkRunner and XS S M Profiles |
| [tasks/P2/TASK-P2-13-p2-vertical-slice-gate-evidence.md](../tasks/P2/TASK-P2-13-p2-vertical-slice-gate-evidence.md) | TASK-P2-13 | planned | P2 Vertical Slice Gate Evidence |
| [tasks/P2/TASK-P2-14-p2-exit-gate-audit.md](../tasks/P2/TASK-P2-14-p2-exit-gate-audit.md) | TASK-P2-14 | planned | P2 Exit Gate Audit |
| [tasks/README.md](../tasks/README.md) | DOC-TASK-INDEX | living | Task Card 索引 |
| [tasks/TASK_TEMPLATE.md](../tasks/TASK_TEMPLATE.md) | TEMPLATE-TASK | baseline | Task Card Template |

更新文档时应同步维护本清单。`uv run python scripts/check_docs.py`会校验本表是否完整覆盖当前142份`docs/**/*.md`，并核对Doc ID、status和title，但不会自动改写清单。根`README.md`、根`AGENTS.md`、非Markdown evidence manifest、代码和脚本不属于正式文档清单。

本清单格式为 `registry_version: 1.0.0`；列结构或状态比较语义变化时提升版本。

文档存在不代表对应代码、Schema、Test 或 Artifact 已经实现。

TASK-P1-02/03/04/05/06均未新增Markdown路径，因此清单行数仍为124。TASK-P1-06只更新已登记文档并新增限定的Schema/Rule/sample/Python/test文件；文档清单不把代码、样例JSON、未变化的lock或ignored临时报告伪装成Markdown条目。

TASK-P1-07同样未新增Markdown路径，清单继续完整覆盖124份`docs/**/*.md`；本Task只更新已登记文档并新增限定Python/unit/property文件、dev lock与既有CI交接。`build/traceability/TASK-P1-07-report.json`与下载的provider artifact保持ignored，不进入文档清单；implementation commit `5a3dbc14c12a107abf4052cca935e3ef59009d3d`的run `32265257468`成功后Task已为`done`。

TASK-P1-08未新增Markdown路径，清单继续覆盖124份`docs/**/*.md`；新增内容仅为限定Snapshot Python、migration和test文件，`build/traceability/TASK-P1-08-report.json`及下载的provider artifact保持ignored且不进入清单。Implementation commit `72670d18a29c9a10cb70f7a263c981a2b660e0ee`的run `32310098594`成功后Task已为`done`。TASK-P1-09同样未新增Markdown路径，只新增限定Problem builder/hash与三份test Python；ignored Task report/provider artifact不进入清单，implementation commit `e8c59547857d2eeace1c9f8b453a5a294cca5ef7`的run `32315513504`成功后Task已为`done`。清单仍完整覆盖124份`docs/**/*.md`。

TASK-P1-10未新增`docs/**/*.md`路径，清单继续完整覆盖124份正式文档；fixture下的`calculation-note.md`、JSON资产、generator/test Python及ignored machine reports均不进入本清单。Implementation commit `5ac08183dd03049ad02c77e6cba80c4621847e0f`的run `32319530217`成功，provider Task report为52 paths/7 rows/0 issues，Task现为`done`。

TASK-P1-11不新增Markdown路径，清单仍完整覆盖124份`docs/**/*.md`。新增application/generator/test Python、workflow及ignored `build/validation`/`build/traceability` JSON都不进入文档清单；implementation commit `fa6c4c1159972a30ea683ad4e6eba98342d3c344`的run `32322511227`成功，provider Task report为43 paths/7 rows/0 issues，Task现为`done`。

TASK-P1-12新增唯一正式Markdown `docs/milestones/P1-exit-gate-audit-report.md`，因此清单从历史124份增至125份；同目录JSON evidence manifest、ignored `build/validation`/`build/traceability` reports与下载到系统临时目录的provider artifacts不进入清单。Audit report现为`baseline`；implementation commit `a5d7e4a68dc12d48e36cb692500f59446f8097b4`的run `32326616525` / artifact `9391591718`成功后Task为`done`。P1 Gate=`READY`不创建P2文档。

TASK-P2-00在用户明确授权后一次新增15张P2 Task Card，因此清单由125份增至140份。P2-00为唯一phase-planning owner，implementation `3298229fae89a54e0641f5907ad90c4fa81569bf` / run `32332003608` / artifact `9393345593`成功后已done；P2-01～14为planned member，没有Diff base、实现或artifact。P1/P2 Milestone状态分别为completed/active；ignored Task report与provider artifact不进入清单。

TASK-P2-01新增唯一正式Markdown `ADR-0010-planning-problem-v2-contract-evolution.md`，清单由140增至141份；Schema/sample/code/tests和ignored machine/trace reports不作为Markdown行。Implementation `c64284685f37ef0d03eacade5699076146653333`的run `32336812748` / artifact `9394931377`成功且Task report为60 paths/10 rows/0 issues，P2-01现为`done`；P2-02～14继续planned。

TASK-P2-02在用户明确授权后以clean、provider-verified `3cf4966481e4e8cb6e075a3305472e0f0a93b99c`为Diff base启动。激活没有新增Markdown路径，清单继续覆盖141份`docs/**/*.md`；机器Schema/sample/report和ignored build evidence不进入本清单。

P2-02实现仍不新增或删除Markdown路径，清单保持141份。四份JSON Schema、四份JSON sample、Python contracts/tests、workflow及ignored `build/validation`/`build/traceability`报告均不作为Markdown inventory行；glossary只同步current schema set并保持原Doc ID/path。Implementation `2661598ecb592942e50c9a13dd41ff5b2535ca0d`的run `32342489997` / artifact `9396828326`成功，Task report为63 paths/11 rows/0 issues，故P2-02现为`done`；P2-03～14保持`planned`且未获启动授权。

TASK-P2-03启动新增唯一Markdown `ADR-0011-ortools-9-15-cp-sat-backend-version-policy.md`，inventory从141增至142份。Backend代码、tests、dependency lock、workflow和ignored machine/trace/audit reports不作为Markdown行。Implementation `9268b88ca7ce90a8f72023241f87e2d3676fd58a`的run `32346208046` / artifact `9398128763`成功且Task report为50 paths/9 rows/0 issues，故Task=`done`；其关闭时P2-04～14尚未启动。

TASK-P2-04启动与实现均未新增或删除Markdown路径，inventory继续完整覆盖142份`docs/**/*.md`。Formal validator/CLI/tests/workflow与ignored `build/validation`/`build/traceability` JSON不作为inventory行；现有说明与治理文档只同步formed/PLANNED边界。Implementation `9b532e2c054b02e1692f345a252922ec7fd469e4`的run `32350068318` / artifact `9399519368`成功且Task report为38 paths/6 rows/0 issues，故Task=`done`；P2-05～14继续`planned`且未获授权。

TASK-P2-05启动不新增或删除Markdown路径，inventory继续完整覆盖142份`docs/**/*.md`；只将已获用户明确授权的该Task同步为`in_progress`。预计新增的core model/mapper/machine CLI/tests与workflow修改均不是正式Markdown inventory条目，`build/validation`/`build/traceability`报告继续ignored；P2-06～14仍为`planned`。

TASK-P2-05实现继续不新增、删除或重命名Markdown路径，inventory应保持142份`docs/**/*.md`完整覆盖。Core builder/mapper/check/tests与ignored JSON不是inventory行；现有文档同步five-C-ID formed、future constraints/objective/Benchmark/Production deferred边界。最终Task/provider报告通过后只更新状态与证据，不改变inventory format version或自动激活P2-06。

本地full治理已确认142份docs与142条inventory entries完整一致，TASK-P2-05 Task diff为49 paths/6 rows/0 issues；provider replay尚待implementation SHA。Registry与inventory format version保持不变。

Implementation artifact `9400957897`已复现142 docs inventory与49-path/6-row/0-issue Task report，TASK-P2-05=`done`。没有新增、删除或重命名Markdown；P2-06～14保持`planned`，inventory与registry版本不变。

TASK-P2-06启动不新增、删除或重命名Markdown路径，inventory继续完整覆盖142份`docs/**/*.md`；只将已获2026-08-21明确授权的该Task同步为`in_progress`。预计新增的temporal builder/machine CLI/tests与workflow修改均不是正式Markdown inventory条目，`build/validation`/`build/traceability`报告继续ignored；P2-07～14仍为`planned`。

TASK-P2-06实现继续不新增、删除或重命名Markdown路径，inventory应保持142份`docs/**/*.md`完整覆盖。Temporal builder/check/tests与ignored JSON不是inventory条目；现有文档同步C-002/005/006/009 formed及C-007/008/objective/Benchmark/Production deferred边界。最终Task/provider报告通过后只更新状态与证据，不改变inventory/registry format version或自动激活P2-07。

本地full治理已确认142份docs与142条inventory entries完整一致，TASK-P2-06 Task diff为53 paths/6 rows/19 checks/0 issues；inventory和registry format version保持不变。

Implementation artifact `9429579311`已复现142 docs inventory与53-path/6-row/19-check/0-issue Task report，TASK-P2-06=`done`。没有新增、删除或重命名Markdown；P2-07～14保持`planned`，inventory与registry版本不变。

TASK-P2-07启动不新增、删除或重命名Markdown路径，inventory继续完整覆盖142份`docs/**/*.md`；只将已获2026-08-21明确授权的该Task同步为`in_progress`。预计新增的fact/lock builder、machine CLI、tests与workflow修改均不是正式Markdown inventory条目，`build/validation`/`build/traceability`报告继续ignored；P2-08～14仍为`planned`。

TASK-P2-07本地实现继续不新增、删除或重命名Markdown路径；full治理确认142份docs与142条inventory entries一致，完整Task range为54 paths/6 rows/19 checks/0 issues。新增Python/tests与ignored JSON不属于inventory；exact provider关闭前TASK-P2-07仍为`in_progress`且P2-08不启动。

Implementation artifact `9430579117`已复现142 docs inventory与54-path/6-row/19-check/0-issue Task report，TASK-P2-07=`done`。没有新增、删除或重命名Markdown；P2-08～14保持`planned`，inventory与registry版本不变。

TASK-P2-08启动不新增、删除或重命名Markdown路径，inventory继续完整覆盖142份`docs/**/*.md`；只将已获2026-08-21明确授权的该Task同步为`in_progress`。预计新增的Strategy/objective/machine CLI/tests与workflow修改均不是正式Markdown inventory条目，`build/validation`/`build/traceability`报告继续ignored；P2-09～14保持`planned`。

TASK-P2-08本地实现继续不新增、删除或重命名Markdown路径；full治理确认inventory完整覆盖142份`docs/**/*.md`，Task range为52 paths/8 rows/19 checks/0 issues。新增Policy/Strategy/objective/check/tests与ignored JSON不属于inventory；现有文档只同步OBJ-001/Global Strategy local formed、exact provider pending及P2-09～14未授权边界。Provider关闭不会改变inventory/registry format version。

Implementation artifact `9431673977`已复现142-doc inventory与52 committed/0 working paths、8 rows、19 checks、0 issues，TASK-P2-08=`done`。没有新增、删除或重命名Markdown；P2-09～14保持`planned`，inventory与registry版本不变。

TASK-P2-09启动不新增、删除或重命名`docs/**/*.md`路径，inventory继续完整覆盖142份文档；只将已获2026-08-21明确授权的该Task同步为`in_progress`。新fixture calculation notes位于`fixtures/**`并由asset manifest/hash治理，不属于本inventory；新增Python/tests与ignored machine JSON同样不是正式Markdown inventory条目。P2-10～14保持`planned`。

TASK-P2-09本地实现仍未新增、删除或重命名`docs/**/*.md`；inventory继续覆盖142份文档。两份Golden和matrix calculation notes位于`fixtures/**`，由asset/manifest hash与SIM-ASSUMPTION-011治理；Python/tests/workflow和ignored JSON不进入inventory。Registry format version及30个trace roots、36个Test IDs、15个OPEN、11个risks、37张Task卡不变；SIM assumptions由10增至11且全部`ACTIVE`。

Implementation artifact `9432982306`已复现142-doc inventory与58 committed/0 working paths、7 rows、19 checks、0 issues，TASK-P2-09=`done`。没有新增、删除或重命名正式Markdown；P2-10～14保持`planned`，inventory与registry版本不变。

TASK-P2-10启动不新增、删除或重命名`docs/**/*.md`路径，inventory继续完整覆盖142份文档；只将已获2026-08-21明确授权的该Task同步为`in_progress`。新增baseline Python/tests/workflow和ignored `reference-scheduler-report.v1`/Task JSON不是正式Markdown inventory条目；P2-11～14保持`planned`，registry format version不变。

TASK-P2-10本地实现仍未新增、删除或重命名`docs/**/*.md`，inventory继续覆盖142份文档。新增baseline Python/tests/workflow及ignored JSON不进入inventory；roots=30、Test IDs=36、OPEN=15、risks=11、Tasks=37保持不变，SIM assumptions由11增至12且全部`ACTIVE`。治理报告为38 paths/6 rows/19 checks/0 issues，registry format version不变。

Implementation artifact `9435264655`已复现142-doc inventory与38 committed/0 working paths、6 rows、19 checks、0 issues，TASK-P2-10=`done`。没有新增、删除或重命名正式Markdown；P2-11～14保持`planned`，inventory与registry版本不变。

TASK-P2-11启动不新增、删除或重命名`docs/**/*.md`路径，inventory继续完整覆盖142份文档；只将已获2026-08-21明确授权的该Task同步为`in_progress`。新增Schema/sample、reporting/exporter Python/tests/workflow和ignored machine/Task JSON不是正式Markdown inventory条目；P2-12～14保持`planned`，registry format version不变。

TASK-P2-11本地实现仍未新增、删除或重命名`docs/**/*.md`，inventory保持142份；两份Schema/sample、reporting/exporter/tests/workflow与ignored output/Task JSON均不进入Markdown清单。Roots=30、Test IDs=36、OPEN=15、SIM assumptions=12、risks=11、Tasks=37不变，registry format version保持`1.0.0`；exact provider形成前Task继续`in_progress`。
