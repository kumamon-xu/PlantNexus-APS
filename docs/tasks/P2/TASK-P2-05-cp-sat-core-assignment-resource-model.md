---
doc_id: TASK-P2-05
title: CP-SAT Core Assignment and Resource Model
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [24, 25, 26, 27, 30, 75]
last_reviewed: 2026-08-20
---

# TASK-P2-05 — CP-SAT Core Assignment and Resource Model

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-TRC-001, NFR-OBS-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-03, TASK-P2-04

Start gate: Backend foundation与formal Validator均`done`；Problem/Solution versions固定；启动前记录Diff base、rule version和solver exact version。

Goal: 在CP-SAT backend实现C-001/C-003/C-004/C-010/C-011的完整assignment、alternative duration、capacity-1 NoOverlap和horizon模型，并由独立Validator接受。

Inputs: Problem v2、backend protocol、formal Validator、constraint-rule-sheet.v1、SolveLimits。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/planning/backends/cp_sat/model.py`、`backend/app/planning/backends/cp_sat/core_constraints.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/solution_mapper.py`、`backend/tests/unit/test_cp_sat_core_model.py`、`backend/tests/property/test_cp_sat_core_properties.py`及`Documents to update`；新增exact路径在进入in_progress前冻结。

Files forbidden to change: Problem/Policy/Solution schema语义、Validator formulas、temporal/calendar/material/fact/lock constraints、objective/Strategy、fixtures/benchmarks/export/P3。

Implementation steps: 建operation/master/optional intervals与exact-one presence；candidate-specific duration；capacity-1 NoOverlap；horizon/complete assignment；solution mapping/model telemetry；precheck zero candidate/overflow；用formal Validator和brute-force tiny properties交叉验证。

Outputs: core CP-SAT model、C-001/003/004/010/011 tests、model-size/timing diagnostics和candidate solutions。

Documentation impact: required

Documents to update: `docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/planning/schedule-validator.md`、`docs/quality/property-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/architecture/technology-stack.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 首个业务CP-SAT模型形成核心可行域，必须绑定C-ID、Validator和solver/version telemetry。

Change-impact matrix rows reviewed: `IMPACT-BACKEND`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-05→C-001/003/004/010/011→TEST-GOLDEN-JSSP/FJSP、TEST-INF-NO-RESOURCE/HORIZON、TEST-PROPERTY→core model/validator artifacts。

Schema changes: none；严格消费P2-01/02已发布合同。

Migration: none。

Dependency changes: none beyondTASK-P2-03 pinned OR-Tools；lock不得漂移。

ADR impact: implements ADR-0003/0004/0008及solver-version ADR；约束语义或tick conversion变化必须新ADR并回到合同Task。

Error behavior: zero candidate/invalid horizon在build前稳定拒绝；MODEL_INVALID不映射INFEASIBLE；只有有完整candidate时输出FEASIBLE/OPTIMAL，且必须Validator PASS才能接受。

Tests: TEST-GOLDEN-JSSP/FJSP、TEST-INF-NO-RESOURCE/HORIZON、TEST-PROPERTY、TEST-VALIDATOR-MUTATION；包含多候选不同duration、back-to-back half-open intervals、overflow、duplicate/missing assignment、model counts。

Benchmark impact: 记录variables/constraints/optional intervals/build/solve/first-feasible/memory诊断；只用tiny correctness cases，不建立XS/S/M阈值。

Simulation scenarios: versioned tiny JSSP/FJSP derived cases；不声称完整P2 Gate。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_cp_sat_core_model.py backend/tests/property/test_cp_sat_core_properties.py backend/tests/validation`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-05-cp-sat-core-assignment-resource-model.md --check-diff --report build/traceability/TASK-P2-05-report.json`；`git diff --check`。

Artifacts: core-model report、candidate/validator/property evidence、Task report。

Provider evidence: exact SHA required `validate`成功并上传model/validator/Task reports；记录solver exact version、run/job/steps/artifact digest。

Completion conditions: 五个C-ID全部由Solver实现且独立Validator正反验证；telemetry真实；local/provider/docs/trace PASS；其余C-ID和OBJ-001不宣称完成。

Explicitly excluded: C-002/005～009、OBJ-001、Reference Scheduler、Export、XS/S/M Benchmark、P3。

PROD_OPEN: OPEN-007/009/010/011/012保持OPEN。

SIM_ASSUMPTIONS: tiny correctness durations/calendars显式versioned，不外推Production。

Rollback: 回退core builder/mapper并保持Backend protocol；已生成candidate仅作为不可发布测试artifact，任何solver-version回退须重跑upgrade replay。
