---
doc_id: TASK-P1-11
title: Common Ingress Pipeline and P1 Gate Evidence
status: in_progress
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [0, 9, 10, 23, 24, 63, 65, 66, 73, 74, 93]
last_reviewed: 2026-08-20
---

# TASK-P1-11 — Common Ingress Pipeline and P1 Gate Evidence

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009, REQ-011, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, ENG-ARCH-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-03～TASK-P1-10

Goal: 用单一 application pipeline编排 Adapter/Synthetic source → Raw Staging → Normalization → Data Validation → Order Expansion → PlanningSnapshot → PlanningProblem，并生成可供 P1 Exit Gate审计的 deterministic machine report和 CI artifact。

Inputs: TASK-P1-03～10 的 versioned contracts/implementations、`SIM-P1-INGRESS-001`、P1 Gate exact rejection cases、phase-aware CI。

Diff base: ea56c3867651c0f03306e66936fd649526049319

Files allowed to change: `backend/app/application/__init__.py`、`backend/app/application/import_pipeline.py`、`backend/app/application/p1_gate_report.py`、`backend/app/simulation/generators/package_generator.py`、`backend/tests/integration/test_p1_common_ingress.py`、`backend/tests/contract/test_p1_exit_rejections.py`、`backend/tests/simulation/test_p1_pipeline_replay.py`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`、生成但不提交的 `build/validation/TASK-P1-11-p1-pipeline.json`、`build/validation/TASK-P1-11-rule-contracts.json`、`build/validation/TASK-P1-11-simulation-contracts.json`、`build/validation/TASK-P1-11-golden.json`、`build/validation/TASK-P1-11-validator-mutations.json`、`build/validation/TASK-P1-11-engineering.json` 与 `build/traceability/TASK-P1-11-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: 下游各模块的业务语义、Schema/registry、P0/P1 fixtures、database migrations、API/product endpoints、Solver/Strategy/Validator、P2、测试期望弱化或绕过 staging/normalization。

Implementation steps: application service只调用公开 protocols并传递 immutable artifacts/versions；ReferenceFileAdapter和Synthetic Generator从 staging后使用同一函数链；两次运行同 Scenario+seed并对比 import bytes/hash、snapshot bytes/hash、problem bytes/hash；四个 rejection fixture走相同入口并核对 exact code；报告记录 versions/entity counts/source/synthetic/code commit与边界；CI执行全部 P0/P1回归、machine report、governance、build和 artifact upload，不声称 Solver/Production。

Outputs: common-ingress application service、`p1-data-pipeline-report.v1`、E2E/negative/CI evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/planning-problem.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/domain/error-model.md`、`docs/operations/README.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/simulation/synthetic-generator-and-determinism.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-11-common-ingress-pipeline-and-gate-evidence.md`。

Documentation impact rationale: 首次形成跨模块产品链路、phase machine report与 CI gate，必须同步端到端、双通道、错误、隔离、质量和追踪事实。

Change-impact matrix rows reviewed: `IMPACT-APPLICATION`、`IMPACT-SIM-GENERATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/002/003/009/011/012及列出的 NFR/ENG → TASK-P1-11 → TEST-P1-COMMON-INGRESS/TEST-SCENARIO-REPLAY/TEST-SNAPSHOT-REPLAY-001/TEST-PROBLEM-REPLAY-001/TEST-DATA-QUALITY-001 → machine report、CI artifact；明确无 Solver/production evidence。

Schema changes: none。

Migration: none；使用既有 staging/snapshot migrations，E2E test在隔离 test DB执行。

Error behavior: 任一 stage失败立即形成所属结构化报告并停止下游；route cycle/missing resource/unit error/missing duration exact code不被 application包装成 SYSTEM_ERROR；partial writes transactionally回滚。

Tests: `TEST-P1-COMMON-INGRESS`、`TEST-SCENARIO-REPLAY`、`TEST-SNAPSHOT-REPLAY-001`、`TEST-PROBLEM-REPLAY-001`、`TEST-DATA-QUALITY-001`、`TEST-SIM-ISOLATION`；两种 source parity、two-run hashes、四负例、partial failure/idempotency、provenance完整与 no-shortcut scan。

Benchmark impact: 报告可记录每 stage elapsed/entity counts但不是 Solver Benchmark或生产 SLA；OPEN-012保持 OPEN。

Simulation scenarios: `SIM-P1-INGRESS-001` 完整走正式链；Production target/DB交叉显式拒绝。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/integration backend/tests/property backend/tests/simulation backend/tests/golden backend/tests/validation`；`uv run python -m app.application.p1_gate_report --root . --scenario fixtures/synthetic/SIM-P1-INGRESS-001 --repeat 2 --report build/validation/TASK-P1-11-p1-pipeline.json`；`uv run pytest -q backend/tests/contract/test_p1_exit_rejections.py`；`uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P1-11-rule-contracts.json`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P1-11-simulation-contracts.json`；`uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P1-11-golden.json`；`uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P1-11-validator-mutations.json`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P1-11-engineering.json`；`docker compose --env-file .env.example config --quiet`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-11-common-ingress-pipeline-and-gate-evidence.md --check-diff --report build/traceability/TASK-P1-11-report.json`；`git diff --check`；`uv build`。

Artifacts: `p1-data-pipeline-report.v1`、pytest/migration/no-shortcut结果、CI uploaded artifact、traceability report。

