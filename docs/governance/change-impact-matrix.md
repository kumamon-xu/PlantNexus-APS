---
doc_id: DOC-GOV-010
title: 变更影响与必审文档矩阵
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 97, 98, 99, 100, 101, 102, 103, 104, 111]
last_reviewed: 2026-08-27
registry_version: 1.0.0
---

# 变更影响与必审文档矩阵

## TASK-P4-03 implementation impact

不可变Diff base=`7b9bfc3069de5d3738e5cc5827d27d197ed3d226`。本Task只增加`0005`、Infrastructure storage/repository/machine evidence、Backend unit/integration/CI contract tests、一个non-skippable workflow step及逐字治理文档，精确命中`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。STATE仅复验ReplanRequest无状态机、既有PlanningRun/ScheduleVersion/ExportJob pair不变以及checkpoint为operational CAS；没有修改`backend/app/domain/**`，因此不命中Domain implementation rule。

`schemas/**`、历史migration、dependency/lock、application/domain/planning/Solver/Validator、event fact projection/Snapshot、Simulator/scenario、API/UI、fixtures/benchmarks、P0～P3历史、P5+和Production能力均为禁止范围且须零差异。提交前Task report已给出0 committed-range/52 working-tree paths、上述六行、19/19 checks与0 issues；独立禁止范围核验为tracked/untracked=0，六个冻结Git object hash全部一致。Implementation及closure provider必须逐项复现。

## TASK-P4-02 implementation impact

不可变Diff base=`4026597ab1015b5ea3a89d241f0d12b5b481dee3`。实际范围为additive Schema/sample、domain pure contracts、两处P3 evidence的current-set metadata兼容、global version metadata、Backend tests、non-skippable workflow evidence、P3 i18n zero-wire checker的future-phase兼容修正及逐字治理文档，预期精确命中`IMPACT-SCHEMA/DOMAIN/APPLICATION/FRONTEND/STATE/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`。`IMPACT-DEPENDENCY`只因`pyproject.toml` metadata路径命中，runtime/dev dependency集合和`uv.lock`零差异；FRONTEND只改evidence path scope、不改UI/API producer；STATE只记录carrier复用既有pairs且ReplanRequest/Simulator无状态机。

本Task不修改historical Schema/sample、migration、repository、event ingress/projector、Planning/Solver/Simulator/API/UI或P5+。PlanningPolicy/SolverReport/ChangeReport语义由Schema与domain pure precheck承载，不修改`backend/app/planning/**`，因此不虚报`IMPACT-PLANNING-CONTRACTS/POLICY/REPORTING`。Implementation artifact `9636892191`已精确复现87 committed/0 working paths、上述12行、36/36 expected/observed documents、19/19 checks与0 issues；本closure只回填provider事实与lifecycle，并保持相同87-path union。

## TASK-P4-01 contract/ADR impact

不可变Diff base=`b96232b2e3f5573baaf735c7fa7935f95e6c88f5`。本Task新增ADR-0013～0015并同步卡片逐字列明的root README、合同、架构、领域、Planning、Simulation、Operations、Quality、Phase与Governance文档；root README current-status矛盾在修改前已按卡片规则扩入，最终allow-list为57 paths。预期精确命中`IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`四行。STATE变化只记录ReplanRequest无独立状态机和既有PlanningRun/ScheduleVersion/ExportJob pair零漂移，不增加machine pair。

相对base，`backend/**`、`schemas/**`、`frontend/**`、fixtures/benchmarks、migration、dependency/lock、test assertion、`.github/workflows/**`、P0～P3历史与P5+均为零差异。三份ADR为accepted decision而非机器/行为实现。Implementation artifact `9634380233`已复现57 committed/0 working paths、精确四行、19/19 checks与0 issues，未出现第五个Rule或allow-list外路径；本closure只回填该provider事实与lifecycle，仍保持相同57-path union。

## TASK-P4-00 phase-transition planning impact

不可变Diff base=`61eeacdd5efc20b2321750e1310e9e21561c9fc2`。本批只修改根README与`docs/**`，关闭P3/激活P4、新增16张P4 Task卡并同步合同/架构/领域/Planning/Simulation/Operations/Quality/Governance的“planned impact”说明。本地Task report得到0 committed-range/83 working-tree unique paths，精确命中`IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`四行、19/19 checks、0 issues；state文档只登记未来责任，不增加或修改state pair。Implementation artifact `9632983094`已复现83 committed/0 working paths、相同四行、19/19 checks与0 issues，故本closure可把P4-00标为`done`；任何后续额外Impact Rule仍必须先停止并扩卡。

相对Diff base，`backend/**`、`frontend/**`、`schemas/**`、migration、`pyproject.toml`/`uv.lock`/npm lock、fixtures/benchmarks、test assertion、`.github/workflows/**`、accepted ADR正文及P0～P3历史Task/Exit evidence必须零差异。TASK-P4-01的三份具名future ADR与TASK-P4-02 Schema只是预期影响，本批不得创建或分配ADR stable ID；P5+、Production identity/authority/external/deployment/capacity/SLA同样禁止。

## TASK-P3-17 audit impact decision

本Task命中`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`与`IMPACT-DOCS`，因此同步current phase、Milestone/Task索引、P3直接合同/Frontend/state/architecture/operations/quality结论、所有治理注册表、trace、inventory、模板及audit report/manifest。相对Diff base的business、Schema、migration、dependency/lock、ADR、test assertion、workflow与Frontend implementation零差异，因此没有触发这些载体的规范变更；审计结论为`READY`、0 gaps且provider pending，不授权P4或Production。

## TASK-P3-16 implementation impact

不可变Diff base=`1636fe9c909b728d49f9907ed9f53030b5921914`。Frontend `src/i18n`、既有display surfaces、Vitest/Playwright/evidence、additive CI step及状态文档的display review精确命中`IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`六行。Frontend test路径由`IMPACT-FRONTEND`覆盖，`IMPACT-TESTS`只匹配`backend/tests/**`，故不虚报。Package/lock、backend、Schema/migration、state implementation、fixture/benchmark、P3-00～15、P4与Production均为禁止范围且零差异；machine Rule table与`registry_version=1.0.0`不变。Implementation artifact `9629193057`中的Task report绑定exact SHA/base并复现79 committed/0 working paths、六行、19/19 checks、0 issues；本closure只写provider事实且自身仍须exact provider。

## TASK-P3-15 impact review

完整Diff base=`06e7f794f486ac34c505237b847462c7c7c36d44`。Implementation只修改治理validator、其unit test、当前Task/phase/Milestone及逐字治理文档，精确命中`IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`五行；artifact `9597967232`已复验26 committed/0 working paths、19 checks与0 issues。

本closure完成稳定ID rename、两个planned Task卡、官方术语规范、Test ID/风险/索引/追踪登记；两份`docs/domain/state-machines/**`只增加display-label/no-machine-pair-impact说明，因此额外命中`IMPACT-STATE`并审查ADR索引、PlanningRun/ScheduleVersion/ExportJob与trace matrix，总计六行。当前没有任何`frontend/**`源文件或业务测试断言变化，因此不命中`IMPACT-FRONTEND`。未来TASK-P3-16若获单独授权，按其精确allow-list预期命中`IMPACT-FRONTEND/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行并需自身Diff base/provider；该future mapping不是本closure证据。Workflow、业务代码、Schema/migration/dependency/lock、P3-00～14、P4与Production相对base必须零差异；machine Rule表与`registry_version=1.0.0`不变，closure最终paths/checks/issues由本地及exact provider report回填。

提交前本地Task report已得到48 unique paths（26 committed-range/46 working-tree sources）、上述六行、19/19 checks与0 issues；closure-only 46 paths均为根README或`docs/**`，完整范围仅另含既有治理脚本与其unit test。该本地结果不替代closure exact provider。

## TASK-P3-14 impact review

不可变Diff base=`6a3e02f00bf46f19915cb59c3c4af7daaac95be4`。本Task逐字allow-list只覆盖Gate application、既有state合同复验、Frontend evidence/config、required CI、focused tests和治理文档，完整range为56 paths并精确命中八行：`IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`，19/19 checks、0 issues。

首个implementation provider只暴露同一allow-listed integration fixture的SHA绑定缺口；corrective未增加路径或Impact Rule，也未修改workflow/business/Schema/dependency/baseline。失败run/job=`32930677030`/`98062166642`与artifact count=0保留；corrective artifact `9593460266`已精确复现56 committed/0 working paths、上述8 rows、19 checks和0 issues。

Schema/sample/rules、migration、dependency/lock、P3-02～13业务/state/repository/API/UI实现、fixtures/baselines/expected、P2历史、P4与Production路径全部冻结。若最终diff出现额外path或Impact row，必须停止并先修订Task卡；Gate失败不得在本Task修改业务或expected。

## TASK-P3-13 impact review

完整Diff base=`3dacf83c0f0bf87a9fa673aa75d61f8ad8659386`，预期精确命中11行：`IMPACT-APPLICATION`（verified download orchestration）、`IMPACT-API`（17+1 transport）、`IMPACT-STATE`（三份状态文档no-pair review）、`IMPACT-FRONTEND`（commands/controls/E2E）、`IMPACT-EXPORT`（loader/archive）、`IMPACT-JOBS`（root-confined store/worker identity）、`IMPACT-INFRA`（required workflow evidence）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。Task card逐字allow-list与Documents to update构成完整union。

禁止范围为Schema/sample/rules、migration、Python/npm dependencies和locks、domain state implementation、repository persistence、P2 package bytes、Solver/Strategy/Validator/KPI、fixtures/benchmarks、external network/storage/MES、P4与Production。任何额外path或Impact row必须先停下扩卡；Task diff和provider artifact都必须为11 rows/全部checks/0 issues。

首个corrective implementation artifact `9589931373`精确绑定`13e16e36fc0a06a079d6832f419950c830f2b96e`并复现91 committed/0 working paths、上述11 rows、19 checks、0 issues，冻结范围无漂移。首个失败artifact `9589702993`不满足完整Gate且按历史保留；其后的首次closure失败也不被改写。

首次closure run `32921871460`又暴露同一allowed `backend/app/exporters/standard_package.py`的wall-clock nondeterminism，Task因此曾恢复`in_progress`。修正只触及该exporter、既有unit test和required docs，仍命中原11 rows/91-path union；Schema/profile/dependency/lock/state/API/Frontend/P4/Production禁止范围不扩张。独立corrective artifact `9590625358`精确绑定`3538d46f8b73ae434057bcbca9037436aa91f2c7`并再次复现91/0/11/19/0，故本closure标Task=`done`；P3-14/15、P4与Production不自动启动。

本矩阵用于在 Task 开始前确定文档影响。表中的文档是“必须审查”，不代表每次都必须修改；如果审查后不修改，Task 完成证据必须逐项说明理由。

## 使用规则

1. 根据计划修改的路径和行为类型匹配所有适用行；
2. 把匹配到的文档写入 Task Card 的 `Documents to update`；
3. 把 Requirement/Test/Artifact/Registry 变化写入 `Traceability updates`；
4. 将这些文档路径加入 `Files allowed to change`；
5. 实施中出现新影响时先修订 Task Card；
6. Task 进入 `in_progress` 时记录完整 HEAD SHA 为 `Diff base`；完成时按 `Diff base..HEAD` 已提交路径与 working tree 路径并集再匹配一次，防止计划、提交前验收和提交后验收相互偏离。

`Change-impact matrix rows reviewed` 必须使用下方稳定 Rule ID。校验器忽略纯 `.gitkeep`，其他 changed path 可以同时命中多条规则；每条命中的 Rule ID 都必须在当前 Task 声明，其 `Required documentation` 必须进入 `Documents to update`。

## Machine-checkable rules

| Rule ID | Changed path globs | Required documentation |
|---|---|---|
| IMPACT-SCHEMA | `schemas/**` | `docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-DOMAIN | `backend/app/domain/**` | `docs/domain/domain-model.md`、`docs/core/glossary.md`、`docs/architecture/data-authority.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-APPLICATION | `backend/app/application/**` | `docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/domain/error-model.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-IMPORT | `backend/app/importers/**`、`backend/app/normalization/**`、`backend/app/data_validation/**` | `docs/contracts/import-and-normalization.md`、`docs/architecture/data-authority.md`、`docs/domain/error-model.md`、`docs/governance/prod-open-register.md` |
| IMPACT-SNAPSHOT | `backend/app/snapshots/**` | `docs/contracts/planning-snapshot.md`、`docs/architecture/provenance-and-versioning.md`、`docs/quality/property-tests.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-PROBLEM | `backend/app/planning/problem/**` | `docs/contracts/planning-problem.md`、`docs/planning/constraint-catalog.md`、`docs/architecture/provenance-and-versioning.md`、`docs/adr/README.md` |
| IMPACT-PLANNING-CONTRACTS | `backend/app/planning/contracts.py`、`backend/app/planning/contracts/**` | `docs/contracts/planning-problem.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/planning/solver-backend-contract.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-POLICY | `backend/app/planning/policy/**` | `docs/contracts/planning-policy-and-solve-limits.md`、`docs/planning/objective-policy.md`、`docs/domain/kpi-contract.md`、`docs/adr/README.md` |
| IMPACT-STRATEGY | `backend/app/planning/strategies/**` | `docs/planning/planning-strategies.md`、`docs/planning/solver-backend-contract.md`、`docs/simulation/performance-gates.md`、`docs/adr/README.md` |
| IMPACT-REPORTING | `backend/app/planning/reporting/**` | `docs/domain/kpi-contract.md`、`docs/planning/solver-backend-contract.md`、`docs/contracts/export-package.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-BACKEND | `backend/app/planning/backends/**` | `docs/planning/solver-backend-contract.md`、`docs/planning/planning-strategies.md`、`docs/planning/constraint-catalog.md`、`docs/planning/objective-policy.md`、`docs/quality/benchmark-regression.md`、`docs/architecture/technology-stack.md`、`docs/adr/README.md` |
| IMPACT-VALIDATOR | `backend/app/planning/validation/**` | `docs/planning/schedule-validator.md`、`docs/planning/constraint-catalog.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-DIAGNOSTICS | `backend/app/planning/diagnostics/**` | `docs/planning/infeasibility-diagnostics.md`、`docs/domain/error-model.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-STATE | `backend/app/domain/state_machines/**`、`docs/domain/state-machines/**` | `docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/adr/README.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-SIM-PROFILE | `backend/app/simulation/profiles/**`、`schemas/scenario/factory-profile*` | `docs/simulation/factory-profile.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/governance/sim-assumption-register.md`、`docs/architecture/provenance-and-versioning.md` |
| IMPACT-SIM-SCENARIO | `backend/app/simulation/scenarios/**`、`schemas/scenario/scenario*` | `docs/simulation/scenario-spec-and-provenance.md`、`docs/simulation/scenario-library-and-matrix.md`、`docs/simulation/performance-gates.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-SIM-GENERATOR | `backend/app/simulation/generators/**` | `docs/simulation/synthetic-generator-and-determinism.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/provenance-and-versioning.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-SIM-EXECUTION | `backend/app/simulation/execution/**` | `docs/simulation/execution-simulator-and-disruptions.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/planning/replanning.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-BENCHMARK | `backend/app/simulation/benchmarks/**`、`benchmarks/**`、`scripts/run_benchmark.py` | `docs/simulation/benchmark-harness.md`、`docs/simulation/performance-gates.md`、`docs/quality/benchmark-regression.md`、`docs/domain/kpi-contract.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-REFERENCE-SCHEDULER | `backend/app/simulation/baselines/**` | `docs/planning/reference-schedulers.md`、`docs/planning/schedule-validator.md`、`docs/planning/objective-policy.md`、`docs/domain/kpi-contract.md`、`docs/simulation/benchmark-harness.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-FIXTURE | `fixtures/**` | `docs/quality/fixtures-and-golden-tests.md`、`docs/quality/validator-mutation-tests.md`、`docs/quality/property-tests.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-API | `backend/app/api/**` | `docs/domain/error-model.md`、`docs/architecture/data-authority.md`、`docs/governance/prod-open-register.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-FRONTEND | `frontend/**` | `docs/frontend/README.md`、`docs/domain/state-machines/schedule-version.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-EXPORT | `backend/app/exporters/**` | `docs/contracts/export-package.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/schedule-version.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-JOBS | `backend/app/jobs/**` | `docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/architecture/module-boundaries.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/quality/test-strategy-and-matrix.md` |
| IMPACT-INFRA | `infra/**`、`backend/app/infrastructure/**`、`backend/migrations/**`、`alembic.ini`、`.env.example`、`.github/workflows/**`、`docker-compose.yml` | `docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/governance/nfr-and-engineering-register.md` |
| IMPACT-DEPENDENCY | `pyproject.toml`、`uv.lock` | `docs/architecture/technology-stack.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/benchmark-regression.md`、`docs/adr/README.md` |
| IMPACT-VERSION-METADATA | `backend/app/__init__.py`、`pyproject.toml` | `docs/contracts/schema-versioning.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/technology-stack.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-PHASE | `docs/milestones/**`、`docs/current_phase.md` | `docs/milestones/README.md`、`docs/tasks/README.md`、`docs/governance/traceability-matrix.md`、`docs/governance/document-inventory.md` |
| IMPACT-GOVERNANCE-REGISTRY | `docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md` | `docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md` |
| IMPACT-GOVERNANCE-VALIDATOR | `scripts/check_docs.py`、`backend/tests/unit/test_check_docs.py` | `README.md`、`docs/README.md`、`docs/agents/AGENTS.md`、`docs/agents/reading-order-and-context-policy.md`、`docs/architecture/repository-layout.md`、`docs/governance/document-control.md`、`docs/governance/traceability-rules.md`、`docs/governance/change-impact-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/TASK_TEMPLATE.md` |
| IMPACT-TESTS | `backend/tests/**` | `docs/quality/test-strategy-and-matrix.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/traceability-matrix.md` |
| IMPACT-DOCS | `docs/**`、`README.md`、`AGENTS.md` | `docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md` |

## 路径与行为映射

| 变更区域或行为 | 必须审查的文档 | 必须检查的追踪/版本 | 额外门 |
|---|---|---|---|
| `schemas/**`、领域 DTO/值对象 | 对应 `contracts/*.md`、`contracts/schema-index.md`、`contracts/schema-versioning.md`、`domain/domain-model.md` | Schema version、REQ/NFR、contract tests、fixtures | 不兼容变更需 migration/compatibility rule |
| `domain/**` 的实体关系或不变量 | `domain/domain-model.md`、相关领域专题、`core/glossary.md`、`architecture/data-authority.md` | REQ、Schema、state/constraint refs | 语义变化可能需要 ADR |
| `application/**` 的跨模块用例/事务编排 | `architecture/end-to-end-planning-flow.md`、`architecture/module-boundaries.md`、`architecture/data-authority.md`、`domain/error-model.md` | REQ/NFR/ENG、integration tests、artifact provenance | 不得复制领域规则或绕过阶段门 |
| `importers/**`、`normalization/**`、`data_validation/**` | `contracts/import-and-normalization.md`、`architecture/data-authority.md`、`domain/error-model.md` | REQ-001～003、OPEN-002/013/015、contract tests | 禁止补猜生产默认值 |
| `snapshots/**`、snapshot hash | `contracts/planning-snapshot.md`、`architecture/provenance-and-versioning.md`、`quality/property-tests.md` | Snapshot/schema/rule version、replay tests | hash 语义变化需兼容说明 |
| `planning/problem/**` | `contracts/planning-problem.md`、`planning/constraint-catalog.md`、`architecture/provenance-and-versioning.md` | Problem version/hash、Golden/Scenario/Benchmark | 必须 ADR 与 replay |
| `planning/policy/**`、目标层级/权重语义 | `contracts/planning-policy-and-solve-limits.md`、`planning/objective-policy.md`、`domain/kpi-contract.md` | OBJ IDs、OPEN-005/006、solver reports | 目标层级变化必须 ADR |
| `planning/strategies/**` | `planning/planning-strategies.md`、`planning/solver-backend-contract.md`、`simulation/performance-gates.md` | REQ-004、Benchmark baseline | 分解/滚动策略必须 ADR 与证据门 |
| `planning/backends/**`、OR-Tools 参数/版本 | Solver contract、strategy、constraint/objective、benchmark regression、technology stack | Solver exact version、lock、Golden/Scenario/Benchmark | Backend/升级必须 ADR |
| `planning/validation/**` | `planning/schedule-validator.md`、`planning/constraint-catalog.md`、`quality/validator-mutation-tests.md`、test matrix | C-ID、REQ-005、Mutation/Property tests | 禁止复用 backend constraint builder |
| `planning/diagnostics/**`、状态映射 | `planning/infeasibility-diagnostics.md`、`domain/error-model.md`、Solver contract | error/status contract tests | UNKNOWN 不得变成 INFEASIBLE |
| PlanningRun/ScheduleVersion/ExportJob 状态或迁移 | 对应 `domain/state-machines/*.md`、相关 Contract、audit/release 文档 | transition tests、migration、REQ-007 | 状态机修改必须 ADR |
| `simulation/profiles/**` | `simulation/factory-profile.md`、scenario matrix、SIM assumption register、versioning | profile version、scenario compatibility | 不得成为生产默认值 |
| `simulation/scenarios/**` | Scenario/provenance、scenario library、performance gates | scenario version、expected behavior、replay | expected result 变化需解释 |
| `simulation/generators/**` | generator/determinism、dual-channel architecture、versioning | generator version、dataset hash、replay tests | 禁止绕过 Standard Import |
| `simulation/execution/**` | execution simulator、ExecutionEvent/Replan contract、`planning/replanning.md` | simulator version、event idempotency、P4 scenarios | 事实保护与 lock tests |
| `simulation/benchmarks/**`、`benchmarks/**` | benchmark harness、performance gates、benchmark regression、KPI contract | profile/baseline version、hardware/environment | 不得生成生产 SLA |
| `fixtures/**`、Golden/Mutation/Property 数据 | fixtures/golden、mutation/property docs、traceability matrix | Fixture/version/seed、Test IDs、expected artifacts | 不覆盖历史 baseline |
| `api/**`、HTTP 状态或 payload | 对应 API contract（形成后）、error model、security/authorization 文档 | OpenAPI/schema version、contract tests、REQ | 当前受实现阶段和 OPEN-002/010 约束 |
| `frontend/**` 的计划编辑/审批/发布 | Frontend 专题、ScheduleVersion state machine、replanning/validator contract | E2E tests、REQ-007/008、audit events | UI 不复制 Solver Logic |
| `exporters/**`、publish | export package、ExportJob/ScheduleVersion state、provenance、release docs | package schema、idempotency、audit/artifact | 仅 APPROVED 可发布 |
| `jobs/**`、Worker、retry/lease | ExportJob state、Operations reliability 文档、error model | idempotency/heartbeat tests、NFR-REL-001 | 禁止 double publish/event |
| `infrastructure/**`、配置、Secret、环境 | configuration/isolation、technology stack、Operations/Runbook（形成后） | NFR-SEC/ISO/OBS、deployment artifacts | 生产变更需安全/回滚证据 |
| dependency/lockfile，尤其 OR-Tools | technology stack、solver contract、benchmark regression、ADR index | dependency version、upgrade replay | OR-Tools 升级强制 ADR/Gate |
| `milestones/**`、`current_phase.md` | Milestone index、task index、traceability matrix、document inventory | Gate artifacts、Task status | 需用户确认才进入下一 Phase |
| 只修改文档 | document inventory、被引用文档、必要的 supersedes/ADR links | doc metadata、links、source sections | 运行文档一致性检查 |

## `Documentation impact: none` 的允许条件

只有同时满足以下条件才可声明 `none`：

- 实际 diff 未触发上表任何语义/路径行，或所有匹配文档经审查确认无需修改；
- 没有对外合同、状态、错误、配置、运维、测试口径或用户行为变化；
- 没有新增/关闭 PROD_OPEN、SIM_ASSUMPTION 或 ADR；
- 完成证据列出已审查的矩阵行和不修改理由。

纯格式化也需要记录影响判断，但可以在理由充分时声明 `none`。

## TASK-P2-10 matrix review

完整Diff base范围命中`IMPACT-REFERENCE-SCHEDULER`、`IMPACT-TESTS`、`IMPACT-INFRA`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Baseline代码触发Reference必审文档；unit/property/integration触发test matrix/docs/trace；workflow触发configuration/technology/operations/NFR；Task lifecycle与SIM-ASSUMPTION-012触发Phase/registry/docs行。

Schema、Planning/Validator、P2-09 Scenario/fixture、dependency/lock、Benchmark implementation/profile、API/DB/Worker、Export与P3路径均为零差异，因此不声明对应Rule ID。Machine rule表无需新增glob或改变`registry_version`；最终path/count以Task governance report真实结果为准。

Implementation artifact `9435264655`已绑定`8ca62bbb1105a1dfae2ee2600ae7e4e62a5bef6c`并复现38 committed/0 working paths、上述六行、19 checks与0 issues；TASK-P2-10据此关闭为`done`。Schema/Planning/Validator/Scenario/Dependency/Benchmark/Export规则继续未命中，P2-11不自动启动。

## TASK-P0-04 matrix review

本 Task 实际路径预期命中 `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-VALIDATOR`、`IMPACT-STATE`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`schemas/rules/**` 由 IMPACT-SCHEMA 覆盖；rule completeness CLI 位于 `backend/app/planning/validation/**`，由 IMPACT-VALIDATOR 覆盖，不需要无边界新 glob。

PlanningProblem、Backend、Fixture、API、Export/Job implementation 路径均不修改，因此不声明对应 Rule ID。本段记录审查结论，不改变 machine rule 表结构或 registry version；最终以 Task diff report 的真实 matched rows 为准。

## TASK-P0-05 matrix review

本 Task 实际路径预期命中 `IMPACT-SCHEMA`、`IMPACT-VALIDATOR`、`IMPACT-SIM-PROFILE`、`IMPACT-SIM-SCENARIO`、`IMPACT-SIM-GENERATOR`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`pyproject.toml` 只更新 schema metadata但仍按 dependency 行审查；`rule_sheet.py` 只解除旧 set exact-value check但仍按 Validator 行审查。

Fixture、Simulation execution/baseline/benchmark implementation、PlanningProblem/Backend、API、Infra/DB、Export/Job 均不修改，因此不声明对应 Rule ID。现有 machine glob/required-document 表无需改变，registry format version 保持 `1.0.0`；最终以 TASK-P0-05 diff report 的真实 matched rows 为准。

## TASK-P0-06 matrix review

本 Task 预期命中 `IMPACT-SIM-SCENARIO`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/simulation/scenarios/golden_fixture.py` 只做 artifact/provenance/hash replay，`backend/tests/golden/**` 承担 test-local direct calculation；没有修改 `planning/validation/**`，因此不声明 `IMPACT-VALIDATOR`。

FactoryProfile artifact 位于 `fixtures/**` 而非 profile code/schema，故由 `IMPACT-FIXTURE` 覆盖，不虚报 `IMPACT-SIM-PROFILE`。Schema、Generator、PlanningProblem、Backend、Benchmark、API、Infra/DB、Export/Job 均不修改；machine rule 表和 registry format version 保持 `1.0.0`，最终以 TASK-P0-06 diff report 的真实 matched rows 为准。

## TASK-P0-07 matrix review

本 Task 预期命中 `IMPACT-VALIDATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/planning/validation/**` 只新增 fixture-local independent evaluator/mutation runner；`fixtures/infeasible/SIM-MINIMAL-001-MUTATIONS/**` 与 `backend/tests/validation/**` 固定 negative evidence；阶段/注册表只同步 P0-07 状态和真实追踪。

Schema、Domain、PlanningProblem、Backend、Simulation code、Golden/其他 tests、dependency/version metadata、Benchmark、API、Infra/DB、Export/Job 均禁止修改，因此不声明对应 Rule ID。现有 machine globs/required-document 列无需改变，registry format version 保持 `1.0.0`；最终以 TASK-P0-07 diff report 的真实 matched rows 为准。

## TASK-P0-08 matrix review

本 Task 预期命中 `IMPACT-API`、`IMPACT-JOBS`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-STATE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`pyproject.toml` 同时触发 dependency/version review；更新 `export-job.md` 触发完整三套 state/ADR/trace review，即使 machine state artifacts 保持只读。首次 diff check 暴露 Alembic/migrations、`.env.example` 与 CI workflow 没有规则覆盖，因此在同一稳定 `IMPACT-INFRA` 行加入这些有界工程路径；required documentation 不变且均已列入 Task。

Schema、Domain、Import/Normalization/Snapshot、Planning/Validator/Backend、Simulation、Exporter、Fixture、Benchmark、Frontend、governance validator 均禁止修改，因此不声明相应 Rule ID。新增路径覆盖没有创建新 Rule ID、没有改变 required-document column/registry table format，`registry_version` 保持 `1.0.0`。最终以 TASK-P0-08 diff report 的真实 matched rows 为准。

## TASK-P0-09 matrix review

本 Task 只修改明确列出的 P0 phase/milestone、governance registry、quality/index/task/audit documents 和 `docs/milestones/P0-exit-gate-evidence-manifest.json`，实际预期命中 `IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。新建 TASK-P0-10 仅为 planned remediation card；没有执行后续任务或外部操作。

Schema、Domain、Constraint/Validator、Simulation、Fixture、Test、Benchmark、API、Infrastructure/workflow、dependency/version metadata、governance validator 和 P1 path均保持只读，因此不声明对应 Rule ID。machine rule table/required-document column 未修改，`registry_version` 保持 `1.0.0`；最终以 TASK-P0-09 diff report 的真实 matched rows 为准。

## TASK-P0-10 matrix review

本 Task 实际路径命中 `IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`.github/workflows/ci.yml` 只交接当前 Task diff/report 和 artifact 引用；`backend/tests/integration/test_ci_contract.py` 增加 exact handoff/no-stale-reference 断言；phase/audit/registry/docs 只同步 GitHub provider 真实证据与 Gate 状态。

Schema、Domain、Import/Snapshot/Planning/Validator implementation、Simulation code/Fixture、Benchmark、API/Job/DB、dependency/version metadata、governance validator、Solver/P1 path 均禁止修改，因此不声明其他 Rule ID。machine rule table/required-document column 与 registry format 不变，`registry_version` 保持 `1.0.0`；最终以 TASK-P0-10 diff report 的真实 matched rows 为准。

## P1 planning baseline review

2026-08-19 的用户授权使 current phase进入 P1并创建 TASK-P1-01～12。本次 planning baseline只修改 phase/milestone/task/governance/quality/index文档，以及为跨阶段校验所必需的 `scripts/check_docs.py` 与 `backend/tests/unit/test_check_docs.py`；不执行任何 P1业务实现。实际路径预期命中 `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。

P1-11首次计划在 `backend/app/application/**` 形成 common-ingress orchestration，因此增加稳定 `IMPACT-APPLICATION` 行，避免未来 application path无机器影响规则。该行只建立治理覆盖，不实现 pipeline，也不改变总规模块边界。Schema、Import、Snapshot、Problem、Simulation、Fixture、Infrastructure workflow和dependency均未在本次 planning baseline中修改。

## TASK-P1-01 matrix review

本 Task实际命中 `IMPACT-GOVERNANCE-VALIDATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。治理脚本/单测实现 phase policy与CI Task discovery；workflow/integration test移除P0-10 handoff并保留原 gates；阶段/注册表/文档只同步 TASK-P1-01 状态和真实追踪。

Schema、Domain、Import/Snapshot/Planning/Validator/Simulation/Fixture、dependency/version metadata、API/Job/DB、Solver/P2均未修改，因此不声明其他 Rule ID。现有 machine globs与required-document列足够覆盖，无需新 Rule ID或 `registry_version`提升；最终以 TASK-P1-01 diff report真实 matched rows为准。

## TASK-P1-02 matrix review

本Task实际路径命中`IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`pyproject.toml`仅改变schema metadata但仍按dependency/version行审查；Schema、data dictionary、domain pure types、contract tests及所有required docs均在有界清单内。

Adapter/Staging/Normalization/DataValidation/Expansion/Snapshot/Problem builder、Migration/DB、API/Job、Simulation Generator/Fixture、Validator、Backend/Solver、Benchmark、Frontend与governance validator均未修改，因此不声明其Rule ID。现有machine globs/required-document列足够覆盖，无需新Rule或`registry_version`提升；最终以TASK-P1-02 diff report真实matched rows为准。

## TASK-P1-03 matrix review

本Task实际路径预期命中`IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/importers/**`只形成Raw Staging pure contract/protocol/assembler；Infrastructure与migration只形成SQLAlchemy insert-only persistence；测试/阶段/注册表同步真实证据。

首次diff check准确暴露原Task卡遗漏的5份phase/governance必审文档，现已先修订卡片并纳入完整review。Schema、Domain、Application orchestration、Adapter reader、Normalization/DataValidation、Snapshot/Problem、Simulation、Fixture、API/Job/Worker、dependency/version metadata、Solver/Benchmark和governance validator均不修改，因此不声明其他Rule ID。machine rule表无需改变，`registry_version`保持`1.0.0`；最终以TASK-P1-03 diff report真实matched rows为准。

## TASK-P1-04 matrix review

本Task实际路径命中`IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。`backend/app/importers/**`形成reader/protocol/Reference Adapter，`pyproject.toml/uv.lock`精确增加openpyxl/defusedxml，限定test文件形成contract/integration evidence；既有Infrastructure machine contract/CI dependency assertion仅同步exact pin集合并保留solver-free断言，阶段、注册表和文档同步真实边界。

启动前检查准确发现原卡遗漏`change-impact-matrix.md`、`traceability-rules.md`、`sim-assumption-register.md`、`milestones/README.md`与`TASK_TEMPLATE.md`，已在激活前加入Documents/allowed scope；首次实际diff检查又发现`pyproject.toml`同时命中`IMPACT-VERSION-METADATA`，因此在继续验收前补入该Rule ID和`schema-versioning.md`。全仓回归随后忠实暴露P0 exact dependency baseline过期，故再次先扩卡，纳入`infrastructure/contract_check.py`、`test_ci_contract.py`、`IMPACT-INFRA`及其configuration/Operations必审文档。Schema、Domain、Application/migration、Normalization/DataValidation、Snapshot/Problem、Simulation/Fixture、API/Job、Solver/Benchmark和governance validator均未修改；machine rule表和`registry_version`保持`1.0.0`，最终以TASK-P1-04 diff report真实matched rows为准。

## TASK-P1-05 matrix review

本Task实际路径命中`IMPACT-SCHEMA`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前先把受global schema断言影响的既有contract tests，以及dependency/phase/governance矩阵强制文档和三份直接architecture说明补入Task Card允许范围；Diff base保持`d63926f84d9d2b7bc46bbcaff5704612af120a34`。

Schema变化只新增unit registry并同步set metadata/data dictionary；Import v2/canonical-records v1原文件、DB/migration、Adapter/Infrastructure、DataValidation/Expansion/Snapshot/Problem、Simulation、API/Job、Solver/Benchmark均未改。`pyproject.toml`无dependency变化，`uv.lock`不变；machine impact rows和registry format version不变，最终以TASK-P1-05 diff report真实matched rows为准。

## TASK-P1-06 matrix review

本Task实际命中`IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-IMPORT`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡遗漏`IMPACT-DOMAIN/DEPENDENCY/VERSION-METADATA/PHASE/GOVERNANCE-REGISTRY`的若干强制文档、两个受global schema version影响的既有contract tests和Task已要求但未分配路径的ImportQualityReport samples，均已在任何业务实现前补入范围；Diff base固定为`75d761332204ec779477ba7242c98517cce1b68b`。

本Task只新增error registry v2、error.v3、ImportQualityReport v1和`backend/app/data_validation/**`，同步domain pure error/types、schema set metadata与限定测试；旧error/import/canonical/unit artifacts由固定SHA-256证明只读。`pyproject.toml`只改schema metadata、dependency与`uv.lock`不变。Planning ScheduleValidator/constraint formula、Adapter/Staging/Normalization、Expansion/Snapshot/Problem、Simulation、API/HTTP、Solver/Benchmark实现均未修改，因此不声明其他Rule ID；最终以TASK-P1-06 diff report真实changed paths/九行matched/0 issues为准。

## TASK-P1-07 matrix review

本Task实际命中`IMPACT-DOMAIN`、`IMPACT-IMPORT`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡遗漏domain/dependency/version/tests/phase/governance/docs行的强制文档与root README，并在任何业务实现前补入范围；全仓回归随后发现workflow未收集property tests，故在修改CI前再次扩卡加入INFRA文件及configuration/Operations必审文档。Diff base始终固定`97728521e187f9f50715de4b04a09098bef62ddf`。

实际实现只新增pure domain production contract、normalization order expansion、unit/property tests和dev-only Hypothesis lock，并在既有workflow/integration contract追加phase-neutral property suite路径；`pyproject.toml`的schema/code metadata与runtime dependencies不变。Schema/error registry、Adapter/Staging/unit-time Normalizer、DataValidation、Snapshot/Problem、Simulation/API/DB/Worker、Constraint/ScheduleValidator、Solver/Benchmark均未修改，因此不声明其他Rule ID；最终以TASK-P1-07 diff report真实changed paths/九行matched/0 issues为准。

## TASK-P1-08 matrix review

本Task实际路径命中`IMPACT-SNAPSHOT`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡遗漏root/docs入口、端到端当前态及TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS行的强制文档，均已在任何Snapshot业务实现前补入允许范围；Diff base固定为`8b4fb4c027305d3e3aa68eec0baaf73cd0598189`。

实际实现只修改`app.snapshots`、新增Infrastructure repository/`0003` migration及限定unit/property/integration/migration tests。Snapshot v1/v2 Schema、Import/Adapter/Normalization/DataValidation/Expansion、dependency/lock/version metadata、Application/Planning/Solver/Simulation/API/Job均不修改，因此不声明SCHEMA/IMPORT/DEPENDENCY/VERSION/APPLICATION等其他Rule ID；machine rule表和`registry_version`保持`1.0.0`。Implementation artifact内TASK-P1-08 diff report精确记录SHA `72670d18a29c9a10cb70f7a263c981a2b660e0ee`、41 changed paths、六行matched、0 issues并由run `32310098594`重放成功。

## TASK-P1-10 matrix review

本Task实际路径命中`IMPACT-IMPORT`、`IMPACT-SIM-GENERATOR`、`IMPACT-FIXTURE`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前已先补入验收所需contract check和各行强制文档；真实生成调用发现`cycle_seconds_per_unit`既有duration合同与normalizer分类矛盾后，按治理规则先停并扩卡加入唯一normalizer/unit regression及IMPORT强制文档。Diff base始终为`11c6ca97882a3be5bf6eb25bab84f69d1dfe469c`。

实际实现仅修复该字段transform分类、新增七层Generator/package/contract check、一个versioned synthetic asset和限定unit/simulation tests。Schema、domain DTO、Adapter/Staging/DataValidation、Snapshot/Problem、Application/API/DB/Worker、dependency/version metadata、Solver/Benchmark及governance validator均不修改；machine rule表和`registry_version`保持`1.0.0`，最终以TASK-P1-10 diff report真实changed paths/七行matched/0 issues为准。

## TASK-P1-11 matrix review

本Task实际路径预期命中`IMPACT-APPLICATION`、`IMPACT-SIM-GENERATOR`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。启动前review发现原卡缺少Generator公开Raw Staging路径及INFRA/PHASE/GOVERNANCE行强制的`technology-stack.md`、`milestones/README.md`、`TASK_TEMPLATE.md`，均在任何业务代码前扩入允许范围；Diff base固定为`ea56c3867651c0f03306e66936fd649526049319`。

实现只新增application orchestration/report、Generator公开`prepare_batch()`、限定contract/integration/simulation tests和CI report命令，不改Schema/registry、Domain/Import/Normalization/DataValidation/Expansion/Snapshot/Problem语义、migration/dependency、API/Worker、Solver/Validator/Benchmark/P2。Machine impact rules和`registry_version`不变，最终以TASK-P1-11 diff report真实paths/7 rows/0 issues为准。

## TASK-P1-12 matrix review

本Task实际路径只命中`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`：新增P1 audit report/JSON manifest并同步current phase、Milestone/Task索引、合同/架构/质量审计结论、根注册表、traceability和文档清单。JSON manifest位于`docs/milestones/**`，由PHASE行覆盖但按文档清单规则不作为Markdown inventory条目。

业务代码、Schema/fixture、test、migration、workflow/infra、dependency/version metadata、governance validator、Solver/P2路径均保持只读，因此不声明其他Rule ID。Machine rule table/required-document列与`registry_version=1.0.0`不变；最终以TASK-P1-12 diff report的actual paths/3 matched rows/0 issues为准。

## TASK-P2-01 matrix review

本Task实际路径预期命中`IMPACT-SCHEMA`、`IMPACT-PROBLEM`、`IMPACT-DOMAIN`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Dependency row是强制review而非lock变化：`pyproject.toml`只提升schema metadata，runtime/dev pins与`uv.lock`必须无diff。INFRA只新增通用CI machine command，不改变service/Compose/deployment。

Schema/Problem/Domain实现限定为additive Problem v2、version-specific APIs、pure precheck与tests；v1 bytes/default API保留。Phase/Governance在exact implementation provider成功后只把P2-01闭环为`done`并同步formed/PLANNED边界，不激活P2-02。Machine rule table/required-document columns与`registry_version=1.0.0`不变；implementation provider Task report为60 paths、10 matched rows和0 issues，最终docs-overview有界更正使完整Task range为61 unique paths并保持相同10 rows/0 issues。

## TASK-P2-02 matrix review

本Task实际路径预期命中`IMPACT-SCHEMA`、`IMPACT-PLANNING-CONTRACTS`、`IMPACT-POLICY`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。Dependency row只因`pyproject.toml`提升schema metadata触发；runtime/dev pins和`uv.lock`无diff。INFRA只增加CI contract-report step，不改变service/deployment。实现中含current schema-set值的glossary在修改前已扩入allow-list；planning-run mapping审查触发STATE后也在修改其余state文档前补齐Rule与required docs。

实现限定为四份Schema/sample、pure JSON-compatible contracts/status/fingerprint checks、测试和CI report；Problem v1/v2、Backend/Constraint/Validator/DB/API/Worker/P3均只读。STATE只同步既有status mapping并确认ScheduleVersion/ExportJob无行为变化。Phase/Governance在exact implementation provider成功后把P2-02闭环为`done`，不激活P2-03/P2-04。Machine rule table/required-document columns与`registry_version=1.0.0`不变；implementation artifact内TASK-P2-02 diff report为63 actual paths、11 matched rows、19 checks和0 issues。

## TASK-P2-03 matrix review

本Task实际命中`IMPACT-POLICY/BACKEND/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`九行。实现限定exact dependency/lock、CP-SAT namespace、historical report compatibility、tests/workflow和Task声明文档；Problem/Policy/Solution/Report Schema/sample及canonical合同、Strategy/C-ID/objective/Validator/fixture/benchmark/export/DB/API/Worker/P3均无差异。

首次solver依赖由ADR-0011和dependency/security review闭环；RISK-011是登记未消除的风险，不改变registry格式。Implementation provider artifact `9398128763`内Task report确认50 actual paths、9 matched rows、19 checks、0 issues，故Task=`done`；P2-04不自动激活。

本地Task diff实际为50 paths、9 matched rows、19 checks和0 issues；provider必须对exact implementation SHA复现该范围。

## TASK-P2-04 matrix review

本Task实际预期命中`IMPACT-VALIDATOR/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`六行。VALIDATOR覆盖formal evaluator、machine CLI和公开导出；INFRA仅增加CI machine command；TESTS覆盖contract/mutation/property/integration；其余三行同步Task/Milestone/trace/register/inventory及说明文档。

Problem/Solution/Validation/Error Schema、fixture历史bytes、`pyproject.toml`/`uv.lock`、Backend/Strategy/constraint model、objective、Benchmark、migration、DB/API/Worker和P3均无差异，故不声明SCHEMA/DEPENDENCY/BACKEND等其他Rule ID。Machine rule table、required-document columns与`registry_version=1.0.0`不变；implementation provider artifact已记录actual paths/checks，TASK-P2-04据此为`done`。

本地Task diff实际为38 paths、6 matched rows、19 checks和0 issues；implementation artifact `9399519368`对exact SHA复现38 committed/0 working paths、相同6 rows/19 checks/0 issues，故影响治理闭环。

## TASK-P2-05 impact review

实际范围必须命中`IMPACT-BACKEND`（CP-SAT model/mapper/consumer）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-PHASE`（唯一active Task与边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（合同/规划/质量/运维同步）六行。Problem/Policy/Solution Schema、rule sheet、formal Validator、dependency/lock、fixture/benchmark、migration、DB/API/Worker和P3无差异，因此不命中SCHEMA/DEPENDENCY/MIGRATION等额外Rule ID。

最终path/check/issue计数必须由TASK-P2-05 diff report和exact provider artifact回填；在验收前不得预写。Registry table与`registry_version=1.0.0`均不修改。

本地TASK-P2-05 report实际为49 paths、6 matched rows、19 checks、0 issues，六行与上方预期完全一致。该数字仍须由exact implementation provider artifact重放后才能闭环。

Implementation artifact `9400957897`已对exact SHA重放49 committed/0 working paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/TESTS`六行、19 checks与0 issues，影响治理闭环。未出现额外SCHEMA/DEPENDENCY/MIGRATION影响。

## TASK-P2-06 impact review

实际范围必须命中`IMPACT-BACKEND`（temporal builder/model/mapper/consumer）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-PHASE`（唯一active Task与阶段边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（合同/规划/质量/运维同步）六行。

Problem/Policy/Solution Schema、rule sheet、formal Validator、Problem builder/hash、dependency/lock、fixture/benchmark、migration、DB/API/Worker和P3无差异，因此不命中SCHEMA/DEPENDENCY/MIGRATION等额外Rule ID。最终path/check/issue计数必须由TASK-P2-06 diff report与exact provider artifact回填；registry tables及`registry_version=1.0.0`保持不变。

本地TASK-P2-06 report实际为53 paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/TESTS`六行、19 checks与0 issues，和预期完全一致；exact provider artifact通过前只作为local evidence。

Implementation artifact `9429579311`已对exact SHA `ba6dd2cdc2eeaae3b60714314bc3d2c155a2d81c`重放53 committed/0 working paths、六行、19 checks与0 issues，影响治理闭环。未出现额外SCHEMA/DEPENDENCY/MIGRATION影响。

## TASK-P2-07 impact review

实际范围必须命中`IMPACT-BACKEND`（fact/lock builder、precheck、model/mapper/consumer）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-PHASE`（唯一active Task与边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（合同/领域/规划/质量/运维同步）六行。

Problem/Policy/Solution Schema、rule sheet、formal Validator、Problem builder/hash、dependency/lock、fixture/benchmark implementation、migration、DB/API/Worker和P3无差异，因此不命中SCHEMA/VALIDATOR/PROBLEM/DEPENDENCY/MIGRATION等额外Rule ID。最终path/check/issue计数必须由TASK-P2-07 diff report与exact provider artifact回填；registry tables及`registry_version=1.0.0`保持不变。

本地Task diff已精确命中上述六行：54 changed paths、19 checks、0 issues；禁止路径相对Diff base无变化。Exact provider artifact仍需在implementation SHA push后复现同一range与Impact Rule集合，Task才可关闭。

Implementation artifact `9430579117`已绑定`5ab65f36d532fd8786eb7ecad3cce406f4d9fb70`并复现54 paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/TESTS`六行、19 checks、0 issues；Task据此关闭为`done`。Schema/Validator/Problem/Dependency/Migration Rule继续未命中，P2-08不自动启动。

## TASK-P2-08 impact review

实际范围必须命中`IMPACT-POLICY`（versioned Simulation Delivery Policy/explicit limits）、`IMPACT-STRATEGY`（single global orchestration）、`IMPACT-BACKEND`（OBJ-001 builder、objective-aware solve/mapper/report）、`IMPACT-TESTS`（unit/property/integration）、`IMPACT-INFRA`（required validate machine step）、`IMPACT-PHASE`（唯一active Task与边界）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk review）和`IMPACT-DOCS`（架构/合同/领域/规划/质量/运维同步）八行。

Planning Schema/contracts、Problem builder/hash、formal Validator、core model/C-ID formulas、dependency/lock、fixture/benchmark implementation、migration、DB/API/Worker和P3/P4无差异，因此不命中SCHEMA/PLANNING-CONTRACTS/PROBLEM/VALIDATOR/DEPENDENCY/MIGRATION等额外Rule ID。最终path/check/issue计数必须由TASK-P2-08 diff report与exact provider artifact回填；registry tables及`registry_version=1.0.0`保持不变。

本地machine report已形成7/7 objective/strategy checks与70 focused/395 full tests；最终Task diff精确为52 changed paths、`IMPACT-BACKEND/DOCS/GOVERNANCE-REGISTRY/INFRA/PHASE/POLICY/STRATEGY/TESTS`八行、19 checks、0 issues。禁止路径相对Diff base无变化；exact provider artifact绑定implementation SHA前TASK-P2-08保持`in_progress`，P2-09不自动启动。

Implementation artifact `9431673977`已绑定`b1ec83ed96120357ecadd41d3f520181838f17c6`并复现52 committed/0 working paths、上述八行、19 checks与0 issues；TASK-P2-08据此关闭为`done`。Schema/Planning contracts/Problem/Validator/Dependency/Migration Rule继续未命中，P2-09不自动启动。

## TASK-P2-09 local impact review

实际差异命中`IMPACT-SIM-SCENARIO/FIXTURE/TESTS/INFRA/PHASE/GOVERNANCE-REGISTRY/DOCS`七行；Task卡已在首个asset产生前展开全部实际路径，并在activation提交后、实现前切换为完整Impact Rule。发布Schema、Planning/Application/Generator、Dependency/Version Metadata、Migration、Benchmark/Reference/Export/API/Jobs均未命中，故对应规则不得虚报。

所有七行required documents已进入本Task `Documents to update`并同步review。本地`TASK-P2-09-report.json`精确为58 paths、7 rows、19 checks、0 issues；provider artifact须重现58 committed/0 working paths并绑定implementation SHA，provider前Task保持`in_progress`。

Implementation artifact `9432982306`已绑定`20e49c92306128b47313059fabe31534814dbe3d`并复现58 committed/0 working paths、上述七行、19 checks与0 issues；TASK-P2-09据此关闭为`done`。Schema/Planning/Application/Generator/Dependency/Migration/Benchmark/Reference/Export规则继续未命中，P2-10不自动启动。

## TASK-P2-11 impact review

完整Diff base范围必须命中`IMPACT-SCHEMA`（KPI/manifest/data dictionary）、`IMPACT-REPORTING`（KPI/SolverReport）、`IMPACT-EXPORT`（internal package）、`IMPACT-STATE`（明确零ScheduleVersion/ExportJob transition）、`IMPACT-TESTS`、`IMPACT-INFRA`（CI machine step）、`IMPACT-DEPENDENCY`与`IMPACT-VERSION-METADATA`（`pyproject.toml`仅schema metadata）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`十一行。

Dependency行是强制review，runtime/dev pins及`uv.lock`必须零差异；State行只审查状态合同且`state-machines.v1`/migration/persistence不得修改。Planning/Strategy/Backend/Validator/Problem/Snapshot/Import/Simulation/P2-09 assets、Benchmark/API/DB/Worker/P3+保持零差异。Machine rule table和`registry_version=1.0.0`不变，最终path/count以Task report为准。

Implementation artifact `9436863185`已绑定`546292831c3bd52185687a4c646c10ae10541ae2`并复现58 committed/0 working paths、上述十一行、19 checks与0 issues；TASK-P2-11据此关闭为`done`。Runtime/dev dependency、`uv.lock`、state persistence、Planning/Strategy/Backend/Validator/Scenario/Benchmark/API/DB/Worker/P3+禁止边界保持零差异，P2-12不自动启动。

## TASK-P2-12 impact review

完整Diff base范围命中`IMPACT-BENCHMARK`（profiles/baselines/runner/CLI）、`IMPACT-REPORTING`（只抽公共schedule KPI pure calculation）、`IMPACT-TESTS`、`IMPACT-INFRA`（CI XS及artifact）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`七行。所有required documents均已列入Task allow-list并同步review。

Schema/global set、Planning Problem/Policy/Strategy/Backend/Validator、Reference算法、P2-09 assets、P2-11 Exporter、dependency/lock、migration/DB/API/Worker和P3+零差异，故不声明对应Rule ID。Machine rule table与`registry_version=1.0.0`不变；最终path/check/issue计数须由Task diff report和exact provider artifact回填，provider前Task保持`in_progress`。

Implementation artifact `9438899443`已绑定`01e7f4bdca88fc903e7caa771f875fc1a70ff357`并复现49 committed/0 working paths、上述七行、19 checks与0 issues；TASK-P2-12据此关闭为`done`。Schema/dependency、Planning/Strategy/Backend/Validator/Reference/Scenario/Exporter/API/DB/Worker/P3+禁止边界保持零差异，P2-13不自动启动。

## TASK-P2-13 impact review

完整Diff base范围命中`IMPACT-APPLICATION`（新增只读Gate orchestrator及精确Exporter合同检查例外）、`IMPACT-TESTS`（Gate/exit/CI与既有application boundary）、`IMPACT-INFRA`（required validate新增Gate命令）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`六行。所有实现和文档路径必须在Task allow-list内，P2-14/P3不得因Gate PASS自动激活。

Schema/global set、migration/database、runtime/dev dependency与`uv.lock`、ADR、Planning/Strategy/Backend/Validator/Reference/Scenario/Benchmark/Exporter实现、API/Worker/P3+均零差异，故不声明对应Rule ID。Gate只消费这些冻结的公开能力；`backend/tests/integration/test_p1_common_ingress.py`的例外只能允许`p2_gate_report.py`直接导入`app.exporters.contract_check`，不得扩大application→exporter反向依赖。Machine rule table与`registry_version=1.0.0`不变；最终path/check/issue计数由Task diff report与exact provider artifact回填。

本地完整Diff治理已实际覆盖37 paths（activation 8 committed、当前37 working-tree union）、上述六行、19 checks与0 issues并PASS。Implementation exact provider artifact形成前不得把该本地结果写成外部required evidence或关闭Task。

Implementation artifact `9440650646`已绑定`dc2e5cd41080603606090ebfc4bc6162941c5f7f`并复现37 committed/0 working paths、上述六行、19 checks与0 issues；TASK-P2-13据此关闭为`done`。Schema/migration/dependency/lock/ADR及冻结业务实现边界保持零差异，P2-14/P3不自动启动。

## TASK-P2-14 impact review

完整Diff base范围只允许命中`IMPACT-PHASE`（audit report/manifest、current phase、Milestone/Task索引）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/open/sim/risk/matrix review）和`IMPACT-DOCS`（合同/规划/质量/清单同步）三行。Ignored `build/validation/TASK-P2-14-*`和`build/traceability/TASK-P2-14-report.json`不进入Git diff或Markdown inventory。

Backend/application、Schema/global set、fixture/benchmark baseline、test assertions、scripts/workflow、dependency/lock、migration/database、ADR、API/Worker、P3+均相对Diff base零差异，故不声明其他Rule ID。Machine rule table、required-document列和`registry_version=1.0.0`不变；最终本地Task diff report已覆盖30 paths、上述3 rows、19 checks、0 issues并PASS。Implementation artifact `9503227240`精确复现30 committed/0 working paths及相同结果，故TASK-P2-14=`done`；closure仍保持相同30-path union与三行影响。

## TASK-P3-00 impact review

本次phase-planning batch相对不可变Diff base `80c403384d1e171258cf874d26605d0d22aff1b2`只允许文档变化，命中`IMPACT-STATE`（三份state-machine文档的P3规划解释）、`IMPACT-PHASE`（current phase、P2/P3 Milestone、16张P3 Task）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/Test/OPEN/SIM/risk/impact/inventory同步）和`IMPACT-DOCS`。所有required documents均列入TASK-P3-00 allow-list与`Documents to update`。

业务代码、Schema、migration、dependency/lock、test assertion、fixture/benchmark、frontend、infra、scripts和workflow必须相对Diff base零差异，因此不声明其他Rule ID。规划implementation与evidence-only closure必须各自由exact required `validate`/artifact复现实际path union、4 rows、完整checks与0 issues；provider形成前TASK-P3-00保持`in_progress`。Machine rule表和`registry_version=1.0.0`不变。

Implementation artifact `9504310381`已绑定`1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7`并复现64 committed/0 working paths、上述4 rows、19 checks、0 issues及禁止范围零差异；因此本closure可把TASK-P3-00标为`done`。Closure仍只命中相同4 rows且不启动任何P3业务实现。

## TASK-P3-01 impact review

完整Diff base `7f65f88b620ea1e8d2f4693911be3b52f4052d5d`范围只允许Task卡逐字列出的Markdown：三份Frontend规范、两份contract、ADR-0012及state/phase/governance/docs同步。预期命中`IMPACT-STATE`（三份state-machine合同review）、`IMPACT-PHASE`（current phase/P3 Milestone/Task index）、`IMPACT-GOVERNANCE-REGISTRY`（REQ/NFR/trace/OPEN/SIM/risk/impact/inventory）和`IMPACT-DOCS`（新文档与清单/一致性合同）。

`backend/**`、`schemas/**`、`frontend/**`、migration、dependency/lock、test assertion、fixture/benchmark、infra/scripts/workflow、P2历史与P4实现必须零差异；因此不声明SCHEMA/FRONTEND/API/APPLICATION/DEPENDENCY/TESTS等行为Rule。Machine rule表和`registry_version=1.0.0`不变。

Implementation artifact `9505303054`已绑定`3bf99cbafdad983795a83a88646240dbb0b24509`并复现43 committed/0 working paths、上述4 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-01标为`done`。Closure仍只命中相同4 rows，不修改合同语义、不启动P3-02，也不形成Schema/API/UI/Production/P4行为Rule。

## TASK-P3-02 impact review

完整Diff base=`a8fcec3383ea0f8d9dca4101056aff37d7eea08c`，实际预期命中10行：`IMPACT-SCHEMA`（7 Schema/7 sample/data dictionary）、`IMPACT-DOMAIN`（pure workspace contracts/check）、`IMPACT-STATE`（三份state文档对齐）、`IMPACT-INFRA`（required CI step）、`IMPACT-DEPENDENCY`（pyproject metadata only）、`IMPACT-VERSION-METADATA`（app/pyproject set`2.6.0`）、`IMPACT-TESTS`（contract/integration）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`。各行required documents均逐字列入Task卡。

`uv.lock`、34份P2 Schema/sample、三份rules、migration、`backend/app/infrastructure|application|api|jobs|exporters`、Solver/Validator、fixtures/benchmarks、`frontend/**`及later-phase machine carriers必须零差异。CI workflow只新增workspace machine command，不增权限/Secret/service/deployment。Implementation artifact `9506913562`已复现65 committed/0 working paths、上述10 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-02标为`done`。Machine impact rule表与`registry_version=1.0.0`不变，P3-03不自动启动。

## TASK-P3-03 impact review

完整Diff base=`9621fda535f66393beab88efc13c100fc805c993`，预期且实际只能命中七行：`IMPACT-DOMAIN`（两个pure persistence-state module）、`IMPACT-STATE`（既有pair文档同步）、`IMPACT-INFRA`（`0004`、shared/four repositories、machine check与单一required CI step）、`IMPACT-TESTS`（unit/integration/migration/CI）、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。各行required docs均逐字进入Task allow-list。

Schema/sample/rules、Planning/Solver/Validator、application/API/jobs/exporters/frontend、dependency/lock、fixture/benchmark与P4路径必须零差异。CI不增权限/Secret/service/deployment；machine Rule表及`registry_version=1.0.0`不变。Implementation artifact `9508445635`已复现52 committed/0 working paths、上述7 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-03标为`done`，P3-04不自动启动。

## TASK-P3-04 impact review

完整Diff base=`62604d05964413a0aa7f763afd720afa2d53a887`，预期且实际只能命中八行：`IMPACT-DOMAIN`（pure lifecycle value/builder）、`IMPACT-APPLICATION`（fresh validation与transaction service/machine CLI）、`IMPACT-STATE`（既有pair文档同步）、`IMPACT-INFRA`（单一required workflow command）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。各行required docs已逐字进入Task allow-list。

Schema/sample/rules、migration/infrastructure repositories、Planning/Strategy/Backend/Validator公式、P2 fixtures/baselines/export bytes、dependency/lock、API/jobs/exporters/frontend与P4必须零差异。CI不改required check、permissions、Secret、service/deployment；machine Rule表和`registry_version=1.0.0`不变。Implementation artifact `9510215582`已复现45 committed/0 working paths、上述8 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-04标为`done`，P3-05不自动启动。

## TASK-P3-05 impact review

完整Diff base=`fc5011f78a242160097521259a1914d864d9ad17`，预期只能命中七行：`IMPACT-DOMAIN`（pure read values/projections/comparison）、`IMPACT-APPLICATION`（read services/machine CLI）、`IMPACT-INFRA`（单一required workflow command）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。各行required docs均逐字进入Task allow-list。

Schema/sample/rules、migration/dependency/lock、repository write/state语义、Planning/Solver/Validator/Exporter、API/Frontend、state pair和P4路径必须零差异；CI不改job名称/permissions/Secret/service/deployment。Provider artifact必须复现上述7 rows、full checks、exact SHA与issues=[]；成功前Task保持`in_progress`且不启动P3-06。

Implementation artifact `9512423712`已绑定`f236fab47aa2565b87a060b2c8bde8f2e8d66229`并复现50 committed/0 working paths、上述7 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-05标为`done`，P3-06不自动启动。

## TASK-P3-06 impact review

完整Diff base=`67d38d030f8b129de7f1b2f6e5b75bd706655396`，预期只能命中八行：`IMPACT-DOMAIN`（pure command identity/semantic/copy-on-write/review-submit values）、`IMPACT-APPLICATION`（fresh Validator/insert或CAS transaction service与machine CLI）、`IMPACT-STATE`（new DRAFT及复用既有DRAFT→READY pair，不新增pair）、`IMPACT-INFRA`（单一required workflow command）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。各行required docs均逐字进入Task allow-list。

Schema/sample/rules、migration/infrastructure repository semantics、dependency/lock、PlanningProblem/Snapshot、Validator/Backend/Strategy/Reporting、API/Frontend、publication/export和P4路径必须零差异；CI不改job名称/permissions/Secret/service/deployment。Provider artifact必须复现上述8 rows、full checks、exact SHA与issues=[]；成功前Task保持`in_progress`且不启动P3-07。

Implementation artifact `9515126567`已绑定`08317637c7fbb51d46880d32523545bb0b4fe1c0`并复现57 committed/0 working paths、上述8 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-06标为`done`，P3-07不自动启动。

## TASK-P3-07 impact review

完整Diff base=`514224b8ff2d507b613797ae697245bab14f79eb`，预期只能命中八行：`IMPACT-DOMAIN`（pure decision identity/authorization/documents）、`IMPACT-APPLICATION`（authorization-before-lookup、CAS+audit service与machine CLI）、`IMPACT-STATE`（只执行既有READY→APPROVED/REJECTED）、`IMPACT-INFRA`（单一required workflow command）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。各行required docs均逐字进入Task allow-list。

Schema/sample/rules、migration/infrastructure repository semantics、dependency/lock、PlanningProblem/Snapshot/Solver/Validator/Backend/Strategy/Reporting、API/Frontend、publication/export和P4必须零差异；CI不改job名称/permissions/Secret/service/deployment。Provider artifact必须复现上述8 rows、full checks、exact SHA与`issues=[]`；成功前Task保持`in_progress`且不启动P3-08。

Corrective implementation artifact `9544333991`已绑定`9aed9d8c5dd86a9a9b972f8e9c5491fd6d2dbaa6`并复现50 committed/0 working paths、上述8 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-07标为`done`，P3-08不自动启动。初始失败run `32793980039`没有artifact且不被覆盖。

## TASK-P3-08 impact review

完整Diff base=`a53c0f7d4a0f0bcd4e02bfeaaa0f6fc4b93157b9`，预期只能命中八行：`IMPACT-DOMAIN`（pure publication identity/authority/documents）、`IMPACT-APPLICATION`（authorization-before-lookup、publish/supersede/current/result/audit transaction与machine CLI）、`IMPACT-STATE`（只执行既有APPROVED→PUBLISHED/PUBLISHED→SUPERSEDED）、`IMPACT-INFRA`（单一required workflow command）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。各行required docs均逐字进入Task allow-list。

Schema/sample/rules、migration/infrastructure repository semantics、dependency/lock、PlanningProblem/Snapshot/Solver/Validator/Backend/Strategy/Reporting、API/Frontend、Exporter/ExportJob与P4必须零差异；CI不改job名称/permissions/Secret/service/deployment。Implementation artifact `9545782727`已绑定`e90475f462b365d2e031445ad28a02ea0b89d2f5`与不可变Diff base，复现51 committed/0 working paths、上述8 rows、19 checks、0 issues及禁止范围零差异；因此本evidence-only closure可把TASK-P3-08标为`done`，P3-09不自动启动。

提交前本地Task report为51 working paths、上述8 rows、19 checks、0 issues；implementation provider已精确重放为51 committed/0 working且冻结禁止路径零差异。

TASK-P3-09实际命中13行：`IMPACT-SCHEMA/DOMAIN/APPLICATION/STATE/EXPORT/JOBS/INFRA/DEPENDENCY/VERSION-METADATA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`。Diff base=`b9c0b1694448a4ec348b0b02107926f6213560c9`；migration、dependency/lock、publication service、P2/v1 bytes、API/frontend/external/P4零差异。首轮full暴露的v1 builder影响已先扩卡并仅用显式2.6常量修正；implementation artifact `9548027237`精确复现76 committed/0 working paths、13 rows、19 checks、0 issues及冻结范围，故本closure可把Task标为`done`且不启动P3-10。

TASK-P3-10实际命中7行：`IMPACT-API/STATE/INFRA/TESTS/PHASE/GOVERNANCE-REGISTRY/DOCS`。Diff base=`f71c4a5a11a3fac0e203e2e92198c26124755927`；API与three test classes、health/CI contract、single required workflow step及逐字文档allow-list可变，Schema/sample/rules、migration、dependency/lock、domain/application/repository/exporter/job、Frontend/external/P4零差异。Implementation artifact `9550224090`精确复现51 committed/0 working paths、7 rows、19 checks、0 issues及冻结范围，故本closure可把Task标为`done`且不启动P3-11。

## TASK-P3-11 impact review

完整Diff base=`26dd519b1f1f84e08d415cfdfce43f286fa82988`，预期只命中六行：`IMPACT-FRONTEND`（locked shell/API adapter/read-only routes/components）、`IMPACT-INFRA`（required Node install/SCA/license/lint/type/test/build/evidence steps）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`和`IMPACT-DOCS`。Task卡逐字allow-list是完整可变范围。

Schema/sample/rules、migration、Python dependency/`uv.lock`、Backend domain/application/repository/API semantics、state machine、Solver/Validator、P3-12+、P4与Production deployment必须零差异。`docs/domain/state-machines/schedule-version.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`和Task Template由Impact Rule复核但无语义变化，允许保持零diff；不得为增加row而改写历史。兼容门禁固定为`typescript-eslint=8.68.0`/`eslint=10.9.1`/`typescript=6.0.3`及TypeScript peer `>=4.8.4 <6.1.0`。

Implementation artifact `9552386549`精确复现74 committed/0 working paths、上述六行、19 checks、0 issues且无额外Impact row。Frontend exact files、required workflow和只读CI contract是唯一代码/CI变化，全部冻结范围仍零差异，故本closure可把Task标为`done`且不启动P3-12。

## TASK-P3-12 impact review

完整Diff base=`3bca1cc10ebedc4d47227bafb2f3f66854ccb526`，实际预期只命中六行：`IMPACT-FRONTEND`（strict visualization contracts/client、Gantt/load/comparison、routes/styles）、`IMPACT-INFRA`（既有required job增加Chromium install/read-only E2E且artifact always收集Playwright）、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`（新增有界SIM-ASSUMPTION-014）和`IMPACT-DOCS`。Task卡逐字allow-list是完整可变范围。

Schema/sample/rules、migration/database、Python dependency/`uv.lock`、`frontend/package-lock.json`及24个pins、Backend domain/application/repository/API semantics、state machine、Solver/Validator/KPI算法、P2 fixture/baseline、command/action、P4与Production deployment/identity/authority必须零差异。`docs/domain/state-machines/schedule-version.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、Task Template与ADR索引由Impact Rule复核但无语义变化，保持零diff。Implementation artifact `9555196470`精确复现55 committed/0 working paths、上述六行、19 checks、0 issues且package-lock/pins零漂移，故本closure可把Task标为`done`；P3-13、P4与Production未启动。
