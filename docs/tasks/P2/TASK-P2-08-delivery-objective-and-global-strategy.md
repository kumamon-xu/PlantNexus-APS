---
doc_id: TASK-P2-08
title: Delivery Objective and Global Strategy
status: in_progress
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

Diff base: 9c55df993b12ae0bdd3d4d38c900d601324c05d2

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/planning/strategies/__init__.py`、`backend/app/planning/strategies/global_cp_sat.py`、`backend/app/planning/policy/__init__.py`、`backend/app/planning/policy/delivery.py`、`backend/app/planning/backends/cp_sat/objectives.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/solution_mapper.py`、`backend/app/planning/backends/cp_sat/contract_check.py`、`backend/app/planning/backends/cp_sat/objective_strategy_check.py`、`backend/tests/unit/test_global_cp_sat_strategy.py`、`backend/tests/unit/test_solver_backend_contract.py`、`backend/tests/property/test_delivery_objective_properties.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；其他路径先修订。

Files forbidden to change: `schemas/**`、`backend/app/planning/contracts.py`、`backend/app/planning/problem/**`、`backend/app/planning/validation/**`、`backend/app/planning/backends/cp_sat/model.py`、C-ID formulas、`pyproject.toml`、`uv.lock`、migration、Validator logic、OBJ-002 Stability/OBJ-003 acceptance、Production default weight、Reference/Export/Benchmark runner、DB/API/Worker/P3/P4。

Implementation steps: 建versioned synthetic delivery weights；定义tardiness ticks/weight integer objective；Strategy precheck→backend→Validator；limits/status/stop reason；objective/bound/gap/timing report；tiny brute-force optimum与limit/UNKNOWN/FEASIBLE tests。

Outputs: GlobalCpSatStrategy、OBJ-001 policy/objective builder、status/limits orchestration和solver report evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/planning/planning-strategies.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/domain/kpi-contract.md`、`docs/domain/error-model.md`、`docs/simulation/performance-gates.md`、`docs/quality/benchmark-regression.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: Objective、Strategy、limits和status决定P2计划选择/报告边界，且必须隔离未知Production权重。

Change-impact matrix rows reviewed: `IMPACT-PHASE`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-08→OBJ-001→TEST-GOLDEN-JSSP/FJSP、TEST-PROPERTY、TEST-SOLVER-UPGRADE→strategy/objective/status artifacts；OBJ-002/003保持PLANNED/非接受目标。

Schema changes: none expected；使用P2-02合同；若report字段不足需先版本化合同Task。

Migration: none。

Dependency changes: none；solver lock固定。

ADR impact: implements ADR-0004/0006；若混合目标、改变lexicographic顺序或Production权重必须停止并superseding ADR。

Error behavior: Validator FAIL永不进入可接受solution；limit无解=UNKNOWN，不冒充INFEASIBLE；unsupported policy/version明确拒绝；FEASIBLE不冒充OPTIMAL。

Tests: TEST-GOLDEN-JSSP/FJSP、TEST-PROPERTY、TEST-SOLVER-UPGRADE、TEST-ERROR-MAPPING-001；tiny brute-force tardiness、priority weight、zero tardiness、limits/status、validator-fail gate与report replay。

Benchmark impact: 开始记录完整objective/bound/gap/build/first-feasible/solve/memory/model size，但正式XS/S/M baseline留P2-12。

Simulation scenarios: versioned Delivery policy + tiny due/priority scenarios；不得称Production policy。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_global_cp_sat_strategy.py backend/tests/property/test_delivery_objective_properties.py backend/tests/unit/test_solver_backend_contract.py backend/tests/validation backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run python -m app.planning.backends.cp_sat.objective_strategy_check --root . --report build/validation/TASK-P2-08-objective-strategy.json`及全部既有P2/P1/P0 machine reports；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`docker compose --env-file .env.example config --quiet`；`uv build`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-08-delivery-objective-and-global-strategy.md --check-diff --report build/traceability/TASK-P2-08-report.json`；`git diff --check`；以Diff base核验Schema、Problem、formal Validator、C-ID rule、dependency/lock、migration与P3/P4禁止路径无差异。

Artifacts: `objective-strategy-report.v1` strategy/objective/status/limits报告、tiny optimality proofs、全部历史machine reports、Task report与CI `plantnexus-ci-evidence-<run-id>`。

Provider evidence: exact SHA required `validate`成功并上传solver/validator/Task evidence；记录solver/policy versions、run/job/steps/artifact digest。

Completion conditions: complete hard model先通过Validator；OBJ-001数值与brute-force一致；status/limit/report真实；local/provider/docs/trace PASS；无OBJ-002/P3/P4。

Explicitly excluded: Stability、makespan接受tie-break、dynamic Replan、Production weights、reference/benchmark/export、approval/publish。

PROD_OPEN: OPEN-006/011/012保持OPEN；只有显式versioned Simulation Policy可运行。

SIM_ASSUMPTIONS: 新增/更新Delivery policy assumption必须版本化并登记；禁止隐式default。

Rollback: 回退Strategy/objective后Backend仅可作内部constraint test，不得输出可接受计划；保留solver reports和policy version历史。

## Activation evidence — 2026-08-21

用户明确授权执行TASK-P2-08。启动时`main=origin/main=9c55df993b12ae0bdd3d4d38c900d601324c05d2`且working tree clean；该SHA的push run `32435755901`、required `validate` job/check `96636509174`（GitHub Actions app `15368`）均`completed/success`。Artifact `9430697910`未过期，digest=`sha256:6fd173b5cdb6cdae4d5f86bbdee773b8ca7679db34d90d52c4db05d5ca18d8c4`、expiry=`2026-11-19T01:17:08Z`。因此P2-02/05/06/07依赖与完整C-001～C-011/formal Validator启动门一致，Diff base冻结为上述HEAD。

启动前scope review确认原卡未包含objective-aware solution mapping、SolverReport assembly的machine CLI、CP-SAT namespace回归、CI workflow/integration contract以及Task lifecycle/Impact Rule必审文档；故先扩展上述允许路径与验收命令，再实施业务代码。当前activation-only差异只命中`IMPACT-PHASE`/`IMPACT-DOCS`；激活提交后、首个业务文件变更前，必须把本卡的impact行切换为实际实现所需`IMPACT-POLICY`、`IMPACT-STRATEGY`、`IMPACT-BACKEND`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Schema/Planning contracts、Problem builder/hash、formal Validator、core model/C-ID公式、OR-Tools exact pin与lock均冻结；本Task只允许显式versioned Simulation Delivery Policy执行OBJ-001，OPEN-006/011/012继续阻断Production。
