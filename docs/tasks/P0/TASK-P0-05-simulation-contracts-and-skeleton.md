---
doc_id: TASK-P0-05
title: Simulation Contracts and Skeleton
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [10, 37, 38, 39, 40, 41, 42, 70, 71, 104]
last_reviewed: 2026-08-19
---

# TASK-P0-05 — Simulation Contracts and Skeleton

Requirement IDs: REQ-011, REQ-012, REQ-013, REQ-014, REQ-015

NFR / ENG IDs: NFR-DET-001, NFR-ISO-001, NFR-TRC-001

Depends on: TASK-P0-03, TASK-P0-04

Goal: 建立 FactoryProfile/ScenarioSpec/manifest Schema、Simulation 模块边界和 deterministic generator protocol skeleton。

Inputs: `docs/simulation/**`、dual-channel architecture、schema index。

Diff base: e6ec5a4ca24ef65b9d48953cdbdfa377f8ba7163

Files allowed to change: `/backend/app/__init__.py`、`/backend/app/planning/validation/rule_sheet.py`、`/backend/app/simulation/profiles/__init__.py`、`/backend/app/simulation/profiles/contracts.py`、`/backend/app/simulation/scenarios/__init__.py`、`/backend/app/simulation/scenarios/contracts.py`、`/backend/app/simulation/generators/__init__.py`、`/backend/app/simulation/generators/contracts.py`、`/backend/app/simulation/generators/determinism.py`、`/backend/app/simulation/generators/package_contract.py`、`/backend/app/simulation/generators/contract_check.py`、`/backend/tests/contract/test_schema_contracts.py`、`/backend/tests/contract/test_rule_contracts.py`、`/backend/tests/simulation/test_simulation_contracts.py`、`/schemas/data_dictionary.yaml`、`/schemas/scenario/factory-profile.schema.json`、`/schemas/scenario/factory-profile.synthetic.json`、`/schemas/scenario/scenario-spec.schema.json`、`/schemas/scenario/scenario-spec.synthetic.json`、`/schemas/scenario/scenario-manifest.schema.json`、`/schemas/scenario/scenario-manifest.synthetic.json`、`/pyproject.toml`、仅在依赖图确有变化时更新的 `/uv.lock`、生成但不提交的 `/build/validation/TASK-P0-05-simulation-contracts.json` 与 `/build/traceability/TASK-P0-05-report.json`，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: `/schemas/json/import-package.schema.json`、`/schemas/json/planning-snapshot.schema.json`、`/schemas/json/planning-problem.schema.json` 等既有发布 artifact；`/fixtures/**` 与正式 `SIM-MINIMAL-001`；`/backend/app/simulation/execution/**`、`/backend/app/simulation/baselines/**`、`/backend/app/simulation/benchmarks/**` 行为实现；CpModel、IntervalVar、Solver backend、PlanningProblem/Snapshot/Normalization builder、生产配置/数据库/API/ORM/Worker、真实 Benchmark 与 P1+ pipeline。

Implementation steps: 以 set-level additive 方式发布 FactoryProfile/ScenarioSpec/ScenarioManifest v1 Schema 和纯标准库 TypedDict/Protocol；区分 contract version、asset/generator version 与 schema set version；以显式 seed、命名空间和 generator version 派生无全局随机状态的 layer seed；提供仅生成空 Standard Import v1 envelope 的 deterministic package primitive 和 canonical JSON/SHA-256；manifest 记录 scenario/profile/generator/seed/generated_at/dataset hash，且 generated_at 不参与 dataset hash；Development/Test/Benchmark target 可用，Production target 必须显式拒绝；required capability 复用既有 capability registry，未知/重复/unsupported 声明显式失败。规则完整性检查只解除对全局 `1.1.0` 的硬编码，不修改 C-ID、状态、错误或 capability 语义。

Outputs: versioned Simulation schemas、module skeleton、determinism/isolation tests。

Documentation impact: required

