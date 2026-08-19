---
doc_id: TASK-P0-06
title: SIM-MINIMAL-001 and Golden Schedule
status: done
spec_version: 0.3.0
phase: P0
normative: true
source_sections: [43, 46, 71, 72, 88]
last_reviewed: 2026-08-19
---

# TASK-P0-06 — SIM-MINIMAL-001 and Golden Schedule

Requirement IDs: REQ-004, REQ-005, REQ-011, REQ-012

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001

Depends on: TASK-P0-05

Goal: 创建可人工验证、可重复生成/导入的 `SIM-MINIMAL-001` 和正确 Golden Schedule。

Inputs: Scenario/FactoryProfile schemas、C-001～C-011 rule sheet、Standard Import skeleton。

Diff base: 42c68ff014ca680e3d13b0e1a6b67a57ec1d82ae

Files allowed to change: `/fixtures/deterministic/SIM-MINIMAL-001/factory-profile.json`、`/fixtures/deterministic/SIM-MINIMAL-001/scenario-spec.json`、`/fixtures/deterministic/SIM-MINIMAL-001/scenario-manifest.json`、`/fixtures/deterministic/SIM-MINIMAL-001/import-package.json`、`/fixtures/deterministic/SIM-MINIMAL-001/golden-schedule.json`、`/fixtures/deterministic/SIM-MINIMAL-001/expected-validation.json`、`/fixtures/deterministic/SIM-MINIMAL-001/expected-kpis.json`、`/fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md`、只负责读取/交叉引用/canonical hash 重放且不评估 C-ID 的 `/backend/app/simulation/scenarios/golden_fixture.py`、`/backend/tests/golden/test_sim_minimal_001.py`、生成但不提交的 `/build/validation/TASK-P0-06-sim-minimal-001.json` 与 `/build/traceability/TASK-P0-06-report.json`，以及下方 `Documents to update` 的明确文档路径。

Files forbidden to change: `/schemas/**`、`/backend/app/planning/**`、`/backend/app/simulation/generators/**`、`/backend/app/simulation/profiles/**`、`/backend/app/simulation/execution/**`、`/backend/app/simulation/baselines/**`、`/backend/app/simulation/benchmarks/**`、`/backend/tests/contract/**`、`/backend/tests/simulation/**`、其他 `/fixtures/**`、`/pyproject.toml`、`/uv.lock`、CpModel、IntervalVar、随机/启发式 Solver、PlanningProblem/Snapshot/Normalization builder、生产数据/参数、Constraint/Objective/KPI/ValidationReport 语义和 P1+ pipeline。

Implementation steps: 以 `SIM-MINIMAL-001@1.0.0` 设计恰好 2 workshops、2 production lines、3 capacity-1 resources、1 order、3 operations；前两道 operation 位于同一车间并提供快/慢两台候选设备，以首尾相接的同机 interval 实际覆盖 C-004，第三道 operation 位于另一车间并受 maintenance calendar 限制，两个 edge 覆盖 C-002 min/max lag 且跨车间 edge 同时声明 C-009 transport lag；以 15 分钟 tick、4 小时 horizon 手算 schedule 与 Delivery/Planning/Resource KPI；把 Profile/Scenario/Import/Manifest/Schedule/expected artifacts 和定量假设引用全部版本化；Import `records` 只使用 P0 fixture-local vocabulary，不声明为 P1 canonical records；`golden_fixture.py` 只做 strict artifact loading、existing pure contract precheck、cross-file identity 与 canonical Import/hash replay，不实现 schedule validator；Golden test 使用与 loader 分离的直接计算逐条复核 C-001～C-011，C-007/C-008 在无 execution fact/lock 时以可验证理由标记 `NOT_APPLICABLE`，不把 rule-sheet metadata 或 expected artifact 自证当作 correctness。

Outputs: ScenarioSpec、FactoryProfile reference、import package、manual schedule、calculation note、expected validation/KPI。

Documentation impact: required

