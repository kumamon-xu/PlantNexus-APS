---
doc_id: TASK-P3-14
title: P3 Vertical Slice Gate Evidence
status: in_progress
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 66, 67, 68, 69, 77, 78, 86, 87, 94, 100]
last_reviewed: 2026-08-26
---

# TASK-P3-14 — P3 Vertical Slice Gate Evidence

Task batch role: phase-plan-member

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, NFR-HUM-001, ENG-ARCH-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P3-01～TASK-P3-13

Start gate: TASK-P3-01～13全部`done`且每个implementation/closure exact provider artifact成功；用户明确授权；clean synchronized main；记录immutable Diff base；P3业务/Schema/migration/dependency/frontend baselines冻结，只允许Gate编排和CI证据。

Goal: 从P2 validated solution开始至少两次重放完整P3链，聚合ScheduleVersion、workspace views、Gantt/new Draft/Validator、approve/reject、approved-only publish、immutability、ExportJob、audit、API与Frontend E2E的版本化Gate报告和blocking gaps。

Non-goals: 不在Gate修业务/Schema/test expected/baseline，不执行Exit Audit，不接Production，不实现P4。

Inputs: P3-01～13公开边界与provider artifacts、P2 correctness/XS基线、P3 Test registry/Milestone Gate。

Diff base: 6a3e02f00bf46f19915cb59c3c4af7daaac95be4

Activation evidence: 用户于2026-08-26明确授权执行TASK-P3-14；启动复核确认`main=origin/main=6a3e02f00bf46f19915cb59c3c4af7daaac95be4`、ahead/behind=`0/0`且working tree clean，P3-01～13全部`done`。13组Diff base→implementation→closure→当前HEAD祖先检查均PASS；26个implementation/closure push run与required `validate` job均success，26个artifact均未过期。下载解析全部artifact后无JSON解析/顶层/check/issues失败，Task trace均绑定各自exact SHA/base且implementation/closure的paths、Impact rows一致。该完整HEAD据此冻结为本Task不可变Diff base。

Local implementation evidence: `p3-vertical-slice-report.v1`两次fresh Backend replay共18 stages/144 subordinate checks、4 exact rejections、14/14 checks且`blocking_gaps=[]`；Frontend两轮各12/12、8 human-control specs，5/5且semantic fingerprint唯一。首次full 615/1由import guard拦截后以逐模块只读例外修正；第二次full 611 pass/5 setup errors精确暴露approval合法并发交错，现已在验证允许集合、single CAS winner/1 audit/exact replay后只归一化projection并保留raw。最终完整本地验收为616 Python、54 Vitest、基础/双Gate Chromium各12/12、全部machine/P2 XS/Gate/SCA/license/Compose/build、Ruff/Pyright和Task 56 working paths/8 Impact Rules/19 checks/0 issues均PASS。

Provider failure/corrective boundary: 首个implementation `0617141e411eea146cd9fc1c512ade900710be7c`的push run `32930677030` / required job `98062166642`在repository suite失败（611 passed/5 shared-fixture setup errors）。原因是CI的`PLANTNEXUS_CODE_COMMIT`已绑定exact SHA，而synthetic Frontend Gate及其嵌套human-control report仍写死`uncommitted`；Gate按合同拒绝，后续upload无reports且artifact count=0。该run作为负证据永久保留且不得rerun。独立corrective只让测试夹具调用Gate既有`_code_commit()`，不改业务、断言语义、workflow、Schema、dependency或冻结基线；exact-SHA定向5/5已PASS。新的corrective exact provider完成前Task保持`in_progress`/`LOCAL_PASS_PROVIDER_PENDING`。

