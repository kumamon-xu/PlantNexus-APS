---
doc_id: TASK-P2-12
title: BenchmarkRunner and XS S M Profiles
status: planned
spec_version: 0.3.0
phase: P2
normative: true
source_sections: [45, 51, 52, 53, 54, 55, 56, 57, 58, 75, 76, 89]
last_reviewed: 2026-08-20
---

# TASK-P2-12 — BenchmarkRunner and XS S M Profiles

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-009, REQ-012, REQ-014, REQ-015

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-VER-001

Depends on: TASK-P2-08, TASK-P2-09, TASK-P2-10, TASK-P2-11

Start gate: Global Strategy、correctness scenarios、Reference Schedulers、report/export均`done`；固定hardware/environment capture、profiles/threshold policy和Diff base。

Goal: 实现BenchmarkRunner与versioned XS/S/M profiles，在同一Problem/Validator/KPI上比较CP-SAT和五个reference schedulers，并记录Gate A全部规模、时间、质量、内存和验证字段。

Inputs: P2 scenarios/export、solver/reference schedulers、BenchmarkReport contract、performance gates、OPEN-011/012边界。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `benchmarks/profiles.yaml`、`benchmarks/baselines/**`、`backend/app/simulation/benchmarks/__init__.py`、`backend/app/simulation/benchmarks/runner.py`、`backend/app/simulation/benchmarks/reporting.py`、`scripts/run_benchmark.py`、`.github/workflows/ci.yml`、`backend/tests/contract/test_benchmark_contract.py`、`backend/tests/integration/test_benchmark_runner.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；所有glob在进入in_progress前展开为精确paths。

Files forbidden to change: Solver/Validator constraint semantics、Production SLA/capacity、L/XL release profiles、P3 state/publish、P4 disruption、历史baseline覆盖。

Implementation steps: 定义profiles/BenchmarkReport；采集problem/model counts、build/first feasible/solve/objective/bound/gap/memory/validator/hardware；同场景跑global+references；correctness-first判定/BENCHMARK_WARNING；PR XS、local/nightly S/M命令与CI artifact；固定baseline且不手工覆盖。

Outputs: BenchmarkRunner、XS/S/M profiles/baselines、CLI、reports、CI hook activation和comparison evidence。

Documentation impact: required

Documents to update: `docs/simulation/benchmark-harness.md`、`docs/simulation/performance-gates.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/domain/kpi-contract.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、本Task卡。

Documentation impact rationale: P2 Gate的XS/S/M和provider artifact必须有版本化profile、环境、报告字段及不外推Production的判定规则。

Change-impact matrix rows reviewed: `IMPACT-BENCHMARK`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-004/005/009/012/014/015→TASK-P2-12→TEST-BENCHMARK/REFERENCE-SCHEDULER/SCENARIO-REPLAY/SOLVER-UPGRADE→XS/S/M reports/baselines/provider artifacts。

Schema changes: BenchmarkReport machine schema may be required；若新增，先在卡内登记exact path、set version、compatibility和contract tests；不得隐式JSON shape。

Migration: none。

Dependency changes: none expected；若memory采集需新dependency，先拆分/ADR/exact pin，不在实现中临时引入。

ADR impact: benchmark baseline建立不新增ADR；solver/profile/threshold语义变化或显著回归豁免必须ADR。OPEN-012未关闭前无Production threshold。

Error behavior: Validator/correctness failure硬失败；unknown/timeout如实记录；CP-SAT劣于reference产生warning；缺字段/硬件/provenance拒绝baseline；不得以性能抵消错误。

Tests: TEST-BENCHMARK、TEST-REFERENCE-SCHEDULER、TEST-SCENARIO-REPLAY、TEST-SOLVER-UPGRADE；runner/report contract、profile validation、determinism、warning/threshold、CI PR hook和artifact tests。

Benchmark impact: 本Task本身建立XS/S/M开发/仿真baseline；记录所有Gate字段但明确不是Production SLA/capacity，历史baselineimmutable/versioned。

Simulation scenarios: P2 correctness matrix + versioned XS/S/M synthetic scenarios；L/XL和disruption不在本Task。

Acceptance commands: `uv run pytest -q backend/tests/contract/test_benchmark_contract.py backend/tests/integration/test_benchmark_runner.py backend/tests/integration/test_ci_contract.py`；`uv run python scripts/run_benchmark.py --profile xs --report build/benchmarks/TASK-P2-12-xs.json`；`uv run python scripts/run_benchmark.py --profile s --report build/benchmarks/TASK-P2-12-s.json`；`uv run python scripts/run_benchmark.py --profile m --report build/benchmarks/TASK-P2-12-m.json`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P2/TASK-P2-12-benchmark-runner-xs-s-m.md --check-diff --report build/traceability/TASK-P2-12-report.json`；`git diff --check`。

Artifacts: versioned profiles/baselines、XS/S/M BenchmarkReports、CI contract/report和Task report。

Provider evidence: exact SHA required `validate`必须实际运行PR/XS benchmark并上传report；S/M如不适合required job须记录独立authorized run/artifacts；核验run/job/steps/artifact digest/expiry和required context。

Completion conditions: XS/S/M全部报告字段真实且Validator PASS；reference comparison完成；CI provider至少XS exact evidence，S/M有可核验provider/local policy证据；docs/trace/provider闭环；不作Production承诺。

Explicitly excluded: L/XL/stress release gate、Production SLA/capacity、dynamic disruptions、P3/P4。

PROD_OPEN: OPEN-011/012保持OPEN；结果不得关闭规模/性能生产阈值。

SIM_ASSUMPTIONS: profile/size/distribution/hardware assumptions显式versioned并登记，不能成为Production defaults。

Rollback: baseline不覆盖；runner/profile错误发布新version并保留旧结果；CI regression保留失败artifact，禁止删除或降低correctness Gate。
