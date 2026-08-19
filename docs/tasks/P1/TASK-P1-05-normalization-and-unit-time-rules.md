---
doc_id: TASK-P1-05
title: Normalization and Unit Time Rules
status: done
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [15, 16, 20, 22, 73, 74, 90, 103]
last_reviewed: 2026-08-19
---

# TASK-P1-05 — Normalization and Unit/Time Rules

Requirement IDs: REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02, TASK-P1-03, TASK-P1-04

Goal: 将 staged source rows 通过显式、版本化规则确定性转换为 canonical Import v2，统一 ID、UTC、整数秒与稳定排序；未知或缺失单位/时区/字段必须拒绝，绝不使用生产默认值。

Inputs: canonical schemas/data dictionary、ReferenceFileAdapter staged rows、ADR-0008、OPEN-001/013/015。

Diff base: d63926f84d9d2b7bc46bbcaff5704612af120a34

Files allowed to change: `schemas/rules/unit-conversion-registry.v1.yaml`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`backend/app/normalization/__init__.py`、`backend/app/normalization/contracts.py`、`backend/app/normalization/ids.py`、`backend/app/normalization/time.py`、`backend/app/normalization/units.py`、`backend/app/normalization/normalizer.py`、`backend/tests/unit/test_normalization.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_rule_contracts.py`、`pyproject.toml`、仅在 metadata/lock 确有变化时更新的 `uv.lock`、生成但不提交的 `build/traceability/TASK-P1-05-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: source Adapter/Raw Staging migration、data validation/order expansion、Snapshot/Problem、Simulation、API、Solver、任何隐式 Production mapping/default。

Implementation steps: 发布 unit-conversion-registry.v1与 compatibility规则；显式 mapping profile将 source field映射为 canonical field，来源冲突拒绝；timestamp必须携带 offset并转 UTC Z，duration/unit以整数算术转秒且拒绝浮点歧义；canonical ID与collection/record排序稳定；生成 canonical Import v2 source/rule provenance与 bytes，但本 Task不做跨实体业务校验。

Outputs: versioned normalization rules、pure normalization modules、canonical Import v2 producer与 unit/contract evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/current_phase.md`、`docs/contracts/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/benchmark-regression.md`、`docs/adr/README.md`、`docs/governance/prod-open-register.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/risk-register.md`、`docs/governance/document-inventory.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/traceability-rules.md`、`docs/governance/sim-assumption-register.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/documentation-consistency-checks.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-05-normalization-and-unit-time-rules.md`。

Documentation impact rationale: unit/time/ID转换与 canonical serialization 是 P1 correctness/hash 语义，且直接受生产开放问题和 Schema versioning约束。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/009、NFR-DET/TRC、ENG-ERR/VER → TASK-P1-05 → TEST-NORMALIZATION-001/TEST-CONTRACT-001 → unit registry、canonical bytes与 tests。

Schema changes: schema set从`2.0.0` additive release到`2.1.0`并新增unit-conversion-registry.v1；不改写import-package.v2/canonical-records.v1，Import v2文档内固定的`schema_set_version=2.0.0`继续保留；规则语义变化须发布新registry version并回放hashes。

Migration: 无数据库迁移；旧 staged rows必须显式选择 mapping/unit rule version，禁止按“latest”静默重解释。

Error behavior: unknown/missing/ambiguous unit、overflow/non-integral second、missing/naive/invalid timezone、duplicate canonical ID、conflicting authority和 unmapped required field明确返回 DATA_ERROR及 source location。

Tests: `TEST-NORMALIZATION-001`、`TEST-CONTRACT-001`；秒/分/时显式转换、UTC offset/DST边界、ID稳定性、排序/round-trip、unit error/missing duration、mapping version变化、same staged input replay。

Benchmark impact: 只采集测试数据 normalization records/sec作为非门禁诊断；不设生产阈值、不运行 Solver benchmark。

