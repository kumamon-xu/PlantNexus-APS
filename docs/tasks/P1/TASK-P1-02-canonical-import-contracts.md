---
doc_id: TASK-P1-02
title: Canonical Import Contracts
status: done
spec_version: 0.3.0
phase: P1
normative: true
source_sections: [15, 16, 17, 18, 19, 20, 23, 73, 74, 91, 103]
last_reviewed: 2026-08-19
---

# TASK-P1-02 — Canonical Import Contracts

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P1-01

Goal: 在不猜 ERP/MES/WMS/CAM 字段映射的前提下，发布严格、版本化的 APS canonical record、Standard Import v2 和 PlanningSnapshot v2 机器合同，为后续 staging、normalization、expansion 与 hash builder 提供唯一数据语义。

Inputs: `docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/domain/domain-model.md`、`docs/architecture/data-authority.md`、ADR-0007/0008/0009、现有 schema set `1.2.0`。

Diff base: ac1ca00d0ecf770c24e4fe4ab1683fb32728d6ce

Files allowed to change: `schemas/json/canonical-records.v1.schema.json`、`schemas/json/import-package.v2.schema.json`、`schemas/json/planning-snapshot.v2.schema.json`、`schemas/samples/import-package.v2.synthetic.json`、`schemas/samples/planning-snapshot.v2.synthetic.json`、`schemas/data_dictionary.yaml`、`backend/app/__init__.py`、`backend/app/domain/__init__.py`、`backend/app/domain/contracts.py`、`backend/app/domain/canonical_records.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_rule_contracts.py`、`pyproject.toml`、仅在 metadata/lock 确有变化时更新的 `uv.lock`、生成但不提交的 `build/traceability/TASK-P1-02-report.json`，以及下方 `Documents to update` 的全部明确路径。

Files forbidden to change: `schemas/json/import-package.schema.json`、`schemas/json/planning-snapshot.schema.json`、其他已发布 v1/v2 artifact、数据库/migrations、Adapter、staging、normalization、data validation、Snapshot/Problem builder、Simulation generator、API、Solver。

Implementation steps: 定义 Factory/Workshop/Line/Resource/Calendar、Product/Routing/Operation/Precedence/ResourceOption、Demand/ProductionOrder/Lot、execution facts/locks 的 canonical collections与稳定引用；必需时间显式 offset并规范目标 UTC、duration/unit/source version字段无默认值；新增 v2 envelope 与 v2 Snapshot payload/provenance，保留 v1 artifact；发布 schema set major compatibility说明、positive/negative/round-trip samples和 pure JSON-compatible types。

