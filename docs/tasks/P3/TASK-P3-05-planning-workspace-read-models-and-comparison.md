---
doc_id: TASK-P3-05
title: Planning Workspace Read Models and Comparison
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [4, 35, 42, 68, 77]
last_reviewed: 2026-08-24
---

# TASK-P3-05 — Planning Workspace Read Models and Comparison

Task batch role: phase-plan-member

Requirement IDs: REQ-002, REQ-003, REQ-004, REQ-005, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-OBS-001, NFR-PER-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-04

Start gate: TASK-P3-04=`done`且provider成功；用户明确授权；clean synchronized main；记录immutable Diff base；至少一个versioned synthetic READY_FOR_REVIEW ScheduleVersion可重放。

Goal: 构建Data Health、Planning Runs、Orders、Operations、Resources、Calendars、Gantt、Resource Load、KPI、Diagnostics、Audit及Version Comparison的solver-neutral read models与确定性查询服务。

Non-goals: 不提供HTTP/UI，不修改ScheduleVersion，不产生ChangeReport，不重排/求解，不审批/发布/导出。

Inputs: P1 canonical/Snapshot事实、P2 solution/KPI/diagnostics、P3 ScheduleVersion/audit repositories与workspace query Schema。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `backend/app/application/workspace_queries.py`、`backend/app/application/schedule_comparison.py`、`backend/app/domain/workspace.py`、相关`__init__.py`、限定unit/property/integration tests、machine CLI及`Documents to update`；实际路径激活前逐字固定。

Files forbidden to change: Schema/migration/dependency、repositories写语义、Planning/Solver/Validator/Exporter、API/Frontend、ScheduleVersion transition、P4 ChangeReport/Replan/ExecutionEvent。

Implementation steps: 定义stable sorting/pagination/filter；从权威records生成各read model；计算资源负载且与schedule assignment一致；版本比较只输出P3 comparison DTO；显式empty/missing/stale/plane错误；property/replay与规模观察。

Outputs: 只读workspace query/comparison services、deterministic report和测试。

Documentation impact: required

Documents to update: `docs/contracts/planning-workspace-api.md`、`docs/frontend/planning-workspace.md`、`docs/domain/domain-model.md`、`docs/domain/kpi-contract.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/quality/property-tests.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、全部governance/trace/impact/inventory必审文档、本Task卡。

Documentation impact rationale: 新的用户可见查询投影与comparison语义必须追溯权威数据、排序、KPI和P4边界。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-002/003/004/005/007/009→TASK-P3-05→TEST-WORKSPACE-READ-MODEL-001/TEST-PROPERTY/TEST-OBS-001→read-model report。

Schema changes: none；严格消费TASK-P3-02 query/comparison Schema。

Migration: none；只读P3 repositories。

Dependency changes: none；资源负载计算使用标准库/既有合同。

ADR impact: none expected，落实TASK-P3-01 accepted Workspace ADR的query边界；若引入缓存/异步物化或改变权威来源，先建ADR。

State-machine impact: none；query不得触发transition或隐式current-version改变。

Error behavior: missing/stale/mixed-plane/tampered lineage明确拒绝；空列表与不存在资源区分；不得把diagnostic缺失写成可行。

Tests: TEST-WORKSPACE-READ-MODEL-001、TEST-PROPERTY、TEST-OBS-001、TEST-SIM-ISOLATION；覆盖每种view、排序/分页、load/KPI一致性、comparison replay与P4 ChangeReport缺席。

Benchmark impact: 建立versioned synthetic read-model规模观察与虚拟化输入计数，不设Production阈值，不改P2 baseline。

Simulation scenarios: 复用既有P2 correctness/XS synthetic ScheduleVersion；新定量profile必须另行登记。

Acceptance commands: 定向unit/property/integration pytest与read-model machine CLI；full tests/Ruff/Pyright/locked sync；full/diff docs治理；`git diff --check`及禁止范围diff。

Artifacts: read-model/comparison report、Task report、provider artifact。

Provider evidence: exact implementation/closure required `validate`/artifact；核对view counts/fingerprints、Task exact SHA/Impact/checks/issues。

Completion conditions: 全部P3页面所需read model可确定重放且source/lineage明确；比较不是ChangeReport；负向/规模观察/provider/docs闭环；无write/API/UI/P4。

Failure handling: 投影与权威事实/KPI不一致时保留失败并停止API/UI；不得在read layer修补源数据或复制Solver逻辑。

Explicitly excluded: command/write、approval/publish/export、HTTP/Frontend、Replan/ChangeReport/OBJ-002、Production SLA。

PROD_OPEN: OPEN-001/002/003/004/015保持OPEN；query不补猜timezone/topology/field authority。

SIM_ASSUMPTIONS: 复用既有资产；任何规模参数仍synthetic-only。

Rollback: read service可回退而不改持久化；已发布query Schema需新版本，不覆盖旧bytes。