Files allowed to change: `backend/app/application/p3_gate_report.py`、`backend/tests/integration/test_p3_vertical_slice.py`、`backend/tests/contract/test_p3_exit_rejections.py`、`backend/tests/integration/test_p1_common_ingress.py`（只允许登记`p3_gate_report.py`的逐模块evidence-orchestrator例外）、`frontend/playwright.p3-gate.config.ts`、`frontend/scripts/p3-gate-evidence.mjs`、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`、`README.md`及`Documents to update`中的逐字路径。除这些路径外不得新增或修改任何文件；发现新增路径或Impact Rule时须先停止并修订本卡。

Files forbidden to change: P3-02～13业务/Schema/migration/dependency/fixtures/baselines/expected artifacts、Solver/Validator公式、P2 historical artifacts、P4/Production implementation。

Implementation steps: 定义`p3-vertical-slice-report.v1`；两次fresh isolated replay；positive review/approve/publish/export flow；reject/new Draft branch；Gantt edit/new ID/fresh Validator；DRAFT/REJECTED publish rejection、PUBLISHED mutation rejection、double publish/export replay；read/API/UI/audit cross-check；保留raw证据与stable semantic projection；CI command/artifact。

Outputs: P3 Gate CLI/report、focused tests、CI required evidence、blocking gap list。

Documentation impact: required

Documents to update: `README.md`、`docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-14-p3-vertical-slice-gate-evidence.md`、`docs/contracts/README.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/export-package.md`、`docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/adr/README.md`、`docs/operations/README.md`、`docs/operations/observability-and-audit.md`、`docs/operations/security.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/quality/benchmark-regression.md`、`docs/quality/fixtures-and-golden-tests.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`。

Documentation impact rationale: 全P3纵向聚合与Gate失败边界、CI artifact及Exit前提形成。

Change-impact matrix rows reviewed: `IMPACT-APPLICATION`、`IMPACT-STATE`、`IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: 所有P3 roots/Tasks/Test IDs→TASK-P3-14→`p3-vertical-slice-report.v1`/Playwright/Task/provider artifact；P3 Exit仍`NOT_PERFORMED`。

Schema changes: none；Gate report保持internal machine contract，若要外部consumer必须另行Schema Task。

Migration: none；只在临时/isolated database运行已发布migration。

Dependency changes: none；所有locks冻结。

ADR impact: none；只验证accepted ADRs，发现偏差登记gap而非改ADR/实现。

State-machine impact: 不新增行为；精确验证DRAFT/REJECTED不可publish、仅APPROVED publish、PUBLISHED immutable、SUPERSEDED与ExportJob pairs。

Error behavior: 任一sub-report/E2E/provider/semantic cross-check失败写FAIL+blocking gap并非零退出；不得聚合掩盖raw failure。

Tests: TEST-P3-VERTICAL-SLICE-001及全部P3 planned IDs；同时重跑TEST-STATE-TRANSITION-001/OUTPUT/IDEMPOTENCY/SIM-ISOLATION和P2 correctness regression。

Benchmark impact: 保留P2 XS required regression及P3 read/render/action/export development observations；不设Production SLA/L/XL。

Simulation scenarios: 两次完全隔离、version/seed/hash固定的synthetic replay；Production path只验证fail closed。

Acceptance commands: `uv run python -m app.application.p3_gate_report --root . --repeat 2 --frontend-report build/validation/TASK-P3-14-frontend-gate.json --p2-report build/validation/TASK-P3-14-p2-gate.json --report build/validation/TASK-P3-14-p3-gate.json`；全部Python tests/Ruff/Pyright/locked sync/build；Frontend以Node `24.19.0`/npm `11.17.0`执行locked install、SCA/license/lint/type/Vitest/build及`PLANTNEXUS_P3_GATE_REPLAY_INDEX=1/2`两次Playwright；P2 XS/Gate regression；full/diff docs治理；`git diff --check`和冻结范围diff。

Artifacts: P3 Gate raw/semantic report、Playwright evidence、P2 regression、Task traceability/provider artifact。

Provider evidence: implementation/closure exact SHA均须successful required `validate`与未过期artifact；下载检查全部JSON/E2E报告、exact SHA/Task/Impact/checks/issues、blocking gaps与branch protection。

Completion conditions: 两次完整P3 replay业务语义一致；全部Milestone Gate/负向/Frontend/CI PASS且0 gaps；所有前置provider链完整；Exit仍未执行；无P3修复/P4/Production声明。

Failure handling: 任一失败保持P3 active，登记有界remediation Task并在修复后重新执行Gate；禁止在本Task改业务或重写失败run。

Explicitly excluded: P3 Exit Audit、业务修复、Production readiness/UAT/publish、P4 Replan/ExecutionSimulator/ChangeReport/OBJ-002。

PROD_OPEN: OPEN-001～015按真实状态保留；Gate不关闭任何条目。

SIM_ASSUMPTIONS: 只使用已登记versioned assumptions；新增定量值须在Gate前由所属Task登记。

Rollback: Gate代码/report可回退，失败/provider历史和业务Version/audit不可删除；成功Gate不自动进入P4或Production。
