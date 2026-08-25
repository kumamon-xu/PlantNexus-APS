---
doc_id: DOC-FRONTEND-INDEX
title: Frontend 文档形成计划
status: baseline
spec_version: 0.3.0
phase: P3
normative: false
source_sections: [68, 69, 77, 78]
last_reviewed: 2026-08-25
---

# Frontend 文档形成计划

TASK-P3-01已在任何Frontend dependency或实现前形成：

- `planning-workspace.md`：Data Health、Runs、Orders、Resources、Gantt、Diagnostics、Approval、Publication 等信息架构；
- `gantt-command-contract.md`：拖拽命令、服务端验证、新 Draft 和 Validator 流程；
- `approval-publication-flow.md`：capability、状态门、幂等发布/导出和审计。

已确定的不变量：React 不复制 Solver Logic；Gantt 不直接更新 PUBLISHED schedule；开发环境额外页面不进入生产入口。审批角色受 OPEN-010 阻塞。

## P3 formation plan

TASK-P3-01已形成Planning Workspace、Gantt command与approval/publication三份详细规范以及页面/API/permission矩阵，并由[ADR-0012](../adr/ADR-0012-planning-workspace-command-state-publication.md)接受server authority、copy-on-write new DRAFT和Frontend组合。P3-01当时没有创建`frontend/**`；TASK-P3-11现建立exact-pinned React/TypeScript/Ant Design/TanStack Query/npm/Vite/Vitest/Playwright foundation和read-only workspace，P3-12才可实现read-only visualization/comparison，P3-13最后接入edit/lock/approve/reject/publish/export并执行browser E2E。UI只发送server command、显示权威状态/错误，不计算排程、绕过Validator或提供PUBLISHED update。

页面规范形成不等于API payload Schema、OpenAPI、组件、bundle、dependency lock、accessibility/E2E或Production UI已经形成。所有行为证据继续由P3-02/05/10～15按序负责；OPEN-010未关闭前Production action default-deny。

## TASK-P3-05 backend read availability

14个Planning Workspace read model的application结果已形成，包含stable carrier reference、完整payload page、lineage/freshness、found-empty/missing和opaque cursor语义；Version Comparison保持P3 DTO。P3-05交接时`frontend/**`仍为零差异；P3-11现只能经P3-10 HTTP适配消费其中获授权的read-only subset，P3-12仍负责Gantt/load/comparison。

## TASK-P3-11 completed read-only boundary

TASK-P3-11已于2026-08-25获明确授权并从不可变Diff base `26dd519b1f1f84e08d415cfdfce43f286fa82988`完成locked foundation与read-only workspace。Gantt、Resource Load、Version Comparison和全部edit/lock/approve/reject/publish/export control仍分别归P3-12/13，均未自动启动。

Node/npm/direct pins、lockfile v3、SCA/license命令以Task卡逐字清单为准。特别地，用户批准的typescript-eslint门禁是固定三元组`typescript-eslint=8.68.0`、`eslint=10.9.1`、`typescript=6.0.3`，而不是latest range；TypeScript必须满足`>=4.8.4 <6.1.0`，CI拒绝range、drift、peer conflict和未审查升级。

Implementation `567e8693db881ea3dfffa011de9021fef9641361`已形成13条read-only route、GET-only canonical query client、default no-token session、strict carrier/reference检查、exact Version precondition、raw UTC/lineage/fingerprint authority、seven-state UI、virtual table和25个Vitest/component/contract/accessibility tests；npm v3 lock来自npm `11.17.0`。Artifact `9552386549`精确复验Frontend 9/9、SCA 0 advisory、336 package license/0 issue及只读阶段边界，故Task=`done`。

## TASK-P3-12 local visualization boundary

TASK-P3-12已从不可变Diff base `3bca1cc10ebedc4d47227bafb2f3f66854ccb526`进入`in_progress`，在不增加dependency或改lock的前提下形成factory/workshop/machine Gantt、Resource Load和two-Version comparison。现有route inventory为18条；Gantt按server UTC/tick/duration定位并做vertical windowing，完整table fallback保留所有operation，load/utilization与comparison change/KPI/summary均逐字显示server事实。

Local 37项Vitest、4项read-only Chromium及12/12 machine已通过；client还把response query fingerprint/correlation/authoritative Version与outbound request及compared Version逐字绑定。`VERSIONED_SYNTHETIC_UI_120@1.0.0`只观察120 total/最多24 mounted rows，不是Production规模或SLA。Client仍无command/action carrier、无token persistence、无Solver/Validator/KPI/Resource Load/delta authority；P3-13 actions、P4与Production均未启动，exact provider形成前Task保持`in_progress`。
