---
doc_id: TASK-P1-07
title: Deterministic Order Expansion
status: done
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [18, 19, 20, 21, 22, 73, 74]
last_reviewed: 2026-08-19
---

# TASK-P1-07 — Deterministic Order Expansion

Requirement IDs: REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-06

Goal: 将已验证的 DemandOrder/ProductionOrder/显式 ProductionLot 与 RoutingVersion 确定性展开为 OperationInstance、候选资源选项和 precedence edges，并保留全部 source lineage；不得自行猜 lot splitting 或 duration fallback。

Inputs: valid canonical Import v2、domain/operation contracts、OPEN-008/014、P1 DataValidation PASS report。

Diff base: 97728521e187f9f50715de4b04a09098bef62ddf

Files allowed to change: `backend/app/domain/production.py`、`backend/app/normalization/order_expansion.py`、`backend/app/normalization/__init__.py`、`backend/tests/unit/test_order_expansion.py`、`backend/tests/property/test_order_expansion_properties.py`、`backend/tests/integration/test_ci_contract.py`、`.github/workflows/ci.yml`、`pyproject.toml`、`uv.lock`、`README.md`、生成但不提交的 `build/traceability/TASK-P1-07-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: Schema/error registry、Adapter/Staging、unit/time Normalizer、DataValidation rules、Snapshot/Problem builder、Simulation、API、Solver、自动 lot split/merge或 duration预测。

Implementation steps: 只接受 source明确提供的 ProductionLot/quantity与 RoutingVersion；按稳定 ID algorithm实例化 operation和 edge；复制 candidate级 final duration/source version、release/material gates、COMPLETED/RUNNING facts与locks；COMPLETED保留在 Snapshot事实但不进入未来 Problem；同输入/版本输出稳定排序；以exact dev-only Hypothesis pin提供generation/shrinking，property tests覆盖 DAG分支/汇合、跨车间和多候选，runtime dependency集合保持不变；把`backend/tests/property`加入phase-neutral repository CI suite并以integration contract防止后续丢失。

Outputs: pure order-expansion service、versioned expansion provenance、unit/property evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/current_phase.md`、`docs/adr/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/schema-versioning.md`、`docs/core/glossary.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/planning/constraint-catalog.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/benchmark-regression.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-07-deterministic-order-expansion.md`。

Documentation impact rationale: Order/Lot/OperationInstance lineage与执行事实进入正式 P1行为，影响 Domain、Import、Problem输入和 Property测试口径。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-07 → TEST-ORDER-EXPANSION-001/TEST-RUNNING → OperationInstance/edge artifacts和 property regressions。

Schema changes: none；消费 TASK-P1-02 canonical contract；`pyproject.toml`只增加dev-only property-test dependency，不改变schema set `2.2.0`或任何document version。若发现字段不足必须停止并先升版，禁止在代码内藏字段。

Migration: none。

Error behavior: missing explicit lot、routing version mismatch、missing option duration/source、duplicate derived ID、invalid execution fact或请求 SPLIT_MERGE明确拒绝；不得自动修复。

Tests: `TEST-ORDER-EXPANSION-001`、`TEST-RUNNING`；serial/parallel/merge/cross-workshop、candidate duration、source lineage、completed/running、explicit lots、stable IDs/order、property generation/shrinking与 missing/fallback负例。

Benchmark impact: property样例记录 entity counts但不声称性能；无 Solver benchmark。

