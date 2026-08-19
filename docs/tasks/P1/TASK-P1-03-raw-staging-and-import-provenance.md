---
doc_id: TASK-P1-03
title: Raw Staging and Import Provenance
status: in_progress
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [9, 15, 62, 65, 66, 73, 93, 94, 95]
last_reviewed: 2026-08-19
---

# TASK-P1-03 — Raw Staging and Import Provenance

Requirement IDs: REQ-001, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-REL-001, NFR-SEC-001, NFR-ISO-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-02

Goal: 建立可审计、幂等、与 canonical consumer 隔离的 Raw Staging 批次/行存储，保留 source/version/file hash/row location/received-at 和 synthetic provenance，但不解析或规范化业务值。

Inputs: Standard Import v2 contract、`docs/contracts/import-and-normalization.md`、worker reliability/idempotency baseline、ADR-0009。

Diff base: d122a1b16dc1b7c91227d587b99fb8a345c7c312

Files allowed to change: `backend/app/importers/__init__.py`、`backend/app/importers/contracts.py`、`backend/app/importers/staging.py`、`backend/app/importers/repository.py`、`backend/app/infrastructure/import_staging_repository.py`、`backend/migrations/versions/0002_raw_import_staging.py`、`backend/tests/unit/test_import_staging.py`、`backend/tests/integration/test_raw_import_staging.py`、`backend/tests/integration/test_migrations_and_infrastructure.py`、生成但不提交的 `build/traceability/TASK-P1-03-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: Schema、source Adapter/CSV/Excel reader、normalization/data validation/order expansion、Snapshot/Problem、Simulation、API、Celery business task、Solver、Production deployment。

Implementation steps: 定义 immutable staged batch/row与 repository protocol；以 content digest + source version + idempotency key 处理 exact replay/conflict；SQLAlchemy adapter和 Alembic reversible migration只保存原始值/定位/安全 metadata；同一 transaction原子落库，synthetic/production data plane不允许交叉；raw rows不得直接供 Problem/Solver 消费。

Outputs: Raw Staging contracts、repository、reversible migration、unit/integration/idempotency evidence。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/contracts/import-and-normalization.md`、`docs/architecture/data-authority.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/domain/error-model.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-03-raw-staging-and-import-provenance.md`。

Documentation impact rationale: 新增持久化、幂等、来源追踪和数据平面隔离行为，影响 Import、Infrastructure、Operations、Error 与追踪合同。

