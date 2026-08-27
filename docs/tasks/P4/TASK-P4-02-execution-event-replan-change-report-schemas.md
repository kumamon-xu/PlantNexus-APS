---
doc_id: TASK-P4-02
title: ExecutionEvent Replan and ChangeReport Machine Contracts
status: planned
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

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `schemas/**`、pure P4 contract/precheck代码、限定contract tests、机器报告命令、required CI additive step及启动时精确展开的命中文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: 既有Schema/sample bytes、`backend/migrations/**`、repository/application/Solver/Simulator/API/UI实现、dependency/lock、P5+

Implementation steps: 冻结历史fingerprints；定义strict/no-default/explicit-version/plane/source carriers；验证offline refs、positive/negative/canonical fingerprints；加入非可跳过机器报告；同步索引和追踪。

Outputs: 版本化P4 schema set、samples、pure values/prechecks及`p4-machine-contract-report.v1`。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/execution-events-and-replan-request.md`、`docs/contracts/planning-policy-and-solve-limits.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/architecture/provenance-and-versioning.md`、`docs/governance/traceability-matrix.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/tasks/P4/TASK-P4-02-execution-event-replan-change-report-schemas.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-SCHEMA`、`IMPACT-DOMAIN`、`IMPACT-PLANNING-CONTRACTS`、`IMPACT-POLICY`、`IMPACT-REPORTING`、`IMPACT-STATE`、`IMPACT-INFRA`、`IMPACT-DEPENDENCY`、`IMPACT-VERSION-METADATA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

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

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: 无consumer前可移除additive版本并保留历史记录；一旦消费只能发布后继版本和兼容迁移。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
