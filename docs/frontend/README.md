---
doc_id: DOC-FRONTEND-INDEX
title: Frontend 文档形成计划
status: baseline
spec_version: 0.3.0
phase: P3
normative: false
source_sections: [68, 69, 77, 78]
last_reviewed: 2026-08-24
---

# Frontend 文档形成计划

TASK-P3-01已在任何Frontend dependency或实现前形成：

- `planning-workspace.md`：Data Health、Runs、Orders、Resources、Gantt、Diagnostics、Approval、Publication 等信息架构；
- `gantt-command-contract.md`：拖拽命令、服务端验证、新 Draft 和 Validator 流程；
- `approval-publication-flow.md`：capability、状态门、幂等发布/导出和审计。

已确定的不变量：React 不复制 Solver Logic；Gantt 不直接更新 PUBLISHED schedule；开发环境额外页面不进入生产入口。审批角色受 OPEN-010 阻塞。

## P3 formation plan

TASK-P3-01已形成Planning Workspace、Gantt command与approval/publication三份详细规范以及页面/API/permission矩阵，并由[ADR-0012](../adr/ADR-0012-planning-workspace-command-state-publication.md)接受server authority、copy-on-write new DRAFT和Frontend组合。TASK-P3-11才可建立exact-pinned React/TypeScript/Ant Design/TanStack Query/npm/Vite/Vitest/Playwright foundation和read-only workspace；P3-12实现read-only visualization/comparison，P3-13最后接入edit/lock/approve/reject/publish/export并执行browser E2E。UI只发送server command、显示权威状态/错误，不计算排程、绕过Validator或提供PUBLISHED update；`frontend/**`当前仍未实现。

页面规范形成不等于API payload Schema、OpenAPI、组件、bundle、dependency lock、accessibility/E2E或Production UI已经形成。所有行为证据继续由P3-02/05/10～15按序负责；OPEN-010未关闭前Production action default-deny。

## TASK-P3-05 backend read availability

14个Planning Workspace read model的application结果已形成，包含stable carrier reference、完整payload page、lineage/freshness、found-empty/missing和opaque cursor语义；Version Comparison保持P3 DTO。`frontend/**`仍为零差异，当前没有React组件、route、virtualization、loading/error UI或browser evidence；P3-11/12只能经P3-10 HTTP适配消费这些server authority结果。
