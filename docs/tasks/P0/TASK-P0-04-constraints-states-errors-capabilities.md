---
doc_id: TASK-P0-04
title: Constraints States Errors and Capabilities
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [8, 26, 27, 30, 32, 33, 34, 91, 98]
last_reviewed: 2026-08-19
---

# TASK-P0-04 — Constraints, States, Errors and Capabilities

Requirement IDs: REQ-004, REQ-005, REQ-007, REQ-008

NFR / ENG IDs: NFR-COR-001, NFR-REL-001, NFR-HUM-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P0-02, TASK-P0-03

Goal: 把 C-001～C-011、Deferred capabilities、三套状态机和产品错误分类转为可测试 rule sheet/contract skeleton。

Inputs: constraint catalog、state machine docs、error model、capability matrix。

Diff base: 0aa215620501ef27bafe7636bf31ff7194f1f075

Files allowed to change: `/backend/app/__init__.py`、`/backend/app/domain/__init__.py`、`/backend/app/domain/contracts.py`、`/backend/app/domain/errors.py`、`/backend/app/domain/capabilities.py`、`/backend/app/domain/validation.py`、`/backend/app/domain/state_machines/__init__.py`、`/backend/app/domain/state_machines/contracts.py`、`/backend/app/planning/validation/__init__.py`、`/backend/app/planning/validation/rule_sheet.py`、`/backend/tests/contract/test_schema_contracts.py`、`/backend/tests/contract/test_rule_contracts.py`、`/schemas/data_dictionary.yaml`、`/schemas/json/error.v2.schema.json`、`/schemas/json/validation-report.v2.schema.json`、`/schemas/json/state-transition.schema.json`、`/schemas/rules/constraint-rule-sheet.v1.yaml`、`/schemas/rules/capability-registry.v1.yaml`、`/schemas/rules/error-code-registry.v1.yaml`、`/schemas/rules/state-machines.v1.yaml`、`/pyproject.toml`、`/uv.lock`、生成但不提交的 `/build/validation/TASK-P0-04-rule-contracts.json` 与 `/build/traceability/TASK-P0-04-report.json`，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: `/schemas/json/error.schema.json`、`/schemas/json/validation-report.schema.json`、`/schemas/json/planning-problem.schema.json` 等既有 v1 artifact；`planning/backends/cp_sat/**`、CpModel/IntervalVar、真实 Solver、候选排程 ScheduleValidator/evaluator、mutation/Golden/infeasible Fixture、审批/发布业务实现、API/ORM/Worker 与 P1 pipeline。

Implementation steps: 为 C-001～C-011 定义输入、公式、positive/negative example、error/violation shape 和 Test ID；为 C-012～C-018 固定 capability/rejection 合同；建立三套状态枚举、显式允许转移、终态和 guard/evidence；建立七类产品错误与稳定 code/category 映射；提供只检查规则表完整性与跨注册表一致性的 CLI。PlanningProblem/Constraint/状态语义沿用总规、ADR-0005/0007，不新增 Solver、Validator evaluator 或发布行为。

Outputs: Validator Rule Sheet、state transition table、error/capability contracts。

Documentation impact: required