Documents to update: `/docs/current_phase.md`、`/docs/contracts/README.md`、`/docs/contracts/import-and-normalization.md`、`/docs/contracts/schema-index.md`、`/docs/contracts/schema-versioning.md`、`/docs/core/glossary.md`、`/docs/domain/domain-model.md`、`/docs/architecture/configuration-environments-and-isolation.md`、`/docs/architecture/module-boundaries.md`、`/docs/architecture/provenance-and-versioning.md`、`/docs/architecture/repository-layout.md`、`/docs/architecture/simulation-first-dual-channel.md`、`/docs/architecture/technology-stack.md`、`/docs/planning/constraint-catalog.md`、`/docs/planning/reference-schedulers.md`、`/docs/planning/schedule-validator.md`、`/docs/planning/solver-backend-contract.md`、`/docs/quality/benchmark-regression.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/quality/validator-mutation-tests.md`、`/docs/simulation/README.md`、`/docs/simulation/benchmark-harness.md`、`/docs/simulation/execution-simulator-and-disruptions.md`、`/docs/simulation/factory-profile.md`、`/docs/simulation/performance-gates.md`、`/docs/simulation/scenario-library-and-matrix.md`、`/docs/simulation/scenario-spec-and-provenance.md`、`/docs/simulation/synthetic-generator-and-determinism.md`、`/docs/adr/README.md`、`/docs/milestones/README.md`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: Profile、Scenario、Generator、provenance 和隔离均属于版本化 Simulation 合同。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-VALIDATOR`、`IMPACT-SIM-PROFILE`、`IMPACT-SIM-SCENARIO`、`IMPACT-SIM-GENERATOR`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: REQ-011/012 与 NFR-DET-001/NFR-ISO-001/NFR-TRC-001 → TASK-P0-05 → TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION/TEST-CONTRACT-001 → FactoryProfile/ScenarioSpec/ScenarioManifest v1、pure generator contracts、empty deterministic Import package 与 machine reports；REQ-013/014/015 只获得可供未来 Execution Simulator/Benchmark/Reference Scheduler 消费的 versioned Scenario manifest/provenance boundary，行为实现继续 `PLANNED`。同步 ENG-VER-001 的 schema set `1.2.0` 证据，不宣称 P1 canonical records、Snapshot/Problem hash、Solver 或 Benchmark 已形成。

Schema changes: schema set `1.1.0` → `1.2.0`（set-level additive）；保留全部既有 JSON/YAML artifact 与 URN，新增 `factory-profile.v1`、`scenario-spec.v1`、`scenario-manifest.v1`。三份根对象使用 JSON Schema Draft 2020-12、稳定 URN、拒绝未知字段、无业务默认值，`synthetic_only/synthetic=true` 且 target environment 排除 Production。

Migration: 无数据库、持久化 Scenario consumer、Fixture 或历史 run artifact；全部 `1.1.0` artifact 原样保留。新 consumer 必须显式要求 v1 Simulation document，不做 alias/隐式升级；未来语义变化发布新 document/asset/generator version。

Error behavior: JSON Schema 对 missing/wrong contract version、missing/negative seed、`synthetic_only=false`、Production target 和未知字段拒绝；pure contracts 对 invalid identity/version/seed、Production target、未知/重复/unsupported capability 以稳定 simulation error code 或既有 capability code 显式失败，禁止回退生产默认值或静默忽略。

Tests: `TEST-CONTRACT-001` 扩展三份 Schema/样本、schema set/data dictionary；`TEST-SCENARIO-REPLAY` 验证 same profile/scenario/generator/seed 得到 byte-identical empty Import package 与相同 dataset hash、版本/seed 变化被 provenance/hash 捕获、命名 layer seed 与调用顺序隔离；`TEST-SIM-ISOLATION` 验证 Schema/pure target guard/Import envelope 均拒绝 Production 混入并验证 capability 显式拒绝；保留并重跑 P0-04 rule tests。

Benchmark impact: 仅提供未来 Benchmark/Reference Scheduler/Execution Simulator 可引用的 Scenario manifest/provenance boundary；不创建 profile baseline、不运行 Solver、不生成 runtime/memory/quality 数值，不作生产 SLA 或性能宣称。

Simulation scenarios: 仅 `SCHEMA-PROFILE-P0-05` / `SCHEMA-SCENARIO-P0-05` / manifest Schema samples 与空 records replay primitive；不创建 Fixture，不创建或引用正式 `SIM-MINIMAL-001`，该场景继续由 TASK-P0-06 独占。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app backend/tests/contract backend/tests/simulation`；`uv run pyright backend/app backend/tests/contract backend/tests/simulation`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-05-simulation-contracts.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-05-simulation-contracts-and-skeleton.md --check-diff --report build/traceability/TASK-P0-05-report.json`；`uv build`。

Artifacts: 三份 versioned Simulation Schema 与 synthetic samples、profile/scenario pure types、七层 Generator protocols、seed/canonical package primitives、TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION、ignored simulation-contract/traceability reports。

Explicitly excluded: 任何非空工厂/订单/工艺生成逻辑、大规模 Generator、SIM-MINIMAL-001、Execution Simulator/Reference Scheduler/Benchmark 行为、Snapshot/PlanningProblem builder、Normalizer、Solver/Validator evaluator、API/DB/Worker。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`；重点审查 OPEN-003/004/011/012，Schema samples 与 empty package 不提供真实工厂拓扑、日历、历史数据或生产阈值。

