---
doc_id: TASK-P0-03
title: Domain and Schema Skeleton
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [17, 18, 19, 20, 23, 24, 36, 70, 71, 103]
last_reviewed: 2026-08-19
---

# TASK-P0-03 — Domain and Schema Skeleton

Requirement IDs: REQ-001, REQ-002, REQ-003, REQ-009

NFR / ENG IDs: NFR-DET-001, NFR-TRC-001, ENG-SOL-001, ENG-VER-001

Depends on: TASK-P0-01, TASK-P0-02

Goal: 建立领域类型和 JSON/Scenario Schema 骨架，固定 Snapshot/Problem/KPI/Error 等顶层合同但不实现 P1 数据管道。

Inputs: `docs/domain/**`、`docs/contracts/**`、data authority、time rules。

Diff base: a0bee020e29bf62fc6294f73a703a253afc0c2c4

Files allowed to change: `/schemas/json/import-package.schema.json`、`/schemas/json/planning-snapshot.schema.json`、`/schemas/json/planning-problem.schema.json`、`/schemas/json/kpi.schema.json`、`/schemas/json/validation-report.schema.json`、`/schemas/json/error.schema.json`、`/schemas/data_dictionary.yaml`、`/schemas/samples/planning-snapshot.synthetic.json`、`/schemas/samples/planning-problem.synthetic.json`、`/backend/app/__init__.py`、`/backend/app/domain/__init__.py`、`/backend/app/domain/types.py`、`/backend/app/domain/contracts.py`、`/backend/app/domain/validation.py`、`/backend/app/snapshots/__init__.py`、`/backend/app/snapshots/contracts.py`、`/backend/app/planning/problem/__init__.py`、`/backend/app/planning/problem/contracts.py`、`/backend/tests/contract/test_schema_contracts.py`、`/pyproject.toml`、`/uv.lock`、生成但不提交的 `/build/traceability/TASK-P0-03-report.json`，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: import pipeline、ORM/migrations、API、Celery、`planning/backends/cp_sat/**`。

Implementation steps: 定义 Draft 2020-12 versioned schema IDs；建立 canonical ID/UTC/duration 纯类型；创建 Import/Snapshot/Problem/KPI/Error/ValidationReport 顶层 skeleton；建立最小引用/时间/工时语义预检；添加 round-trip/positive/negative contract tests。PlanningProblem 决策沿用 ADR-0003，不新增 Solver 或新架构决定。

Outputs: Schema skeleton、纯领域类型、data dictionary 初版、contract test results。

Documentation impact: required

