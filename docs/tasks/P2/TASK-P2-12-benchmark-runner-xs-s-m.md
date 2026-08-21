---
doc_id: TASK-P2-12
title: BenchmarkRunner and XS S M Profiles
status: in_progress
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [45, 51, 52, 53, 54, 55, 56, 57, 58, 75, 76, 89]
last_reviewed: 2026-08-21
---

# TASK-P2-12 — BenchmarkRunner and XS S M Profiles

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012, REQ-014, REQ-015

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-VER-001

Depends on: TASK-P2-08, TASK-P2-09, TASK-P2-10, TASK-P2-11

Start gate: Global Strategy、correctness scenarios、Reference Schedulers、report/export均`done`；固定hardware/environment capture、profiles/threshold policy和Diff base。启动时还必须确认P2-11 closure HEAD的required `validate`/artifact精确成功、P2-09 correctness assets与P2-10五算法可重放、P2-11 KPI/Export仍通过，并冻结Schema/Planning/Strategy/Backend/Validator/Reference/Export/lock边界。

Goal: 实现BenchmarkRunner与versioned XS/S/M profiles，在同一Problem/Validator/KPI上比较CP-SAT和五个reference schedulers，并记录Gate A全部规模、时间、质量、内存和验证字段。

Inputs: P2 scenarios/export、solver/reference schedulers、BenchmarkReport contract、performance gates、OPEN-011/012边界。

Diff base: 58db14e8f18fb50866fb757d4c89e76fef1141f1

