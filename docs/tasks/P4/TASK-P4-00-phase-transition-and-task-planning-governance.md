---
doc_id: TASK-P4-00
title: P4 Phase Transition and Task Planning Governance
status: in_progress
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-00 — P4 Phase Transition and Task Planning Governance

Task batch role: phase-planning-owner

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-012, REQ-013, REQ-014

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, NFR-HUM-001, ENG-ARCH-001, ENG-SOL-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P3-17

Start gate: 用户于2026-08-27明确批准P3→P4；TASK-P3-00～17全部`done`；P3 Exit report/manifest均为`READY`且`blocking_gaps=[]`；audit implementation `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`与evidence-only closure `61eeacdd5efc20b2321750e1310e9e21561c9fc2`为直接父子提交，两个exact SHA的required `validate`、GitHub Actions app `15368`和未过期artifact均已下载复验；启动时`main=origin/main=remote main=61eeacdd5efc20b2321750e1310e9e21561c9fc2`、ahead/behind=`0/0`且working tree clean。

Goal: 只关闭P3 Milestone、激活P4、创建完整P4 Task依赖计划并同步文档治理；不执行TASK-P4-01或任何P4业务、Schema、migration、dependency、test assertion或workflow变化。

Non-goals: 不实现ExecutionEvent、ReplanRequest、freeze window、OBJ-002、ChangeReport、Execution Simulator、API或UI；不创建P5 Task；不声明Production readiness、UAT、真实approval authority、external publish/deployment或capacity/SLA。

Inputs: P3 Exit report/manifest及implementation/closure artifacts；P4 Milestone；总规§35/47～50/79～80；全部相关ADR、架构、合同、Schema、状态机、规划、仿真、质量和治理基线；用户本次授权。

Diff base: 61eeacdd5efc20b2321750e1310e9e21561c9fc2

Files allowed to change: `docs/tasks/P4/TASK-P4-00-phase-transition-and-task-planning-governance.md`、`docs/tasks/P4/TASK-P4-01-dynamic-replanning-contract-and-adr-baseline.md`、`docs/tasks/P4/TASK-P4-02-execution-event-replan-change-report-schemas.md`、`docs/tasks/P4/TASK-P4-03-replan-event-persistence-and-state-transactions.md`、`docs/tasks/P4/TASK-P4-04-execution-event-ingestion-and-fact-projection.md`、`docs/tasks/P4/TASK-P4-05-freeze-window-and-effective-lock-projection.md`、`docs/tasks/P4/TASK-P4-06-stability-objective-and-change-report.md`、`docs/tasks/P4/TASK-P4-07-lexicographic-replan-solver-and-validator.md`、`docs/tasks/P4/TASK-P4-08-replan-application-and-schedule-version-lineage.md`、`docs/tasks/P4/TASK-P4-09-deterministic-execution-simulator-core.md`、`docs/tasks/P4/TASK-P4-10-disruption-scenario-library-and-replay.md`、`docs/tasks/P4/TASK-P4-11-change-report-read-model-and-export-integration.md`、`docs/tasks/P4/TASK-P4-12-dynamic-replanning-http-api.md`、`docs/tasks/P4/TASK-P4-13-replanning-workspace-ui-and-browser-e2e.md`、`docs/tasks/P4/TASK-P4-14-p4-vertical-slice-gate-evidence.md`、`docs/tasks/P4/TASK-P4-15-p4-exit-gate-audit.md`；以及`Documents to update`中逐字列出的路径与ignored `build/traceability/TASK-P4-00-report.json`。

Files forbidden to change: `backend/**`、`schemas/**`、`frontend/**`、`fixtures/**`、`benchmarks/**`、`infra/**`、`scripts/**`、`.github/workflows/**`、`pyproject.toml`、`uv.lock`、`backend/migrations/**`、P3 Exit report/manifest、P0～P3历史Task/ADR事实、任何P4业务实现、P5+详细Task和Production凭证。

Implementation steps: 精确复核P3状态/拓扑/required checks/artifacts/branch protection；将P3置为completed并激活P4；按合同/ADR→机器合同→持久化→事件事实投影→freeze→OBJ-002/ChangeReport→词典序Solver→Replan应用→Simulator→五类场景→read/export→API→UI→Vertical Gate→Exit Audit拆分TASK-P4-01～15；登记12个P4 Test ID与3项风险；同步全部命中文档和清单；运行本地验收；提交/push并核验exact provider；以evidence-only closure关闭本Task，但不启动P4-01。

Outputs: active P4治理基线、16张P4 Task卡、明确依赖图/启动门/阶段边界、61项Test registry、17项risk registry、185份Markdown inventory及双提交provider证据。

