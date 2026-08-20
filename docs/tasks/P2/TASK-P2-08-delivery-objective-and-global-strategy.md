---
doc_id: TASK-P2-08
title: Delivery Objective and Global Strategy
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [28, 29, 35, 52, 53, 75]
last_reviewed: 2026-08-20
---

# TASK-P2-08 — Delivery Objective and Global Strategy

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-02, TASK-P2-05, TASK-P2-06, TASK-P2-07

Start gate: C-001～C-011 solver slices与formal Validator均formed；Policy/Solution contracts固定；批准versioned Simulation Delivery Policy并记录Diff base。

Goal: 实现GlobalCpSatStrategy、SolveLimits和仅OBJ-001 weighted tardiness目标/可解释status lifecycle；hard feasibility始终优先，未授权OBJ-002/003不得进入接受语义。

Inputs: complete CP-SAT feasible model、PlanningPolicy/SolveLimits/Solution/SolverReport、due/priority facts、ADR-0004/0006、OPEN-006/011/012。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/planning/strategies/__init__.py`、`backend/app/planning/strategies/global_cp_sat.py`、`backend/app/planning/policy/delivery.py`、`backend/app/planning/backends/cp_sat/objectives.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/tests/unit/test_global_cp_sat_strategy.py`、`backend/tests/property/test_delivery_objective_properties.py`及`Documents to update`；其他路径先修订。

Files forbidden to change: C-ID formulas、Validator logic、OBJ-002 Stability/OBJ-003 acceptance、Production default weight、Reference/Export/Benchmark runner、DB/API/Worker/P3/P4。

Implementation steps: 建versioned synthetic delivery weights；定义tardiness ticks/weight integer objective；Strategy precheck→backend→Validator；limits/status/stop reason；objective/bound/gap/timing report；tiny brute-force optimum与limit/UNKNOWN/FEASIBLE tests。

Outputs: GlobalCpSatStrategy、OBJ-001 policy/objective builder、status/limits orchestration和solver report evidence。

Documentation impact: required

Documents to update: `docs/planning/planning-strategies.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/domain/kpi-contract.md`、`docs/domain/error-model.md`、`docs/simulation/performance-gates.md`、`docs/quality/benchmark-regression.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/architecture/technology-stack.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: Objective、Strategy、limits和status决定P2计划选择/报告边界，且必须隔离未知Production权重。

Change-impact matrix rows reviewed: `IMPACT-POLICY`、`IMPACT-STRATEGY`、`IMPACT-BACKEND`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-08→OBJ-001→TEST-GOLDEN-JSSP/FJSP、TEST-PROPERTY、TEST-SOLVER-UPGRADE→strategy/objective/status artifacts；OBJ-002/003保持PLANNED/非接受目标。

Schema changes: none expected；使用P2-02合同；若report字段不足需先版本化合同Task。

Migration: none。

Dependency changes: none；solver lock固定。

ADR impact: implements ADR-0004/0006；若混合目标、改变lexicographic顺序或Production权重必须停止并superseding ADR。

Error behavior: Validator FAIL永不进入可接受solution；limit无解=UNKNOWN，不冒充INFEASIBLE；unsupported policy/version明确拒绝；FEASIBLE不冒充OPTIMAL。

Tests: TEST-GOLDEN-JSSP/FJSP、TEST-PROPERTY、TEST-SOLVER-UPGRADE、TEST-ERROR-MAPPING-001；tiny brute-force tardiness、priority weight、zero tardiness、limits/status、validator-fail gate与report replay。

Benchmark impact: 开始记录完整objective/bound/gap/build/first-feasible/solve/memory/model size，但正式XS/S/M baseline留P2-12。

Simulation scenarios: versioned Delivery policy + tiny due/priority scenarios；不得称Production policy。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_global_cp_sat_strategy.py backend/tests/property/test_delivery_objective_properties.py backend/tests/validation`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-08-delivery-objective-and-global-strategy.md --check-diff --report build/traceability/TASK-P2-08-report.json`；`git diff --check`。

Artifacts: strategy/objective/status/limits report、tiny optimality proofs、Task report。

Provider evidence: exact SHA required `validate`成功并上传solver/validator/Task evidence；记录solver/policy versions、run/job/steps/artifact digest。

Completion conditions: complete hard model先通过Validator；OBJ-001数值与brute-force一致；status/limit/report真实；local/provider/docs/trace PASS；无OBJ-002/P3/P4。

Explicitly excluded: Stability、makespan接受tie-break、dynamic Replan、Production weights、reference/benchmark/export、approval/publish。

PROD_OPEN: OPEN-006/011/012保持OPEN；只有显式versioned Simulation Policy可运行。

SIM_ASSUMPTIONS: 新增/更新Delivery policy assumption必须版本化并登记；禁止隐式default。

Rollback: 回退Strategy/objective后Backend仅可作内部constraint test，不得输出可接受计划；保留solver reports和policy version历史。