Documents to update: `/docs/current_phase.md`、`/docs/contracts/import-and-normalization.md`、`/docs/domain/kpi-contract.md`、`/docs/architecture/provenance-and-versioning.md`、`/docs/planning/constraint-catalog.md`、`/docs/planning/schedule-validator.md`、`/docs/quality/fixtures-and-golden-tests.md`、`/docs/quality/validator-mutation-tests.md`、`/docs/quality/property-tests.md`、`/docs/quality/test-strategy-and-matrix.md`、`/docs/quality/documentation-consistency-checks.md`、`/docs/simulation/README.md`、`/docs/simulation/factory-profile.md`、`/docs/simulation/scenario-spec-and-provenance.md`、`/docs/simulation/scenario-library-and-matrix.md`、`/docs/simulation/synthetic-generator-and-determinism.md`、`/docs/simulation/performance-gates.md`、`/docs/milestones/README.md`、`/docs/tasks/README.md`、`/docs/tasks/TASK_TEMPLATE.md`、`/docs/governance/requirements-register.md`、`/docs/governance/nfr-and-engineering-register.md`、`/docs/governance/traceability-rules.md`、`/docs/governance/traceability-matrix.md`、`/docs/governance/prod-open-register.md`、`/docs/governance/sim-assumption-register.md`、`/docs/governance/risk-register.md`、`/docs/governance/change-impact-matrix.md`、`/docs/governance/document-inventory.md`、本 Task Card。

Documentation impact rationale: 首个 Golden Fixture 会形成稳定 Scenario/Test/Artifact 引用和具体 SIM_ASSUMPTION。

Change-impact matrix rows reviewed: `IMPACT-SIM-SCENARIO`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

Traceability updates: REQ-004/005 → C-001～C-011 fixture-local independent positive calculations（不形成 Solver 或通用 Validator evaluator）；REQ-011/012 与 NFR-DET-001/NFR-TRC-001 → `SIM-MINIMAL-001@1.0.0` → `TEST-GOLDEN-FJSP` / `TEST-SCENARIO-REPLAY` / TEST-CALENDAR/MATERIAL/CROSS-WORKSHOP/MAX-LAG positive slice → versioned Profile/Scenario/Import/Manifest/Golden/expected artifacts 和 replay report；NFR-COR-001 → manual formula evidence/hard violation count 0。同步 SIM-ASSUMPTION 定量参数、fixture/hash provenance 与 P0 进度；TEST-VALIDATOR-MUTATION、negative rejection、正式 ValidationReport/KPI、Snapshot/Problem/Solver 继续 `PLANNED`。

Schema changes: none。既有 FactoryProfile/Scenario/Manifest/Import v1 足够表达本 fixture；Golden Schedule、expected validation/KPI 使用明确 `golden-*.v1` fixture-local version，不注册为 repository-wide Schema 或 P1 canonical contract。若发现必须修改 Schema 才能完成，则停止本 Task 并先修订 TASK-P0-03/05 边界。

Migration: 无。

Error behavior: Fixture 文件缺失/未知、JSON 根不是 object、Profile/Scenario/Manifest pure contract 不合法、跨文件 ID/version/seed/capability/source/package 不一致、Production 标记混入、canonical dataset/hash 不一致或 expected C-ID 集不完整时 replay 以明确 issue 失败；人工结果不可复算时测试失败，不调整规则迎合 Fixture。P0-06 不输出通用 Validator violation。

Tests: FactoryProfile/Scenario/Manifest/Import JSON Schema PASS；pure semantic precheck PASS；non-empty canonical Import byte/hash stability；manifest/Scenario/Profile/Generator/seed/capability/package cross-reference；strict 2 workshop/3 resource/alternative/cross-workshop/maintenance facts；Golden Schedule 每个 applicable C-ID 直接复算、C-007/C-008 N/A 理由；expected KPI 由 schedule/calendar/order 复算；source boundary 不含 Solver/Validator evaluator import。

Benchmark impact: 只作为 correctness fixture，不作性能结论。

Simulation scenarios: SIM-MINIMAL-001。

