---
doc_id: DOC-FRONTEND-INDEX
title: Frontend 文档形成计划
status: planned
spec_version: 0.3.0
phase: P3
normative: false
source_sections: [68, 69, 77, 78]
last_reviewed: 2026-08-24
---

# Frontend 文档形成计划

P3 前不编造页面 payload、权限和交互细节。实现前应形成：

- `planning-workspace.md`：Data Health、Runs、Orders、Resources、Gantt、Diagnostics、Approval、Publication 等信息架构；
- `gantt-command-contract.md`：拖拽命令、服务端验证、新 Draft 和 Validator 流程；
- `approval-publication-flow.md`：角色、状态门、幂等发布和审计。

已确定的不变量：React 不复制 Solver Logic；Gantt 不直接更新 PUBLISHED schedule；开发环境额外页面不进入生产入口。审批角色受 OPEN-010 阻塞。

## P3 formation plan

TASK-P3-01须先形成Planning Workspace、Gantt command与approval/publication三份详细规范以及页面/API/permission矩阵。TASK-P3-11才可建立exact-pinned frontend foundation和read-only Order/Gantt/Load/version shell；P3-12实现read-only visualization/comparison，P3-13最后接入edit/lock/approve/reject/publish/export并执行browser E2E。UI只发送server command、显示权威状态/错误，不计算排程、绕过Validator或提供PUBLISHED edit；当前frontend仍未实现。