Documents to update: `/docs/current_phase.md`、`/docs/contracts/README.md`、`/docs/contracts/planning-solution-and-schedule-version.md`、`/docs/contracts/schema-index.md`、`/docs/contracts/schema-versioning.md`、`/docs/core/capability-matrix.md`、`/docs/core/glossary.md`、`/docs/domain/domain-model.md`、`/docs/domain/error-model.md`、`/docs/domain/state-machines/planning-run.md`、`/docs/domain/state-machines/schedule-version.md`、`/docs/domain/state-machines/export-job.md`、`/docs/architecture/data-authority.md`、`/docs/architecture/provenance-and-versioning.md`、`/docs/architecture/technology-stack.md`、`/docs/planning/constraint-catalog.md`、`/docs/planning/schedule-validator.md`、`/docs/planning/solver-backend-contract.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/quality/validator-mutation-tests.md`、`/docs/quality/benchmark-regression.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/adr/README.md`、`/docs/milestones/README.md`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: Constraint、状态、错误和能力合同是规范性核心，任何可执行 rule sheet 都必须与人类文档保持双向一致。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-VALIDATOR`、`IMPACT-STATE`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: REQ-004/005/007/008、NFR-COR-001/NFR-REL-001/NFR-HUM-001、ENG-VAL-001/ENG-ERR-001/ENG-VER-001 → TASK-P0-04 → TEST-RULE-SHEET-001/TEST-STATE-TRANSITION-001/TEST-ERROR-MAPPING-001/TEST-CAPABILITY-001 → versioned Schema/YAML registries、pure contracts 与 rule-contract report；C-001～C-018、ADR-0005/0007 和后续 TEST-VALIDATOR-MUTATION 保持可追踪且不虚报实现。

Schema changes: schema set `1.0.0` → `1.1.0`（set-level additive）；保留 `error.v1`、`validation-report.v1` 原 artifact，新增非互换的 `error.v2`、`validation-report.v2` 与首次 `state-transition.v1`；新增四份 `*.v1` YAML registry/rule contracts。所有 JSON Schema 使用 Draft 2020-12、稳定 URN、拒绝未知根字段且无业务默认值。

Migration: 无数据库或历史 artifact migration；v1 文件继续可按 v1 boundary 验证，v2 consumer 必须显式要求 v2，不做 alias/静默升级。当前无 Error/Validation 持久化 consumer；未来迁移只能通过显式 adapter/new artifact 完成。

Error behavior: 七类总规 category 不变；`UNSUPPORTED_CAPABILITY`、`INVALID_STATE_TRANSITION`、`SCHEDULE_VALIDATION_FAILED` 使用独立稳定 code/category 映射。未知 capability 是 DATA_ERROR，已登记但 V1 不支持/延迟的 capability 返回 UNSUPPORTED_CAPABILITY；非法状态转移不得静默接受。

Tests: `TEST-RULE-SHEET-001`（C-001～C-018 唯一/完整、字段/公式/正反例/violation/Test ID）、`TEST-STATE-TRANSITION-001`（三套状态 positive/negative/terminal）、`TEST-ERROR-MAPPING-001`（七类、code/category、v1/v2 isolation）、`TEST-CAPABILITY-001`（registry 与 explicit rejection）；保留并重跑 `TEST-CONTRACT-001`。

Benchmark impact: 仅把总规既有 Constraint semantics 固定为规则表，不修改 PlanningProblem、Solver、Constraint 语义或 baseline；P0 无 Solver/Scenario baseline，因此不生成虚假性能数据，P2 replay 责任不变。

Simulation scenarios: future-capability examples 只验证明确拒绝。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app backend/tests/contract`；`uv run pyright backend/app backend/tests/contract`；`uv run pytest -q backend/tests/unit backend/tests/contract`；`uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-04-rule-contracts.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-04-constraints-states-errors-capabilities.md --check-diff --report build/traceability/TASK-P0-04-report.json`；`uv build`。

Artifacts: `/schemas/rules/*.v1.yaml`、三份新增 versioned JSON Schema、pure domain/state/rule contracts、`TEST-*` contract tests、ignored rule-contract/traceability reports。

Explicitly excluded: 用任何 Solver 验证 rule sheet。

PROD_OPEN: OPEN-004/005/006/008/009；同时审查 C-006/状态门相关 OPEN-007/010，全部保持 OPEN，不猜值、不关闭。

SIM_ASSUMPTIONS: 未支持能力场景的 expected result 可为 `UNSUPPORTED_CAPABILITY`。

Rollback: schema set metadata 可回退到 `1.0.0` 并移除尚无 consumer 的新增 v2/v1 artifacts；不得覆盖或删除既有 v1、已分配 C-ID、状态名或错误历史。若新增合同已被消费，则发布新版本并显式迁移，不原地回写。

