---
doc_id: TASK-P1-09
title: PlanningProblem Builder and Hash
status: planned
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [13, 14, 24, 26, 73, 74, 89]
last_reviewed: 2026-08-19
---

# TASK-P1-09 — PlanningProblem Builder and Hash

Requirement IDs: REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-07, TASK-P1-08

Goal: 从 immutable Snapshot v2 构建现有 `planning-problem.v1` 可表达的 solver-neutral PlanningProblem，固定 builder/hash语义以满足 P1 replay gate；不创建任何 Solver、decision variable或求解结论。

Inputs: PlanningSnapshot v2、PlanningProblem v1 Schema、ADR-0003/0008、C-001～C-011 input requirements、explicit tick/horizon config。

Diff base: 进入 `in_progress` 前记录当时完整 40 字符 HEAD SHA

Files allowed to change: `backend/app/planning/problem/__init__.py`、`backend/app/planning/problem/contracts.py`、`backend/app/planning/problem/builder.py`、`backend/app/planning/problem/hashing.py`、`backend/tests/unit/test_planning_problem_builder.py`、`backend/tests/property/test_planning_problem_properties.py`、`backend/tests/golden/test_p1_problem_replay.py`、生成但不提交的 `build/validation/TASK-P1-09-engineering.json` 与 `build/traceability/TASK-P1-09-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: `schemas/json/planning-problem.schema.json`、Snapshot/Import contracts、Constraint/Objective semantics、`planning/backends/**`、`planning/strategies/**`、ScheduleValidator、OR-Tools/dependencies、API、Exporter、Benchmark baseline。

Implementation steps: builder只读 Snapshot且显式接收 builder version/tick/horizon；COMPLETED排除、RUNNING/resource options/edges/unavailable intervals/capabilities按合同投影；duration tick使用整数 ceiling但Problem保留权威秒；stable sort/canonical serialization；problem_hash排除 self hash/运行噪声并包含 Snapshot identity、builder/rule/config；调用既有 pure precheck；若 v1不能表达必需 P1事实则停止并提 Schema/ADR修订，不在代码内藏字段。

Outputs: solver-neutral builder、problem hash vectors、property/Golden replay evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-snapshot.md`、`docs/planning/constraint-catalog.md`、`docs/planning/solver-backend-contract.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/module-boundaries.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/adr/ADR-0003-solver-neutral-planning-problem.md`、`docs/adr/README.md`、`docs/quality/property-tests.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/P1/TASK-P1-09-planning-problem-builder-and-hash.md`。

Documentation impact rationale: 首次真实 Problem builder/hash实现会固定 Snapshot→Problem映射、replay和后续 P2 consumer边界。

Change-impact matrix rows reviewed: `IMPACT-PROBLEM`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-09 → TEST-PROBLEM-REPLAY-001/TEST-CONTRACT-001 → builder/hash vectors/property/Golden artifacts；Solver/Validator仍 `PLANNED`。

Schema changes: none；消费 planning-problem.v1。任何合同字段/语义变化需要新 Problem version、ADR和 replay，不在本 Task静默修改。

Migration: none。

Error behavior: invalid Snapshot、quality/provenance mismatch、unsupported capability、missing Problem-required fact、invalid horizon/tick/reference/duration明确为 DATA_ERROR或 MODEL_INVALID；不得转为 INFEASIBLE。

Tests: `TEST-PROBLEM-REPLAY-001`、`TEST-CONTRACT-001`；same input hash、key/order/noise、version/config change、running/completed、candidate duration/ticks、edge/calendar/reference、round-trip/property与 no-OR-Tools import。

Benchmark impact: PlanningProblem行为变更按规则审查；P1仅记录 builder entity counts/build time，因无 Solver不形成 BenchmarkReport或性能阈值。

Simulation scenarios: 以 P1 canonical synthetic fixture重放；P0 hand fixture只作对照，不直接提升其 vocabulary。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/planning/problem backend/tests/unit/test_planning_problem_builder.py backend/tests/property/test_planning_problem_properties.py backend/tests/golden/test_p1_problem_replay.py`；`uv run pyright backend/app/planning/problem backend/tests/unit/test_planning_problem_builder.py backend/tests/property/test_planning_problem_properties.py backend/tests/golden/test_p1_problem_replay.py`；`uv run pytest -q backend/tests/unit/test_planning_problem_builder.py backend/tests/property/test_planning_problem_properties.py backend/tests/golden/test_p1_problem_replay.py backend/tests/contract/test_schema_contracts.py`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P1-09-engineering.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-09-planning-problem-builder-and-hash.md --check-diff --report build/traceability/TASK-P1-09-report.json`；`git diff --check`；`uv build`。

Artifacts: Problem hash vectors/Golden/property results、engineering no-Solver report、traceability report。

Completion conditions: same Snapshot/config/versions产生 byte-identical Problem/hash；变化敏感性与 round-trip通过；Problem无 ORM/API/OR-Tools类型；ADR边界未改变或已先停止升级；docs/trace/governance PASS。

Explicitly excluded: CpModel/IntervalVar、GlobalCpSatStrategy、Solver status/solution、ScheduleValidator、objective、Benchmark、P2能力。

PROD_OPEN: OPEN-004/005/006/007/009/012/014/015 保持 OPEN；Problem消费显式事实而不补猜。

SIM_ASSUMPTIONS: tick/horizon必须来自 versioned Scenario/config；不得成为 Production默认值。

Rollback: builder version/hash不可重解释历史；回退保留旧 version与 artifacts，语义修复发布新 builder/Problem version并重放。

## Completion evidence

执行时填写 builder/version/hash vectors、static scan、changed paths、测试与文档/ADR审查结果。
