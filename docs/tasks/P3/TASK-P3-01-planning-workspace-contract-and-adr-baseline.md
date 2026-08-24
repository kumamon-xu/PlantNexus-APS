---
doc_id: TASK-P3-01
title: Planning Workspace Contract and ADR Baseline
status: planned
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 65, 66, 68, 69, 77, 78, 94, 97]
last_reviewed: 2026-08-24
---

# TASK-P3-01 — Planning Workspace Contract and ADR Baseline

Task batch role: phase-plan-member

Requirement IDs: REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-TRC-001, NFR-ISO-001, NFR-SEC-001, NFR-HUM-001, ENG-ARCH-001, ENG-ERR-001, ENG-VER-001

Depends on: TASK-P3-00

Start gate: TASK-P3-00=`done`且其closure exact provider成功；用户另行明确授权TASK-P3-01；`main=origin/main`、working tree clean；启动时把当时完整40字符HEAD写入Diff base。必须在任何P3 Schema、migration、dependency或业务代码之前完成并接受本Task合同/ADR。

Goal: 形成P3全部页面、read/command API payload、ScheduleVersion/ExportJob/audit边界及authority-neutral permission matrix，接受P3 command/state/publication架构ADR，为后续实现提供单一规范基线。

Non-goals: 不创建Schema/Python/DB/API/Frontend，不选择Production角色，不关闭OPEN-002/010，不执行approve/publish/export。

Inputs: P3 Milestone、ScheduleVersion/ExportJob状态机、ADR-0002/0005/0007/0009、P2 validated output、总规§33～35/65～69/77～78/94、OPEN-002/010。

Diff base: set only when this Task enters in_progress; must be the immediate full 40-character HEAD

Files allowed to change: `docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/README.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/adr/README.md`、激活时以当时下一个未使用编号逐字固定的一份P3 Workspace ADR及`Documents to update`中的明确文档；任何新增路径须在激活提交中逐字固定。

Files forbidden to change: `backend/**`、`schemas/**`、`frontend/**`、migrations、`.github/workflows/**`、`pyproject.toml`、`uv.lock`、P2历史report/manifest/Task、P4 ExecutionEvent/Replan/ChangeReport/OBJ-002实现。

Implementation steps: 冻结页面/路由/状态视图；定义query/command envelopes、错误与幂等key；定义view/edit/lock/approve/reject/publish/export/audit capabilities但不绑定真实角色；明确Production default-deny与Simulation test actor；记录transaction/immutability/audit/publication/ExportJob边界ADR；同步追踪与风险。

Outputs: 三份Frontend规范、两份P3合同、一份accepted P3 Workspace ADR、页面/API/权限/状态/审计/幂等矩阵。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/contracts/README.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、新增的五份规范/ADR及本Task卡。

Documentation impact rationale: P3实现前置条件就是详细页面、API payload与permission matrix；状态、数据权威、审计、发布和模块方向需要ADR与跨文档一致性。

Change-impact matrix rows reviewed: `IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/009→TASK-P3-01→TEST-WORKSPACE-CONTRACT-001/TEST-STATE-TRANSITION-001→versioned docs/ADR；只形成合同证据，不写实现链接。

Schema changes: none；只列出TASK-P3-02必须发布的文档名、URN、兼容分类与consumer，不创建机器Schema。

Migration: none；只定义事务、不变量、索引/唯一性需求，实际DDL留给TASK-P3-03。

Dependency changes: none；Frontend package manager/build/test组合必须在ADR/技术栈审查中明确，但任何lockfile只允许TASK-P3-11修改。

ADR impact: required；记录command-only编辑、新Version、authorized-human capability、approved-only idempotent publication、Export与Publish分离、Production default-deny及P4边界；不得以ADR关闭OPEN-010。

State-machine impact: pair集合保持既有v1；只补齐guard/actor/reason/audit/idempotency/persistence解释。若需新state/pair立即停止并单独提出superseding ADR与版本化迁移计划。

Error behavior: 明确DATA_ERROR/MODEL_INVALID/VALIDATION_FAILED/INVALID_STATE_TRANSITION/AUTHORIZATION_DENIED/IDEMPOTENCY_CONFLICT/EXPORT_FAILED的责任层与HTTP映射计划；UNKNOWN不得改写为INFEASIBLE，未授权Production必须fail closed。

Tests: TEST-WORKSPACE-CONTRACT-001、TEST-STATE-TRANSITION-001、TEST-ERROR-MAPPING-001的planned contract matrix；本Task只做文档一致性/链接检查，不得标为行为formed。

Benchmark impact: 记录Gantt/read-model/frontend规模测试维度但不设Production阈值；P2 XS/S/M基线只读。

Simulation scenarios: 只定义后续使用既有P2 synthetic schedule验证状态/交互，不新增定量值；需要新值时由执行Task注册。

Acceptance commands: `uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-01-planning-workspace-contract-and-adr-baseline.md --check-diff --report build/traceability/TASK-P3-01-report.json`；`uv run pytest -q backend/tests/unit/test_check_docs.py backend/tests/contract/test_rule_contracts.py`；`git diff --check`；禁止范围diff命令按Diff base核验`backend schemas frontend migrations .github pyproject.toml uv.lock`零变化。

Artifacts: 页面/API/permission/state矩阵、ADR、Task traceability report、exact provider artifact。

Provider evidence: implementation和evidence-only closure均须精确绑定required `validate`与未过期artifact；Task report必须记录exact SHA、Impact rows、19项或当时完整checks及0 issues。

Completion conditions: 页面/API/payload/permission/错误/状态/审计/幂等矩阵无缺口；ADR accepted；OPEN-002/010仍OPEN且Production default-deny；文档/追踪/provider闭环；无代码/Schema/migration/dependency/P4实现。

Failure handling: 合同冲突、权限来源不明或需要新state时保持Task `in_progress`/失败证据，停止后继；不得用test actor冒充Production authority。

Explicitly excluded: P3-02+实现、真实身份提供商/RBAC角色、MES adapter、Production approval/publish、dynamic Replan/ExecutionEvent/ChangeReport/OBJ-002。

PROD_OPEN: OPEN-002/010/015保持OPEN；permission matrix只定义capability和默认拒绝，不猜人/组织/系统责任。

SIM_ASSUMPTIONS: 可定义非定量的Simulation test-actor边界；任何新增定量数据必须另行注册且不得关闭OPEN。

Rollback: 文档/ADR在未被consumer使用前可由有界superseding变更修正；accepted ADR和已发布合同不得删除或重写，后续变化使用新ADR/版本。