Acceptance commands: `uv sync --locked`；`uv run ruff check backend/app backend/tests/contract backend/tests/simulation backend/tests/golden`；`uv run pyright backend/app backend/tests/contract backend/tests/simulation backend/tests/golden`；`uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden`；`uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P0-06-sim-minimal-001.json`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-06-minimal-scenario-and-golden-schedule.md --check-diff --report build/traceability/TASK-P0-06-report.json`；`git diff --exit-code 42c68ff014ca680e3d13b0e1a6b67a57ec1d82ae -- schemas backend/app/planning backend/app/simulation/generators backend/app/simulation/profiles pyproject.toml uv.lock`；`git diff --check`；`uv build`。

Artifacts: complete deterministic fixture package、`golden-fixture-replay-report.v1`（ignored build artifact）和人工验证说明。

Explicitly excluded: 真实求解逻辑、生产参数、规模 Benchmark。

PROD_OPEN: 不关闭；所有 topology/time 数值是 synthetic。

SIM_ASSUMPTIONS: 新增并引用 SIM-ASSUMPTION-006～009，分别固定本 fixture version 的 topology/resource counts、time grid/horizon/calendar、operation durations/precedence/transport、order gates/due/weight；它们全部 synthetic-only，不作为生产默认值或通用 XS baseline。

Rollback: 删除该 fixture version；如果已经作为 baseline 发布，则新建修订版，不覆盖历史。

## Completion evidence

Completed at: `2026-08-19T12:56:18+08:00`

### Delivered artifacts

- 正式 correctness asset：[`SIM-MINIMAL-001@1.0.0`](../../../fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md) 固定 `PROFILE-SIM-MINIMAL-FJSP@1.0.0`、`P0-MANUAL-FIXTURE-ASSEMBLER@1.0.0`、seed 6001、2 workshops、2 lines、3 capacity-1 resources、1 order、3 operations、alternative resources、cross-workshop edge 和一个 maintenance interval；全部数值引用 SIM-ASSUMPTION-006～009，且 `synthetic_only/synthetic=true`。
- Standard Import/provenance：10 个 fixture-local collection、15 个 records 进入 `import-package.v1`；manifest 引用 Scenario/Profile/Assembler/seed/capabilities/package，`canonical-json.v1` hash 为 `sha256:fd8e5af387c7d4197a2664dfa89e93912091647d5809f1b76468d36edab29c10`。`generated_at` 不进入 hash；`sim-minimal-records.v1` 不声明为 P1 canonical vocabulary。
- 人工 Golden：三道 assignment 为 `[0,4)`、`[4,6)`、`[8,12)`，覆盖同机边界、material exact boundary、maintenance end boundary、0/1800 秒 precedence lag、900 秒 transport、duration 和 16-tick horizon。C-001～C-006/C-009～C-011 直接复算 PASS；C-007/C-008 因无 execution facts/locks 明确 N/A；hard violation count 期望为 0。
- KPI/objective：从事实复算 completion `11:00Z`、due `11:30Z`、weighted tardiness 0、horizon-relative makespan 10800 秒、3 scheduled/0 unscheduled 及三台资源 busy/available/utilization；maintenance/transport lower bound 证明最早 completion 为 tick 12。`golden-kpi.v1` / `golden-validation.v1` 明确是 fixture-local expected artifacts，不冒充正式 `kpi.v1` / `validation-report.v2`。
- 实现与测试：[`golden_fixture.py`](../../../backend/app/simulation/scenarios/golden_fixture.py) 只做 8-artifact strict load、pure contract precheck、cross-file join 和 hash replay；[`test_sim_minimal_001.py`](../../../backend/tests/golden/test_sim_minimal_001.py) 形成 5 项 TEST-GOLDEN-FJSP/TEST-SCENARIO-REPLAY positive tests，并验证 loader 不导入 Planning/Solver/evaluator。没有创建 P0-07 rule evaluator、mutation、PlanningProblem、Solver 或 Benchmark。

### Acceptance results

| Command | Exit code | Result |
|---|---:|---|
| `uv sync --locked` | 0 | PASS；resolved/checked 17 packages，lock 无漂移。 |
| `uv run ruff check backend/app backend/tests/contract backend/tests/simulation backend/tests/golden` | 0 | PASS；`All checks passed!`。 |
| `uv run pyright backend/app backend/tests/contract backend/tests/simulation backend/tests/golden` | 0 | PASS；0 errors、0 warnings、0 informations。 |
| `uv run pytest -q backend/tests/unit backend/tests/contract backend/tests/simulation backend/tests/golden` | 0 | PASS；46 passed（8 governance unit + 23 contract + 10 simulation + 5 Golden）。 |
| `uv run python -m app.simulation.scenarios.golden_fixture --fixture fixtures/deterministic/SIM-MINIMAL-001 --report build/validation/TASK-P0-06-sim-minimal-001.json` | 0 | PASS；8 artifacts、10 collections、15 records、3 assignments、11 C-ID expectations、0 issues；scope 为 artifact-integrity-and-replay-only。 |
| `uv run python scripts/check_docs.py` | 0 | PASS；107 docs、30 roots/trace rows、27 Test IDs、15 OPEN、9 SIM assumptions、10 risks、9 Tasks。 |
| `uv run python scripts/check_docs.py --task docs/tasks/P0/TASK-P0-06-minimal-scenario-and-golden-schedule.md --check-diff --report build/traceability/TASK-P0-06-report.json` | 0 | PASS；39 paths、6 impact rows、20 required review docs、19 actually changed、0 missing refs/issues。 |
| `git diff --exit-code 42c68ff014ca680e3d13b0e1a6b67a57ec1d82ae -- schemas backend/app/planning backend/app/simulation/generators backend/app/simulation/profiles pyproject.toml uv.lock` | 0 | PASS；Schema、Planning/Validator、Generator/Profile code、dependency/version metadata 均未改动。 |
| `git diff --check` | 0 | PASS；无 whitespace error，仅输出 Windows LF→CRLF working-copy 提示。 |
| `uv build` | 0 | PASS；成功构建 sdist 与 wheel。 |

### Documentation impact and traceability

Documentation impact: `required`。实际 diff 为 39 paths：2 个 Python files、8 个 fixture artifacts、29 份 Markdown。机器矩阵命中 `IMPACT-SIM-SCENARIO`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`；20 份 required review documents 中 19 份实际更新。唯一未修改的 `/docs/tasks/TASK_TEMPLATE.md` 已逐项审查：现有模板已要求 Simulation contract/asset/generator/canonicalization version、seed、hash、Standard Import、Production rejection 及 sample/Fixture/Benchmark 边界，P0-06 没有形成新的通用 Task 字段或治理语义，因此无需机械改写。

