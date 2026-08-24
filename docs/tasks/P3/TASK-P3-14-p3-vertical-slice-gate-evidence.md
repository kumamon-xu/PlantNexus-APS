---
doc_id: TASK-P3-14
title: P3 Vertical Slice Gate Evidence
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 66, 67, 68, 69, 77, 78, 86, 87, 94, 100]
last_reviewed: 2026-08-24
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

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/application/p3_gate_report.py`、相关`__init__.py`、`backend/tests/integration/test_p3_vertical_slice.py`、`backend/tests/contract/test_p3_exit_rejections.py`、frontend P3 Gate/Playwright orchestration文件、`.github/workflows/ci.yml`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`；实际路径激活前固定。

Files forbidden to change: P3-02～13业务/Schema/migration/dependency/fixtures/baselines/expected artifacts、Solver/Validator公式、P2 historical artifacts、P4/Production implementation。

Implementation steps: 定义`p3-vertical-slice-report.v1`；两次fresh isolated replay；positive review/approve/publish/export flow；reject/new Draft branch；Gantt edit/new ID/fresh Validator；DRAFT/REJECTED publish rejection、PUBLISHED mutation rejection、double publish/export replay；read/API/UI/audit cross-check；保留raw证据与stable semantic projection；CI command/artifact。

Outputs: P3 Gate CLI/report、focused tests、CI required evidence、blocking gap list。

Documentation impact: required

Documents to update: P3 Milestone/current phase/task index、P3 contracts/frontend/state/architecture/operations/quality Gate说明、全部governance/trace/OPEN/SIM/risk/impact/inventory必审文档、`docs/tasks/TASK_TEMPLATE.md`、本Task卡。

Documentation impact rationale: 全P3纵向聚合与Gate失败边界、CI artifact及Exit前提形成。

Change-impact matrix rows reviewed: `IMPACT-APPLICATION`、`IMPACT-FRONTEND`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

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

Acceptance commands: P3 Gate CLI `--repeat 2`（激活前固定report路径）；全部Python tests/Ruff/Pyright/locked sync/build；frontend npm locked/lint/type/test/build/Playwright；P2 XS/Gate regression；full/diff docs治理；`git diff --check`和冻结范围diff。

Artifacts: P3 Gate raw/semantic report、Playwright evidence、P2 regression、Task traceability/provider artifact。

Provider evidence: implementation/closure exact SHA均须successful required `validate`与未过期artifact；下载检查全部JSON/E2E报告、exact SHA/Task/Impact/checks/issues、blocking gaps与branch protection。

Completion conditions: 两次完整P3 replay业务语义一致；全部Milestone Gate/负向/Frontend/CI PASS且0 gaps；所有前置provider链完整；Exit仍未执行；无P3修复/P4/Production声明。

Failure handling: 任一失败保持P3 active，登记有界remediation Task并在修复后重新执行Gate；禁止在本Task改业务或重写失败run。

Explicitly excluded: P3 Exit Audit、业务修复、Production readiness/UAT/publish、P4 Replan/ExecutionSimulator/ChangeReport/OBJ-002。

PROD_OPEN: OPEN-001～015按真实状态保留；Gate不关闭任何条目。

SIM_ASSUMPTIONS: 只使用已登记versioned assumptions；新增定量值须在Gate前由所属Task登记。

Rollback: Gate代码/report可回退，失败/provider历史和业务Version/audit不可删除；成功Gate不自动进入P4或Production。