Change-impact matrix rows reviewed: `IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/009、NFR-TRC/REL/SEC/ISO、ENG-ARCH/ERR/VER → TASK-P1-03 → TEST-IMPORT-STAGING-001/TEST-IDEMPOTENCY → migration、repository tests与 provenance artifact。

Schema changes: Business Schema none；关系表属于 internal persistence schema，不能冒充 Standard Import contract。

Migration: 新增 `0002_raw_import_staging`，必须在空库和含样例批次库验证 upgrade/downgrade；downgrade是破坏性开发回滚，执行时需记录数据影响。

Error behavior: digest/idempotency冲突、source/version缺失、跨 data-plane 引用、重复 row identity、事务失败以稳定错误返回；不保存或回显 Secret/异常原文。

Tests: `TEST-IMPORT-STAGING-001`、`TEST-IDEMPOTENCY`；batch/row immutable semantics、exact replay、conflict、transaction rollback、synthetic/production isolation、migration round-trip、raw-not-canonical boundary。

Benchmark impact: 只记录小型 synthetic staging 行数/耗时用于回归观察，不设生产阈值、不运行 Solver Benchmark。

Simulation scenarios: 使用显式 synthetic inline records；不修改正式 Scenario/Fixture，不将 staging 样例作为生产数据。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/importers backend/app/infrastructure/import_staging_repository.py backend/tests/unit/test_import_staging.py backend/tests/integration`；`uv run pyright backend/app/importers backend/app/infrastructure/import_staging_repository.py backend/tests/unit/test_import_staging.py backend/tests/integration`；`uv run pytest -q backend/tests/unit/test_import_staging.py backend/tests/integration/test_raw_import_staging.py backend/tests/integration/test_migrations_and_infrastructure.py`（该 integration suite必须实际执行空库及含样例批次的 upgrade/downgrade）；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-03-raw-staging-and-import-provenance.md --check-diff --report build/traceability/TASK-P1-03-report.json`；`git diff --check`。

Artifacts: migration revision、staging test result、traceability report；不提交真实源文件或 credentials。

Completion conditions: staged metadata字段齐全且 immutable；replay/conflict/rollback/isolation/migration tests PASS；raw rows无直接 Snapshot/Problem/Solver入口；文档/追踪与提交前后 governance PASS。

Explicitly excluded: 解析、字段映射、单位转换、业务校验、API/Worker 编排、真实 PostgreSQL 生产部署、Solver。

PROD_OPEN: OPEN-002/015 保持 OPEN；internal staging列不是外部接口或字段权威决定。

SIM_ASSUMPTIONS: 不新增工厂参数；测试批次显式 synthetic。

Rollback: 使用 migration downgrade与 repository feature removal；已被 Snapshot 引用的数据不得无审计删除，执行时需先确认开发测试数据范围。

## Completion evidence

2026-08-19按用户指令启动。启动时HEAD与`origin/main`均为`d122a1b16dc1b7c91227d587b99fb8a345c7c312`，working tree clean，TASK-P1-02=`done`且其最终provider replay为`success`，因此该commit固定为不可变Diff base。已完整复核Task引用的Import v2合同、Raw Staging/Worker幂等基线、ADR-0009、总规及相关代码/测试/治理文档；不新增ADR、业务Schema或依赖。首次diff governance真实返回5项`DIFF-IMPACT`：原规划卡遗漏`change-impact-matrix`、`sim-assumption-register`、`traceability-rules`、Milestone index与Task template；按规则先把这5份必审文档补入允许/更新范围并完整复核，业务实现范围不扩大。migration revision/DB、changed paths、source counts、命令退出码、数据影响、文档/追踪与provider evidence将在实现和验收后继续填写。

Implementation candidate共36个changed paths（committed range=0、working tree=36）：27份声明文档全部实际更新；其余为4份Importer contract/protocol/assembler/export、SQLAlchemy repository、`0002_raw_import_staging`、2份新test与1份既有migration/infrastructure test。实现固定immutable opaque batch/row、source/version/content及row digest/location/UTC provenance、Production/Simulation conditional、plane+source+idempotency scope、deterministic request fingerprint、exact replay/conflict、单transaction batch+rows、sanitized failure和raw-not-canonical boundary；没有update/delete、Adapter、Normalization、DataValidation、Snapshot/Problem或Solver入口。

本地Task Acceptance真实结果：`uv sync --locked` exit 0（58 packages，`uv.lock`无diff）；Task范围Ruff exit 0、Pyright 0 errors；unit+raw integration+migration 23 passed in 1.23s；full/diff docs checks exit 0（124 docs、30 roots、36 Test IDs、15 OPEN、9 SIM、10 risks、22 Tasks；diff 36 paths/6 impact rows/0 issues）；`git diff --check` exit 0，仅报告既有Windows line-ending转换提示。`build/traceability/TASK-P1-03-report.json`为ignored machine artifact。

额外CI parity回归：repository Ruff/Pyright PASS，全部unit/contract/simulation/golden/validation/integration 121 passed in 2.21s；rule contracts（11 active/7 deferred/20 capabilities/19 error codes/3 machines/27 states/42 transitions）、Simulation replay（8 checks）、Golden replay、13-case mutation、engineering contract与Compose config均exit 0；`uv build`成功生成sdist/wheel。小型staging观察仅覆盖2-row synthetic batch和上述suite耗时，不设生产阈值、不运行Solver Benchmark。

Migration数据影响：空库upgrade创建`raw_import_batches/raw_import_rows`；含1个explicit synthetic batch/1 row的临时SQLite downgrade到`0001`会删除两表及该样例，re-upgrade后为空，再downgrade base成功。该destructive evidence只作用于pytest临时目录，没有删除用户、真实或Production数据；Production downgrade必须另行确认范围/备份。Schema set/产品error registry/dependency/lock保持不变，OPEN-002/015及全部15项OPEN继续OPEN，SIM-ASSUMPTION-001～009不变，无新ADR。

追踪已更新为REQ-001/009、NFR-TRC/REL/SEC/ISO、ENG-ARCH/ERR/VER→TASK-P1-03→TEST-IMPORT-STAGING-001/TEST-IDEMPOTENCY→raw contracts/repository/migration/tests。实际impact rows为`IMPACT-DOCS/GOVERNANCE-REGISTRY/IMPORT/INFRA/PHASE/TESTS`；Adapter、Normalization/DataValidation、independent Production DB、PostgreSQL race/outage、Worker编排、Snapshot/Problem/Solver和P2继续`PLANNED`。本地实现已满足Completion conditions；implementation commit、提交后governance和provider evidence待完成。
