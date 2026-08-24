---
doc_id: TASK-P3-00
title: P3 Phase Transition and Task Planning Governance
status: done
spec_version: 0.3.0
phase: P3
normative: true
source_sections: [33, 34, 65, 66, 67, 68, 69, 77, 78, 94, 97, 98, 99, 100, 101, 110, 111]
last_reviewed: 2026-08-24
---

# TASK-P3-00 — P3 Phase Transition and Task Planning Governance

Task batch role: phase-planning-owner

Requirement IDs: REQ-004, REQ-005, REQ-006, REQ-007, REQ-009

NFR / ENG IDs: NFR-COR-001, NFR-DET-001, NFR-TRC-001, NFR-ISO-001, NFR-REL-001, NFR-SEC-001, NFR-OBS-001, NFR-PER-001, NFR-HUM-001, ENG-ARCH-001, ENG-VAL-001, ENG-ERR-001, ENG-VER-001, ENG-LOG-001

Depends on: TASK-P2-14

Start gate: 用户已明确批准P2→P3；TASK-P2-00～14全部`done`；P2 Exit report/manifest均为`READY`且`blocking_gaps=[]`；P2-14 audit implementation `65c556789f176ad9de55523d6420737bb60f933f`及evidence-only closure `80c403384d1e171258cf874d26605d0d22aff1b2`为连续祖先提交，其required `validate`与artifact均精确成功；启动时`main=origin/main=80c403384d1e171258cf874d26605d0d22aff1b2`且working tree clean。

Goal: 仅关闭P2 Milestone、激活P3 Milestone、建立完整P3 Task依赖计划并同步治理注册表；不实现任何P3业务、Schema、迁移、依赖、测试断言或workflow。

Non-goals: 不执行TASK-P3-01～15，不创建P3 Schema/DB/API/UI/状态行为，不修改P2实现或历史证据，不进入P4，不形成Production readiness/approval/publish。

Inputs: P2 Exit report/manifest、P2-14 implementation/closure provider artifacts、P3 Milestone、总规§33～35/65～69/77～78/94/97～106、架构/合同/状态/质量/治理基线及用户本次授权。

Diff base: 80c403384d1e171258cf874d26605d0d22aff1b2