## Completion evidence

Completed at: `2026-08-19T11:27:15+08:00`

### Delivered artifacts

- Schema set `1.1.0`：以 set-level additive 方式新增 `error.v2`、`validation-report.v2`、`state-transition.v1`；`error.v1`、`validation-report.v1`、`planning-problem.v1` 经 `git diff --exit-code <Diff base> -- <paths>` 验证保持原文件不变，v1/v2 不静默互换。
- Machine registries：`constraint-rule-sheet.v1` 完整覆盖 11 个 V1 active constraints 与 7 个 deferred constraints；`capability-registry.v1` 覆盖 20 个 capability；`error-code-registry.v1` 覆盖七类与 19 个唯一 code mapping；`state-machines.v1` 覆盖 3 套 machine、27 states、42 allowed transitions。
- Pure contracts：标准库 `errors.py`、`capabilities.py`、`state_machines/contracts.py` 与 rule-sheet completeness CLI；不含 ORM/API/Pydantic/OR-Tools、CpModel、candidate schedule evaluator、状态持久化或审批/发布动作。
- Tests：[`test_rule_contracts.py`](../../../backend/tests/contract/test_rule_contracts.py) 形成 TEST-RULE-SHEET-001、TEST-STATE-TRANSITION-001、TEST-ERROR-MAPPING-001、TEST-CAPABILITY-001；连同 TEST-CONTRACT-001 和治理单测共 31 tests（8 unit + 23 contract）。
- Machine reports（ignored）：`build/validation/TASK-P0-04-rule-contracts.json` 为 `rule-contract-report.v1` PASS、0 issues；`build/traceability/TASK-P0-04-report.json` 为 `traceability-report.v1` PASS、0 issues。
- Build artifacts（ignored）：sdist 与 wheel 均成功；wheel 清单确认包含 capability/error/state-machine/rule-sheet modules。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/checked 17 packages，lock 无漂移。 |
| `uv run ruff check backend/app backend/tests/contract` | 0 | PASS；`All checks passed!`。 |
| `uv run pyright backend/app backend/tests/contract` | 0 | PASS；0 errors、0 warnings、0 informations。 |
| `uv run pytest -q backend/tests/unit backend/tests/contract` | 0 | PASS；31 passed（8 governance unit + 23 contract）。 |
| `uv run python -m app.planning.validation.rule_sheet --report build/validation/TASK-P0-04-rule-contracts.json` | 0 | PASS；active 11、deferred 7、capabilities 20、error codes 19、machines 3、states 27、transitions 42。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；107 docs、30 root IDs、30 trace rows、27 Test IDs、15 OPEN、5 SIM assumptions、10 risks、9 Tasks。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-04-constraints-states-errors-capabilities.md --check-diff --report build/traceability/TASK-P0-04-report.json` | 0 | PASS；57 paths、10 impact rows、31/31 required documents、0 missing refs、0 issues。 |
| `uv build` | 0 | PASS；成功构建 sdist 与 wheel。 |

以上命令在完成状态、追踪链接和本证据写入后再次执行，结果保持 PASS。额外 `git diff --check` exit 0，仅输出 Windows working-copy LF→CRLF 提示，无 whitespace error。

### Documentation impact and traceability

Documentation impact: `required`。实际修改 36 份 Markdown：Contracts（README、PlanningSolution/ScheduleVersion、Schema index/versioning）、Core（Capability Matrix、Glossary）、Domain（model、error、三套 state machine）、Architecture（authority、provenance、technology）、Planning（Constraint Catalog、ScheduleValidator、Solver contract）、Quality（test matrix、mutation、benchmark、documentation checks）、ADR index、Current Phase/Milestone/Task indexes/template/card，以及九份 Governance registry/matrix/inventory 文档。影响矩阵要求的 31 份 supporting documents 全部进入 observed documents。

Traceability updates:

- REQ-004 / NFR-COR-001 → C-001～C-018 rule sheet → TASK-P0-04 → TEST-RULE-SHEET-001 → YAML/CLI report；Solver/candidate correctness 仍为 `PLANNED`。
- REQ-005 / ENG-VAL-001 → validation-report.v2 + independent validation-package import boundary → TEST-RULE-SHEET-001；真实 evaluator、illegal Fixture 与 TEST-VALIDATOR-MUTATION 仍由 TASK-P0-07/P2。
- REQ-007 / NFR-HUM-001 → ScheduleVersion state registry → TEST-STATE-TRANSITION-001；权限、audit、immutability 与 publish implementation 仍为 P3 `PLANNED`。
- NFR-REL-001 → ExportJob retry/terminal contract → TEST-STATE-TRANSITION-001；Worker/lease/idempotency implementation 仍由 TASK-P0-08/P3。
- REQ-008 → DYNAMIC_REPLANNING capability declaration/state boundary；ExecutionEvent/Replan/ChangeReport 仍为 P4 `PLANNED`。
- ENG-ERR-001 → error.v2 + seven categories/19 codes → TEST-ERROR-MAPPING-001；HTTP mapping `PLANNED`。
- ENG-VER-001 → schema set `1.1.0` in pyproject/package/data dictionary、v1 preservation、explicit compatibility/migration 与 TEST-CONTRACT-001。
- ADR-0005/0007 decisions 未改变；rule completeness 不冒充 ScheduleValidator PASS，状态 metadata 不冒充业务实现，因此未新增 ADR。

Change-impact matrix match:

- `IMPACT-SCHEMA`：data dictionary、新增三份 JSON Schema/四份 rule registries与 Contract/index/version/domain/trace 同步。
- `IMPACT-DOMAIN`：error/capability/state pure contracts 与 domain/glossary/authority/trace 同步。
- `IMPACT-VALIDATOR`：仅 completeness/import-boundary module，与 ScheduleValidator/Constraint/Mutation/Test/trace 同步；无 candidate evaluator。
- `IMPACT-STATE`：三套 machine human/machine tables、ADR index 与 trace 同步；无 persistence/action。
- `IMPACT-DEPENDENCY` / `IMPACT-VERSION-METADATA`：只更新 schema metadata；runtime/dependency pins/lock 不变，无 OR-Tools replay。
- `IMPACT-TESTS`：四个新 Test ID 链接真实 tests/artifacts，31 tests PASS。
- `IMPACT-PHASE`：只记录 P0-04 完成；P0 Gate 未通过，P0-05/P1 未启动。
- `IMPACT-GOVERNANCE-REGISTRY`：REQ/NFR/ENG/OPEN/SIM/RISK/trace/version review 全量同步，registry format versions 不变。
- `IMPACT-DOCS`：metadata、links、fences、inventory 与引用全量 PASS。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`；尤其 OPEN-004/005/007/009/010 未被 rule/guard 文本关闭，OPEN-006/008 未获得默认权重/lot policy。SIM_ASSUMPTIONS: 未新增/修改，五项继续 `ACTIVE`；unsupported expected result 不是 Scenario 事实。Risks: RISK-003/004/006 控制加强但无实现证据，RISK-001～010 全部继续 `MONITORED`。Benchmark impact: 无 PlanningProblem/Solver/Scenario baseline 变化，不伪造性能结果；P2 首个 baseline 必须记录 rule/report version。Schema/Migration: set-level additive `1.1.0`，v1 保留；无 DB、persisted consumer 或历史 run artifact，故 migration none，未来 consumer 必须显式 adapter/new version。Rollback: 尚无 consumer 时可移除新增 artifacts 并把 metadata 恢复 `1.0.0`；一旦消费则必须发布新版本/迁移，不覆盖 v1 或删除已分配 C-ID/state/code。
