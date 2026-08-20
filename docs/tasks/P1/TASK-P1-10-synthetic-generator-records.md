---
doc_id: TASK-P1-10
title: Synthetic Generator Canonical Records
status: in_progress
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [10, 37, 38, 39, 40, 41, 42, 43, 73, 74, 104]
last_reviewed: 2026-08-20
---

# TASK-P1-10 — Synthetic Generator Canonical Records

Requirement IDs: REQ-001, REQ-003, REQ-009, REQ-011, REQ-012

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02, TASK-P1-05, TASK-P1-06, TASK-P1-07

Goal: 实现七层 deterministic Synthetic Generator，使 versioned FactoryProfile/ScenarioSpec/seed 生成非空 canonical Import v2 records与 manifest/hash；Generator仍只输出 Standard Import，不得直接构造 Snapshot、Problem或Solver对象。

Inputs: FactoryProfile/ScenarioSpec contracts、canonical Import v2、unit/normalization/data-validation contracts、ADR-0001/0009、existing seed/canonical-json primitives。

Diff base: 11c6ca97882a3be5bf6eb25bab84f69d1dfe469c

Files allowed to change: `backend/app/simulation/generators/contracts.py`、`backend/app/simulation/generators/determinism.py`、`backend/app/simulation/generators/package_contract.py`、`backend/app/simulation/generators/topology.py`、`backend/app/simulation/generators/routing.py`、`backend/app/simulation/generators/orders.py`、`backend/app/simulation/generators/calendars.py`、`backend/app/simulation/generators/materials.py`、`backend/app/simulation/generators/execution_states.py`、`backend/app/simulation/generators/locks.py`、`backend/app/simulation/generators/package_generator.py`、`backend/app/simulation/generators/contract_check.py`、`backend/app/simulation/generators/__init__.py`、`backend/app/normalization/normalizer.py`、`backend/tests/unit/test_normalization.py`、`fixtures/synthetic/SIM-P1-INGRESS-001/factory-profile.json`、`fixtures/synthetic/SIM-P1-INGRESS-001/scenario-spec.json`、`fixtures/synthetic/SIM-P1-INGRESS-001/calculation-note.md`、`backend/tests/simulation/test_p1_synthetic_generator.py`、生成但不提交的 `build/traceability/TASK-P1-10-report.json` 与 `build/validation/TASK-P1-10-generator.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: P0 deterministic/infeasible fixtures、canonical/Scenario Schemas、Adapter/Staging/DataValidation行为、除`cycle_seconds_per_unit`按既有canonical duration合同分类之外的Normalization行为、Snapshot/Problem、Simulation execution/baseline/benchmark、API、Solver、Production config。

Implementation steps: 先把normalizer中遗漏的`cycle_seconds_per_unit`按其既有canonical字段/Schema/DataValidation语义纳入显式duration transform兼容表并增加直接回归测试，不改变字段、单位注册表或其他Normalization行为；每层只消费 immutable GenerationContext和命名 child seed；Profile提供全部 range/distribution，不在代码硬编码生产/通用默认；生成 topology/routing/orders/calendars/material/execution/locks records并由 package layer稳定合并；先产 source-shaped Standard Import输入再走公开 normalization/validation边界，不调用 Snapshot/Problem；manifest记录 versions/seed/generated_at，hash只覆盖 canonical package；Production target和unsupported capability显式拒绝；创建一个小型 versioned P1 synthetic regression asset并登记实际新 assumptions（如需要）。

Outputs: seven-layer generators、non-empty Standard Import v2 package、replay manifest/hash与 synthetic regression asset。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/architecture/data-authority.md`、`docs/domain/error-model.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/simulation/README.md`、`docs/simulation/factory-profile.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/synthetic-generator-and-determinism.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/performance-gates.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-10-synthetic-generator-records.md`。

Documentation impact rationale: Generator从 empty protocol升级为非空 versioned data producer，改变 Scenario/Profile/seed/hash与 common-ingress风险证据。