Capability ownership and boundaries: TASK-P4-01拥有语义/ADR；02机器合同；03持久化/状态事务；04 ExecutionEvent→事实/Snapshot；05 freeze/effective locks；06 OBJ-002/ChangeReport pure semantics；07 lexicographic Solver/Validator；08 ReplanRequest应用与new DRAFT lineage；09 Execution Simulator core；10五类连续场景；11 ChangeReport read/export；12 API；13 UI/E2E；14 Vertical Gate；15独立Exit Audit。P5 advanced capabilities和Production/external authority始终排除。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/P4-dynamic-replanning.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/core/capability-matrix.md`、`docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/export-package.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/planning/planning-strategies.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/planning/solver-backend-contract.md`、`docs/simulation/README.md`、`docs/simulation/execution-simulator-and-disruptions.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/benchmark-harness.md`、`docs/simulation/performance-gates.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/quality/property-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/benchmark-regression.md`、`docs/governance/document-control.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`

Documentation impact rationale: current phase、P3/P4 Milestone、完整Task集合、Requirement/NFR/ENG/Test/risk/OPEN/SIM/Impact/inventory追踪和P4直接合同/架构/状态/质量分配同时变化；P3事实仅追加transition记录，不改写Exit、失败run、corrective chain或provider evidence。

Change-impact matrix rows reviewed: `IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: P3 READY+用户授权→TASK-P4-00；REQ-004/005/006/007/008/009/012/013/014与相关NFR/ENG→TASK-P4-01～15→12个新增PLANNED Test ID和既有TEST-REPLAN/回归IDs→未来machine/provider artifacts；所有root仍为`ALLOCATED`，本Task只形成规划治理。

Contract impact: planning-only；现有human/machine contracts与schema set `2.7.0`逐字保持行为不变，只登记P4-01/02的后继责任。

Schema changes: none；schema set保持`2.7.0`且所有Schema/sample bytes不变。TASK-P4-02只登记预期additive release，不在本Task创建。

Migration: none；TASK-P4-03只登记预期additive/reversible revision，不在本Task创建或执行。

Dependency changes: none；Python/npm direct pins、`uv.lock`和`frontend/package-lock.json`逐字保持不变。P4计划默认复用现有依赖。

ADR impact: none for this transition；TASK-P4-01登记Event/Fact/Replan、Freeze/Stability/ChangeReport、Execution Simulator Common-Path三份预期ADR并须在任何P4 Schema/代码前独立形成，stable ID只在该Task启动时分配；本Task不创建或接受技术ADR。

State-machine impact: 只登记P4-01决定ReplanRequest状态责任、P4-02发布carrier、P4-03实现持久化的依赖顺序；当前`state-machines.v1`、PlanningRun/ScheduleVersion/ExportJob集合、pair、guard、migration和行为均不改变。

Error behavior: 任一P3状态、提交拓扑、required check、artifact SHA/Task/Diff base/Impact Rules/checks/issues、branch protection、HEAD或clean-tree不一致立即停止且不切Phase；规划owner/member、依赖、文档清单或禁止范围不一致同样硬失败。

Tests: 只运行既有治理/phase-policy/CI contract回归；新增TEST-EXECUTION-EVENT-CONTRACT-001、TEST-REPLAN-REQUEST-CONTRACT-001、TEST-P4-PERSISTENCE-001、TEST-EXECUTION-FACT-PROJECTION-001、TEST-FREEZE-WINDOW-001、TEST-STABILITY-OBJECTIVE-001、TEST-CHANGE-REPORT-001、TEST-EXECUTION-SIMULATOR-001、TEST-DISRUPTION-REPLAY-001、TEST-REPLAN-API-001、TEST-REPLAN-FRONTEND-001、TEST-P4-VERTICAL-SLICE-001均为`PLANNED`；不修改测试代码或断言。

Benchmark impact: none；P4-14必须保留P2 XS/S/M与P3 Gate回归并记录development observations，但本Task不运行新P4 Benchmark、不建立Production threshold/capacity/SLA。