Documents to update: `/docs/current_phase.md`、`/docs/contracts/README.md`、`/docs/contracts/import-and-normalization.md`、`/docs/contracts/schema-index.md`、`/docs/contracts/schema-versioning.md`、`/docs/contracts/planning-snapshot.md`、`/docs/contracts/planning-problem.md`、`/docs/domain/domain-model.md`、`/docs/domain/operation-instance-and-resource-options.md`、`/docs/domain/time-calendar-and-material-boundaries.md`、`/docs/domain/kpi-contract.md`、`/docs/domain/error-model.md`、`/docs/core/glossary.md`、`/docs/architecture/data-authority.md`、`/docs/architecture/provenance-and-versioning.md`、`/docs/architecture/repository-layout.md`、`/docs/architecture/technology-stack.md`、`/docs/planning/constraint-catalog.md`、`/docs/planning/solver-backend-contract.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/quality/property-tests.md`、`/docs/quality/benchmark-regression.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/adr/README.md`、`/docs/milestones/README.md`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: Schema 和纯领域类型会固定合同字段、版本、不变量及序列化语义。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-SNAPSHOT`、`IMPACT-PROBLEM`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: REQ-001/002/003/009、NFR-DET/TRC、ENG-SOL/VER 到 Schema、contract tests 和 data dictionary artifacts 的关系。

Schema changes: 首次发布 schema set `1.0.0` 与 `*.v1` 合同；根对象默认拒绝未知字段且不声明业务默认值。未来任何字段/语义变化按兼容规则升版。

Migration: 无数据库迁移；从 `unassigned` 到首次 `1.0.0`，此前无已发布 consumer 或历史 artifact 可迁移。

Error behavior: invalid version/reference/time/duration 明确拒绝。

Tests: `TEST-CONTRACT-001`；Schema meta-validation/positive/negative、UTC/duration、reference integrity、unknown field policy、synthetic isolation、serialization round-trip、schema index/data dictionary coverage。

Benchmark impact: PlanningProblem contract 首次落地触发 Benchmark 规则审查；P0 尚无固定 Scenario/Solver/baseline，故不生成或伪造性能结果，P2 replay 仍为 `PLANNED`。

Simulation scenarios: 只提供 Schema sample，不生成正式场景。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app backend/tests/contract`；`uv run pyright backend/app backend/tests/contract`；`uv run pytest -q backend/tests/unit backend/tests/contract`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-03-domain-and-schema-skeleton.md --check-diff --report build/traceability/TASK-P0-03-report.json`；`uv build`。

Artifacts: published schema files、`schemas/data_dictionary.yaml`、explicitly synthetic samples、contract test result、ignored `build/traceability/TASK-P0-03-report.json`。

Explicitly excluded: Normalization、Snapshot builder/hash 实现、Solver、生产 Adapter。

PROD_OPEN: OPEN-001/002/003/004/007/013/015 引用但不关闭。

SIM_ASSUMPTIONS: sample 数据显式 synthetic。

Rollback: 使用 schema version/compatibility 规则回退；已发布版本不可无痕覆盖。

## Completion evidence

Completed at: `2026-08-19T10:31:56+08:00`

### Delivered artifacts

- Schema set `1.0.0`：六份 JSON Schema Draft 2020-12 artifacts——`import-package.v1`、`planning-snapshot.v1`、`planning-problem.v1`、`kpi.v1`、`error.v1`、`validation-report.v1`；每份均有稳定 URN `$id`，根对象拒绝未知字段且无 `default`。
- Data dictionary 与 samples：`schemas/data_dictionary.yaml` 记录版本、单位、字段边界和 PROD_OPEN；两份 sample 均明确 synthetic，不是正式 Scenario、Fixture 或生产默认值。
- Pure contracts：`backend/app/domain/`、`backend/app/snapshots/contracts.py`、`backend/app/planning/problem/contracts.py` 提供标准库值语义、JSON-compatible `TypedDict` 和最小 reference/UTC/duration/lag precheck；不包含 ORM、API、Pydantic、OR-Tools、Builder、hash 或 Solver。
- Version/tooling：`pyproject.toml`、`app.SCHEMA_VERSION` 与 data dictionary 均为 `1.0.0`；runtime dependencies 仍为空，dev group/`uv.lock` 精确锁定 jsonschema、PyYAML、pytest、Ruff 和 Pyright。
- Tests：[`TEST-CONTRACT-001`](../../../backend/tests/contract/test_schema_contracts.py) 覆盖 schema meta/positive/negative、错误版本、未知字段、UTC、duration/tick、引用、RUNNING facts、Production/Synthetic 隔离、JSON round-trip 和 data dictionary coverage。
- Traceability report：`build/traceability/TASK-P0-03-report.json` 由 `.gitignore` 排除；记录 Diff base/HEAD `a0bee020e29bf62fc6294f73a703a253afc0c2c4`、58 changed paths、10 impact rows、29/29 expected/observed documents、0 missing refs、0 issues。
- Build artifacts（ignored）：`dist/plantnexus_aps-0.0.0.tar.gz` 与 wheel；wheel 清单确认包含全部 domain/snapshot/problem contract modules。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/checked 17 packages，lock 无漂移。 |
| `uv run ruff check backend/app backend/tests/contract` | 0 | PASS；`All checks passed!`。 |
| `uv run pyright backend/app backend/tests/contract` | 0 | PASS；0 errors、0 warnings、0 informations。 |
| `uv run pytest -q backend/tests/unit backend/tests/contract` | 0 | PASS；21 tests passed（8 governance unit + 13 schema contract）。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；107 docs、30 root IDs、30 trace rows、23 Test IDs、15 OPEN、5 SIM assumptions、10 risks、9 Tasks。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-03-domain-and-schema-skeleton.md --check-diff --report build/traceability/TASK-P0-03-report.json` | 0 | PASS；58 paths、10 impact rows、29/29 required documents、0 issues。 |
| `uv build` | 0 | PASS；成功构建 sdist 与 wheel。 |

