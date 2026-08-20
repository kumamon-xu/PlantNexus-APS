---
doc_id: TASK-P2-07
title: Execution Facts and Hard Lock Model
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [25, 26, 30, 35, 50, 75]
last_reviewed: 2026-08-20
---

# TASK-P2-07 — Execution Facts and Hard Lock Model

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P2-06

Start gate: TASK-P2-06=`done`；Problem v2 RUNNING/COMPLETED anchor与lock字段已验证；固定execution/lock facts和Diff base。

Goal: 实现C-007/C-008：COMPLETED排除但历史lag有效，RUNNING资源/实际开始/剩余未来占用固定，HARD lock resource/start/end不可移动；SOFT lock仅保留供未来稳定性且不作为硬约束。

Inputs: Problem v2 facts/locks、CP-SAT core/temporal model、formal Validator、ADR-0007、C-007/008 rule sheet。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/planning/backends/cp_sat/fact_lock_constraints.py`、`backend/app/planning/backends/cp_sat/model.py`、`backend/tests/unit/test_cp_sat_fact_lock_model.py`、`backend/tests/property/test_cp_sat_fact_lock_properties.py`及`Documents to update`；其他路径先修订卡片。

Files forbidden to change: Problem schema、Validator formulas、SOFT lock objective、dynamic Replan、ExecutionSimulator、P0 asset bytes、Export/Benchmark/P3。

Implementation steps: 固定RUNNING master/assignment/remaining interval；应用historical anchors；排除COMPLETED未来assignment；固定HARD lock三要素及一致性；保留SOFT metadata不硬化；构造lock/no-resource/horizon infeasible；Validator和property交叉。

Outputs: fact/lock constraint builder、C-007/008正反/property/infeasibility证据及model report。

Documentation impact: required

Documents to update: `docs/planning/constraint-catalog.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/objective-policy.md`、`docs/planning/schedule-validator.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/planning/replanning.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/architecture/technology-stack.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: execution facts和HARD lock是事实保护边界，错误实现会产生不可接受计划并影响未来Replan。

Change-impact matrix rows reviewed: `IMPACT-BACKEND`、`IMPACT-TESTS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012→TASK-P2-07→C-007/008→TEST-RUNNING/INF-LOCK/PROPERTY/VALIDATOR-MUTATION→fact-lock solver/validator artifacts。

Schema changes: none；消费Problem v2。

Migration: none。

Dependency changes: none。

ADR impact: implements ADR-0007；若允许移动RUNNING/HARD lock或把SOFT变hard必须停止并新建superseding ADR。

Error behavior: fact/lock自相矛盾在model build前明确拒绝；真实不可行返回INFEASIBLE；不得静默降级lock为hint或重新选择RUNNING资源。

Tests: TEST-RUNNING、TEST-INF-LOCK、TEST-PROPERTY、TEST-VALIDATOR-MUTATION；覆盖completed-active lag、running occupancy、hard start/end/resource、soft non-hard、conflicts和deterministic replay。

Benchmark impact: 记录fixed interval/constraint counts与solver telemetry；不运行动态Replan或稳定性benchmark。

Simulation scenarios: versioned Running/Hard Lock correctness scenarios；不注入事件流。

Acceptance commands: `uv run pytest -q backend/tests/unit/test_cp_sat_fact_lock_model.py backend/tests/property/test_cp_sat_fact_lock_properties.py backend/tests/validation`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-07-execution-facts-and-hard-lock-model.md --check-diff --report build/traceability/TASK-P2-07-report.json`；`git diff --check`。

Artifacts: fact-lock model/validator/property report、infeasibility cases、Task report。

Provider evidence: exact SHA required `validate`成功，artifact含C-007/008 evidence和Task report，记录run/job/steps/digest。

Completion conditions: C-007/008全部事实保护在Solver与Validator独立PASS；冲突负例明确；SOFT boundary保持；local/provider/docs/trace闭环。

Explicitly excluded: OBJ-002 stability、ExecutionSimulator、event/replan、approval/publish、P3/P4。

PROD_OPEN: OPEN-005/007保持OPEN；freeze policy和事实authority不猜。

SIM_ASSUMPTIONS: Running/lock比例和值只属于versioned scenarios。

Rollback: 回退fact-lock builder并禁止使用缺少C-007/008的Backend生成可接受结果；保留冲突/失败证据。
