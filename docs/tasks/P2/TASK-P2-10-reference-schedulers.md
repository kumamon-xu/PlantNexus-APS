---
doc_id: TASK-P2-10
title: Reference Schedulers
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [51, 52, 53, 54, 75]
last_reviewed: 2026-08-20
---

# TASK-P2-10 — Reference Schedulers

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-015

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-VER-001

Depends on: TASK-P2-01, TASK-P2-02, TASK-P2-04

Start gate: Problem/Solution/formal Validator contracts=`done`；固定算法tie-break和Diff base；不依赖CP-SAT实现细节。

Goal: 实现FCFS、EDD、SPT、Priority+EDD与Greedy Earliest Available Machine reference schedulers，消费同一Problem并由同一独立Validator/KPI口径评估。

Inputs: Problem v2、PlanningSolution、formal Validator、objective/KPI definitions、P2 correctness scenarios。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/simulation/baselines/__init__.py`、`backend/app/simulation/baselines/reference_schedulers.py`、`backend/app/simulation/baselines/contracts.py`、`backend/tests/unit/test_reference_schedulers.py`、`backend/tests/property/test_reference_scheduler_properties.py`及`Documents to update`；其他路径先修订。

Files forbidden to change: CP-SAT backend/Strategy/constraints、Validator formulas、Problem schema、Production fallback/API、BenchmarkRunner/Export/P3。

Implementation steps: 定义deterministic selection/tie-break；五算法在同一hard-feasibility helper边界上生成完整candidate或明确失败；调用formal Validator；计算基础tardiness/makespan；检测partial/random output；生成comparison report。

Outputs: 五个baseline scheduler、deterministic/feasibility/property tests和reference report。

Documentation impact: required

Documents to update: `docs/planning/reference-schedulers.md`、`docs/planning/schedule-validator.md`、`docs/planning/objective-policy.md`、`docs/domain/kpi-contract.md`、`docs/simulation/benchmark-harness.md`、`docs/quality/benchmark-regression.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、本Task卡。

Documentation impact rationale: baseline算法是P2 quality sanity check，必须使用相同事实/Validator/KPI且明确非生产fallback。

Change-impact matrix rows reviewed: `IMPACT-REFERENCE-SCHEDULER`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/015→TASK-P2-10→TEST-REFERENCE-SCHEDULER/PROPERTY→五算法/validator/KPI report；Global CP-SAT比较留P2-12。

Schema changes: none。

Migration: none。

Dependency changes: none；baseline禁止OR-Tools import。

ADR impact: none；如用作Production fallback或简化hard constraints必须新ADR并另行授权。

Error behavior: 无法构造完整合法计划返回明确failure并保留Validator结果；不得输出partial schedule或把heuristic failure写成Problem INFEASIBLE。

Tests: TEST-REFERENCE-SCHEDULER、TEST-PROPERTY、TEST-GOLDEN-JSSP/FJSP、TEST-VALIDATOR-MUTATION；算法identity/tie-break/replay、hard constraints和无OR-Tools scan。

Benchmark impact: 形成baseline算法输出/feasibility/weighted tardiness/makespan/runtime字段；正式同场景比较和阈值在P2-12。

Simulation scenarios: 使用P2-09 correctness scenarios；不新建performance profile。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_reference_schedulers.py backend/tests/property/test_reference_scheduler_properties.py backend/tests/golden backend/tests/validation`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-10-reference-schedulers.md --check-diff --report build/traceability/TASK-P2-10-report.json`；`git diff --check`。

Artifacts: reference-scheduler comparison report、property/validator evidence、Task report。

Provider evidence: exact SHA required `validate`成功，artifact含五算法身份/结果/Validator与Task report，记录run/job/digest。

Completion conditions: 五算法确定且不绕过Problem/Validator/KPI；合法输出PASS、失败明确；local/provider/docs/trace闭环；不成为Production fallback。

Explicitly excluded: CP-SAT修改、benchmark profiles/thresholds、Export、API/Worker/P3。

PROD_OPEN: OPEN-006/011/012保持OPEN。

SIM_ASSUMPTIONS: tie-break/weights只在versioned baseline policy中显式声明。

Rollback: 删除baseline实现不影响Global Strategy；保留comparison artifacts；任何已发布benchmark必须标注baseline version不可重解释。