SIM_ASSUMPTIONS: 复用 SIM-ASSUMPTION-001/002（synthetic-only profile 与显式 seed replay）和 SIM-ASSUMPTION-004/005 的能力拒绝/复杂度标签边界；所有 sample `synthetic_only=true`，不新增概率、规模默认值或正式 Scenario 假设。

Rollback: 新合同尚无 Fixture/consumer 时可移除三份 v1 Schema/sample、pure simulation modules并把 schema set metadata 恢复 `1.1.0`；一旦被 TASK-P0-06 或外部 artifact 消费，只能发布新版本并显式迁移，禁止覆盖已发布 v1 或修改历史 dataset hash。

## Completion evidence

Completed at: `2026-08-19T12:31:26+08:00`

### Delivered artifacts

- Schema set `1.2.0`：以 set-level additive 方式新增 [`factory-profile.v1`](../../../schemas/scenario/factory-profile.schema.json)、[`scenario-spec.v1`](../../../schemas/scenario/scenario-spec.schema.json)、[`scenario-manifest.v1`](../../../schemas/scenario/scenario-manifest.schema.json) 和三份 synthetic Schema samples；`pyproject.toml`、`app.SCHEMA_VERSION` 与 data dictionary 一致，全部 `1.0.0/1.1.0` JSON/YAML artifacts 保持原文件不变。
- Pure contracts：FactoryProfile/ScenarioSpec/Manifest TypedDict 与 semantic precheck；Topology/Routing/Order/Calendar/Material/ExecutionState/Lock 七层 Protocol；无 ORM/API/Pydantic/OR-Tools、PlanningProblem、Solver、Snapshot/Normalization builder 或生产配置。
- Determinism：`SeedMaterial` 以显式 root seed + Generator ID/version + 命名 namespace/label/index 派生，避免全局/可变 RNG；required capability 先按 set 语义 canonical sort。`canonical-json.v1` 输出 UTF-8 stable JSON，`dataset_hash=sha256(canonical Import bytes)`。
- Common ingress primitive：只生成合法 `import-package.v1` metadata envelope，`synthetic=true`、显式 `scenario_id`、`records={}`；manifest 的 `generated_at` 不参与 dataset hash。固定 sample hash 为 `sha256:cd0fb164704530e83197ec5cc806acc86dc8430f15e503c5840f898397fa9456`。
- Isolation/error：Development/Test/Benchmark 可建 context；Production target 返回 `SYNTHETIC_REFERENCE_IN_PRODUCTION`。未知/重复/unsupported capability 分别沿用既有稳定 code 并显式拒绝；Schema 同时拒绝 missing/negative seed、wrong version、unknown field 与 synthetic flag 反转。
- Tests/reports：[`test_simulation_contracts.py`](../../../backend/tests/simulation/test_simulation_contracts.py) 形成 10 项 TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION tests；ignored `simulation-contract-report.v1` 为 PASS、8 checks、0 issues，`traceability-report.v1` 为 PASS、65 paths、11 impact rows、0 issues。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/checked 17 packages，runtime dependency 空集与 lock 无漂移。 |
| `uv run ruff check backend/app backend/tests/contract backend/tests/simulation` | 0 | PASS；`All checks passed!`。 |
| `uv run pyright backend/app backend/tests/contract backend/tests/simulation` | 0 | PASS；0 errors、0 warnings、0 informations。 |
| `uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation` | 0 | PASS；41 passed（8 governance unit + 23 contract + 10 simulation）。 |
| `uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P0-05-simulation-contracts.json` | 0 | PASS；8/8 determinism/isolation checks、0 issues、0 record collections。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；107 docs、30 roots、30 trace rows、27 Test IDs、15 OPEN、5 SIM assumptions、10 risks、9 Tasks。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-05-simulation-contracts-and-skeleton.md --check-diff --report build/traceability/TASK-P0-05-report.json` | 0 | PASS；65 paths、11 impact rows、32/32 required documents observed、0 missing refs、0 issues。 |
| `uv build` | 0 | PASS；成功构建 sdist 与 wheel。 |

验收后额外复核：`git diff --exit-code <Diff base> -- schemas/json schemas/rules` exit 0，证明既有发布 Schema/rule artifacts 未被改写；`git diff --check` exit 0（仅 Windows LF→CRLF working-copy 提示）；wheel 清单包含 9 个 `app/simulation/**` modules；P0-04 rule CLI 在 schema set `1.2.0` 下仍 PASS（active 11、deferred 7、capabilities 20、error codes 19、machines 3、states 27、transitions 42）。

### Documentation impact and traceability

Documentation impact: `required`。实际 diff 为 65 paths：11 个 package modules、3 个 tests、7 个 Schema/data-dictionary artifacts、`pyproject.toml` 与 43 份 Markdown。机器矩阵命中 `IMPACT-SCHEMA`、`IMPACT-VALIDATOR`、`IMPACT-SIM-PROFILE`、`IMPACT-SIM-SCENARIO`、`IMPACT-SIM-GENERATOR`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`；32 份 required review documents 全部实际更新，未使用“审查但不改”的豁免。

Traceability updates:

- REQ-011 / NFR-DET-001 → FactoryProfile v1 + seven-layer protocols + named seed/canonical Import/hash → TASK-P0-05 → TEST-SCENARIO-REPLAY → Schema/sample/pure modules/report；非空 generator 与 P1 pipeline 仍 `PLANNED`。
- REQ-012 / NFR-TRC-001 → ScenarioSpec/ScenarioManifest v1 → TASK-P0-05 → TEST-SCENARIO-REPLAY → stable sample hash/manifest；正式 Scenario Library、`SIM-MINIMAL-001`、code-commit/run/export audit 仍 `PLANNED`。
- NFR-ISO-001 → synthetic-only Schema + target/context/Import guards → TASK-P0-05 → TEST-SIM-ISOLATION；独立 DB、Simulation API 404、publish/export/deployment guard 仍 `PLANNED`。
- REQ-013/014/015 仅获得未来 Execution Simulator/Benchmark/Reference Scheduler 可引用的 Scenario identity/version/hash boundary；没有行为实现或完成证据，追踪矩阵保持 `PLANNED`。
- ENG-VER-001 → additive schema set `1.2.0`、历史 artifacts 保留、独立 contract/asset/generator/canonicalization versions 与 compatibility/migration statement。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`；尤其 Schema sample 不关闭 OPEN-003/004，empty records 不关闭 OPEN-002/013/015，manifest/hash 不关闭 OPEN-011/012。SIM_ASSUMPTIONS: 未新增，SIM-ASSUMPTION-001/002/004/005 获得机器字段但五项仍 `ACTIVE`。Risks: RISK-002/004/007 的早期控制增强，缺少真实 pipeline/DB/API evidence，因此 RISK-001～010 继续 `MONITORED`。Benchmark impact: 无 Solver/Problem/baseline/硬件数据，不生成性能报告或 SLA。Migration: 无 DB、consumer、正式 Fixture 或历史 run artifact，故 none。ADR: 仅落实 ADR-0001/0009，决定未改变，不新增 ADR。

Diff base 与验收时 Git HEAD 均为 `e6ec5a4ca24ef65b9d48953cdbdfa377f8ba7163`；报告 source counts 为 committed range 0、working tree 65。本 Task 未提交用户工作树。Rollback 在 TASK-P0-06 消费前可移除 additive artifacts 并恢复 schema metadata `1.1.0`；消费后必须新版本/显式迁移，不覆盖 v1 或历史 hash。