Simulation scenarios: none；只把五类连续场景分配给TASK-P4-10/14。新定量值必须在未来Task登记SIM_ASSUMPTION；本Task不新增或猜测数值。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-00-phase-transition-and-task-planning-governance.md --check-diff --report build/traceability/TASK-P4-00-report.json`；`git diff --check`；`git diff --exit-code 61eeacdd5efc20b2321750e1310e9e21561c9fc2 -- backend schemas frontend infra scripts .github pyproject.toml uv.lock fixtures benchmarks`；Milestone/Task/dependency/registry/inventory consistency核验。

Artifacts: `traceability-report.v1`、P3 prerequisite verification record、P4 allocation/registry count record、GitHub exact run/job/artifact/required-check evidence。

Provider evidence: GitHub repository/branch/workflow固定为`kumamon-xu/PlantNexus-APS`/`main`/`.github/workflows/ci.yml`；implementation与evidence-only closure各自必须有exact push run、successful required `validate`、GitHub Actions app `15368`、完整steps、未过期artifact及Task report exact SHA/Diff base/Impact Rules/checks/issues核验。

Completion conditions: P3证据一致且P3=`completed`、P4=`active`；TASK-P4-01～15均为依赖/启动门/不可变Diff base规则/目标与非目标/scope/Contract/Schema/migration/dependency/ADR/state/六能力边界/tests/CI/docs/completion/failure/rollback完整的`planned`成员，P4-15最后；full/diff治理、phase policy、禁止范围和双提交provider均PASS；P4-01未启动，P5/Production未进入。

Failure handling: 任一本地治理、scope、push、required check或artifact核验失败时停止，保留失败run并在TASK-P4-00允许范围内提交有界corrective；不标done、不启动P4-01，不以文档覆盖provider事实，不重写P3历史或force-push。

Production boundary: 不形成Production readiness/UAT/deployment、真实identity/approval/event authority、external MES/ERP/storage/publish或capacity/SLA；全部OPEN保持真实状态。

P5 boundary: 不创建P5 Task，不实现secondary resource、batch、sequence setup、tool/fixture capacity、多工厂、alternative route、decomposition、rolling/hybrid或其他advanced capability。

Explicitly excluded: TASK-P4-01及后续实现；业务代码/Schema/migration/dependency/test/workflow；Execution/Replan/Simulator运行；P5 Task/能力；Production readiness/UAT/deployment/真实authority/external publish/capacity/SLA。

PROD_OPEN: OPEN-001～015全部保持`OPEN`；尤其OPEN-002/005/006/010/011/012/015继续阻止真实接口、Production freeze/priority/authority/capacity/SLA/data authority结论。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～015全部保持`ACTIVE`；本Task不新增定量假设。未来P4-05/09/10/13必须在使用新值前登记versioned assumption。

Rollback: push前整体回退本Task文档变化并保持P3 active；push后事实错误只用有界corrective/superseding治理提交，保留P3 Exit、失败run、corrective链和provider artifacts，禁止reset/force-push。

## Completion evidence

### Verified transition prerequisites

- TASK-P3-00～17 front matter全部为`done`；P3 report/manifest均为`READY`且`blocking_gaps=[]`。
- P3 audit implementation `201be9c6fd1b433a9d0a629a3ae7d4ffe1107476`的唯一父提交是`0933e10760096cdf8e812b2d41b34916e9db5750`；closure `61eeacdd5efc20b2321750e1310e9e21561c9fc2`的唯一父提交是implementation，直接拓扑完整。
- Implementation run/job/artifact=`33033591189`/`98391337626`/`9631260796`，digest=`sha256:49833cdb63c9703a3837a194fd05d648b721d23719f0096a96fbbe0642937852`，expiry=`2026-11-25T02:32:29Z`；closure run/job/artifact=`33034464425`/`98394043379`/`9631608856`，digest=`sha256:ecab5845264202fa0bef70db1bbbcccb9a446a0b43cffe5b8508aae9d8e78b0c`，expiry=`2026-11-25T02:49:20Z`。两个required `validate`均success且app ID=`15368`。
- 两份fresh下载artifact各44 files/38 JSON、0 parse error；Task均为TASK-P3-17，Diff base均为`0933e10760096cdf8e812b2d41b34916e9db5750`，19/19 checks、0 issues、P2 Gate 11/11、P3 Gate 14/14、i18n 8/8、双locale及机器合同证据一致，exact SHA分别匹配implementation/closure。
- Branch required context仍为`validate`且绑定GitHub Actions app `15368`；启动时`main=origin/main=remote main=61eeacdd5efc20b2321750e1310e9e21561c9fc2`、ahead/behind=`0/0`且工作树clean。故phase transition前提成立。

### Planning implementation evidence

- Full governance=`PASS`：185 docs、30 roots、30 trace rows、61 Test IDs、15 OPEN、15 SIM assumptions、17 risks、71 Tasks，current owner=TASK-P4-00。
- Task diff governance=`PASS`：相对不可变Diff base共有0 committed-range/83 working-tree unique paths，精确命中`IMPACT-DOCS`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-PHASE`、`IMPACT-STATE`四行，19/19 checks、0 issues；未注册future ADR ID的首轮失败已通过改为TASK-P4-01启动时分配stable ID纠正，没有创建空ADR。
- `uv sync --locked`解析/检查69 packages；Ruff全绿；Pyright为0 errors/0 warnings；治理unit+CI contract回归为51 passed；`git diff --check`、phase/dependency/inventory一致性与禁止范围命令均PASS。
- Implementation SHA/provider及evidence-only closure事实只能在提交/push后的exact验证中回填；当前TASK-P4-00保持`in_progress`，P4-01保持`planned`且未获执行授权。
