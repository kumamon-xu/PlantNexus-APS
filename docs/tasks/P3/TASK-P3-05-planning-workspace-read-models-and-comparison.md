---
doc_id: TASK-P3-05
title: Planning Workspace Read Models and Comparison
status: in_progress
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

Diff base: fc5011f78a242160097521259a1914d864d9ad17

Files allowed to change: `.github/workflows/ci.yml`、`backend/app/application/__init__.py`、`backend/app/application/workspace_queries.py`、`backend/app/application/schedule_comparison.py`、`backend/app/application/workspace_read_model_check.py`、`backend/app/domain/__init__.py`、`backend/app/domain/workspace.py`、`backend/tests/unit/test_workspace_read_models.py`、`backend/tests/property/test_workspace_read_model_properties.py`、`backend/tests/contract/test_workspace_read_model_contract.py`、`backend/tests/integration/test_workspace_queries.py`、`backend/tests/integration/test_ci_contract.py`及`Documents to update`的逐字路径；ignored machine report只允许写入`build/validation/ci-p3-workspace-read-models.json`或本地同类路径，Task report只允许写入`build/traceability/TASK-P3-05-report.json`或CI同类路径；除此以外均禁止。

Files forbidden to change: Schema/migration/dependency、repositories写语义、Planning/Solver/Validator/Exporter、API/Frontend、ScheduleVersion transition、P4 ChangeReport/Replan/ExecutionEvent。

Implementation steps: 定义stable sorting/pagination/filter；从权威records生成各read model；计算资源负载且与schedule assignment一致；版本比较只输出P3 comparison DTO；显式empty/missing/stale/plane错误；property/replay与规模观察。

Outputs: 只读workspace query/comparison services、deterministic report和测试。

Documentation impact: required

Documents to update: `docs/tasks/P3/TASK-P3-05-planning-workspace-read-models-and-comparison.md`、`docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/authorization-and-audit.md`、`docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/domain/kpi-contract.md`、`docs/core/glossary.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/README.md`、`docs/operations/observability-and-audit.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/property-tests.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`。

Documentation impact rationale: 新的用户可见查询投影与comparison语义必须追溯权威数据、排序、KPI和P4边界。

Change-impact matrix rows reviewed: `IMPACT-DOMAIN`、`IMPACT-APPLICATION`、`IMPACT-INFRA`、`IMPACT-TESTS`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

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

## Activation evidence

2026-08-24在用户明确授权后，以P3-04 evidence-only closure `fc5011f78a242160097521259a1914d864d9ad17`作为不可变Diff base启动。启动前确认`main=origin/main`、ahead/behind=`0/0`且working tree clean；P3-04 implementation→closure拓扑为`a9be974855bb825784d639b7f6675e5a33e4273d`→`fc5011f78a242160097521259a1914d864d9ad17`。Closure run/job/artifact=`32700684160`/`97351382226`/`9510431988`，required `validate`来自GitHub Actions app `15368`且success；artifact未过期，digest=`sha256:a42541fd57ed58a28e738d6be229f1d134b2b357049f5974cf0fa35da490447d`，23/23 JSON全部可解析并PASS，lifecycle为8/8、Task report为45 committed/0 working paths、8 rows、19 checks、0 issues。

启动时重新运行P3-04 lifecycle machine boundary，确认versioned synthetic ScheduleVersion提交态为`READY_FOR_REVIEW`、exact replay=`1`、service Solver调用=`0`且8/8 checks PASS。该重放只证明P3-05拥有可读的上游Version；P3-05产品服务不得调用Solver、写repository或推进状态。为使本Task machine report成为required provider artifact，workflow只增加non-skippable离线检查命令并保持required job名称、permissions、Secret、service和deployment不变，因此在实现前显式加入`IMPACT-INFRA`及其required documents。

## Local implementation evidence

Pure domain现形成14种`WorkspaceView`、七文档lineage binding、complete payload→strict carrier fingerprint、stable filter/sort/query-scope cursor、found-empty/missing/stale/plane/tamper语义及deterministic P3 comparison。Application形成read-only ScheduleVersion/Audit repository ports、workspace query和two-Version comparison service；产品service无Solver/write/transition port。Required workflow只新增`workspace_read_model_check`命令。

本地machine报告为8/8 PASS：13个普通view共23个payload、1个comparison、query/comparison各1次exact replay、4类negative、两个Version/两个AuditEvent在所有read前后保持相同row count、product-service Solver调用0；comparison无ChangeReport/Replan。Unit/property/contract/integration/CI定向组合33 PASS，全仓527 PASS，locked sync、Ruff、Pyright、Compose、build、full/diff docs、`git diff --check`和禁止范围均通过；治理为50 working paths、7 Impact rows、19 checks、0 issues。以上仍是provider-pending实现事实，Task保持`in_progress`；implementation exact provider与closure尚须完成，P3-06不得自动启动。