Traceability updates:

- REQ-004/005、NFR-COR-001 → constraint-rule-sheet.v1 → TASK-P0-06 → TEST-GOLDEN-FJSP/CALENDAR/MATERIAL/CROSS-WORKSHOP/MAX-LAG positive slice → Golden Schedule/expected validation/calculation note；reusable evaluator、negative mutation、正式 ValidationReport 与 Solver 仍 `PLANNED`。
- REQ-011/012、NFR-DET-001/NFR-TRC-001 → Profile/Scenario/Assembler/seed/assumptions → non-empty Standard Import/manifest/hash → TEST-SCENARIO-REPLAY → `golden-fixture-replay-report.v1`；P1 canonical mapping/Normalization/Snapshot/Problem 和程序化 distribution generator 仍 `PLANNED`。
- ENG-VAL-001 只获得 loader 无 Planning/Solver import 和 test-local independent formulas 的 positive evidence；没有修改 `backend/app/planning/validation/**`，TEST-VALIDATOR-MUTATION 继续由 TASK-P0-07 独占。
- ENG-VER-001 增加 Profile/Scenario/Assembler/Golden expected asset version/hash；Schema set 保持 `1.2.0`，没有 Schema compatibility/migration 变化。

PROD_OPEN: OPEN-001～015 全部保持 `OPEN`，没有 closure record。SIM_ASSUMPTIONS: 新增 SIM-ASSUMPTION-006～009，连同既有五项共 9 项均 `ACTIVE`；只绑定 `SIM-MINIMAL-001@1.0.0`，不成为生产事实或通用 XS/Benchmark baseline。Risks: RISK-001/002/003/004/009 的早期控制增强，但缺少 P1 pipeline、mutation evaluator、生产隔离与历史/性能证据，因此 RISK-001～010 全部保持 `MONITORED`。

Schema changes: none；既有 v1 Schema 足够，fixture-local expected formats 不注册为全局 Schema。Migration: none；无 DB/consumer/历史 run。Benchmark impact: none；未运行 Solver、未采集 runtime/gap/memory/model size、不修改 `benchmarks/**` 或 OPEN-012。ADR: 落实 ADR-0001/0005，决定未改变，不新增 ADR。

Diff base 与验收时 Git HEAD 均为 `42c68ff014ca680e3d13b0e1a6b67a57ec1d82ae`；报告 source counts 为 committed range 0、working tree 39。本 Task 未提交用户工作树。Rollback 在其他 Task 消费前可删除整个 `SIM-MINIMAL-001@1.0.0` bundle、loader/test 和对应文档追踪；一旦 P0-07 或外部 artifact 引用，必须发布新 Scenario/Profile/fixture version 与新 hash，禁止覆盖历史 `1.0.0`。TASK-P0-07 保持 `planned`，本 Task 未自动进入下一任务。
