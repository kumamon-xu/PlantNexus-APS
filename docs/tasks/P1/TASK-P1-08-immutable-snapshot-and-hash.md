---
doc_id: TASK-P1-08
title: Immutable PlanningSnapshot and Hash
status: done
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [23, 40, 62, 73, 74, 101, 103]
last_reviewed: 2026-08-20
---

# TASK-P1-08 — Immutable PlanningSnapshot and Hash

Requirement IDs: REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, ENG-SOL-001, ENG-VER-001

Depends on: TASK-P1-03, TASK-P1-06, TASK-P1-07

Goal: 从已验证、已展开的 canonical facts 构建 immutable PlanningSnapshot v2，定义 canonical hash projection和 deterministic snapshot ID，并用持久化约束证明已创建 Snapshot 不可就地修改。

Inputs: PlanningSnapshot v2 Schema、canonical package/quality report/expanded operations、ADR-0007/0009、provenance rules。

Diff base: 8b4fb4c027305d3e3aa68eec0baaf73cd0598189

Files allowed to change: `backend/app/snapshots/__init__.py`、`backend/app/snapshots/contracts.py`、`backend/app/snapshots/canonical.py`、`backend/app/snapshots/builder.py`、`backend/app/snapshots/repository.py`、`backend/app/infrastructure/snapshot_repository.py`、`backend/migrations/versions/0003_planning_snapshots.py`、`backend/tests/unit/test_snapshot_builder.py`、`backend/tests/property/test_snapshot_properties.py`、`backend/tests/integration/test_snapshot_repository.py`、`backend/tests/integration/test_migrations_and_infrastructure.py`、`README.md`、生成但不提交的 `build/traceability/TASK-P1-08-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: Snapshot v1/v2 Schema、Import/Adapter/Normalization/DataValidation/Expansion语义、PlanningProblem/Solver、Simulation Generator、API、ScheduleVersion/Export。

Implementation steps: canonicalize所有 Snapshot事实和 source/rule/schema/expansion versions；hash排除 self hash、随机 UUID、received/generated timestamps等噪声但包含 cutoff和业务事实；snapshot_id由 versioned digest派生；builder要求 quality PASS；repository content-addressed insert-only并拒绝 hash/content冲突或 update/delete；synthetic Snapshot必须保留 scenario/profile/generator/seed，Production不得引用 synthetic source；reversible migration与 replay/property tests。

Outputs: Snapshot builder/hash/repository、immutable migration与 deterministic replay artifacts。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/import-and-normalization.md`、`docs/domain/domain-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/data-authority.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-08-immutable-snapshot-and-hash.md`。

Documentation impact rationale: Snapshot hash projection、ID、immutability、persistence与 synthetic provenance 是 P1 Gate和后续所有 run的核心合同。

