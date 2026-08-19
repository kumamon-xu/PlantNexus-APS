---
doc_id: DOC-AGENT-004
title: Agent 角色与模块边界
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [12, 13, 30, 41, 51, 69]
last_reviewed: 2026-08-19
---

# Agent 角色与模块边界

本项目不依靠“角色人格”决定真相，角色只限定责任与审查视角。

| 视角 | 主要责任 | 必须避免 |
|---|---|---|
| Architecture | 模块依赖、ADR、环境边界 | 越过业务权威决定参数 |
| Data/Contract | Import、Schema、Snapshot、Problem | 把 ORM/API/Solver 类型混入合同 |
| Planning/Solver | Strategy、Backend、目标、诊断 | 在 domain/UI 建模或修改 Validator 迎合结果 |
| Validator/Quality | 独立规则、Mutation、Golden、Property | 复用 CP-SAT constraint builder |
| Simulation/Benchmark | Profile、Scenario、Generator、replay | 绕过正式入口或宣称生产容量 |
| Frontend/Workspace | 命令、显示、审批体验 | 复制 Solver 逻辑、直接更新 published plan |
| Release/Operations | idempotency、audit、provenance、runbook | 把未验证结果发布或隐藏失败 |

一个 Task 可以跨多个视角，但允许修改文件必须显式列出，并为高风险边界安排独立审查。