Change-impact matrix rows reviewed: `IMPACT-IMPORT`、`IMPACT-SIM-GENERATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/003/009/011/012、NFR-DET/TRC/ISO、ENG-ARCH/ERR/VER → TASK-P1-10 → TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION → versioned generator/source package/manifest/hash/fixture artifacts。

Schema changes: none；严格消费已发布 Profile/Scenario/Import contracts。Generator语义变化提升 generator/asset version，不借 schema set掩盖。

Migration: none；P0 empty/manual fixture artifacts只读，不迁移或覆盖。

Error behavior: invalid range/seed/version、unknown/duplicate/unsupported capability、Production target、生成后 normalization/data validation失败都结构化拒绝；不得删记录或改变约束使场景通过。

Tests: `TEST-SCENARIO-REPLAY`、`TEST-SIM-ISOLATION`；`cycle_seconds_per_unit`显式unit conversion regression、same input bytes/hash、layer call-order independence、seed/profile/generator version sensitivity、non-empty collection/reference validity、Production/unsupported rejection、no Planning/Solver import。

Benchmark impact: regression asset只验证 correctness/replay，不是 XS生产容量或 Benchmark baseline；不运行 Solver。

Simulation scenarios: 新建 `SIM-P1-INGRESS-001` 小型 synthetic regression asset；所有定量值必须在 Profile/Scenario与 SIM_ASSUMPTION register明确，不能成为 Production default。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/normalization/normalizer.py backend/app/simulation/generators backend/tests/unit/test_normalization.py backend/tests/simulation/test_p1_synthetic_generator.py`；`uv run pyright backend/app/normalization/normalizer.py backend/app/simulation/generators backend/tests/unit/test_normalization.py backend/tests/simulation/test_p1_synthetic_generator.py`；`uv run pytest -q backend/tests/unit/test_normalization.py -k cycle_seconds_per_unit`；`uv run pytest -q backend/tests/simulation/test_p1_synthetic_generator.py backend/tests/simulation/test_simulation_contracts.py`；`uv run pytest -q backend/tests/simulation/test_p1_synthetic_generator.py -k no_planning_or_solver_import`；`uv run python -m app.simulation.generators.contract_check --report build/validation/TASK-P1-10-generator.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-10-synthetic-generator-records.md --check-diff --report build/traceability/TASK-P1-10-report.json`；`git diff --check`；`uv build`。

Artifacts: Profile/Scenario asset、generated Import/manifest/hash report、tests、traceability report。

Completion conditions: `cycle_seconds_per_unit`按已发布duration合同经显式source unit转换为整数秒且直接回归通过；same Scenario/Profile/generator/seed产生相同 non-empty Import bytes/hash；所有七层有独立测试与命名 seed；输出通过 normalization/data validation且无 Snapshot/Problem/Solver shortcut；isolation/docs/trace/governance PASS。

Explicitly excluded: Execution Simulator、Benchmark/Reference Scheduler、Snapshot/Problem direct construction、Solver、真实工厂分布或生产容量声明。

PROD_OPEN: OPEN-003/004/011/012/013/015 保持 OPEN；synthetic asset不能关闭任何生产问题。

SIM_ASSUMPTIONS: 复用 SIM-ASSUMPTION-001/002/004；新增定量分布前必须先登记稳定 ID并绑定 asset version。

Rollback: 保留旧 generator/asset/hash；失败修复发布新 version，禁止覆盖或重写已提交 replay artifact。

## Completion evidence

### Activation evidence

- 2026-08-20（Asia/Hong_Kong）：P1-02/05/06/07依赖均为`done`，`main`与`origin/main`同步且working tree干净；以完整HEAD `11c6ca97882a3be5bf6eb25bab84f69d1dfe469c`固定immutable Diff base并进入`in_progress`。
- Scope precheck发现验收命令要求的`generators/contract_check.py`原未列入允许范围，因此在业务实现前显式补入；同时按已声明的IMPACT-FIXTURE/PHASE/GOVERNANCE-REGISTRY/TESTS/DOCS补齐矩阵要求的强制审查文档。该修订不改变Goal、合同、Schema、依赖、验收命令或Phase边界。
- 首次真实source-shaped package调用暴露既有Normalization合同缺口：`cycle_seconds_per_unit`在canonical DTO、Import Schema和DataValidation中均为integer duration，但normalizer兼容表因字段不以`_seconds`结尾而错误要求`TEXT`；因此无法在原范围内同时通过公开normalization与validation。按治理规则先停止实现并记录证据，再把唯一兼容修复文件、直接unit regression、`IMPACT-IMPORT`及其强制文档加入范围；不改变Schema、字段、unit registry、其他Normalization行为或Task Diff base。
- 完成时填写generator/profile/scenario versions、seed/hash、collection counts、tests、changed paths、assumption与文档结果；在provider证据闭环前保持`in_progress`。