Change-impact matrix rows reviewed: `IMPACT-SNAPSHOT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/009、NFR-DET/TRC/ISO/REL、ENG-SOL/VER → TASK-P1-08 → TEST-SNAPSHOT-REPLAY-001/TEST-SIM-ISOLATION → hash vectors、property/repository/migration evidence。

Schema changes: none；实现已发布 planning-snapshot.v2，发现语义不足须停止并走 Schema version Task。

Migration: 新增 `0003_planning_snapshots` insert-only storage；空库/含 Snapshot upgrade-downgrade测试并记录 downgrade数据损失边界。

Error behavior: quality非 PASS、provenance缺失、hash/content冲突、mutation/update/delete、synthetic/production混用、invalid cutoff明确失败；同内容 replay返回同 identity而非复制可变记录。

Tests: `TEST-SNAPSHOT-REPLAY-001`、`TEST-SIM-ISOLATION`；hash vectors、key/order/noise变化、cutoff/rule/version变化、round-trip、immutability、repository conflict、migration与 property shrinking。

Benchmark impact: 记录 synthetic entity counts/hash/build time作为诊断；不设生产阈值、不运行 Solver。

Simulation scenarios: synthetic Snapshot保留完整 provenance；Production isolation负例必测，未建立独立 Production deployment声明。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/snapshots backend/app/infrastructure/snapshot_repository.py backend/tests/unit/test_snapshot_builder.py backend/tests/property/test_snapshot_properties.py backend/tests/integration`；`uv run pyright backend/app/snapshots backend/app/infrastructure/snapshot_repository.py backend/tests/unit/test_snapshot_builder.py backend/tests/property/test_snapshot_properties.py backend/tests/integration`；`uv run pytest -q backend/tests/unit/test_snapshot_builder.py backend/tests/property/test_snapshot_properties.py backend/tests/integration/test_snapshot_repository.py backend/tests/integration/test_migrations_and_infrastructure.py`（该 integration suite必须实际执行空库及含 Snapshot 的 upgrade/downgrade）；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-08-immutable-snapshot-and-hash.md --check-diff --report build/traceability/TASK-P1-08-report.json`；`git diff --check`；`uv build`。

Artifacts: canonical hash vectors、Snapshot/repository/migration tests、traceability report。

Completion conditions: same canonical facts/cutoff/versions得到同 snapshot bytes/hash/id；任何事实/version变化改变 hash；insert-only与 isolation负例通过；migration、docs、traceability和提交前后 governance PASS。

Explicitly excluded: PlanningProblem/Solver、mutable Snapshot correction、ScheduleVersion、API、Production release或关闭数据权威 OPEN。

PROD_OPEN: OPEN-001/002/004/007/009/015 保持 OPEN；Snapshot只固化已提供事实，不补猜。

SIM_ASSUMPTIONS: synthetic provenance引用已登记 assumptions；不得把 snapshot内容作为生产校准。

Rollback: 不改写既有 Snapshot；代码回滚保留 content-addressed记录，migration downgrade前必须确认仅开发/测试且记录数据影响。

## Completion evidence

### Implementation and provider closure

- 时间：2026-08-20（Asia/Hong_Kong）。Task=`done`；immutable Diff base=`8b4fb4c027305d3e3aa68eec0baaf73cd0598189`，implementation commit=`72670d18a29c9a10cb70f7a263c981a2b660e0ee`，已按用户授权直接push受保护的`main`。提交前Task diff report记录committed-range sources=`0`、working-tree sources=`41`；implementation artifact记录committed-range=`41`、working-tree=`0`，两者均为41 changed paths、6 impact rows、0 issues。
- Hash contract：Snapshot document=`planning-snapshot.v2`、schema document set=`2.0.0`、canonicalization=`canonical-json.v1`、semantic projection=`snapshot-hash-projection.v1`。投影只接受已登记字段，排除self ID/hash和未登记的received/generated/runtime噪声，保留cutoff、业务时间/事实、schema/rule/expansion/source versions与provenance；所有集合及resource capability、calendar interval、routing requirement/candidate、instance/edge/lock均显式稳定排序。
- 固定向量：基于P1-02 synthetic schema sample并按P1-05规则重算content-derived Import package identity，canonical bytes=`9212`，Snapshot hash=`sha256:44f422f81490159c4b0343a52aadd7991191684fa3b25394a0dd8b8a1b7e591a`，Snapshot ID=`planning-snapshot-v2-44f422f81490159c4b0343a52aadd7991191684fa3b25394a0dd8b8a1b7e591a`。实体计数为各基础实体1条、routing operation/resource option/operation instance各2条、routing/expanded edge各1条、execution fact/lock各1条；未修改schema sample。
- Builder/immutability：只接受exact canonical Import v2、content-derived package ID、exact matching且PASS/0-error的quality report、与Import/report/source provenance一致且自校验通过的`OrderExpansionResult`及strict UTC cutoff。缺失/FAIL/stale/tampered input、package/report/expansion mismatch、invalid cutoff、Production/Synthetic混用均返回稳定Snapshot error code；`ImmutablePlanningSnapshot`持有canonical bytes且每次读取返回fresh decoded copy。
- Repository/migration：SQLAlchemy Core repository按单一`production`或`simulation` plane永久绑定，写前重验完整hash/ID/bytes/plane，content-addressed insert与exact replay原子化；identity/content conflict、update/delete和SQL失败明确且不泄漏SQL。`0003_planning_snapshots`以`0002_raw_import_staging`为parent，保存canonical bytes及其storage digest；SQLite/PostgreSQL分别创建BEFORE UPDATE/DELETE immutability trigger。空库与含Snapshot upgrade/downgrade/re-upgrade均已测试；downgrade删除Snapshot表及数据，只有确认开发/测试影响后方可执行。真实PostgreSQL race/outage仍无证据。
- Tests：9 unit + 4 fixed-seed Hypothesis property + 5 repository integration，并与migration suite共同执行为`25 passed`。Seeds=`20260820/20260821/20260822/20260823`，max examples=`32/32/24/24`，覆盖集合/内部顺序不变量、事实变化、cutoff变化和非合同噪声排除；无失败或minimized corpus。Full repository regression=`238 passed`。
- 诊断：同一已准备synthetic input执行5轮、每轮20次build，`min=2.079 ms`、`mean=2.091 ms`、`max=2.099 ms`；这只记录本机synthetic诊断，不设Production阈值、不形成Solver benchmark。
- Provider：GitHub Actions push run [`32310098594`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32310098594)，attempt=`1`、event=`push`、head SHA=`72670d18a29c9a10cb70f7a263c981a2b660e0ee`、status/conclusion=`completed/success`；required `validate` job [`96251145353`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32310098594/job/96251145353)及全部步骤成功。Artifact `9386127863` / `plantnexus-ci-evidence-32310098594`未过期，size=`6266` bytes，expires_at=`2026-11-17T22:43:14Z`；provider与下载ZIP digest均为`sha256:69d68183bad614631df07234a3ca88508379ab89ec715f811ee7f529d6f17e0c`。Artifact含Task trace report及5份validation machine report且全部PASS；Task report精确记录本Task、implementation SHA、Diff base、41 committed paths、6 matched impact rows和0 issues。公开branch metadata确认`main`受保护，required context=`validate`。
- 本地命令：`uv sync --locked` PASS（63 packages）；Task Ruff PASS；Task Pyright PASS（0 errors/warnings）；Task pytest PASS（25 passed in 4.25s）；full repository pytest PASS（238 passed in 11.11s）；full docs治理 PASS（124 docs/30 roots/36 Test IDs/15 OPEN/9 SIM/10 risks/22 tasks）；Task diff docs治理 PASS（41 paths/6 rows/0 issues）；`git diff --check` PASS；`uv build` PASS（sdist + wheel）。
- Trace/边界：REQ-002/003/009、NFR-DET/TRC/ISO/REL、ENG-SOL/ERR/VER → TASK-P1-08 → TEST-SNAPSHOT-REPLAY-001 + TEST-SIM-ISOLATION slice → builder/hash/repository/migration tests。Schema、dependency/lock、Import/Adapter/Normalization/DataValidation/Expansion semantics均未改；PlanningProblem/common ingress/Solver/P2未开始。所有root ID保持`ALLOCATED`；OPEN-001/002/004/007/009/015及其余PROD_OPEN保持OPEN，SIM-ASSUMPTION-001～009保持ACTIVE，风险保持MONITORED。P1-09保持`planned`，不会在本Task闭环中自动启动。
