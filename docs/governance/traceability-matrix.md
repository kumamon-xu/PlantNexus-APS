---
doc_id: DOC-GOV-005
title: 追踪矩阵
status: living
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [5, 6, 71, 86]
last_reviewed: 2026-08-19
registry_version: 1.0.0
---

# 追踪矩阵

本表每个已登记 REQ/NFR/ENG 根 ID 恰好一行。`REGISTERED` 只表示规范路径和治理追踪存在；`PLANNED`、`DEFERRED` 不得被解释成实现证据。

| Root | Kind | Normative landing | Planned milestone / first task | Evidence state |
|---|---|---|---|---|
| REQ-001 | REQ | `docs/contracts/import-and-normalization.md` | P0-P1 / TASK-P0-03 schema；P1 Task 未创建 | [`import-package.v1`](../../schemas/json/import-package.schema.json) + [`TEST-CONTRACT-001`](../../backend/tests/contract/test_schema_contracts.py) formed；import pipeline PLANNED |
| REQ-002 | REQ | `docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md` | P0-P1 / TASK-P0-03 schema；P1 Task 未创建 | [`planning-snapshot.v1`](../../schemas/json/planning-snapshot.schema.json) + pure type + contract test formed；normalization/builder/hash PLANNED |
| REQ-003 | REQ | `docs/contracts/import-and-normalization.md`、`docs/domain/operation-instance-and-resource-options.md` | P0-P1 / TASK-P0-03 schema；P1 Task 未创建 | [`planning-problem.v1` Operation skeleton](../../schemas/json/planning-problem.schema.json) + reference/duration precheck formed；order/lot/routing expansion PLANNED |
| REQ-004 | REQ | `docs/architecture/end-to-end-planning-flow.md`、`docs/planning/constraint-catalog.md` | P2 / TASK-P0-04（contract）、TASK-P0-06（positive fixture） | [`constraint-rule-sheet.v1`](../../schemas/rules/constraint-rule-sheet.v1.yaml) + [`SIM-MINIMAL-001` direct Golden calculations](../../backend/tests/golden/test_sim_minimal_001.py) formed；solver implementation PLANNED |
| REQ-005 | REQ | `docs/planning/schedule-validator.md` | P0-P2 / TASK-P0-04 contract、TASK-P0-06 positive、TASK-P0-07 mutation | [`validation-report.v2`](../../schemas/json/validation-report.v2.schema.json) + rule sheet + positive Golden + [fixture-local independent evaluator/13 mutation suite](../../backend/tests/validation/test_schedule_validator_mutations.py) formed；P2 production/performance integration PLANNED |
| REQ-006 | REQ | `docs/contracts/export-package.md` | P2-P3 / P1+ Task 未创建 | REGISTERED；implementation PLANNED |
| REQ-007 | REQ | `docs/domain/state-machines/schedule-version.md` | P0/P3 / TASK-P0-04 contract；P1+ Task 未创建 | [`state-machines.v1`](../../schemas/rules/state-machines.v1.yaml) + [`TEST-STATE-TRANSITION-001`](../../backend/tests/contract/test_rule_contracts.py) formed；approval/publish persistence PLANNED |
| REQ-008 | REQ | `docs/planning/replanning.md` | P0/P4 / TASK-P0-04 capability boundary；P1+ Task 未创建 | DYNAMIC_REPLANNING contract declaration formed；ExecutionEvent/Replan implementation PLANNED |
| REQ-009 | REQ | `docs/architecture/provenance-and-versioning.md` | P0-P4 / TASK-P0-01、TASK-P0-02、TASK-P0-03 | Repository provenance [PASS](../tasks/P0/TASK-P0-01-documentation-and-repository-governance.md#completion-evidence)；schema IDs/version/data dictionary formed；real hash/manifest/audit PLANNED |
| REQ-010 | REQ | `docs/core/capability-matrix.md` | P6 / P1+ Task 未创建 | REGISTERED；capability DEFERRED |
| REQ-011 | REQ | `docs/simulation/synthetic-generator-and-determinism.md` | P0-P1 / TASK-P0-05、TASK-P0-06 | [`factory-profile.v1`](../../schemas/scenario/factory-profile.schema.json) + seven-layer [`Generator Protocol`](../../backend/app/simulation/generators/contracts.py) + empty and committed non-empty Import [`TEST-SCENARIO-REPLAY`](../../backend/tests/golden/test_sim_minimal_001.py) formed；P1 distribution generator/canonical pipeline PLANNED |
| REQ-012 | REQ | `docs/simulation/scenario-spec-and-provenance.md` | P0-P2 / TASK-P0-05、TASK-P0-06 | [`scenario-spec.v1`](../../schemas/scenario/scenario-spec.schema.json) + [`scenario-manifest.v1`](../../schemas/scenario/scenario-manifest.schema.json) + formal [`SIM-MINIMAL-001@1.0.0`](../../fixtures/deterministic/SIM-MINIMAL-001/scenario-spec.json) / replay / Golden formed；broader Scenario Library PLANNED |
| REQ-013 | REQ | `docs/simulation/execution-simulator-and-disruptions.md` | P4 / TASK-P0-05 provenance boundary；P1+ Task 未创建 | ScenarioManifest version/seed boundary formed；Execution Simulator/event/fact preservation PLANNED |
| REQ-014 | REQ | `docs/simulation/benchmark-harness.md` | P2 / TASK-P0-05 provenance boundary；P1+ Task 未创建 | ScenarioManifest/dataset hash/complexity contract formed；BenchmarkRunner/report/baseline PLANNED |
| REQ-015 | REQ | `docs/planning/reference-schedulers.md` | P2 / TASK-P0-05 provenance boundary；P1+ Task 未创建 | Scenario identity/hash comparison boundary formed；Reference Scheduler implementation PLANNED |
| NFR-COR-001 | NFR | `docs/planning/constraint-catalog.md`、`docs/planning/schedule-validator.md` | P0-P2 / TASK-P0-04、TASK-P0-06、TASK-P0-07 | C-001～C-011 formula/v2 contract + Golden PASS + [`SIM-MINIMAL-001-MUTATIONS@1.0.0`](../../fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/expected-outcomes.json) 13 FAIL/15 hard violations formed；formal Problem/Solver/scale evidence PLANNED |
| NFR-DET-001 | NFR | `docs/contracts/planning-snapshot.md`、`docs/contracts/planning-problem.md`、`docs/simulation/synthetic-generator-and-determinism.md` | P0-P1 / TASK-P0-03、TASK-P0-05、TASK-P0-06 | Strict UTC/duration + empty and non-empty Import canonical hash/named seed [`TEST-SCENARIO-REPLAY`](../../backend/tests/golden/test_sim_minimal_001.py) formed；Snapshot/Problem replay PLANNED |
| NFR-TRC-001 | NFR | `docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-rules.md` | P0-P4 / TASK-P0-01、TASK-P0-02、TASK-P0-03、TASK-P0-05、TASK-P0-06 | Repository/schema trace + Scenario/Profile/Generator/seed/assumption/package/hash [`manifest`](../../fixtures/deterministic/SIM-MINIMAL-001/scenario-manifest.json) formed；production sources/code commit/run/export audit PLANNED |
| NFR-ISO-001 | NFR | `docs/architecture/configuration-environments-and-isolation.md` | P0-P1 / TASK-P0-05、TASK-P0-08 | Schema/pure context/Import [`TEST-SIM-ISOLATION`](../../backend/tests/simulation/test_simulation_contracts.py) formed；DB/API/publish/deployment isolation PLANNED |
| NFR-REL-001 | NFR | `docs/domain/state-machines/export-job.md` | P0-P3 / TASK-P0-04 contract、TASK-P0-08 worker | ExportJob allowed/retry/terminal transition contract formed；worker/idempotency tests PLANNED |
| NFR-SEC-001 | NFR | `docs/architecture/configuration-environments-and-isolation.md` | P0-P3 / TASK-P0-08 | REGISTERED；security tests/review PLANNED |
| NFR-OBS-001 | NFR | `docs/domain/kpi-contract.md`、`docs/architecture/provenance-and-versioning.md` | P0-P2 / TASK-P0-08 | REGISTERED；observability tests PLANNED |
| NFR-PER-001 | NFR | `docs/simulation/performance-gates.md`、`docs/quality/benchmark-regression.md` | P0-P7 / TASK-P0-08 | REGISTERED；production threshold remains OPEN-012 |
| NFR-HUM-001 | NFR | `docs/domain/state-machines/schedule-version.md` | P0/P3 / TASK-P0-04 contract；P1+ Task 未创建 | only-APPROVED publish transition contract formed；authorization/approval tests PLANNED |
| ENG-ARCH-001 | ENG | `docs/architecture/repository-layout.md`、`docs/architecture/module-boundaries.md`、`docs/adr/ADR-0002-modular-monolith-and-solver-worker.md` | P0 / TASK-P0-01 | Repository build/import smoke [PASS](../tasks/P0/TASK-P0-01-documentation-and-repository-governance.md#completion-evidence)；API/Worker behavior PLANNED |
| ENG-SOL-001 | ENG | `docs/contracts/planning-problem.md`、`docs/planning/solver-backend-contract.md`、`docs/adr/ADR-0003-solver-neutral-planning-problem.md` | P0-P2 / TASK-P0-03 | Solver-neutral [`Schema`](../../schemas/json/planning-problem.schema.json) / [`pure type`](../../backend/app/planning/problem/contracts.py) formed；builder/backend/Solver PLANNED |
| ENG-VAL-001 | ENG | `docs/planning/schedule-validator.md`、`docs/adr/ADR-0005-independent-schedule-validator.md` | P0-P2 / TASK-P0-04 contract、TASK-P0-06 positive、TASK-P0-07 mutation | Rule metadata + [`schedule_validator.py`](../../backend/app/planning/validation/schedule_validator.py) independent evaluator + formula-free mutation/dependency tests formed；P2 production/performance Validator PLANNED |
| ENG-ERR-001 | ENG | `docs/domain/error-model.md`、`docs/planning/infeasibility-diagnostics.md` | P0-P2 / TASK-P0-04、TASK-P0-07 | [`error.v2`](../../schemas/json/error.v2.schema.json) + 19-code registry + TEST-ERROR-MAPPING-001 + exact mutation `VALIDATION_FAILED/SCHEDULE_VALIDATION_FAILED` details formed；HTTP mapping PLANNED |
| ENG-VER-001 | ENG | `docs/architecture/provenance-and-versioning.md`、`docs/contracts/schema-versioning.md`、`docs/architecture/technology-stack.md` | P0-P7 / TASK-P0-01～TASK-P0-06 | code/spec lock PASS；schema set `1.2.0` in [`pyproject`](../../pyproject.toml)、[`package metadata`](../../backend/app/__init__.py)、[`data dictionary`](../../schemas/data_dictionary.yaml)，historical artifacts preserved + Simulation/fixture asset versions/replay formed |
| ENG-LOG-001 | ENG | `docs/architecture/technology-stack.md`、`docs/architecture/provenance-and-versioning.md` | P0 / TASK-P0-08 | REGISTERED；logging implementation PLANNED |

TASK-P0-02 的 validator 已证明本表 Roots 与两个根注册表完全相等，并已将 `TEST-TRACEABILITY-VALIDATOR`、脚本、unit test 和报告摘要链接回 NFR-TRC-001 / ENG-VER-001；[Completion evidence](../tasks/P0/TASK-P0-02-requirements-and-traceability.md#completion-evidence) 记录真实命令结果。每个后续 Task 完成时只增加真实路径和真实结果；计划项继续保留 `PLANNED`。

TASK-P0-03 已形成上述 Schema/type/test 路径并通过 [Completion evidence](../tasks/P0/TASK-P0-03-domain-and-schema-skeleton.md#completion-evidence) 中的真实 Acceptance Commands。该 PASS 只覆盖 P0 contract skeleton；REQ-001/002/003 的 P1 pipeline、NFR-DET 的 hash/replay、ENG-SOL 的 builder/backend 均继续保持 `PLANNED`。

TASK-P0-04 已形成 rule/state/error/capability machine artifacts、pure contracts 和四项 contract test 路径，并通过 [Completion evidence](../tasks/P0/TASK-P0-04-constraints-states-errors-capabilities.md#completion-evidence) 中的真实 Acceptance Commands。该 PASS 只覆盖 P0 contracts/completeness；TEST-VALIDATOR-MUTATION、Solver correctness、状态持久化、审批/发布或 Replan implementation 继续保持 `PLANNED`。

TASK-P0-05 已形成三份 Simulation v1 Schema/sample、Profile/Scenario pure precheck、七层 Protocol、empty Standard Import replay/hash/isolation tests 与 machine report。该证据只覆盖 P0 contract slice；`SIM-MINIMAL-001`、non-empty canonical records、Import/Snapshot/Problem pipeline、DB/API isolation、Execution/Benchmark/Reference Scheduler/Solver 继续保持 `PLANNED`，最终命令结果以本 Task Completion evidence 为准。

TASK-P0-06 已形成 `SIM-MINIMAL-001@1.0.0` Profile/Scenario、fixture-local non-empty Import、manifest/hash、人工 Golden、expected validation/KPI、计算说明、只读 replay loader 和直接计算 tests。该证据只覆盖 committed correctness fixture 与 positive C-ID/KPI calculation；P1 canonical record mapping/Normalization、正式 PlanningProblem/candidate/ValidationReport/KPI、通用 Validator/negative mutation、Solver/Benchmark 继续保持 `PLANNED`，最终命令结果以本 Task Completion evidence 为准。

TASK-P0-07 已形成 fixture-local independent evaluator、13-case mutation suite、exact v2 expected outcomes、11-C-ID/13-class coverage、18 validation tests 和 `validator-mutation-report.v1` machine evidence。positive Golden/hash 保持不变，mutation materializer 与 evaluator/expected artifact 分离，validation package 继续无 backend/OR-Tools import。该证据不实现 P1 canonical/PlanningProblem/candidate 或 P2 Solver comparison/Property/Benchmark/API/state integration；最终命令结果以本 Task Completion evidence 为准。