Simulation scenarios: 使用合法 synthetic canonical inputs；随机失败保存 seed/minimized example/version/hash，不修改正式 P0 fixture。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/domain/production.py backend/app/normalization backend/tests/unit/test_order_expansion.py backend/tests/property/test_order_expansion_properties.py backend/tests/integration/test_ci_contract.py`；`uv run pyright backend/app/domain/production.py backend/app/normalization backend/tests/unit/test_order_expansion.py backend/tests/property/test_order_expansion_properties.py backend/tests/integration/test_ci_contract.py`；`uv run pytest -q backend/tests/unit/test_order_expansion.py backend/tests/property/test_order_expansion_properties.py backend/tests/integration/test_ci_contract.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-07-deterministic-order-expansion.md --check-diff --report build/traceability/TASK-P1-07-report.json`；`git diff --check`；`uv build`。

Artifacts: expansion test/property corpus、seed/minimized failures（如有）、traceability report。

Completion conditions: 同 valid canonical input + expansion version产生相同 instances/edges；显式 lot与 lineage完整；missing duration/lot/unsupported split负例通过；无默认/AI/Solver；docs/trace/governance PASS。

Explicitly excluded: 自动 lot sizing/splitting、BOM/MRP、duration fallback/prediction、Snapshot persistence、Problem/Solver、schedule validation。

PROD_OPEN: OPEN-007/008/014/015 保持 OPEN；Production必须显式提供本 Task所需事实。

SIM_ASSUMPTIONS: property/generated values显式 synthetic并记录 seed，不成为业务默认值。

Rollback: expansion version不可重解释历史 output；回退 consumer时保留来源与旧版本，发现错误发布新版本并回放 Snapshot。

## Completion evidence

### Implementation and provider closure

- 时间：2026-08-19（Asia/Hong_Kong）。Immutable implementation commit=`5a3dbc14c12a107abf4052cca935e3ef59009d3d`，已按用户授权直接push受保护的`main`；该精确SHA的required provider evidence已成功，Task据此标记`done`。
- Diff：immutable base=`97728521e187f9f50715de4b04a09098bef62ddf`。提交前report记录committed-range sources=`0`、working-tree sources=`45`；implementation artifact记录committed-range=`45`、working-tree=`0`，两者均为45 changed paths、9 impact rows、0 issues。
- 实际范围：implementation commit包含`.github/workflows/ci.yml`、`README.md`、`backend/app/domain/production.py`、`backend/app/normalization/{__init__.py,order_expansion.py}`、`backend/tests/{unit/test_order_expansion.py,property/test_order_expansion_properties.py,integration/test_ci_contract.py}`、`pyproject.toml`、`uv.lock`及最初登记的36份文档，共45 paths。Provider closure review随后发现`docs/architecture/end-to-end-planning-flow.md`仍保留“链路止于DataValidation”的当前态陈述；在修改该文档前先扩卡纳入第37份文档，最终base-range union为46 paths，没有范围外路径。
- 版本/输出：`order-expansion.v1` + `canonical-json.v1`；Operation ID basis=`version + lot ID + routing operation ID`，edge ID basis=`version + lot ID + routing edge ID`，均为canonical JSON SHA-256。`OrderExpansionResult`携带Import/PASS-report/source/synthetic provenance、sorted instances/edges、canonical bytes和独立`sha256:` expansion hash；它不是Snapshot/Problem hash。
- 行为：只展开source-explicit ProductionLot；branch/merge/cross-workshop edge逐lot复制；candidate setup/cycle/final duration/source version、due/release/material gates、RUNNING/COMPLETED事实与locks逐项保留；NOT_STARTED不伪造fact，COMPLETED不从事实层丢弃。Missing lot/route/option/duration、quality mismatch、duplicate fact、fact/lock lineage和version错误明确`DATA_ERROR`；SPLIT_MERGE明确`UNSUPPORTED_CAPABILITY`，无fallback/AI/Solver。
- Property：exact dev pin=`hypothesis==6.165.10`，transitive=`sortedcontainers==2.4.0`，`uv.lock` SHA-256=`7ae68d242b1f80ad05a2ae51b09552ca9e19214d33ef8380bc74ff4c87ee64dd`。Positive seed=`20260819`/64 max examples，negative seed=`20260820`/24 max examples；生成1～3 lots、4-op branch/merge、2 workshops/resources、1～2 candidates及fact/lock组合。无失败，故无minimized failure/corpus可记录；shrinking路径由generated missing-candidate property实际启用。
- CI handoff：全仓检查发现旧workflow未收集`backend/tests/property`；在修改CI前已扩卡纳入`IMPACT-INFRA`及强制文档。现有phase-neutral repository suite已加入property目录，`test_ci_contract.py`固定该路径，既有gates/中性artifact/Task discovery未弱化。
- Provider：GitHub Actions push run [`32265257468`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32265257468)=`completed/success`，required `validate` job [`96108055149`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32265257468/job/96108055149)及全部步骤成功。Artifact `9369917400` / `plantnexus-ci-evidence-32265257468`未过期，size=`6380` bytes，expires_at=`2026-11-17T14:38:47Z`，provider digest=`sha256:8aeb7416516f7932436bbf406d800cdbdeb8313ba9249f2709b7df71647e566e`；下载ZIP SHA-256完全一致并含6份machine evidence。其Task report精确记录task=`TASK-P1-07`、result=`PASS`、git_head=`5a3dbc14c12a107abf4052cca935e3ef59009d3d`、diff_base=`97728521e187f9f50715de4b04a09098bef62ddf`、45 committed paths、9 impact rows和0 issues；公开branch元数据显示`main`受保护且required context为`validate`。
- Trace：REQ-003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-07 → TEST-ORDER-EXPANSION-001 + TEST-RUNNING P1 slice → `domain.production`/`normalization.order_expansion`/unit/property tests。P2 TEST-PROPERTY、Snapshot/Problem/common ingress/Solver仍`PLANNED`；所有root ID继续`ALLOCATED`。
- Schema/Migration：none。`schemas/**`、product error registry、`app.SCHEMA_VERSION`和`pyproject` schema metadata未改；schema set=`2.2.0`，Import/Snapshot v2 document=`2.0.0`。无DB/migration/data rewrite；dev dependency rollback只移除Hypothesis pin/lock和property CI path，历史expansion output必须仍按v1解释。
- 文档：本卡最终列出的37份文档全部实际更新；没有必审但未更新项。实际matrix rows=`IMPACT-DOMAIN/IMPORT/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`；implementation machine report=`PASS`、45 paths、9 rows、0 issues，closure governance=`PASS`、46 paths、9 rows、0 issues。PROD_OPEN-007/008/014/015继续OPEN；SIM-ASSUMPTION-001～009保持ACTIVE；property值不成为Production default或Benchmark baseline。
- 本地命令：`uv sync --locked` PASS（63 packages）；Task Ruff PASS；Task Pyright PASS（0 errors）；Task pytest PASS（14 passed：7 unit + 2 property + 5 CI contract）；extra full repository pytest PASS（219 passed）；full docs PASS（124 docs/30 roots/36 tests/22 tasks）；Task diff docs PASS；`git diff --check` PASS；`uv build` PASS（sdist + wheel）。Snapshot/Problem/common ingress/Solver仍未形成，P1-08保持`planned`且本次不自动启动。