Completion conditions: Adapter与Synthetic从 staging后调用同一实现链；same scenario+seed的 import/snapshot/problem bytes与hash均相同；四拒绝 exact；partial failure/isolation/idempotency通过；CI/full/diff/build PASS且无 Solver/P2。

Explicitly excluded: 产品 API/Worker调度、CpSatBackend/Solver/Validator、ScheduleVersion/Export、Production deployment/readiness、P2。

PROD_OPEN: OPEN-001～015 均不关闭；Reference/Synthetic E2E不是生产接口验收。

SIM_ASSUMPTIONS: 只使用 versioned/registered P1 Scenario assumptions，不向 Production policy传播。

Rollback: application orchestration可回退但不得绕过任何 stage；machine/CI失败历史保留，旧 Snapshot/Problem hash不重写。

## Completion evidence

### Activation evidence

- 2026-08-20（Asia/Hong_Kong）：TASK-P1-03～10均为`done`，`main`与`origin/main`同步且working tree干净；以完整HEAD `ea56c3867651c0f03306e66936fd649526049319`固定immutable Diff base并进入`in_progress`。
- Scope precheck发现本Task的governance矩阵强制文档`docs/architecture/technology-stack.md`、`docs/milestones/README.md`、`docs/tasks/TASK_TEMPLATE.md`原未列入允许范围，且既有generator只公开直达Import的`generate()`，不能在不绕过Raw Staging的前提下进入common ingress。业务实现前先把三份强制文档、`package_generator.py`的公开staging handoff和`IMPACT-SIM-GENERATOR`加入范围；Goal、Diff base、Schema、fixture、依赖与P1/P2边界不变。
- Provider证据闭环前Task保持`in_progress`；只允许提交本卡43条union diff路径及七条已审查impact rows。

### Local implementation acceptance

- 唯一application编排为`Adapter/Synthetic → Raw Staging → Normalization → Data Validation → Order Expansion → immutable PlanningSnapshot → solver-neutral PlanningProblem`。Generator新增公开`prepare_batch()`并由既有`generate()`复用；Reference side只用临时、等价的fixture-local CSV驱动正式`ReferenceFileAdapter`，不形成Production binding。Application不捕获或改写各stage结构化错误，也不导入API、Infrastructure、Backend、Strategy、Validator、OR-Tools或SQLAlchemy捷径。
- `p1-data-pipeline-report.v1`在`SIM-P1-INGRESS-001@1.0.0`、generator `1.0.0`、seed `20260820`下完成14/14 checks。Import含16个collections/49 records，dataset hash=`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`、package ID=`import-9eea9bd41216b3a2b337a83f2b6f5438a287f219251168ce8d574f4b9fb6b2c6`、quality report ID=`import-quality-600341c55f6f8511bd25387fcf2a9f3ff62d2c72901f8bb454df32636b4cafbe`；expansion hash=`sha256:7a5192e12414cead7877bd1133cfe62d364468d1e261da96e0a43cc8d938be1f`。
- Snapshot ID=`planning-snapshot-v2-090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`、hash=`sha256:090e0e08e05bb569d0aae00461803cebd56f87444243484a3696126bfe510409`；Problem hash=`sha256:71c0b729dd2b08ba1d14d5a281029b8d9bc13596a90a5189fb20176e19f690da`、canonical bytes digest=`sha256:c3ff3f0cc810007da4dc251642896b0d8b6fab1f98d4d5bced743752904e9233`，含6个operation instances与4条precedence edges。Synthetic两次运行及Reference/Synthetic之间的Import、Snapshot、Problem bytes/hash均相同。
- 四个独立source mutation均在Data Validation停止且不调用下游：route cycle=`DATA_ERROR/ROUTE_CYCLE`、missing resource=`DATA_ERROR/MISSING_RESOURCE`、unit error=`DATA_ERROR/UNIT_CONVERSION_ERROR`、missing duration=`DATA_ERROR/MISSING_DURATION`。跨data-plane输入在Normalization前以`DATA_PLANE_MISMATCH`拒绝；未生成partial Snapshot/Problem。
- Local acceptance：`uv sync --locked` PASS；Ruff PASS；Pyright=`0 errors, 0 warnings, 0 informations`；Task聚焦suite=`17 passed`；exact rejection suite=`4 passed`；full repository=`271 passed`；P1 pipeline machine report=`14/14 PASS`；rule sheet、synthetic generator、Golden、mutation与engineering六份既有machine checks全部PASS；Docker Compose config、`git diff --check`与`uv build`均PASS。
- Governance：full docs=`PASS`（124 docs/30 roots/36 tests/15 OPEN/10 SIM/10 risks/22 tasks）；Task diff=`PASS`（43 paths/7 impact rows/0 issues），精确匹配`IMPACT-APPLICATION/SIM-GENERATOR/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`。P0 `engineering-skeleton-report.v1`中的`business_pipeline=NOT_IMPLEMENTED`只表示该冻结P0检查器自身不执行业务链，不是当前仓库全局状态；历史P0报告不重写，P1 report为本链权威证据。
- Boundary：无Schema/registry、migration、dependency/lock、fixture、Solver/Strategy/Validator、candidate schedule、API、Production readiness或P2变更。OPEN-001～015仍为`OPEN`，SIM-ASSUMPTION-001～010仍为`ACTIVE`，所有root继续`ALLOCATED`；implementation commit、GitHub run/job/artifact与protected-branch provider证据待提交并精确核验后回填。
