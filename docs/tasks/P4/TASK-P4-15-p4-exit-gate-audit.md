---
doc_id: TASK-P4-15
title: P4 Exit Gate Audit
status: planned
spec_version: 0.3.0
phase: P4
normative: true
source_sections: [35, 47, 48, 49, 50, 79, 80, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-27
---

# TASK-P4-15 — P4 Exit Gate Audit

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-012, REQ-013, REQ-014

NFR / ENG IDs: all registered NFR and ENG IDs

Depends on: TASK-P4-14

Start gate: 前序依赖全部`done`且其implementation/closure exact provider均成功；用户对TASK-P4-15另行明确授权；启动时`main=origin/main=remote main`、ahead/behind=`0/0`、working tree clean；把该时点完整40字符HEAD写入不可变Diff base；先将planned范围展开为逐字exact allow-list。

Goal: 在全部P4 closure后的clean synchronized baseline上独立审计Task拓扑、exact provider artifacts、Schema/migration/state/ADR/依赖、事件/事实/freeze/目标/报告/Simulator/API/UI/Gate/治理及阶段边界，给出READY或NOT_READY。

Non-goals: 不修实现、不改断言/expected、不补跑旧SHA冒充成功、不关闭PROD_OPEN、不切P5、不声明Production readiness。

Inputs: TASK-P4-00～14全部Diff base/implementation/closure/provider evidence、P4 Gate raw reports、所有历史失败/corrective链。

Diff base: not assigned; record the clean provider-verified 40-character HEAD only when this Task is separately authorized and activated

Files allowed to change: `docs/milestones/P4-exit-gate-audit-report.md`、`docs/milestones/P4-exit-gate-evidence-manifest.json`、独立audit observation输出及精确治理文档；以及`Documents to update`中的逐字路径。激活前必须把目录范围展开为exact paths。

Files forbidden to change: 业务代码、Schema/migration/dependency/lock、tests/workflow、fixtures/baselines、前序Task历史、P5+、Production artifacts

Implementation steps: 冻结HEAD；逐提交/required check/artifact/expiry/digest下载复验；fresh完整本地命令和双Gate；核对合同/Schema/migration/state/ADR/test/trace/open/sim/risk；形成machine manifest；0 gaps才READY。

Outputs: P4 Exit audit report、machine manifest、provider-verifiable audit evidence；不改变current phase直到用户另行批准。

Capability ownership and boundaries: 本Task的直接owner见Goal/Outputs；ExecutionEvent、ReplanRequest、freeze window、OBJ-002 Stability、ChangeReport、Execution Simulator中未由本Task直接形成的能力只允许作为冻结输入或明确后继，不得旁路实现。P4只形成隔离Simulation/development证据；P5 advanced capabilities与Production/external authority/capacity/SLA均排除。

Documentation impact: required

Documents to update: `docs/milestones/P4-exit-gate-audit-report.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P4-dynamic-replanning.md`、`docs/tasks/README.md`、`docs/contracts/README.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/planning/replanning.md`、`docs/simulation/execution-simulator-and-disruptions.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/tasks/P4/TASK-P4-15-p4-exit-gate-audit.md`

Documentation impact rationale: 本Task会改变其owner能力的合同/实现证据和追踪状态；所有Impact Rule必审文档须在激活前逐字确认，未修改者在Completion evidence逐项说明。

Change-impact matrix rows reviewed: `IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: 全部P4 roots→TASK-P4-00～15→61 registered Test IDs/machine reports→implementation/closure provider artifacts→P4 audit report/manifest。

Contract impact: none；独立审计全部P4与retained P0～P3 contracts，任何偏差形成blocking gap，不在Audit内修改合同。

Schema changes: none；只审计全部P4 versions/fingerprints/compatibility，任何差异为gap。

Migration: none；只执行/审计empty/populated round-trip及数据边界。

Dependency changes: none；只核验exact locks/SCA/license/solver version。

ADR impact: none；只核验TASK-P4-01形成的三份exact accepted ADR及历史ADR不可变。

State-machine impact: 只审计所有state/pair/guards/negative paths，不新增或修改。

Error behavior: 未知版本/类型/状态/authority、重复ID不同fingerprint、stale base、跨plane、缺失provenance或任何Validator/contract失败均fail closed；不得把UNKNOWN写成INFEASIBLE、把Simulation值写成Production默认或把partial result写成成功。

Tests: fresh运行全部registered suites、P2/P3/P4 Gates、五类连续场景、browser和governance；不改断言。

Test IDs: all 61 registered Test IDs and required machine reports

Benchmark impact: 只记录development correctness/quality/runtime/memory观察；不得建立Production capacity/SLA。若本Task不执行Benchmark，明确复用并冻结P2 XS/S/M baseline。

Simulation scenarios: 逐项审计五类连续场景、seed/config/hash/assumption及facts/locks/Validator/ChangeReport证据。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；Task-specific focused tests与machine command；完整registered pytest；必要的Frontend/Playwright/SCA/license；全部历史machine contracts与P2/P3 Gates；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P4/TASK-P4-15-p4-exit-gate-audit.md --check-diff --report build/traceability/TASK-P4-15-report.json`；`git diff --check`；相对Diff base的forbidden-scope核验。

Artifacts: `p4-exit-gate-evidence-manifest.v1`、audit observations、Task/provider artifact。

Provider evidence: GitHub `kumamon-xu/PlantNexus-APS` / `main` / `.github/workflows/ci.yml`；implementation与evidence-only closure必须分别绑定exact SHA的required `validate`（GitHub Actions app `15368`）、未过期artifact、Task/Diff base/Impact Rules/checks/issues一致性；失败run保留并以新corrective SHA重跑。

Completion conditions: 前序全部done且provider完整；所有mandatory checks PASS；`blocking_gaps=[]`才READY；audit implementation和evidence-only closure各自exact provider成功；current phase仍P4等待用户批准。；文档/追踪/OPEN/SIM/risk/inventory一致；实现与evidence-only closure均经exact provider；不自动启动下一Task。

Failure handling: 任一本地、scope、required check或artifact不一致即保持`in_progress`并停止；保留失败run，限定corrective commit只能在原allow-list内；需要扩范围先更新Task并重新做Impact review，禁止重写历史。

Production boundary: READY只表示P4 Exit可由用户评估，不自动形成Production readiness/UAT/authority/external integration/deployment/capacity/SLA。

P5 boundary: Audit不得创建P5 Task、Schema、ADR或实现；READY也不自动授权P5 transition。

Explicitly excluded: P5+能力；Production readiness/UAT/deployment；真实approval authority/identity/RBAC；external publish/MES/ERP/storage；未关闭OPEN的freeze/priority/capacity/SLA默认；未经授权的下一Task。

PROD_OPEN: OPEN-001～015保持真实状态；本Task不得自行关闭。需要Production字段/authority/freeze/target/capacity时必须引用正式closure record。

SIM_ASSUMPTIONS: 只能使用或新增显式versioned、bounded、non-Production的SIM_ASSUMPTION；任何新数值须在本Task完成前登记，不得外推Production。

Rollback: READY被provider或事实推翻时立即撤回并在P4创建remediation；保留失败run和历史，不force-push。

## Completion evidence

保持空白直到本Task获得独立授权并执行。计划卡不是实现、测试PASS、provider evidence或Production声明。
