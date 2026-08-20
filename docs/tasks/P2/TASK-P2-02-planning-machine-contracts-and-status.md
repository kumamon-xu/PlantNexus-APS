---
doc_id: TASK-P2-02
title: Planning Machine Contracts and Status
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [13, 14, 28, 29, 35, 57, 75, 96]
last_reviewed: 2026-08-20
---

# TASK-P2-02 — Planning Machine Contracts and Status

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-01

Start gate: TASK-P2-01=`done`且Problem v2版本/ADR/fingerprint固定；启动前固定Diff base和合同文件名。

Goal: 建立PlanningPolicy、SolveLimits、PlanningSolution、SolverReport与统一Solver status的版本化machine contracts，供Backend、Validator、Strategy、Export共同消费。

Inputs: Problem v2、OBJ-001、SolverBackend合同、PlanningRun/error状态语义、ADR-0004/0006/0008。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `schemas/json/planning-policy.schema.json`、`schemas/json/solve-limits.schema.json`、`schemas/json/planning-solution.schema.json`、`schemas/json/solver-report.schema.json`、`schemas/data_dictionary.yaml`、`backend/app/planning/policy/__init__.py`、`backend/app/planning/policy/contracts.py`、`backend/app/planning/contracts.py`、`backend/tests/contract/test_planning_machine_contracts.py`及`Documents to update`；新增路径进入in_progress前逐字冻结。

Files forbidden to change: CP-SAT backend/OR-Tools、constraint实现、Validator判定、fixtures/benchmarks、DB/API/Worker、P3状态动作。

Implementation steps: 固定四类合同及版本；定义OPTIMAL/FEASIBLE/INFEASIBLE/UNKNOWN/MODEL_INVALID/CANCELLED/FAILED映射、objective stages、timing/model/memory/provenance字段；实现pure validation/canonicalization；Schema正反/round-trip/status测试；同步文档/追踪。

Outputs: 四份JSON Schema、solver-neutral types/prechecks、status/error mapping与fixed samples/report。

Documentation impact: required

Documents to update: `docs/contracts/README.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/objective-policy.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/domain/kpi-contract.md`、`docs/architecture/provenance-and-versioning.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 机器合同和状态是P2各实现Task的共同边界，必须在代码前固定版本、错误和provenance。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-PLANNING-CONTRACTS`、`IMPACT-POLICY`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-02→TEST-CONTRACT-001/TEST-ERROR-MAPPING-001→四类contract artifacts；仅合同formed，Solver/Validator/metric值仍PLANNED。

Schema changes: required；additive schema-set release，四个新document version，显式registry/unknown-field/no-default/round-trip与sample属性。

Migration: none；不创建PlanningRun/ScheduleVersion persistence。

Dependency changes: none；标准库+pydantic既有边界内实现pure合同。

ADR impact: no new ADR if strictly implementing ADR-0004/0006/0008 and existing status semantics；任何目标顺序、状态含义或time unit变化必须停止并新增superseding ADR。

Error behavior: limits耗尽无认证解=`UNKNOWN/NO_SOLUTION_WITHIN_LIMIT`，模型错误=`MODEL_INVALID`，系统异常=`FAILED`；不得把UNKNOWN写成INFEASIBLE或FEASIBLE写成OPTIMAL。

Tests: TEST-CONTRACT-001、TEST-ERROR-MAPPING-001；覆盖每种status、非法组合、objective stage/bound/gap、UTC/ticks、timing非负、version/provenance、canonical replay。

Benchmark impact: 只固定未来BenchmarkReport可引用字段，不生成benchmark数值或阈值。

Simulation scenarios: fixed synthetic samples only；无Solver执行。

Acceptance commands: `uv run pytest -q backend/tests/contract/test_planning_machine_contracts.py backend/tests/contract/test_schema_contracts.py backend/tests/contract/test_rule_contracts.py`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-02-planning-machine-contracts-and-status.md --check-diff --report build/traceability/TASK-P2-02-report.json`；`git diff --check`。

Artifacts: schema/sample fingerprints、status mapping report、Task traceability report。

Provider evidence: exact implementation SHA required `validate`/steps/artifact success；artifact须包含Task report和contract evidence，记录immutable provider metadata/digest/expiry。

Completion conditions: 合同完整且互相引用可离线解析；全部status语义可二值验证；Schema/version/docs/trace/provider闭环；无Solver/constraint/DB行为。

Explicitly excluded: OR-Tools、实际求解、C-ID实现、READY_FOR_REVIEW状态迁移、API/persistence、P3审批发布。

PROD_OPEN: OPEN-006/011/012不关闭；Production权重和limit/default不写入Schema默认值。

SIM_ASSUMPTIONS: Simulation policy必须显式version，不成为Production default。

Rollback: 新合同尚无consumer时删除additive release并恢复set metadata；已有consumer后只能发布兼容新版本，不重写历史合同。