以上命令在完成状态、追踪链接和本证据写入后再次执行，结果保持 PASS。

### Documentation impact and traceability

Documentation impact: `required`。实际修改任务卡 `Documents to update` 列出的全部 37 份 Markdown：Contract/Domain/Architecture/Planning/Quality/ADR 文档同步机器事实，治理注册表与追踪记录同步版本/审查结论，Current Phase/Milestone/Task/Inventory 同步状态。影响矩阵要求的 29 份 supporting documents 全部出现在 observed documents 中。

Traceability updates:

- REQ-001 → `import-package.v1` + TEST-CONTRACT-001；Import/Normalization pipeline 仍为 `PLANNED`。
- REQ-002 → `planning-snapshot.v1`、pure type、UTC/isolation/round-trip tests；Snapshot builder/hash 仍为 `PLANNED`。
- REQ-003 → `planning-problem.v1` Operation/ResourceOption skeleton 与 reference/duration precheck；order/lot/routing expansion 仍为 `PLANNED`。
- REQ-009 / NFR-TRC-001 → stable schema URNs、schema set version、data dictionary、Diff base 和本节证据；real source/hash/manifest/audit 仍为 `PLANNED`。
- NFR-DET-001 → strict UTC/seconds/ticks 与 deterministic JSON round-trip；canonical Snapshot/Problem hash 和 Scenario replay 仍为 `PLANNED`。
- ENG-SOL-001 → ADR-0003-aligned Solver-neutral PlanningProblem Schema/type；Problem builder、Backend 和 Solver 仍为 `PLANNED`。
- ENG-VER-001 → `pyproject.toml`、`app.SCHEMA_VERSION`、data dictionary、versioned machine artifacts、lock 和 compatibility/migration statement。
- TASK-P0-03 → TEST-CONTRACT-001 → six Schemas/data dictionary/synthetic samples/test and traceability reports；TASK-P0-04 保持 `planned`，未自动启动。

Change-impact matrix match:

- `IMPACT-SCHEMA`：机器 Schema、human contracts、schema index/version、domain model、traceability 与 contract tests 同步。
- `IMPACT-DOMAIN`：纯类型/预检与 glossary、data authority、domain model、traceability 同步；无 ORM/FastAPI/OR-Tools。
- `IMPACT-SNAPSHOT`：Snapshot contract/provenance/property-test 边界同步；builder/hash/replay 未实现。
- `IMPACT-PROBLEM`：PlanningProblem contract、Constraint catalog、ADR index、provenance 与 Benchmark review 同步；无 Solver Benchmark 可伪造。
- `IMPACT-DEPENDENCY` / `IMPACT-VERSION-METADATA`：锁定 dev tools，runtime dependency 仍空；schema version 三处一致，未引入 OR-Tools。
- `IMPACT-TESTS`：TEST-CONTRACT-001 登记并链接真实测试；documentation consistency 明确 Schema validator 的独立职责。
- `IMPACT-PHASE`：只记录 P0-03 完成；P0 Gate 未通过，P0-04/P1 未启动。
- `IMPACT-GOVERNANCE-REGISTRY`：新增 version-metadata path rule；REQ/NFR/OPEN/SIM/RISK 注册表均记录真实审查，未改变 ID/status/format semantics。
- `IMPACT-DOCS`：metadata、links、fences、inventory 和注册引用全量 PASS。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`；Schema 仅引用既有问题，不关闭、不猜值。SIM_ASSUMPTIONS: 未新增/修改；sample 显式 synthetic 且无工厂参数。Benchmark impact: 已审查，因无 Problem builder/Solver/固定 Scenario baseline，不生成性能结果；P2 replay 仍为 `PLANNED`。Schema/Migration: 首次 `1.0.0`，此前无 published consumer/history/DB，故无数据迁移；未来版本不得无痕覆盖 v1。Rollback: 可移除未被 consumer 使用的 1.0.0 skeleton 与 dev tooling并恢复 `unassigned`，但一旦外部发布/消费，必须发布新版本并按兼容规则迁移，不能覆盖 v1。
