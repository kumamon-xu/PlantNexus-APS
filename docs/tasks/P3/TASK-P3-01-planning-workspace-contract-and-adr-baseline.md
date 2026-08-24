---
doc_id: TASK-P3-01
title: Planning Workspace Contract and ADR Baseline
status: done
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

Diff base: 7f65f88b620ea1e8d2f4693911be3b52f4052d5d

Activation evidence: TASK-P3-00 closure=`7f65f88b620ea1e8d2f4693911be3b52f4052d5d`，GitHub Actions run `32682015727` / required `validate` job `97300206924` / artifact `9504453154`均为success且artifact未过期；artifact内Task=`TASK-P3-00`、exact SHA一致、19 checks PASS、issues=`[]`。启动时`main=origin/main`且working tree clean，用户已于2026-08-24明确授权执行本Task。

Files allowed to change: `docs/frontend/README.md`、`docs/frontend/planning-workspace.md`、`docs/frontend/gantt-command-contract.md`、`docs/frontend/approval-publication-flow.md`、`docs/contracts/planning-workspace-api.md`、`docs/contracts/authorization-and-audit.md`、`docs/contracts/README.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/adr/README.md`、`docs/adr/ADR-0012-planning-workspace-command-state-publication.md`、`docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-01-planning-workspace-contract-and-adr-baseline.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`，并包含下方`Documents to update`中的所有逐字路径。除上述逐字路径外不得新增或修改其他路径；任何新增路径须先修订本卡并重新执行差异治理。

Files forbidden to change: `backend/**`、`schemas/**`、`frontend/**`、migrations、`.github/workflows/**`、`pyproject.toml`、`uv.lock`、P2历史report/manifest/Task、P4 ExecutionEvent/Replan/ChangeReport/OBJ-002实现。

Implementation steps: 冻结页面/路由/状态视图；定义query/command envelopes、错误与幂等key；定义view/edit/lock/approve/reject/publish/export/audit capabilities但不绑定真实角色；明确Production default-deny与Simulation test actor；记录transaction/immutability/audit/publication/ExportJob边界ADR；同步追踪与风险。

Outputs: 三份Frontend规范、两份P3合同、一份accepted P3 Workspace ADR、页面/API/权限/状态/审计/幂等矩阵。

Documentation impact: required

Documents to update: `docs/current_phase.md`、`docs/milestones/P3-planning-workspace.md`、`docs/milestones/README.md`、`docs/tasks/README.md`、`docs/contracts/README.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/error-model.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/quality/documentation-consistency-checks.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/adr/README.md`、三份新增Frontend规范、两份新增P3合同、`docs/adr/ADR-0012-planning-workspace-command-state-publication.md`及本Task卡。

Documentation impact rationale: P3实现前置条件就是详细页面、API payload与permission matrix；状态、数据权威、审计、发布和模块方向需要ADR与跨文档一致性。

