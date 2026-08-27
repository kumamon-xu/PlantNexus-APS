---
doc_id: TASK-P4-02
title: ExecutionEvent Replan and ChangeReport Machine Contracts
status: in_progress
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-02 — ExecutionEvent Replan and ChangeReport Machine Contracts

Task batch role: phase-plan-member

Requirement IDs: REQ-005, REQ-007, REQ-008, REQ-009, REQ-013

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-SEC-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P4-01

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-02另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 发布严格、可离线解析且additive的P4机器合同与样例，覆盖ExecutionEvent、ReplanRequest、ChangeReport、ExecutionSimulationManifest以及ADR要求的Policy/SolverReport/ScheduleVersion/Export carrier演进。

Non-goals: 不创建数据库、不执行业务状态、不投影事实、不求解、不运行Simulator；Schema sample不冒充行为证据。

Inputs: TASK-P4-01 accepted ADR/合同、冻结schema set 2.7.0及全部历史Schema/sample fingerprints。

Diff base: 4026597ab1015b5ea3a89d241f0d12b5b481dee3

Files allowed to change: `.github/workflows/ci.yml`、`README.md`、`backend/app/__init__.py`、`backend/app/application/export_job_check.py`、`backend/app/domain/execution_contract_check.py`、`backend/app/domain/execution_contracts.py`、`backend/app/domain/workspace_contract_check.py`、`backend/tests/contract/test_import_validation.py`、`backend/tests/contract/test_p3_export_contracts.py`、`backend/tests/contract/test_p4_machine_contracts.py`、`backend/tests/contract/test_rule_contracts.py`、`backend/tests/contract/test_schema_contracts.py`、`backend/tests/contract/test_unit_conversion_registry.py`、`backend/tests/integration/test_ci_contract.py`、`frontend/scripts/i18n-evidence.mjs`、`pyproject.toml`、`schemas/data_dictionary.yaml`、`schemas/json/change-report.schema.json`、`schemas/json/execution-event.schema.json`、`schemas/json/execution-simulation-manifest.schema.json`、`schemas/json/export-job.v3.schema.json`、`schemas/json/export-manifest.v3.schema.json`、`schemas/json/planning-policy.v2.schema.json`、`schemas/json/replan-request.schema.json`、`schemas/json/schedule-version.v2.schema.json`、`schemas/json/solver-report.v2.schema.json`、`schemas/samples/change-report.v1.synthetic.json`、`schemas/samples/execution-event.v1.synthetic.json`、`schemas/samples/execution-simulation-manifest.v1.synthetic.json`、`schemas/samples/export-job.v3.synthetic.json`、`schemas/samples/export-manifest.v3.synthetic.json`、`schemas/samples/planning-policy.v2.synthetic.json`、`schemas/samples/replan-request.v1.synthetic.json`、`schemas/samples/schedule-version.v2.synthetic.json`、`schemas/samples/solver-report.v2.synthetic.json`、`docs/README.md`、`docs/adr/README.md`、`docs/frontend/README.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/technology-stack.md`、`docs/contracts/README.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/export-package.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/core/glossary.md`、`docs/current_phase.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/prod-open-register.md`、`docs/governance/requirements-register.md`、`docs/governance/risk-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/traceability-rules.md`、`docs/milestones/P4-dynamic-replanning.md`、`docs/milestones/README.md`、`docs/operations/README.md`、`docs/planning/objective-policy.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/planning/solver-backend-contract.md`、`docs/quality/benchmark-regression.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/simulation/execution-simulator-and-disruptions.md`、`docs/tasks/P4/TASK-P4-02-execution-event-replan-change-report-schemas.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`。该逐字集合完整包含下方Documents to update；除ignored `build/validation/ci-p4-machine-contracts.json`与`build/traceability/TASK-P4-02-report.json`外不得新增或修改其他路径，任何扩展必须先更新本卡并重新执行Impact review。

Files forbidden to change: 既有Schema/sample bytes、`backend/migrations/**`、`frontend/**`（仅上述`frontend/scripts/i18n-evidence.mjs`兼容检查除外）、repository/application/Solver/Simulator/API/UI实现、dependency/lock、P5+

Implementation steps: 冻结历史fingerprints；定义strict/no-default/explicit-version/plane/source carriers；验证offline refs、positive/negative/canonical fingerprints；加入非可跳过机器报告；同步索引和追踪。

