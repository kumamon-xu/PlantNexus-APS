---
doc_id: TASK-P2-09
title: Golden Scenario and Property Integration
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [43, 44, 45, 46, 56, 75, 86, 87]
last_reviewed: 2026-08-20
---

# TASK-P2-09 — Golden Scenario and Property Integration

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, ENG-SOL-001, ENG-VAL-001, ENG-VER-001

Depends on: TASK-P2-04, TASK-P2-05, TASK-P2-06, TASK-P2-07, TASK-P2-08

Start gate: complete Solver+Validator+OBJ-001 chain formed；固定Scenario/Profile/Generator/policy/solver versions和所有existing asset hashes；记录Diff base。

Goal: 建立正式P2 correctness场景集，覆盖Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock，并以property/mutation验证Solver→Validator与deterministic replay。

Inputs: P0/P1 assets、complete P2 pipeline、Scenario contracts、C-001～C-011、OBJ-001、existing mutation set。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `fixtures/deterministic/P2-GOLDEN-JSSP/**`、`fixtures/deterministic/P2-GOLDEN-FJSP/**`、`fixtures/synthetic/P2-CORRECTNESS-MATRIX/**`、`backend/app/simulation/scenarios/p2_correctness.py`、`backend/tests/golden/test_p2_golden_solver.py`、`backend/tests/simulation/test_p2_scenario_matrix.py`、`backend/tests/property/test_p2_solver_properties.py`、`backend/tests/validation/test_p2_solver_mutations.py`及`Documents to update`；所有实际新增路径/asset versions在进入in_progress前展开为精确清单。

Files forbidden to change: P0/P1 immutable asset bytes/hashes、production data、XS/S/M performance profiles、Reference Scheduler/Export/CI Gate、Solver constraint语义、P3+。

Implementation steps: 人工计算JSSP/FJSP optimum/allowed outcomes；创建六类versioned scenarios/manifests；走正式Import→Snapshot→Problem；运行Strategy→Validator；构造formula-free mutations/property reordering；固定hash与machine report。

Outputs: versioned P2 correctness catalog、Golden calculations、solver/validator replay report和property/mutation evidence。

Documentation impact: required

Documents to update: `docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/performance-gates.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、本Task卡。

Documentation impact rationale: Gate correctness assets必须可手算、版本化、重放并与性能profile/Production数据明确隔离。

Change-impact matrix rows reviewed: `IMPACT-FIXTURE`、`IMPACT-SIM-SCENARIO`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012→TASK-P2-09→全部C-ID/OBJ-001→TEST-GOLDEN-JSSP/FJSP、CALENDAR/MATERIAL/RUNNING/CROSS-WORKSHOP/INF-LOCK/PROPERTY/VALIDATOR-MUTATION/SCENARIO-REPLAY→versioned assets/reports。

Schema changes: none expected；若Scenario/manifest合同不足必须另做versioned schema change并修订本卡。

Migration: none。

Dependency changes: none。

ADR impact: none if only adding evidence；任何约束/目标/Scenario semantics变化须对应ADR与solver replay。

Error behavior: expected result mismatch、hash drift、Validator failure、unsupported capability或mutation未命中exact C-ID均hard fail；不得更新expected来隐藏回归。

Tests: 全部P2 correctness Test IDs，至少两个独立replay、stable hashes、合法Problem properties、每个C-ID负例、Solver与Validator独立性。

Benchmark impact: correctness only；可记录运行诊断但不成为XS/S/M/Production baseline。

Simulation scenarios: Golden JSSP/FJSP + Cross Workshop + Calendar + Material Delay + Running + Hard Lock，均固定ID/version/seed/policy/expected behavior。

Acceptance commands: `uv run pytest -q backend/tests/golden/test_p2_golden_solver.py backend/tests/simulation/test_p2_scenario_matrix.py backend/tests/property/test_p2_solver_properties.py backend/tests/validation/test_p2_solver_mutations.py`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-09-golden-scenario-property-integration.md --check-diff --report build/traceability/TASK-P2-09-report.json`；`git diff --check`。

Artifacts: committed versioned assets/calculation notes、correctness replay/mutation/property reports和Task report。

Provider evidence: exact SHA required `validate`成功，artifact含P2 correctness hashes/status/Validator和Task report；记录run/job/steps/artifact digest/expiry。

Completion conditions: 七类Gate场景全部可重放且Validator PASS/expected status一致；每个C-ID正反/Property覆盖；hash/version/docs/trace/provider闭环；无性能或Production外推。

Explicitly excluded: XS/S/M performance baseline、Reference Scheduler、Export、P2 Exit audit、P3/P4。

PROD_OPEN: OPEN-001～015状态不因synthetic correctness关闭。

SIM_ASSUMPTIONS: 每个非显式输入值引用active/versioned assumption；变化必须升asset/generator/policy version。

Rollback: 新asset不可原地改写；错误使用新version/superseding manifest；失败evidence保留，Solver回退需重跑全catalog。