Change-impact matrix rows reviewed: `IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: REQ-006/007/009→TASK-P3-01→TEST-WORKSPACE-CONTRACT-001/TEST-STATE-TRANSITION-001→versioned docs/ADR；只形成合同证据，不写实现链接。

Schema changes: none；`planning-workspace-api.md`已逐项列出TASK-P3-02必须发布的`schedule-version/workspace-query/workspace-command/schedule-version-comparison/audit-event/publication-result/export-job.v1`文件、URN、新文档compatibility与consumer，不创建机器Schema；schema set保持`2.5.0`。

Migration: none；只定义事务、不变量、索引/唯一性需求，实际DDL留给TASK-P3-03。

Dependency changes: none；ADR-0012/技术栈已选择React+TypeScript+Ant Design+TanStack Query、npm+`package-lock.json`/`npm ci`、Vite、Vitest+Testing Library与Playwright，但本Task不安装或锁定任何版本；任何lockfile只允许TASK-P3-11在独立授权后修改。

ADR impact: required；已接受`docs/adr/ADR-0012-planning-workspace-command-state-publication.md`，固定command-only/copy-on-write新DRAFT、capability/default-deny、APPROVED-only idempotent internal publication、Export与Publish分离、append-only audit、Frontend组合及P4边界；未关闭OPEN-002/010/015。

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

## Completion evidence

### Activation and immutable range

- 2026-08-24启动时`main=origin/main=7f65f88b620ea1e8d2f4693911be3b52f4052d5d`、ahead/behind=`0/0`且working tree clean；该完整SHA为不可变Diff base。
- TASK-P3-00 closure exact provider为run `32682015727` / required `validate` job `97300206924` / artifact `9504453154`；下载复核20份JSON均PASS，Task/SHA、4 rows、19 checks、issues=`[]`一致。
- 本地pre-commit验收时Git HEAD仍为Diff base；Task report记录`committed_range=0`、`working_tree=43`。最终implementation提交为`3bf99cbafdad983795a83a88646240dbb0b24509`，其provider结果见下方闭环证据。

### Actual scope and outputs

- 实际差异43 paths，全部属于卡片逐字allow-list且outside count=`0`：新增ADR-0012、三份Frontend规范、两份P3 contract；更新37份phase/state/contract/architecture/operations/quality/governance/index/Task文档。
- 页面/路由/read model、Gantt command、approve/reject/publish/export、capability、state、error、audit、idempotency和P3/P4/Production矩阵已形成；ADR-0012 status=`accepted`。
- `docs/**/*.md`由159增至165并全部登记；roots=30、trace rows=30、Test IDs=48、OPEN=15、SIM assumptions=13、risks=13、Tasks=53，registry format version均不变。
- Schema/migration/dependency/Benchmark均为none；schema set保持`2.5.0`，`state-machines.v1`及P2 Schema/error/fixture/benchmark bytes不变。Frontend stack只是selected-not-installed；`frontend/**`、`pyproject.toml`、`uv.lock`无差异。

### Traceability, error and boundary review

- `REQ-006/007/009 + NFR-TRC/ISO/SEC/HUM + ENG-ARCH/ERR/VER → TASK-P3-01 → six new docs/ADR-0012 → TEST-WORKSPACE-CONTRACT-001/TEST-STATE-TRANSITION-001/TEST-ERROR-MAPPING-001`已登记；三个Test ID只承载planned contract matrix/既有preservation检查，不声明P3 behavior formed。
- P3 control error采用planned `workspace-control.v1` namespace；`AUTHORIZATION_DENIED/IDEMPOTENCY_CONFLICT/EXPORT_FAILED`未加入或冒充`error-code-registry.v2`，UNKNOWN仍为NO_SOLUTION_WITHIN_LIMIT且不等于INFEASIBLE。
- OPEN-002/010/015保持OPEN且无closure record；SIM-ASSUMPTION-001～013全部ACTIVE且无新增定量值；RISK-012/013及全部风险继续MONITORED。
- P3-02～15未启动；ExecutionEvent/ReplanRequest/freeze/OBJ-002/ChangeReport/Execution Simulator、真实identity/RBAC/MES target、Production approval/publish/readiness均未形成。

### Local acceptance

- `uv run python scripts/check_docs.py`：exit 0，`PASS repository governance: docs=165 roots=30 trace_rows=30 tests=48 open=15 sim=13 risks=13 tasks=53 task=TASK-P3-01`。
- `uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-01-planning-workspace-contract-and-adr-baseline.md --check-diff --report build/traceability/TASK-P3-01-report.json`：exit 0，43 paths、`IMPACT-DOCS/GOVERNANCE-REGISTRY/PHASE/STATE`、19 checks、0 issues。
- `uv run pytest -q backend/tests/unit/test_check_docs.py backend/tests/contract/test_rule_contracts.py`：exit 0，`27 passed in 0.49s`；只证明治理和既有state/error contracts未漂移。
- `git diff --check`：exit 0；仅Windows工作区LF→CRLF提示，无whitespace error。
- 相对Diff base检查`backend schemas frontend .github pyproject.toml uv.lock`为0 paths；P2 Task/Milestone/audit report/manifest历史范围为0 paths。

### Provider and rollback status

Implementation `3bf99cbafdad983795a83a88646240dbb0b24509`的GitHub push run `32684713630` / required `validate` job/check `97307562801`（GitHub Actions app `15368`）均为`success`，32/32 steps成功。Branch protection精确要求context=`validate`、app_id=`15368`。Artifact `9505303054` / `plantnexus-ci-evidence-32684713630`大小`86023` bytes、digest=`sha256:06cd50a3172e234a9d2227737ecbfa648a4eb3b35cfc2d34c0e1d3bdb597b593`、expiry=`2026-11-22T02:56:31Z`且未过期。

下载复核artifact内20份JSON均可解析且PASS、所有显式issues总数为0、checks无失败；13份携带`code_commit`的历史能力报告均绑定implementation exact SHA，其原始P0/P2 `task_id`作为能力来源历史保留。`ci-current-task-report.json`精确绑定TASK-P3-01、implementation SHA与Diff base，记录43 committed/0 working paths、`IMPACT-DOCS/GOVERNANCE-REGISTRY/PHASE/STATE`、19/19 checks和issues=`[]`。

因此本evidence-only closure将TASK-P3-01标为`done`；closure自身的exact provider只能在push后由交付验收核验，不能在提交内自引用。P3-02仍为`planned`且需要新的用户明确授权、clean synchronized/provider-verified HEAD及新的不可变Diff base；本closure不启动P3-02。

回滚只可移除尚未被consumer使用的新文档candidate并恢复索引；一旦accepted ADR/合同被P3-02+消费，必须用new/superseding ADR/document version修正，不能改写历史。没有业务数据、Schema、DB、dependency或外部side effect需要回滚。