Files allowed to change: `benchmarks/profiles.yaml`、`benchmarks/baselines/p2-xs.v1.json`、`benchmarks/baselines/p2-s.v1.json`、`benchmarks/baselines/p2-m.v1.json`、`backend/app/simulation/benchmarks/__init__.py`、`backend/app/simulation/benchmarks/runner.py`、`backend/app/simulation/benchmarks/reporting.py`、`backend/app/planning/reporting/__init__.py`、`backend/app/planning/reporting/kpi.py`、`scripts/run_benchmark.py`、`.github/workflows/ci.yml`、`backend/tests/contract/test_benchmark_contract.py`、`backend/tests/integration/test_benchmark_runner.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；baseline glob已在首个实现文件前展开为上述三个精确、不可覆盖的v1文件。Reporting修改只允许把既有KPI v2的schedule-level delivery/planning/resource计算抽为公共pure函数，使Global与Reference共享同一口径；不得改变KPI v2字节、ID、Schema或P2-11 package结果。新增路径必须先修订本卡。

Files forbidden to change: `schemas/**`、`pyproject.toml`、`backend/app/__init__.py`、`uv.lock`、`fixtures/**`、`backend/app/simulation/scenarios/**`、`backend/app/simulation/baselines/**`、`backend/app/planning/contracts.py`、`backend/app/planning/problem/**`、`backend/app/planning/policy/**`、`backend/app/planning/strategies/**`、`backend/app/planning/backends/**`、`backend/app/planning/validation/**`、`backend/app/exporters/**`、除明列文件外的`backend/tests/**`、migration/DB/API/Worker、Solver/Validator constraint semantics、KPI/Export既有输出语义、Production SLA/capacity、L/XL release profiles、P3 state/publish、P4 disruption、历史baseline覆盖。

Implementation steps: 定义strict internal `benchmark-profile-set.v1`、`benchmark-report.v1`、`benchmark-baseline.v1`；由versioned XS/S/M profile确定性生成source-shaped benchmark blueprint，并经P2-09正式Raw→Import→Quality→Expansion→Snapshot→Problem链；采集orders/lots/operations/edges/resources/candidates/calendar/fact/lock/material/horizon、model counts、build/first feasible/solve/validation/total、objective/bound/gap、memory、Validator、KPI、Export与hardware/environment；同一Problem运行Global和五个references并用公共schedule KPI口径核对；warm-up/repetition后形成median/p95；correctness-first判定/BENCHMARK_WARNING；PR只跑XS，local/nightly可跑S/M；三个v1 baseline只允许首次创建，后续变化必须新版本且不得覆盖。

Outputs: BenchmarkRunner、XS/S/M profiles/baselines、CLI、reports、CI hook activation和comparison evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/simulation/README.md`、`docs/simulation/benchmark-harness.md`、`docs/simulation/performance-gates.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/quality/benchmark-regression.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/domain/kpi-contract.md`、`docs/planning/reference-schedulers.md`、`docs/planning/solver-backend-contract.md`、`docs/contracts/export-package.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: P2 Gate的XS/S/M和provider artifact必须有版本化profile、环境、报告字段及不外推Production的判定规则。

Change-impact matrix rows reviewed: `IMPACT-BENCHMARK`、`IMPACT-REPORTING`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012/014/015→TASK-P2-12→TEST-BENCHMARK/REFERENCE-SCHEDULER/SCENARIO-REPLAY/SOLVER-UPGRADE→XS/S/M reports/baselines/provider artifacts。

Schema changes: none。Benchmark Profile/Report/Baseline是P2内部machine evidence合同，由`reporting.py`的exact-key/type/version validator与contract tests固定，不是跨系统Business Schema或可发布package合同；global schema set继续`2.5.0`。若未来发布JSON Schema、把报告加入外部Export或持久化consumer，必须先修订本卡/另建Task并登记set version、compatibility、sample和contract tests，禁止隐式shape漂移。

Migration: none。

Dependency changes: none expected；若memory采集需新dependency，先拆分/ADR/exact pin，不在实现中临时引入。

ADR impact: benchmark baseline建立不新增ADR；solver/profile/threshold语义变化或显著回归豁免必须ADR。OPEN-012未关闭前无Production threshold。

Error behavior: Validator/correctness failure硬失败；unknown/timeout如实记录；CP-SAT劣于reference产生warning；缺字段/硬件/provenance拒绝baseline；不得以性能抵消错误。

Tests: TEST-BENCHMARK、TEST-REFERENCE-SCHEDULER、TEST-SCENARIO-REPLAY、TEST-SOLVER-UPGRADE；runner/report contract、profile validation、determinism、warning/threshold、CI PR hook和artifact tests。

Benchmark impact: 本Task本身建立XS/S/M开发/仿真baseline；记录所有Gate字段但明确不是Production SLA/capacity，历史baselineimmutable/versioned。

Simulation scenarios: P2 correctness matrix + versioned XS/S/M synthetic scenarios；L/XL和disruption不在本Task。

Acceptance commands: `uv run pytest -q backend/tests/contract/test_benchmark_contract.py backend/tests/integration/test_benchmark_runner.py backend/tests/integration/test_ci_contract.py`；`uv run python scripts/run_benchmark.py --profile xs --report build/benchmarks/TASK-P2-12-xs.json`；`uv run python scripts/run_benchmark.py --profile s --report build/benchmarks/TASK-P2-12-s.json`；`uv run python scripts/run_benchmark.py --profile m --report build/benchmarks/TASK-P2-12-m.json`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden backend/tests/validation backend/tests/integration backend/tests/property`；全部既有P0/P1/P2 machine reports；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`docker compose --env-file .env.example config --quiet`；`uv build`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-12-benchmark-runner-xs-s-m.md --check-diff --report build/traceability/TASK-P2-12-report.json`；`git diff --check`；相对Diff base核验Schema/fixture/Scenario/Reference/Strategy/Backend/Validator/Exporter/lock/P3禁止路径零差异。

Artifacts: versioned profiles/baselines、XS/S/M BenchmarkReports、CI contract/report和Task report。

Provider evidence: exact SHA required `validate`必须实际运行PR/XS benchmark并上传report；S/M如不适合required job须记录独立authorized run/artifacts；核验run/job/steps/artifact digest/expiry和required context。

Completion conditions: XS/S/M全部报告字段真实且Validator PASS；reference comparison完成；CI provider至少XS exact evidence，S/M有可核验provider/local policy证据；docs/trace/provider闭环；不作Production承诺。

Explicitly excluded: L/XL/stress release gate、Production SLA/capacity、dynamic disruptions、P3/P4。

PROD_OPEN: OPEN-011/012保持OPEN；结果不得关闭规模/性能生产阈值。

SIM_ASSUMPTIONS: `SIM-ASSUMPTION-013`精确登记profile/size/distribution/seed/repetition/environment与development-only边界；不能成为Production defaults。

Rollback: baseline不覆盖；runner/profile错误发布新version并保留旧结果；CI regression保留失败artifact，禁止删除或降低correctness Gate。

## Activation evidence — 2026-08-21

用户明确授权执行TASK-P2-12。启动时`main=origin/main=58db14e8f18fb50866fb757d4c89e76fef1141f1`且working tree clean；P2-11 implementation `546292831c3bd52185687a4c646c10ae10541ae2`及其evidence closure均为该HEAD祖先。基线push run `32455399561`、required `validate` job/check `96691604529`（GitHub Actions app `15368`）均`completed/success`；branch protection精确要求`validate`/app `15368`。Artifact `9437086153`（`plantnexus-ci-evidence-32455399561`，41110 bytes）未过期，digest=`sha256:1da721655426224cf9dae4f3ee9cc16c4fbe1433e4c601ace3aef61f32f91156`、expiry=`2026-11-19T06:41:15Z`；其中P2-11 output report为8/8，Task report为58 committed/0 working paths、11 rows、19 checks、0 issues，全部18份machine/trace JSON为PASS。故P2-08/09/10/11依赖、提交拓扑与provider证据一致，Diff base冻结为上述HEAD。

启动范围审查确认原计划卡需要补齐两项：Task lifecycle会修改current phase/Milestone/index，故加入`IMPACT-PHASE`及其required documents；“同一KPI”不能依靠Benchmark层复制公式，故加入`IMPACT-REPORTING`与两份既有KPI Python路径，只允许抽取公共pure schedule metrics并以P2-11回归证明KPI v2/Export字节不变。`benchmarks/baselines/**`在首个实现文件前展开为三个精确v1路径；不引入Schema/dependency/ADR，不修改P2-09 assets、P2-10 algorithms、P2-11 exporter或任何Solver/Validator语义。Activation-only差异只允许命中`IMPACT-PHASE/IMPACT-DOCS`；完整实现最终按七个声明Impact Rule重新计算。P2-13/14与P3未启动。

## Local implementation evidence — 2026-08-21

已形成strict `benchmark-profile-set.v1`、`benchmark-report.v1`、`benchmark-baseline.v1`、deterministic source-shaped generator、正式Raw→Import→Quality→Expansion→Snapshot→Problem assembler、Global与五个Reference同Problem比较及公共pure schedule KPI。XS/S/M固定为1次warm-up加3次measured replay，三个不可覆盖v1 baseline记录environment/problem/complexity/quality/timing/memory；correctness/Validator/baseline drift硬失败，CP-SAT劣于reference只产生`BENCHMARK_WARNING`，跨环境只适用absolute development ceiling。

本地focused=`27 passed`、full repository=`466 passed`，XS/S/M BenchmarkReport均为8/8 PASS；P2-11 KPI v2/export回归为8/8且历史输出不变，全部历史machine reports PASS，Ruff/Pyright为0问题，Compose与build成功。Full docs与Task diff治理为142 docs、49 paths、7 rows、19 checks、0 issues，`git diff --check`及冻结/禁止路径复核PASS。CI已用真实`run_benchmark.py --profile xs`替代deferred hook并将report纳入artifact，S/M按本地policy保留。Exact implementation provider evidence尚待本Task收口，因此status仍为`in_progress`；P2-13/14、P3、L/XL与Production阈值均未启动。
