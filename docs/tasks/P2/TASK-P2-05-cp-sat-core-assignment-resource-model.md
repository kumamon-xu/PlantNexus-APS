---
doc_id: TASK-P2-05
title: CP-SAT Core Assignment and Resource Model
status: in_progress
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

Start gate: Backend foundation与formal Validator均`done`；Problem/Solution versions固定；用户于2026-08-20明确授权执行本Task；启动时`main=origin/main`、working tree clean，并记录Diff base、rule version、solver exact version及依赖Task的exact provider evidence。

Goal: 在CP-SAT backend实现C-001/C-003/C-004/C-010/C-011的完整assignment、alternative duration、capacity-1 NoOverlap和horizon模型，并由独立Validator接受。

Inputs: Problem v2、backend protocol、formal Validator、constraint-rule-sheet.v1、SolveLimits。

Diff base: c75f7a0e96b7591ffa9220d0de942f8841283093

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/planning/backends/cp_sat/__init__.py`、`backend/app/planning/backends/cp_sat/model.py`、`backend/app/planning/backends/cp_sat/core_constraints.py`、`backend/app/planning/backends/cp_sat/backend.py`、`backend/app/planning/backends/cp_sat/solution_mapper.py`、`backend/app/planning/backends/cp_sat/core_model_check.py`、`backend/app/planning/backends/cp_sat/contract_check.py`、`backend/tests/unit/test_cp_sat_core_model.py`、`backend/tests/unit/test_solver_backend_contract.py`、`backend/tests/property/test_cp_sat_core_properties.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；新增exact路径已在进入`in_progress`时冻结，后续两条历史兼容路径依下方scope review在修改前补充。

Files forbidden to change: Problem/Policy/Solution schema语义、Validator formulas、temporal/calendar/material/fact/lock constraints、objective/Strategy、fixtures/benchmarks/export/P3。

Implementation steps: 建operation/master/optional intervals与exact-one presence；candidate-specific duration；capacity-1 NoOverlap；horizon/complete assignment；solution mapping/model telemetry；precheck zero candidate/overflow；用formal Validator和brute-force tiny properties交叉验证。

Outputs: core CP-SAT model、C-001/003/004/010/011 tests、model-size/timing diagnostics和candidate solutions。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/domain/kpi-contract.md`、`docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/planning/schedule-validator.md`、`docs/quality/property-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: 首个业务CP-SAT模型形成核心可行域，必须绑定C-ID、Validator和solver/version telemetry。

