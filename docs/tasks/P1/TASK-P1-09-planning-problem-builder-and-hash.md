---
doc_id: TASK-P1-09
title: PlanningProblem Builder and Hash
status: done
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [13, 14, 24, 26, 73, 74, 89]
last_reviewed: 2026-08-20
---

# TASK-P1-09 — PlanningProblem Builder and Hash

Requirement IDs: REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-07, TASK-P1-08

Goal: 从 immutable Snapshot v2 构建现有 `planning-problem.v1` 可表达的 solver-neutral PlanningProblem，固定 builder/hash语义以满足 P1 replay gate；不创建任何 Solver、decision variable或求解结论。

Inputs: PlanningSnapshot v2、PlanningProblem v1 Schema、ADR-0003/0008、C-001～C-011 input requirements、explicit tick/horizon config。

Diff base: 100e2573a76462ad2a0751e9e4aae7990c9048dd

Files allowed to change: `backend/app/planning/problem/__init__.py`、`backend/app/planning/problem/contracts.py`、`backend/app/planning/problem/builder.py`、`backend/app/planning/problem/hashing.py`、`backend/tests/unit/test_planning_problem_builder.py`、`backend/tests/property/test_planning_problem_properties.py`、`backend/tests/golden/test_p1_problem_replay.py`、生成但不提交的 `build/validation/TASK-P1-09-engineering.json` 与 `build/traceability/TASK-P1-09-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: `schemas/json/planning-problem.schema.json`、Snapshot/Import contracts、Constraint/Objective semantics、`planning/backends/**`、`planning/strategies/**`、ScheduleValidator、OR-Tools/dependencies、API、Exporter、Benchmark baseline。

Implementation steps: builder只读 Snapshot且显式接收 builder version/tick/horizon；COMPLETED排除、RUNNING/resource options/edges/unavailable intervals/capabilities按合同投影；duration tick使用整数 ceiling但Problem保留权威秒；stable sort/canonical serialization；problem_hash排除 self hash/运行噪声并包含 Snapshot identity、builder/rule/config；调用既有 pure precheck；若 v1不能表达必需 P1事实则停止并提 Schema/ADR修订，不在代码内藏字段。

Outputs: solver-neutral builder、problem hash vectors、property/Golden replay evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-snapshot.md`、`docs/planning/constraint-catalog.md`、`docs/planning/solver-backend-contract.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/module-boundaries.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/adr/ADR-0003-solver-neutral-planning-problem.md`、`docs/adr/README.md`、`docs/quality/property-tests.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-09-planning-problem-builder-and-hash.md`。

Documentation impact rationale: 首次真实 Problem builder/hash实现会固定 Snapshot→Problem映射、replay和后续 P2 consumer边界。

Change-impact matrix rows reviewed: `IMPACT-PROBLEM`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-09 → TEST-PROBLEM-REPLAY-001/TEST-CONTRACT-001 → builder/hash vectors/property/Golden artifacts；Solver/Validator仍 `PLANNED`。

Schema changes: none；消费 planning-problem.v1。任何合同字段/语义变化需要新 Problem version、ADR和 replay，不在本 Task静默修改。

Migration: none。

Error behavior: invalid Snapshot、quality/provenance mismatch、unsupported capability、missing Problem-required fact、invalid horizon/tick/reference/duration明确为 DATA_ERROR或 MODEL_INVALID；不得转为 INFEASIBLE。

Tests: `TEST-PROBLEM-REPLAY-001`、`TEST-CONTRACT-001`；same input hash、key/order/noise、version/config change、running/completed、candidate duration/ticks、edge/calendar/reference、round-trip/property与 no-OR-Tools import。

Benchmark impact: PlanningProblem行为变更按规则审查；P1仅记录 builder entity counts/build time，因无 Solver不形成 BenchmarkReport或性能阈值。

Simulation scenarios: 以 P1 canonical synthetic fixture重放；P0 hand fixture只作对照，不直接提升其 vocabulary。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/planning/problem backend/tests/unit/test_planning_problem_builder.py backend/tests/property/test_planning_problem_properties.py backend/tests/golden/test_p1_problem_replay.py`；`uv run pyright backend/app/planning/problem backend/tests/unit/test_planning_problem_builder.py backend/tests/property/test_planning_problem_properties.py backend/tests/golden/test_p1_problem_replay.py`；`uv run pytest -q backend/tests/unit/test_planning_problem_builder.py backend/tests/property/test_planning_problem_properties.py backend/tests/golden/test_p1_problem_replay.py backend/tests/contract/test_schema_contracts.py`；`uv run python -m app.infrastructure.contract_check --root . --report build/validation/TASK-P1-09-engineering.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-09-planning-problem-builder-and-hash.md --check-diff --report build/traceability/TASK-P1-09-report.json`；`git diff --check`；`uv build`。

Artifacts: Problem hash vectors/Golden/property results、engineering no-Solver report、traceability report。

Completion conditions: same Snapshot/config/versions产生 byte-identical Problem/hash；变化敏感性与 round-trip通过；Problem无 ORM/API/OR-Tools类型；ADR边界未改变或已先停止升级；docs/trace/governance PASS。

Explicitly excluded: CpModel/IntervalVar、GlobalCpSatStrategy、Solver status/solution、ScheduleValidator、objective、Benchmark、P2能力。

PROD_OPEN: OPEN-004/005/006/007/009/012/014/015 保持 OPEN；Problem消费显式事实而不补猜。

SIM_ASSUMPTIONS: tick/horizon必须来自 versioned Scenario/config；不得成为 Production默认值。

Rollback: builder version/hash不可重解释历史；回退保留旧 version与 artifacts，语义修复发布新 builder/Problem version并重放。

## Completion evidence

### Implementation and provider closure

- 时间：2026-08-20（Asia/Hong_Kong）。Task=`done`；immutable Diff base=`100e2573a76462ad2a0751e9e4aae7990c9048dd`，implementation commit=`e8c59547857d2eeace1c9f8b453a5a294cca5ef7`，已按用户授权直接push受保护的`main`。提交前Task diff report为30 changed paths、5 impact rows、0 issues；implementation artifact精确记录committed-range=`30`、working-tree=`0`。
- Builder/hash：`planning-problem.v1`、`planning-problem-builder.v1`、`planning-problem-hash-projection.v1`、`canonical-json.v1`。Builder只接受`verify_snapshot`通过的immutable Snapshot v2及显式version/tick/horizon；horizon start精确等于cutoff。Canonical ordering覆盖resource、active operation/candidate、edge、relevant calendar interval和platform capability；hash排除self与未登记runtime noise，Snapshot content ID绑定rule/facts/upstream versions。
- 固定向量：Snapshot hash=`sha256:44f422f81490159c4b0343a52aadd7991191684fa3b25394a0dd8b8a1b7e591a`，Problem hash=`sha256:6e4afffebf464de5c156094c894dccb5fe3efc712449f8583bcd91e1694dff72`，canonical bytes=`1827`，bytes digest=`sha256:1f00ad7a856395328e9eb2c70afe8fe5878d69c3d8618ae7ef45bca34ef08645`；counts=`1 resource / 2 active operations / 1 edge / 0 relevant intervals`。
- Projection/error：RUNNING保留actual start/assigned resource/remaining seconds；权威candidate seconds不改写，integer ceiling只做horizon完整性检查；COMPLETED过滤。Completed-active edge、horizon-intersecting active lock和multi-factory在v1不可表达时返回module-local`UNSUPPORTED_PROBLEM_FACT/UNSUPPORTED_CAPABILITY`；invalid Snapshot/config/fact与built output分别保持DATA_ERROR/MODEL_INVALID，任何路径都不产生INFEASIBLE。Content-hashed active DAG cycle、tampered bytes/hash也明确拒绝。
- Tests：10 unit + 3 fixed-seed Hypothesis properties + 2 Golden；seeds=`20260820/20260821/20260822`，max examples=`48/32/32`，无failure/minimized corpus。Task-focused suite（含现有TEST-CONTRACT-001）=`34 passed in 1.26s`；full repository regression=`253 passed in 8.50s`。Ruff PASS；Pyright=`0 errors, 0 warnings, 0 informations`；no-OR-Tools/ORM/API/Infrastructure source scan PASS。
- Informational build probe：Python `3.12.13`，同一small canonical vector执行200次完整build+verify，median=`1.090 ms`、p95=`1.177 ms`；只记录1/2/1/0 entity counts与本机诊断，不设gate/SLA，不形成BenchmarkReport。
- Acceptance：`uv sync --locked` PASS（63 packages）；Task Ruff/Pyright/Pytest PASS；engineering report PASS（6 checks，`solver=NOT_INSTALLED`、business pipeline/distributed persistence/production deployment均未claim）；full docs PASS（124 docs/30 roots/36 tests/15 OPEN/9 SIM/10 risks/22 tasks）；Task diff PASS（30 paths/5 impact rows/0 issues）；`git diff --check` PASS；`uv build`成功生成sdist与wheel。
- Provider：GitHub Actions push run [`32315513504`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32315513504)，attempt=`1`、event=`push`、head SHA=`e8c59547857d2eeace1c9f8b453a5a294cca5ef7`、status/conclusion=`completed/success`；required `validate` job [`96266776018`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32315513504/job/96266776018)及全部步骤成功。Artifact `9387907707` / `plantnexus-ci-evidence-32315513504`未过期，size=`6245` bytes，expires_at=`2026-11-17T23:59:15Z`；provider与下载ZIP digest均为`sha256:1ede296252bb04e9015240e13222eaf4ee783bc6e7582012cac0a441fd624568`。Artifact含Task trace report及5份validation machine report且全部PASS；Task report精确记录本Task、implementation SHA、Diff base、30 committed paths、5 matched impact rows与0 issues。公开branch metadata确认`main`受保护。
- Trace：REQ-002/003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-09 → TEST-PROBLEM-REPLAY-001 + TEST-CONTRACT-001 → builder/hash fixed vector/property/Golden/engineering/trace reports。Schema、dependency/lock、Snapshot/Import、C-ID/Objective、Backend/Strategy/Validator/API/Exporter/Benchmark baseline均未修改；ADR-0003/0008 review确认既有决定未变，不新增ADR。
- Required-document review without edit：`docs/governance/change-impact-matrix.md` machine rules无需变化；`traceability-rules.md`证据链语义未变；`prod-open-register.md`中OPEN-004/005/006/007/009/012/014/015及其余项无closure evidence而保持OPEN；`sim-assumption-register.md`无新增/修改且tick/horizon只来自显式test config；`documentation-consistency-checks.md`的validator/command语义未改；`milestones/README.md`的phase transition规则未改；`TASK_TEMPLATE.md`字段/验收规则未改。它们均已纳入Task允许范围并完成审查。
- Rollback/边界：不修改Problem v1 Schema或历史hash；语义修复必须发布新builder/Problem/hash version并重放。当前无Solver、candidate schedule、PlanningRun、ScheduleValidator、common ingress、P1-10或P2实现；建议下一项执行P1-10，但本Task闭环未自动启动它。
