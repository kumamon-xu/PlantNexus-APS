---
doc_id: TASK-P2-06
title: CP-SAT Temporal Calendar and Material Model
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [25, 26, 27, 30, 75]
last_reviewed: 2026-08-20
---

# TASK-P2-06 — CP-SAT Temporal Calendar and Material Model

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-05

Start gate: TASK-P2-05 core model=`done`且formal Validator PASS；固定tick/rounding、calendar half-open及lag seconds规则和Diff base。

Goal: 实现C-002/C-005/C-006/C-009的precedence min/max lag、calendar unavailable intervals、release/material gate与cross-workshop transport，不静默放宽秒/tick边界。

Inputs: core CP-SAT model、Problem v2 edges/calendars/gates、ADR-0008、formal Validator、Golden lag/calendar/material facts。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/planning/backends/cp_sat/temporal_constraints.py`、`backend/app/planning/backends/cp_sat/model.py`、`backend/tests/unit/test_cp_sat_temporal_model.py`、`backend/tests/property/test_cp_sat_temporal_properties.py`及`Documents to update`；其他路径先修订卡片。

Files forbidden to change: contracts/schema、Validator formulas、fact/lock/objective/Strategy、P0 immutable assets、Reference/Export/Benchmark/P3。

Implementation steps: 统一UTC seconds→ticks边界；建min/max lag上下界；transport独立叠加；固定unavailable intervals进入NoOverlap；release/material gate；覆盖inclusive/max-lag和fragmented calendar；Solver结果交独立Validator与tiny brute force。

Outputs: temporal constraint builder、C-002/005/006/009正反/property证据、timing/model delta report。

Documentation impact: required

Documents to update: `docs/planning/constraint-catalog.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/objective-policy.md`、`docs/planning/schedule-validator.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/quality/property-tests.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/architecture/technology-stack.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: lag/tick/calendar/gate实现决定可行域边界，必须与独立秒级Validator和Golden一致。

Change-impact matrix rows reviewed: `IMPACT-BACKEND`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012→TASK-P2-06→C-002/005/006/009→TEST-MAX-LAG/CALENDAR/MATERIAL/CROSS-WORKSHOP/PROPERTY→solver+validator reports。

Schema changes: none。

Migration: none。

Dependency changes: none；solver lock固定。

ADR impact: none if implementing ADR-0008 and catalog formulas exactly；任何rounding、calendar或lag语义偏差需superseding ADR并停止。

Error behavior: invalid/overflow tick或unsupported calendar在build前拒绝；max-lag不可省略；无解返回INFEASIBLE only with certified status，limit未知仍UNKNOWN。

Tests: TEST-MAX-LAG、TEST-CALENDAR、TEST-MATERIAL、TEST-CROSS-WORKSHOP、TEST-PROPERTY、TEST-VALIDATOR-MUTATION；覆盖exact boundary、碎片calendar、min+transport组合、non-integral seconds和infeasible cases。

Benchmark impact: 记录constraint/interval增量和真实build/solve telemetry；不定义Production阈值。

Simulation scenarios: SIM-MINIMAL-001 derived formal case + versioned cross/calendar/material cases；asset变化升version。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_cp_sat_temporal_model.py backend/tests/property/test_cp_sat_temporal_properties.py backend/tests/golden backend/tests/validation`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-06-cp-sat-temporal-calendar-material-model.md --check-diff --report build/traceability/TASK-P2-06-report.json`；`git diff --check`。

Artifacts: temporal-model/validator/property report、model delta和Task report。

Provider evidence: exact SHA required `validate`/all steps success，artifact包含temporal evidence与Task report并记录digest/expiry。

Completion conditions: 四个C-ID solver+Validator一致；边界/负例/property PASS；telemetry、docs、trace和provider闭环；facts/locks/objective仍未形成。

Explicitly excluded: C-007/008、OBJ-001、dynamic Replan、setup/buffer/preemption、P3。

PROD_OPEN: OPEN-004/009/010/011/012保持OPEN；transport/calendar Production来源不猜。

SIM_ASSUMPTIONS: calendar/material/transport值仅versioned synthetic。

Rollback: 独立撤销temporal builder并回到P2-05 core；保留失败case/report，禁止通过删掉max-lag或calendar让测试变绿。