Outputs: 版本化P4 schema set、samples、pure values/prechecks及`p4-machine-contract-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/frontend/README.md`、`docs/core/glossary.md`、`docs/adr/README.md`、`docs/contracts/README.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/export-package.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-problem.md`、`docs/contracts/planning-snapshot.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/domain/kpi-contract.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/data-authority.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/simulation-first-dual-channel.md`、`docs/architecture/technology-stack.md`、`docs/planning/objective-policy.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/planning/solver-backend-contract.md`、`docs/simulation/execution-simulator-and-disruptions.md`、`docs/operations/README.md`、`docs/quality/benchmark-regression.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/prod-open-register.md`、`docs/governance/requirements-register.md`、`docs/governance/risk-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/traceability-matrix.md`、`docs/governance/traceability-rules.md`、`docs/milestones/P4-dynamic-replanning.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、本Task卡。

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-FRONTEND`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-008/009/013→P4 machine carriers→TEST-CONTRACT-001、TEST-EXECUTION-EVENT-CONTRACT-001、TEST-REPLAN-REQUEST-CONTRACT-001、TEST-CHANGE-REPORT-001→`p4-machine-contract-report.v1`。

Contract impact: required；发布与TASK-P4-01三份accepted ADR逐字一致的versioned machine carriers、URN、fingerprint、sample及negative interchange规则。

Schema changes: required additive release；保留2.7.0及全部document bytes，逐document记录URN/version/compatibility/consumer/fingerprint，禁止in-place reinterpretation。

Migration: none；P4-03消费新合同后才创建迁移。

Dependency changes: none expected；仅metadata version可变，runtime/dev pins与lockfiles必须零差异。

ADR impact: none beyond strict conformance to TASK-P4-01形成的三份exact accepted ADR；启动门必须解析其stable IDs，任何语义偏差先停止并建立superseding ADR。

State-machine impact: 仅发布经P4-01决定的state carrier/allowed-pair合同；不执行transition或持久化。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: TEST-CONTRACT-001、TEST-EXECUTION-EVENT-CONTRACT-001、TEST-REPLAN-REQUEST-CONTRACT-001、TEST-CHANGE-REPORT-001；offline refs、negative drift、canonical replay、historical freeze。

