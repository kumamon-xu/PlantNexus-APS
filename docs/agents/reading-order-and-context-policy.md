---
doc_id: DOC-AGENT-002
title: Agent 读取顺序与上下文策略
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [2]
last_reviewed: 2026-08-27
---

# Agent 读取顺序与上下文策略

## 默认最小上下文

```text
/AGENTS.md（薄入口）
→ docs/agents/AGENTS.md（规则正文）
→ Current Phase
→ Current Task
→ Referenced Contracts/Constraints/ADRs
→ Code
→ Tests
```

目的不是减少理解，而是避免每个任务机械加载整份总规后遗漏当前任务边界。

根 `README.md` 是已落地命令和仓库地图的操作入口，只能在 Task 边界与引用规范已经确认后作为辅助上下文读取，不能覆盖规范正文。

## 必须扩大上下文的情况

- spec version 变化；
- 发现 Contract 互相冲突；
- 任务需要改变模块依赖方向；
- 修改 PlanningProblem/SolverBackend/Validator/Constraint/Objective；
- 修改 PlanningRun/ScheduleVersion/ExportJob；
- 修改 publication、performance gate 或 production boundary。
- 修改P3 locale、用户可见业务/错误文案、时间/单位格式或双语human-control surface。

TASK-P3-16已形成并由exact implementation provider复验的`src/i18n`、双语Vitest/Playwright与`p3-frontend-i18n-report.v1`必须作为上述扩大上下文的一部分读取；本closure provider仍须核验，也不授权TASK-P3-17。

此时完整读取总规、相关 ADR 和追踪矩阵；必要时先创建 ADR/更新 Task，再开始编码。

P3本地化还必须读取`../frontend/official-zh-cn-terminology-map.md`、Frontend规范、Planning Workspace API/error合同及ScheduleVersion/ExportJob状态机。术语文档是展示语义规范而非wire contract；未知机器值必须保留raw并fail visibly。

## 不应加载

与当前 Task 无关的未来 Phase 设计、Historical 数据、未批准方案或大规模日志，不作为默认上下文。P1+ Milestone 只是路线，不是实施授权。

`scripts/check_docs.py` 会从 `docs/current_phase.md` 读取当前 `Pn`，保留 prior-phase terminal Task、允许 current-phase详细卡并拒绝 future-phase详细卡；同时检查文档结构、注册 ID、Task 引用、逐根 traceability，以及 `--check-diff` 下 `Diff base..HEAD` 与 working tree并集的 change-impact Rule ID/必审文档覆盖。Agent 必须在 Task进入 `in_progress` 时先记录完整不可变 `Diff base`。P1及以后卡还必须有 `Completion conditions`。

CI 的 `--discover-task-from <event-base-sha>`只从一次 event range选择唯一 current-phase Task Card，随后仍以卡片 `Diff base`审计真实 Task范围；零个/多个/非 current Task均不得猜测。校验器只能验证已经编码的治理规则；Agent仍须完整读取当前 Task引用的语义 Contract/Constraint/ADR，并对机器规则未表达的语义影响负责。

阶段计划形成后如需改号、增卡或重命名，必须先有独立治理Task和用户明确授权。合法修订range只允许唯一`phase-plan-amendment-owner`；成员保持`planned/ready`且无implementation SHA，稳定Task ID用于识别rename，base中active/done成员与删除历史均不可改写。该owner只归属规划diff，不授权自动执行任何成员。