### Local implementation evidence (provider pending)

- 2026-08-20（Asia/Hong_Kong）：七层generator、source-shaped `ReferenceFileAdapter v1` rows、公开Normalization/Data Validation handoff、P1 package/manifest验证与`SIM-P1-INGRESS-001@1.0.0`资产已实现；Task仍为`in_progress`，因为implementation commit与对应GitHub provider evidence尚未产生。P1-11未启动。
- Replay identity：`PROFILE-SIM-P1-INGRESS-001@1.0.0`、`SIM-P1-INGRESS-001@1.0.0`、generator `PLANTNEXUS-P1-CANONICAL-IMPORT-GENERATOR@1.0.0`、seed=`20260820`、generation manifest=`synthetic-generation-manifest.v1`、Import=`import-package.v2`、schema set=`2.2.0`。16个canonical collections全部非空，共49条记录；dataset hash=`sha256:24a74b4f43b0ba42ed458983e0c4776613911924ae5250d9df8ae9e4f14cb1c4`，package ID=`import-9eea9bd41216b3a2b337a83f2b6f5438a287f219251168ce8d574f4b9fb6b2c6`，quality report ID=`import-quality-600341c55f6f8511bd25387fcf2a9f3ff62d2c72901f8bb454df32636b4cafbe`且`PASS/0 errors`。
- Determinism/isolation：same input产生byte-identical canonical package/hash，`generated_at`不进入dataset hash；seed/profile version变化改变结果，generator version mismatch显式拒绝；每层仅使用immutable context与命名child seed，测试证明purity及调用顺序独立。AST isolation证明无PlanningSnapshot/PlanningProblem/Solver/Application/ORM import；Production target、unsupported capability、Profile/Scenario mismatch及公开Normalization/Data Validation失败均结构化拒绝。
- Normalization scope correction只把`cycle_seconds_per_unit`按已发布duration合同纳入显式unit transform分类，并增加`min → second`直接回归；未改变Schema、字段、unit registry或其他Normalization行为。P0 empty generator contract与既有Simulation contract tests保持通过。
- Local acceptance：`uv sync --locked` PASS；Task Ruff PASS；Pyright=`0 errors, 0 warnings, 0 informations`；direct Normalization regression=`1 passed`；P1 generator + P0 Simulation contract suite=`18 passed`；no-Planning/Solver import slice=`1 passed`；generator machine report=`PASS`（7/7 checks）；full repository=`262 passed`；full docs governance=`PASS`（124 docs/30 roots/36 tests/15 OPEN/10 SIM/10 risks/22 tasks）；Task diff governance=`PASS`（52 paths/7 impact rows/0 issues）；`git diff --check` PASS；`uv build`成功生成sdist与wheel。以上命令已在格式化后的最终working tree重放。
- Trace/assumptions：REQ-001/003/009/011/012、NFR-DET/TRC/ISO、ENG-ARCH/ERR/VER → TASK-P1-10 → TEST-SCENARIO-REPLAY/TEST-SIM-ISOLATION → generator/asset/package/manifest/hash/machine reports。新增`SIM-ASSUMPTION-010`只绑定本asset的49-record correctness/replay；SIM-ASSUMPTION-001～010保持`ACTIVE`，全部PROD_OPEN与风险状态保持原状，不能据此声明Benchmark、容量或Production readiness。
- Scope/rollback：当前Task union diff为52条允许路径，匹配`IMPACT-DOCS/FIXTURE/GOVERNANCE-REGISTRY/IMPORT/PHASE/SIM-GENERATOR/TESTS`七行且无越界。无Schema、migration、dependency/lock、Snapshot/Problem、Solver、Benchmark baseline、API或P2变更；历史generator/fixture/hash不重解释，语义变更必须发布新generator/asset version。