Simulation scenarios: 使用 explicit synthetic source values验证同入口；Simulation Config不得注入 Production default。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/normalization backend/tests/unit/test_normalization.py backend/tests/contract/test_unit_conversion_registry.py backend/tests/contract/test_schema_contracts.py backend/tests/contract/test_rule_contracts.py`；`uv run pyright backend/app/normalization backend/tests/unit/test_normalization.py backend/tests/contract/test_unit_conversion_registry.py backend/tests/contract/test_schema_contracts.py backend/tests/contract/test_rule_contracts.py`；`uv run pytest -q backend/tests/unit/test_normalization.py backend/tests/contract/test_unit_conversion_registry.py backend/tests/contract/test_schema_contracts.py backend/tests/contract/test_rule_contracts.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-05-normalization-and-unit-time-rules.md --check-diff --report build/traceability/TASK-P1-05-report.json`；`git diff --check`；`uv build`。

Artifacts: unit registry、canonical Import samples/replay result、traceability report。

Completion conditions: 同 staged input + mapping/unit rule version产生 byte-identical canonical Import；unit error与 missing duration exact rejection通过；无隐式 default/float rounding；versions/docs/traceability与提交前后 governance均 PASS。

Explicitly excluded: 生产 unit policy closure、跨实体 DAG/reference validation、order expansion、Snapshot/Problem、API、Solver。

PROD_OPEN: OPEN-001/002/013/015 保持 OPEN；只实现显式规则，不批准默认单位或字段权威。

SIM_ASSUMPTIONS: synthetic sample单位/时区必须显式且只属于测试资产。

Rollback: 保留旧 rule version与 hash evidence；consumer回退时显式选择旧版本，禁止覆盖或重解释历史 canonical package。

## Completion evidence

Activation evidence（2026-08-19）：依赖TASK-P1-02/03/04均为`done`；启动时working tree干净且HEAD/origin/main均为`d63926f84d9d2b7bc46bbcaff5704612af120a34`，该SHA对应P1-04最终GitHub Actions run `32247501371`的required `validate` job `96051120094`=`success`。启动前已完整复核AGENTS、P1 Milestone、技术总规、相关合同/ADR/治理/测试和相邻Task；基线文档治理PASS。不可变合同基线hash：canonical-records.v1=`fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e`，import-package.v2=`166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56`。启动前将受schema set断言影响的两份既有contract tests和change-impact矩阵要求的全部文档补入允许范围；未执行P1-05业务实现。

Local implementation evidence（2026-08-19）：schema set从`2.0.0`加法更新到`2.1.0`，新增`unit-conversion-registry.v1`（SHA-256=`faa20954bcfa8d61ad1f8609f05d89baf38af278b2ba1b7890f50455c9e0e8d2`）；Import v2 document内仍固定`2.0.0`。canonical-records.v1/import-package.v2两份immutable hash与上述基线完全相同。data dictionary从`8f9f91d5944c1ae8d29da42c62dee12e3fc125364fbab0413b3943b537e85d8e`变为`c3058d95da7cd463d4c0ddd37900eb49213e7016918f488c5d7ef5c4d6ea161e`，pyproject从`ae9ca3f04b4c37727f64a495c0bb6d9f7c012f3c419e1be8df3f696953cd041b`变为`16891f326570aa90a38ce951b1174b123da1d88231810700fb7c2bd16e880169`；只改schema metadata，`uv.lock`无diff，`uv sync --locked`确认61 packages无漂移。

实现形成`mapping-profile.v1`、stable namespaced/cross-authority ID、显式source record provenance、strict offset→UTC Z、integer-only unit conversion、canonical ordering/serialization/package ID/dataset hash及Production/Simulation guard。正向覆盖schema/domain-valid minimal Import、DST/nested interval、same rows在order/batch ID/received-at/file digest/location变化下byte-identical replay、mapping version改变bytes/hash；负向覆盖duplicate JSON/ID、missing/unmapped field、source/profile/version/data-plane/provenance conflict、naive/fractional/unknown offset、missing/unknown/float/non-integral/overflow duration及invalid synthetic/mapping contract。Missing reference可被producer结构化输出但由后续domain precheck拒绝，证明TASK-P1-06边界未被吞并；source scan确认Normalization不导入DataValidation/Snapshot/Planning/OR-Tools且无unit default。

本地Acceptance：Task-focused Ruff/Pyright均0问题，focused pytest=`66 passed`；full repository Ruff/Pyright均0问题，full pytest=`189 passed`；`uv build`成功。Full governance=`PASS`（124 docs、30 roots、30 trace rows、36 tests、15 PROD_OPEN、9 SIM assumptions、10 risks、22 tasks）；Task diff governance=`PASS`（49 changed paths、8 matched impact rows、0 issues），`git diff --check`通过。

Implementation/provider evidence（2026-08-19）：implementation commit=`d52aa62d36e8d89eba318cb5fc586311680e030f`，已直接push到受保护的`main`。该精确SHA的GitHub Actions push run [`32252308695`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32252308695)为`completed/success`，required `validate` job [`96065907901`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32252308695/job/96065907901)全部步骤成功。Artifact `9364897397` / `plantnexus-ci-evidence-32252308695`未过期，provider digest=`sha256:5db1ccbb242b555d8a95d36ac9cc1b1373dab95d482dbde17ab7fb369cce2966`；下载ZIP的SHA-256完全一致，内含6份machine evidence。其`traceability/ci-current-task-report.json`精确记录task=`TASK-P1-05`、result=`PASS`、git_head=`d52aa62d36e8d89eba318cb5fc586311680e030f`、diff_base=`d63926f84d9d2b7bc46bbcaff5704612af120a34`、49 changed paths、8 matched impact rows和0 issues。GitHub公开branch元数据显示`main`受保护，direct-push rule反馈明确要求`validate`，且该精确SHA的同名check为`success`。

Completion decision：byte-identical replay、unit/missing-duration exact rejection、无隐式default/float rounding、版本/文档/追踪、提交前后governance和implementation provider CI均已满足，故本Task标记`done`。本次仅追加完成证据的提交仍需在push后对其精确SHA独立核验CI；该非自引用核验不改变上述实现结论。TASK-P1-06保持`planned`且未启动，未进入P2。