Outputs: canonical-records.v1、import-package.v2、planning-snapshot.v2、data dictionary、pure types 与 contract evidence。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/contracts/README.md`、`docs/contracts/import-and-normalization.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/core/glossary.md`、`docs/domain/domain-model.md`、`docs/domain/operation-instance-and-resource-options.md`、`docs/domain/time-calendar-and-material-boundaries.md`、`docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/repository-layout.md`、`docs/architecture/technology-stack.md`、`docs/planning/solver-backend-contract.md`、`docs/adr/README.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/benchmark-regression.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/milestones/README.md`、`docs/milestones/P1-data-and-snapshot.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P1/TASK-P1-02-canonical-import-contracts.md`。

Documentation impact rationale: 新 canonical 字段、document version、schema set compatibility 与 Snapshot payload 会成为所有 P1 producer/consumer 的合同基线。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-001/002/003/009、NFR-DET/TRC、ENG-SOL/ERR/VER → TASK-P1-02 → TEST-CONTRACT-001 → v2 Schemas/data dictionary/pure types；实现类证据继续标记 `PLANNED`。

Schema changes: set-level major release；保留所有 `1.2.0` artifact，新增 canonical-records.v1、import-package.v2、planning-snapshot.v2；明确 backward/forward incompatibility与拒绝旧 consumer规则。

Migration: 无数据库 consumer；v1 fixture/history 保留只读，后续 Adapter 必须显式产出 v2，禁止 alias 或覆盖 v1。

Error behavior: 缺少必需 ID/source/version/unit/duration、未知字段、非法 synthetic provenance、非法 UTC/引用形状在 Schema/pure precheck 层明确拒绝；不补默认值。

Tests: `TEST-CONTRACT-001`；Draft 2020-12 meta、positive/negative、v1/v2 isolation、unknown/default、reference shape、UTC/unit/duration、Production/Synthetic 条件、round-trip、dictionary coverage和既有rule-contract schema-set regression。

Benchmark impact: 尚无 Solver；contract/hash 语义变化登记为 P1 replay 输入，不生成性能结论。

Simulation scenarios: samples 必须 synthetic；不修改或冒充正式 `SIM-MINIMAL-001`，不创建分布 Generator。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app/domain backend/tests/contract`；`uv run pyright backend/app/domain backend/tests/contract`；`uv run pytest -q backend/tests/unit backend/tests/contract`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P1/TASK-P1-02-canonical-import-contracts.md --check-diff --report build/traceability/TASK-P1-02-report.json`；`git diff --check`；`uv build`。

Artifacts: versioned Schemas、data dictionary、synthetic samples、contract-test result、traceability report。

Completion conditions: v1 artifacts逐字保留；v2 canonical collections满足领域/权威边界且无隐式生产默认值；Schema set/version metadata一致；正反/round-trip tests与提交前后治理均 PASS；Adapter/pipeline仍未实现。

Explicitly excluded: 真实源字段 mapping、Production Adapter、staging/normalization/validation/expansion/builder、API、ORM、Solver、关闭 OPEN-002/013/015。

PROD_OPEN: OPEN-001/002/003/004/007/008/009/013/014/015 均只引用不关闭。

SIM_ASSUMPTIONS: 只使用已登记 synthetic sample 边界；不得把 sample 数值提升为 Profile 或生产事实。

Rollback: 已发布 v2 不原地覆盖；失败时停止 consumer 开发并保留 v1，可发布修正版新版本而非改写历史。

## Completion evidence

2026-08-19按用户指令启动。启动时HEAD与`origin/main`均为`ac1ca00d0ecf770c24e4fe4ab1683fb32728d6ce`，working tree clean，P1-01最终provider replay为`success`，因此该commit固定为不可变Diff base。影响矩阵复核补入原卡遗漏的dependency、phase、governance-registry必审文档；未扩大Schema/domain合同以外的业务实现范围。实现、测试、提交与provider证据完成后继续填写。

工作版本已新增canonical-records.v1、Import v2、Snapshot v2、两份synthetic sample、data dictionary与pure JSON-compatible types/prechecks，并将schema set metadata同步为`2.0.0`；Import/Snapshot v1 SHA-256固定为`ceab72f8f2adc3008a8489050372912a0bb6798751a0cedec9bbaa3a83f59621`和`d3b68f330c54df8c0e35f72e8058e60c981cfd5b58103d78c03c55fdf1876c0d`。Draft 2020-12跨URN registry/sample validation、Ruff、Pyright和29项相关contract tests已通过首轮检查。最终Acceptance、changed-path/report摘要、commit/provider evidence及所有必审文档review仍待本Task完成阶段填写。

本地implementation candidate共50个changed paths（committed range=0、working tree=50）：Task声明的37份文档全部实际更新；其余为3份新Schema、2份sample、data dictionary、schema metadata、domain pure types/exports与2份contract tests。Task diff governance匹配`IMPACT-DEPENDENCY/DOCS/DOMAIN/GOVERNANCE-REGISTRY/PHASE/SCHEMA/TESTS/VERSION-METADATA`共8行、0 issues；full governance同样PASS。REQ-001/002/003/009、NFR-DET/TRC、ENG-SOL/ERR/VER已连接TASK-P1-02→TEST-CONTRACT-001→v2 artifacts/pure precheck，producer/pipeline/builder evidence继续`PLANNED`。

本地Acceptance真实结果：`uv sync --locked` exit 0（58 packages，`uv.lock`无diff）；Task范围Ruff exit 0、Pyright 0 errors、unit+contract 44 passed；full/diff docs checks exit 0（124 docs、30 roots、36 Test IDs、15 OPEN、9 SIM、10 risks、22 Tasks；diff 50 paths/8 impact rows）；`git diff --check` exit 0；`uv build`生成sdist/wheel并exit 0。额外CI parity回归：repository Ruff/Pyright PASS、全部unit/contract/simulation/golden/validation/integration 103 passed，rule/simulation/golden/mutation/engineering五类machine contracts与Compose config全部exit 0。

新artifact SHA-256：canonical=`fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e`、Import v2=`166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56`、Snapshot v2=`d30ed42f8e5d1b497e2c41aec8bd840c1530e8a16c8594e22ed8db2dbc676a09`、Import sample=`3b0a1654edb947e3ef1ae2c0a6b00fb4ae782d2d98282ac1b09663fc406eec6e`、Snapshot sample=`9e41ef51a55b765d94264cde00c0a34368af4c8269c47c8dbdf836c738272027`。Compatibility为breaking major且显式拒绝旧consumer；无数据库migration、dependency/lock变化、新ADR、Benchmark/Solver或Production默认值；OPEN列表保持OPEN，sample不新增SIM assumption。

Implementation commit=`64c40b5c21ab0be8955e55edc007e04337cac417`（50 paths、3387 insertions/57 deletions）。提交后full/diff governance再次PASS，report为committed range=50、working tree=0、8 impact rows、0 issues；working tree clean。直接push`main`时GitHub提示required `validate`尚待运行并发生rule bypass，该提示未计为PASS。

真实provider closure：GitHub repository=`kumamon-xu/PlantNexus-APS`、branch=`main`、workflow=`PlantNexus repository gates`；run [`32241366290`](https://github.com/kumamon-xu/PlantNexus-APS/actions/runs/32241366290)，event=`push`、attempt=1、head SHA=`64c40b5c21ab0be8955e55edc007e04337cac417`、status=`completed`、conclusion=`success`。Job `validate` ID=`96032439734`为success，checkout/setup/sync/lint/type/tests/五类contracts/Compose/docs+Task diff/Benchmark deferred hook/build/upload及post steps全部success。Artifact ID=`9360906246`、name=`plantnexus-ci-evidence-32241366290`、size=6333 bytes、digest=`sha256:90484bc64d02458f2fced9d8e7691fa8251149884e6d9f272407b7e50fa83fc3`、expired=false、expires=`2026-11-17T10:10:24Z`。公开branch state为`main.protected=true`，required check=`validate`/app ID=`15368`。

所有Completion conditions满足，Task标记`done`。本evidence-only状态提交自身无法被上述implementation run包含；按治理自引用边界，推送后仍执行同一workflow并在任务交付中报告最终run，不借此启动TASK-P1-03或进入P2。