Test IDs: TEST-CONTRACT-001, TEST-EXECUTION-EVENT-CONTRACT-001, TEST-REPLAN-REQUEST-CONTRACT-001, TEST-CHANGE-REPORT-001

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 仅synthetic samples，显式非Production；不计入五类连续Gate。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-02-execution-event-replan-change-report-schemas.md --check-diff --report build/traceability/TASK-P4-02-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-machine-contract-report.v1`、schema inventory/fingerprint manifest、Task report与provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 全部P4 carrier严格通过正负/round-trip/offline/fingerprint检查；历史Schema逐字冻结；依赖/迁移/行为零差异；exact provider与治理闭环。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: carrier只能表达明确plane/provenance，不赋予真实authority、external endpoint、deployment、UAT或capacity/SLA语义。

P5 boundary: Schema不得预埋secondary resource、batch、sequence setup、tool/fixture capacity、多工厂、alternative route、decomposition或rolling/hybrid字段。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 九份sample的固定contract vector登记为`SIM-ASSUMPTION-016`；它只覆盖`SIM-P4-CONTRACT-001@1.0.0`的seed/virtual clock/freeze/assignment与复用P2 SolveLimits数值，不是Simulator/Scenario行为或Production默认。

Rollback: 无consumer前可移除additive版本并保留历史记录；一旦消费只能发布后继版本和兼容迁移。

## Completion evidence

2026-08-27 implementation候选已形成，但在exact provider与evidence-only closure完成前继续保持`in_progress`。本候选发布schema set `2.8.0`的九份additive strict JSON Schema与九份synthetic sample，并提供pure value/precheck及`p4-machine-contract-report.v1`；没有创建数据库、迁移、依赖、repository/application/Solver/Simulator/API/UI行为，也没有形成P5+或Production能力。

本地机器证据为：P4 report `8/8 PASS`、`issues=[]`，覆盖9 schemas、9 samples、58份历史artifact、35个Schema rejection与7个semantic rejection；additive manifest=`sha256:b4e6ce8492fc31760a94ffc8955b92f89c8006500c437eb568b58dff7f667260`，历史manifest继续为`sha256:523ab38a466aa76c97ee39cfa52b7b1d43c77ba4dd622c3d27c409ee9af7242e`，`uv.lock`继续为`sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`，migration仍为7 files/latest `0004`/manifest `sha256:d9df0944263154a0de9dd896780b7ef571614635e879c39ad1cac48f19a53f5b`。全部历史P0/P1/P2/P3 machine contracts、0004 round-trip、P2 benchmark、P2/P3双重回放Gate均PASS且`blocking_gaps=[]`。

工程与跨栈验收为：`uv sync --locked`、ruff、pyright、build、Compose、SCA、license、Frontend lint/typecheck/Vite build、67项Vitest、Chromium baseline及两次Gate replay各12项、Frontend Gate `5/5`、i18n evidence `8/8`全部PASS；Frontend证据使用contract要求的npm `11.17.0`。完整registered pytest=`631 passed`。文档治理为`docs=188`、`roots=30`、`trace_rows=30`、`tests=61`、`open=15`、`sim=16`、`risks=17`、`tasks=71`；Task差异治理为`diff_paths=87`、12条matched Impact Rules、19 checks、`issues=[]`，`git diff --check`通过。

相对不可变Diff base `4026597ab1015b5ea3a89d241f0d12b5b481dee3`的87条路径全部落在逐字allow-list；既有Schema/sample bytes、dependency/lock、migration、state pair、业务行为、P5+与Production/external authority/capacity/SLA禁止范围均保持不变。implementation exact SHA、required `validate`、run/job/artifact/digest及closure证据将在provider成功后由evidence-only提交写回；TASK-P4-03不会自动启动。

## Activation evidence

用户于2026-08-27明确授权执行TASK-P4-02。启动复核确认`main=origin/main=remote main=4026597ab1015b5ea3a89d241f0d12b5b481dee3`、ahead/behind=`0/0`且working tree clean；TASK-P4-01=`done`，implementation `abd70942a41984a9a3956f43d39065b19e4405c3`与closure `4026597ab1015b5ea3a89d241f0d12b5b481dee3`为直接父子拓扑，run/job/artifact分别为`33042150006`/`98417935201`/`9634380233`与`33042751772`/`98419816451`/`9634583546`。两份required `validate`均由GitHub Actions app `15368`成功提供；artifact未过期，digest分别为`sha256:d5078a89a3bbc8a8ffe9654c76dab04a0dd50955859f9fac1cf332a377d0cc3a`与`sha256:b25742c1b4e4c8fc19ee50e55d9c32bddd1b8de5d8588872d0bd2d1c4fe94b75`，下载复核Task/SHA/Diff base/四条Impact Rules/19 checks/`issues=[]`及全部validation JSON均一致PASS；branch protection仍精确要求`validate`/app `15368`。

启动前冻结2.7.0下全部58份既有JSON Schema/sample，按`<POSIX-relative-path>=<lowercase-sha256>\n`排序并以LF连接形成manifest摘要`sha256:523ab38a466aa76c97ee39cfa52b7b1d43c77ba4dd622c3d27c409ee9af7242e`；`uv.lock`摘要=`sha256:8b13617f31aa6a933347fc7b8ba010330cbb3f2d764f75c306dd9b6d77387a82`。范围审查把additive set固定为`2.8.0`、九份新document version与九份sample，并只为既有P3 machine evidence开放current-set metadata兼容行；历史document const/URN/bytes/report语义、dependency pins、state pairs和业务实现仍禁止改变。

本地完整跨栈回归发现P3-16 i18n evidence以其历史Diff base永久禁止所有未来`backend/**`/`schemas/**`变化，导致合法additive P4 Schema在当前及provider提交态均确定性失败。按Failure handling先扩卡：只新增`frontend/scripts/i18n-evidence.mjs`及`IMPACT-FRONTEND`必审文档，修正为冻结P3 Frontend API/P3 Backend API exact files、P3 workspace/export Schema、state/error registries与lock；不修改Frontend source、route、机器值、test assertion或P3证据结论。

本Task保持`in_progress`直到implementation exact provider成功并由evidence-only closure写回完成事实；TASK-P4-03及其他后继仍为`planned`，不会自动启动。