Files allowed to change: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/P3-planning-workspace.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/tasks/P3/TASK-P3-00-phase-transition-and-task-planning-governance.md`、`docs/tasks/P3/TASK-P3-01-planning-workspace-contract-and-adr-baseline.md`、`docs/tasks/P3/TASK-P3-02-schedule-version-workspace-and-export-schemas.md`、`docs/tasks/P3/TASK-P3-03-schedule-version-audit-and-export-persistence.md`、`docs/tasks/P3/TASK-P3-04-validated-solution-to-reviewable-schedule-version.md`、`docs/tasks/P3/TASK-P3-05-planning-workspace-read-models-and-comparison.md`、`docs/tasks/P3/TASK-P3-06-gantt-edit-and-lock-command-pipeline.md`、`docs/tasks/P3/TASK-P3-07-approval-rejection-and-audit-service.md`、`docs/tasks/P3/TASK-P3-08-idempotent-publication-and-supersession.md`、`docs/tasks/P3/TASK-P3-09-export-job-and-standard-package.md`、`docs/tasks/P3/TASK-P3-10-planning-workspace-http-api.md`、`docs/tasks/P3/TASK-P3-11-frontend-foundation-and-read-only-workspace.md`、`docs/tasks/P3/TASK-P3-12-gantt-resource-load-and-version-comparison-ui.md`、`docs/tasks/P3/TASK-P3-13-human-control-actions-and-ui-e2e.md`、`docs/tasks/P3/TASK-P3-14-p3-vertical-slice-gate-evidence.md`、`docs/tasks/P3/TASK-P3-15-p3-exit-gate-audit.md`，以及`Documents to update`中的明确文档和ignored `build/traceability/TASK-P3-00-report.json`。

Files forbidden to change: `backend/app/**`、`backend/tests/**`、`schemas/**`、`backend/migrations/**`、`fixtures/**`、`benchmarks/**`、`frontend/**`、`infra/**`、`scripts/**`、`.github/workflows/**`、`pyproject.toml`、`uv.lock`、P2 audit report/manifest及其他P0～P2历史Task卡、任何P4+详细Task或Production/发布凭证。

Implementation steps: 复核P2状态/提交/provider内容；把P2置为completed并激活P3；按合同→Schema→持久化→状态服务→读取/编辑→审批/发布/导出→API→Frontend→Vertical Gate→Exit Audit拆分P3-01～15；同步Requirement/NFR/ENG/Test/OPEN/SIM/RISK/Impact/Inventory/trace；运行本地验收；提交并push；核验exact provider artifact；以evidence-only closure关闭本Task。

Outputs: active P3治理基线、16张P3 Task卡、明确依赖图与启动门、更新后的追踪/测试/风险/清单，以及exact provider证据。

Documentation impact: required

Documents to update: `README.md`、`docs/README.md`、`docs/current_phase.md`、`docs/milestones/README.md`、`docs/milestones/P2-cp-sat-vertical-slice.md`、`docs/milestones/P3-planning-workspace.md`、`docs/tasks/README.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/contracts/README.md`、`docs/contracts/schema-index.md`、`docs/contracts/schema-versioning.md`、`docs/contracts/planning-solution-and-schedule-version.md`、`docs/contracts/export-package.md`、`docs/core/capability-matrix.md`、`docs/architecture/end-to-end-planning-flow.md`、`docs/architecture/module-boundaries.md`、`docs/architecture/data-authority.md`、`docs/architecture/provenance-and-versioning.md`、`docs/architecture/configuration-environments-and-isolation.md`、`docs/architecture/technology-stack.md`、`docs/architecture/repository-layout.md`、`docs/domain/domain-model.md`、`docs/domain/error-model.md`、`docs/domain/execution-facts-locks-and-replan.md`、`docs/domain/state-machines/planning-run.md`、`docs/domain/state-machines/schedule-version.md`、`docs/domain/state-machines/export-job.md`、`docs/frontend/README.md`、`docs/planning/replanning.md`、`docs/planning/schedule-validator.md`、`docs/operations/README.md`、`docs/operations/security.md`、`docs/operations/observability-and-audit.md`、`docs/operations/worker-reliability-and-idempotency.md`、`docs/quality/test-strategy-and-matrix.md`、`docs/quality/ci-gates-and-definition-of-done.md`、`docs/quality/documentation-consistency-checks.md`、`docs/governance/document-control.md`、`docs/governance/requirements-register.md`、`docs/governance/nfr-and-engineering-register.md`、`docs/governance/traceability-rules.md`、`docs/governance/traceability-matrix.md`、`docs/governance/prod-open-register.md`、`docs/governance/sim-assumption-register.md`、`docs/governance/risk-register.md`、`docs/governance/change-impact-matrix.md`、`docs/governance/document-inventory.md`、`docs/adr/README.md`及Files allowed to change中逐字列出的16张P3 Task卡。

Documentation impact rationale: current phase、两个Milestone、当前阶段详细Task集合、状态/发布规划、Test ID分配、风险与跨文档追踪同时变化；历史P2证据只追加transition说明，不改写原结论或失败记录。

Change-impact matrix rows reviewed: `IMPACT-STATE`、`IMPACT-PHASE`、`IMPACT-GOVERNANCE-REGISTRY`、`IMPACT-DOCS`

Traceability updates: P2 READY/用户授权→TASK-P3-00；REQ-004/005/006/007/009与相关NFR/ENG→TASK-P3-01～15→新旧planned Test IDs→未来machine/provider artifacts；根ID继续`ALLOCATED`，本Task不形成P3业务evidence。

Schema changes: none；schema set保持`2.5.0`，P3 Schema只分配给TASK-P3-02。

Migration: none；持久化与可逆migration只分配给TASK-P3-03。

Dependency changes: none；Python和Frontend依赖、lock与CI setup均保持不变，Frontend首次落地只允许TASK-P3-11按P3-01决定执行。

ADR impact: none for this governance-only transition；TASK-P3-01负责在任何P3合同/代码前形成command/state/authorization/publication架构决定，不在本Task预先接受技术实现。

State-machine impact: 只把既有PlanningRun/ScheduleVersion/ExportJob语义分配到未来P3 Task；不修改state-machines.v1、状态集合、allowed pair、guard、持久化或迁移，也不把规划文字写成已实现行为。

Error behavior: 任一P2状态、HEAD、祖先、required check或artifact内容不一致即停止且不切Phase；规划batch owner/member不唯一、成员预填实现SHA或出现P4详细卡时治理检查必须失败。

Tests: 仅运行既有TEST-PHASE-GOVERNANCE-001与TEST-TRACEABILITY-VALIDATOR回归；登记12个P3 planned Test ID，不修改测试代码或断言，也不得写成formed。

Benchmark impact: none；只要求后续P3 Gate保持P2 XS/S/M回归，不新建性能baseline或Production SLA。

Simulation scenarios: none；P3未来验收优先复用versioned P2 synthetic evidence，任何新增定量场景须在对应Task另行登记。

Acceptance commands: `uv sync --locked`；`uv run ruff check .`；`uv run pyright backend/app backend/tests`；`uv run pytest -q backend/tests/unit/test_check_docs.py backend/tests/integration/test_ci_contract.py`；`uv run python scripts/check_docs.py`；`uv run python scripts/check_docs.py --task docs/tasks/P3/TASK-P3-00-phase-transition-and-task-planning-governance.md --check-diff --report build/traceability/TASK-P3-00-report.json`；`git diff --check`；`git diff --exit-code 80c403384d1e171258cf874d26605d0d22aff1b2 -- backend schemas frontend infra scripts .github pyproject.toml uv.lock fixtures benchmarks`。

Artifacts: `traceability-report.v1`、P2 prerequisite verification record、P3 task allocation/registry counts、GitHub exact run/job/artifact/required-check evidence。

Provider evidence: GitHub repository/branch/workflow固定为`kumamon-xu/PlantNexus-APS`/`main`/`.github/workflows/ci.yml`；implementation与evidence-only closure各自必须有exact push run、successful required `validate`、app ID、完整steps、未过期artifact及Task report的exact SHA/Impact rows/checks/issues核验。

Completion conditions: P2证据一致且P2=`completed`、P3=`active`；P3-01～15均为规模适中、依赖/启动门/Diff base/scope/Schema/migration/dependency/ADR/state/test/CI/docs/completion/failure/rollback完整的`planned`成员，P3-15最后；full/diff治理、禁止范围与provider双提交均PASS；无P3实现、P4 Task或Production声明。

Failure handling: 任一本地治理、禁止范围、push、required check或artifact核验失败时停止并保留失败证据；不关闭TASK-P3-00、不启动P3-01，不以文档声明覆盖provider事实。若phase前提被推翻，追加有界更正并恢复一致治理状态，禁止改写P2历史或force-push。

Explicitly excluded: TASK-P3-01或后续实现、Schema/migration/dependency/test/workflow变更、API/Frontend/状态/审批/发布/导出执行、P4 Dynamic Replanning、Production readiness/approval/publish。

PROD_OPEN: OPEN-001～015全部保持OPEN；尤其OPEN-002与OPEN-010继续阻止真实外部接口和Production角色/授权结论。

SIM_ASSUMPTIONS: SIM-ASSUMPTION-001～013全部保持ACTIVE；本Task不新增定量假设，不用synthetic证据关闭PROD_OPEN。

Rollback: push前整体回退本Task文档变更并保持P2 active；push后如发现事实错误只追加有界更正/superseding治理提交，保留P2 audit、失败run与provider artifacts，禁止reset/force-push改写历史。

## Completion evidence

启动前确认TASK-P2-00～14全部`done`，P2 report/manifest均为`READY`且`blocking_gaps=[]`；13组前序implementation/closure及P2-14 `c6e5756 → 65c5567 → 80c4033`拓扑、required checks/artifacts均一致。`main=origin/main=80c403384d1e171258cf874d26605d0d22aff1b2`且working tree clean，因此phase transition前提成立。

本地验收：locked sync成功；Ruff与Pyright为0问题；governance unit/CI contract=`35 passed`；full docs为159 docs、30 roots/trace rows、48 Test IDs、15 OPEN、13 SIM assumptions、13 risks、53 Tasks；current Task diff为64 paths、4 Impact rows、19 checks、0 issues；`git diff --check`与相对Diff base的业务代码/Schema/frontend/infra/scripts/workflow/dependency/fixture/benchmark禁止范围均PASS。

Planning implementation `1d4b1a5c0ad6dc13df18588fbdcb9732e5ef15e7`的GitHub push run `32681493976` / required `validate` job `97298850740`（app `15368`）均success，32/32 steps成功。Artifact `9504310381` / `plantnexus-ci-evidence-32681493976`大小`86292` bytes、digest=`sha256:306ccfc7fedef1541c36bcc4afb0727239bd3fb9a17dd4b7ea022fd7c3d4fe64`、expiry=`2026-11-22T01:58:21Z`且未过期；下载的20份JSON全部可解析并PASS。Task report精确绑定implementation SHA/Diff base，记录64 committed/0 working paths、`IMPACT-DOCS/GOVERNANCE-REGISTRY/PHASE/STATE`、19/19 checks与0 issues。

因此本evidence-only closure将TASK-P3-00标为`done`；closure自身的exact provider只能在push后由交付验收核验，不能在提交内自引用。TASK-P3-01仍为`planned`且未获执行授权，P4/Production仍未进入。
