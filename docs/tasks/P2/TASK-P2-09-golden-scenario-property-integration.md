---
doc_id: TASK-P2-09
title: Golden Scenario and Property Integration
status: done
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [43, 44, 45, 46, 56, 75, 86, 87]
last_reviewed: 2026-08-21
---

# TASK-P2-09 — Golden Scenario and Property Integration

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, ENG-SOL-001, ENG-VAL-001, ENG-VER-001

Depends on: TASK-P2-04, TASK-P2-05, TASK-P2-06, TASK-P2-07, TASK-P2-08

Start gate: complete Solver+Validator+OBJ-001 chain formed；固定Scenario/Profile/Generator/policy/solver versions和所有existing asset hashes；记录Diff base。

Goal: 建立正式P2 correctness场景集，覆盖Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock，并以property/mutation验证Solver→Validator与deterministic replay。

Inputs: P0/P1 assets、complete P2 pipeline、Scenario contracts、C-001～C-011、OBJ-001、existing mutation set。

Diff base: 15c298f343a47db2a922544944ff5e02e4ca72d9

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/simulation/scenarios/__init__.py`、`backend/app/simulation/scenarios/p2_correctness.py`、`backend/tests/golden/test_p2_golden_solver.py`、`backend/tests/simulation/test_p2_scenario_matrix.py`、`backend/tests/property/test_p2_solver_properties.py`、`backend/tests/validation/test_p2_solver_mutations.py`、`backend/tests/integration/test_ci_contract.py`、`fixtures/deterministic/P2-GOLDEN-JSSP/factory-profile.json`、`fixtures/deterministic/P2-GOLDEN-JSSP/scenario-spec.json`、`fixtures/deterministic/P2-GOLDEN-JSSP/scenario-blueprint.json`、`fixtures/deterministic/P2-GOLDEN-JSSP/correctness-manifest.json`、`fixtures/deterministic/P2-GOLDEN-JSSP/expected-outcome.json`、`fixtures/deterministic/P2-GOLDEN-JSSP/calculation-note.md`、`fixtures/deterministic/P2-GOLDEN-FJSP/factory-profile.json`、`fixtures/deterministic/P2-GOLDEN-FJSP/scenario-spec.json`、`fixtures/deterministic/P2-GOLDEN-FJSP/scenario-blueprint.json`、`fixtures/deterministic/P2-GOLDEN-FJSP/correctness-manifest.json`、`fixtures/deterministic/P2-GOLDEN-FJSP/expected-outcome.json`、`fixtures/deterministic/P2-GOLDEN-FJSP/calculation-note.md`、`fixtures/synthetic/P2-CORRECTNESS-MATRIX/factory-profile.json`、`fixtures/synthetic/P2-CORRECTNESS-MATRIX/scenario-catalog.json`、`fixtures/synthetic/P2-CORRECTNESS-MATRIX/scenario-blueprints.json`、`fixtures/synthetic/P2-CORRECTNESS-MATRIX/calculation-note.md`及`Documents to update`；以上为进入`in_progress`前冻结的全部实际新增路径。

Files forbidden to change: `fixtures/deterministic/SIM-MINIMAL-001/**`、`fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/**`、`fixtures/synthetic/SIM-P1-INGRESS-001/**`及其他P0/P1 immutable asset bytes/hashes、`schemas/**`、`backend/app/planning/**`、`backend/app/application/**`、`backend/app/simulation/generators/**`、`pyproject.toml`、`uv.lock`、migration、production data、`benchmarks/**`与XS/S/M performance profiles、Reference Scheduler/Export、Solver/Validator/Constraint/Objective语义、DB/API/Worker、P3+。

Implementation steps: 人工计算JSSP/FJSP optimum/allowed outcomes；创建六类versioned scenarios/manifests；走正式Import→Snapshot→Problem；运行Strategy→Validator；构造formula-free mutations/property reordering；固定hash与machine report。

Outputs: versioned P2 correctness catalog、Golden calculations、solver/validator replay report和property/mutation evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/repository-layout.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/technology-stack.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/performance-gates.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: Gate correctness assets必须可手算、版本化、重放并与性能profile/Production数据明确隔离。

Change-impact matrix rows reviewed: `IMPACT-SIM-SCENARIO`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012→TASK-P2-09→全部C-ID/OBJ-001→TEST-GOLDEN-JSSP/FJSP、CALENDAR/MATERIAL/RUNNING/CROSS-WORKSHOP/INF-LOCK/PROPERTY/VALIDATOR-MUTATION/SCENARIO-REPLAY→versioned assets/reports。

Schema changes: none expected；若Scenario/manifest合同不足必须另做versioned schema change并修订本卡。

Migration: none。

Dependency changes: none。

ADR impact: none if only adding evidence；任何约束/目标/Scenario semantics变化须对应ADR与solver replay。

Error behavior: expected result mismatch、hash drift、Validator failure、unsupported capability或mutation未命中exact C-ID均hard fail；不得更新expected来隐藏回归。

Tests: 全部P2 correctness Test IDs，至少两个独立replay、stable hashes、合法Problem properties、每个C-ID负例、Solver与Validator独立性。

Benchmark impact: correctness only；可记录运行诊断但不成为XS/S/M/Production baseline。

Simulation scenarios: Golden JSSP/FJSP + Cross Workshop + Calendar + Material Delay + Running + Hard Lock，均固定ID/version/seed/policy/expected behavior。

Acceptance commands: `uv run pytest -q backend/tests/golden/test_p2_golden_solver.py backend/tests/simulation/test_p2_scenario_matrix.py backend/tests/property/test_p2_solver_properties.py backend/tests/validation/test_p2_solver_mutations.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；`uv run python -m app.simulation.scenarios.p2_correctness --root . --report build/validation/TASK-P2-09-correctness.json`及全部既有P2/P1/P0 machine reports；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`docker compose --env-file .env.example config --quiet`；`uv build`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-09-golden-scenario-property-integration.md --check-diff --report build/traceability/TASK-P2-09-report.json`；`git diff --check`；以Diff base核验Schema、Planning/Application/Generator、Solver/Validator/C-ID/Objective、dependency/lock、P0/P1 assets、Benchmark、migration与P3+禁止路径无差异。

Artifacts: committed versioned assets/calculation notes、correctness replay/mutation/property reports和Task report。

Provider evidence: exact SHA required `validate`成功，artifact含P2 correctness hashes/status/Validator和Task report；记录run/job/steps/artifact digest/expiry。

Completion conditions: 七类Gate场景全部可重放且Validator PASS/expected status一致；每个C-ID正反/Property覆盖；hash/version/docs/trace/provider闭环；无性能或Production外推。

Explicitly excluded: XS/S/M performance baseline、Reference Scheduler、Export、P2 Exit audit、P3/P4。

PROD_OPEN: OPEN-001～015状态不因synthetic correctness关闭。

SIM_ASSUMPTIONS: 每个非显式输入值引用active/versioned assumption；变化必须升asset/generator/policy version。

Rollback: 新asset不可原地改写；错误使用新version/superseding manifest；失败evidence保留，Solver回退需重跑全catalog。

## Activation evidence — 2026-08-21

用户明确授权执行TASK-P2-09。启动时`main=origin/main=15c298f343a47db2a922544944ff5e02e4ca72d9`且working tree clean；P2-08 implementation `b1ec83ed96120357ecadd41d3f520181838f17c6`为该HEAD祖先。基线push run `32439301758`、required `validate` job/check `96646617379`（GitHub Actions app `15368`）均`completed/success`；artifact `9431840946`未过期，digest=`sha256:b7de66a574d81ce959bbaf290b3b0d80e67fdb72460e8d4a1cf2989d219f6974`、expiry=`2026-11-19T02:16:54Z`。因此P2-04～08依赖、formal Validator、完整C-001～C-011与OBJ-001启动链一致，Diff base冻结为上述HEAD。

既有`SIM-MINIMAL-001`、`SIM-MINIMAL-001-MUTATIONS`与`SIM-P1-INGRESS-001`共15个文件的逐路径SHA-256已按repository-relative path排序；`UTF-8(path + space + digest)`逐行以LF连接后的清单摘要固定为`sha256:cab42c498ad74607d8e7bb172b6daf3f320626eb0e08b2d155e1b31cb8b45df4`。同时冻结Scenario/Profile/Manifest Schema=`79c0ee97…5f10`/`391d5b02…ff50`/`67ba4835…07ef`、Problem v2 Schema=`e6e4a984…87c8`、Solution Schema=`4344468e…df4`、rule sheet=`83fc3663…1e2`、Problem builder/hash=`c96a55a8…f291`/`ec2b98ed…76b4e`、Global Strategy=`c3c5f057…4133`、formal Validator=`e120cc65…8d9f`、Simulation policy=`437e4876…b558`、P1 generator=`44c9cf4b…c370`及`uv.lock=8b13617f…7a82`。版本边界固定为`planning-problem-builder.v2`、`global-cp-sat-strategy.v1`、`cp-sat-backend.v1`、OR-Tools `9.15.6755`、`constraint-rule-sheet.v1`、`objective-policy.v1`及approved Simulation Delivery Policy `POLICY-P2-SIM-DELIVERY-OBJ001-001@1.0.0`。

启动前scope review确认原卡未展开fixture-local blueprint/catalog/manifest实际路径，也遗漏Scenario package export、correctness machine CLI、CI workflow/integration contract及Task lifecycle/Impact Rule必审文档；故在任何新asset或实现文件产生前先冻结上述allow-list。新证据合同固定为`p2-correctness-blueprint.v1`、`p2-correctness-catalog.v1`、`p2-correctness-manifest.v1`与assembler `PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`；七个Scenario分别为`P2-GOLDEN-JSSP`、`P2-GOLDEN-FJSP`、`P2-CROSS-WORKSHOP`、`P2-CALENDAR`、`P2-MATERIAL-DELAY`、`P2-RUNNING`、`P2-HARD-LOCK`，asset/profile version均固定`1.0.0`。它们是fixture-local evidence contract，不修改发布Schema；正式链必须逐例走Raw Staging→Normalization/Import v2→Data Validation→Expansion→Snapshot v2→Problem v2→Global Strategy→formal Validator。当前activation-only差异只命中`IMPACT-PHASE`/`IMPACT-DOCS`；实现完成时按完整Diff base range复算上述七行Impact Rule。P2-10～14、P3与性能/Production范围均未启动。

## Local implementation evidence — 2026-08-21

已提交准备两份独立Golden与五例shared matrix资产，固定Profile/Scenario/assembler/pipeline/policy/backend/solver version、seed、四类对象hash及Import/Snapshot/Problem hash。Fixture-local assembler仅产生source-shaped Raw rows；七例全部经公开P1/P2链取得OPTIMAL、OBJ-001=0和formal Validator PASS，正向集合合计覆盖C-001～C-011。SIM-ASSUMPTION-011明确所有tiny数值只用于correctness。

Row-order Hypothesis replay保持Import/Snapshot/Problem/assignment/report一致，fresh independent Validator property为7/7 PASS；11个formula-free Solver-candidate mutation各自稳定只命中同名C-ID。`p2-correctness-report.v1`为8/8 PASS并复核P0/P1 immutable asset manifest及Schema/Problem/Strategy/Validator/Policy/Generator/lock fingerprints。Focused=`45 passed`、full repository=`427 passed`、Ruff/Pyright=0；全部P0/P1/P2 machine reports、142-doc治理、58 paths/7 rows/19 checks/0 issues、Compose、`uv build`、version smoke、`git diff --check`和禁止路径核验均PASS。Exact provider尚未形成，Task保持`in_progress`。

## Provider evidence and completion — 2026-08-21

Implementation `20e49c92306128b47313059fabe31534814dbe3d`已直接push到`main`。GitHub push run [`32442651322`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32442651322)（attempt 1）为`completed/success`；required [`validate` job/check `96656224252`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32442651322/job/96656224252)由GitHub Actions app `15368`执行，25个主步骤/全部post步骤均success。Branch protection仍精确要求`validate`/app `15368`。

Artifact `9432982306`（`plantnexus-ci-evidence-32442651322`，33761 bytes）未过期，digest=`sha256:c736a2f029f119850f8a0c9b40b0dbbd0898383f10ddbc798f7182ff5ec90e09`、expiry=`2026-11-19T03:14:03Z`。下载复核确认16/16 JSON reports全部PASS；`ci-p2-correctness.json`的`code_commit`精确绑定implementation SHA并为8/8 checks、7 scenarios/Validator passes/property replays、11 mutations、C-001～C-011正负覆盖；`ci-current-task-report.json`绑定同一SHA和Diff base，记录58 committed/0 working paths、7 Impact Rules、19 checks、0 issues。

因此Goal、测试、hash/version、文档/追踪、provider和回滚边界全部满足，TASK-P2-09=`done`。XS/S/M Benchmark、Reference Scheduler、Export、P2 Exit Audit、Production与P3/P4仍明确排除；P2保持`active`，本次关闭不授权或启动TASK-P2-10。