Change-impact matrix rows reviewed: `IMPACT-BACKEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009→TASK-P2-05→C-001/003/004/010/011→TEST-GOLDEN-JSSP/FJSP、TEST-INF-NO-RESOURCE/HORIZON、TEST-PROPERTY→core model/validator artifacts。

Schema changes: none；严格消费P2-01/02已发布合同。

Migration: none。

Dependency changes: none beyondTASK-P2-03 pinned OR-Tools；`ortools==9.15.6755`与`uv.lock` SHA-256=`8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`必须保持不变。

ADR impact: implements ADR-0003/0004/0008及solver-version ADR；约束语义或tick conversion变化必须新ADR并回到合同Task。

Error behavior: zero candidate/invalid horizon在build前稳定拒绝；MODEL_INVALID不映射INFEASIBLE；只有有完整candidate时输出FEASIBLE/OPTIMAL，且必须Validator PASS才能接受。

Tests: TEST-GOLDEN-JSSP/FJSP、TEST-INF-NO-RESOURCE/HORIZON、TEST-PROPERTY、TEST-VALIDATOR-MUTATION；包含多候选不同duration、back-to-back half-open intervals、overflow、duplicate/missing assignment、model counts。

Benchmark impact: 记录variables/constraints/optional intervals/build/solve/first-feasible/memory诊断；只用tiny correctness cases，不建立XS/S/M阈值。

Simulation scenarios: versioned tiny JSSP/FJSP derived cases；不声称完整P2 Gate。

Acceptance commands: `uv sync --locked`；`uv run pytest -q backend/tests/unit/test_cp_sat_core_model.py backend/tests/property/test_cp_sat_core_properties.py backend/tests/validation backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python -m app.planning.backends.cp_sat.core_model_check --root . --report build/validation/TASK-P2-05-core-model.json`；`uv run python -m app.planning.validation.problem_validator_check --root . --report build/validation/TASK-P2-04-formal-schedule-validator.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-05-cp-sat-core-assignment-resource-model.md --check-diff --report build/traceability/TASK-P2-05-report.json`；`docker compose --env-file .env.example config --quiet`；`uv build`；`git diff --exit-code c75f7a0e96b7591ffa9220d0de942f8841283093 -- pyproject.toml uv.lock schemas backend/app/planning/contracts.py backend/app/planning/policy/contracts.py backend/app/planning/problem backend/app/planning/validation fixtures benchmarks`；`git diff --check`。

Artifacts: core-model report、candidate/validator/property evidence、Task report。

Provider evidence: exact SHA required `validate`成功并上传model/validator/Task reports；记录solver exact version、run/job/steps/artifact digest。

Completion conditions: 五个C-ID全部由Solver实现且独立Validator正反验证；telemetry真实；local/provider/docs/trace PASS；其余C-ID和OBJ-001不宣称完成。

Explicitly excluded: C-002/005～009、OBJ-001、Reference Scheduler、Export、XS/S/M Benchmark、P3。

PROD_OPEN: OPEN-007/009/010/011/012保持OPEN。

SIM_ASSUMPTIONS: tiny correctness durations/calendars显式versioned，不外推Production。

Rollback: 回退core builder/mapper并保持Backend protocol；已生成candidate仅作为不可发布测试artifact，任何solver-version回退须重跑upgrade replay。

## Activation evidence

2026-08-20用户明确授权执行TASK-P2-05。启动复核时working tree clean，`main=origin/main=c75f7a0e96b7591ffa9220d0de942f8841283093`；TASK-P2-03/04均为`done`，实现`9268b88ca7ce90a8f72023241f87e2d3676fd58a`/`9b532e2c054b02e1692f345a252922ec7fd469e4`均为HEAD祖先。该HEAD的GitHub push run `32350571302`、required `validate` job `96368639237`均`completed/success`；artifact `9399702868`=`plantnexus-ci-evidence-32350571302`，digest=`sha256:17c540429834a5ef586da9443b7e4801bd0aa99f6b3399253d26ac392a2bebed`、`expired=false`、expires=`2026-11-18T08:47:41Z`，required context仍为`validate`/GitHub Actions app ID `15368`。

启动冻结SHA-256：Problem v2/Solution/Policy/Limits Schema=`e6e4a984…87c8`/`4344468e…8df4`/`62624424…1bda`/`8caff522…1d95`，rule sheet=`83fc3663…f1e2`，formal Validator=`e120cc65…48d9`，Planning contracts=`d5f7a7e4…ae630`，Problem hashing=`ec2b98ed…76b4e`，Backend/status=`e6fb5017…bf01`/`b03e5cfb…a636`，`uv.lock=8b13617f…7a82`。Local runtime为CPython `3.12.13` / Windows，installed OR-Tools=`9.15.6755`。本Task不修改上述Schema/rule/Validator/Problem/lock字节。

实现边界在任何Backend代码修改前固定：仅对C-001/003/004/010/011建模；含precedence/calendar/release-material gate/RUNNING/HARD-SOFT lock等P2-06/07事实的Problem必须在build前稳定拒绝，不得静默忽略。Core solve不添加`Minimize/Maximize`或Strategy；即使native纯可行模型返回OPTIMAL，在OBJ-001未实现时也只能输出诚实的业务`FEASIBLE`及已测量candidate metric/0 lower bound，不声称最优。新增machine CLI、workflow、integration contract和PHASE/INFRA必审文档路径已在进入`in_progress`时冻结；P2-06+与P3不在授权范围。

实现前scope review发现：P2-03的`contract_check.py`与`test_solver_backend_contract.py`仍把`CpSatBackend.solve()`永久拒绝、OR-Tools只出现在原两个文件作为current-repository断言，与P2-05被规划的consumer形成必然冲突。因此在触碰这两个文件前补入exact allow-list，仅允许把断言更新为“foundation smoke历史边界保留、current core consumer由TASK-P2-05负责”并扩展CP-SAT package namespace集合；不改P2-03历史artifact、status/parameter/version映射或任何Schema/rule/Validator。

## Local implementation evidence

实现形成C-001/003/004/010/011 master/optional interval、exact-one、candidate-specific duration、capacity-1 NoOverlap与horizon model；Problem含precedence/calendar/late release-material/RUNNING/lock时build前稳定拒绝。完整native candidate被诚实降级为业务FEASIBLE、映射seconds/ticks/UTC，并仅在formal Validator PASS后保留；模型无objective，Solution stage只作post-solve weighted-tardiness measurement。

2026-08-20本地验收：`uv sync --locked` PASS；指定focused suite=`64 passed`；全仓suite=`360 passed`；Ruff/Pyright均0；core machine report=`6/6 PASS`，counts=`5 constraints/2 candidates/1 infeasible/2 prechecks/2 validator mutations/4 oracle cases`；formal report=`6/6 PASS`；治理full=`142 docs/30 roots/36 tests/15 OPEN/10 SIM/11 risks/37 tasks`，Task diff=`49 paths/6 impact rows/19 checks/0 issues`；compose config、`uv build`、immutable contract/lock/schema/rule/Validator/fixture/benchmark diff及`git diff --check`均PASS。Local report仍为`code_commit=uncommitted`，Task在exact implementation provider evidence前保持`in_progress`。
