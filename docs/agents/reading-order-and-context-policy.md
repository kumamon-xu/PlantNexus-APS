---
doc_id: DOC-AGENT-002
title: Agent 读取顺序与上下文策略
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [2]
last_reviewed: 2026-08-19
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

此时完整读取总规、相关 ADR 和追踪矩阵；必要时先创建 ADR/更新 Task，再开始编码。

## 不应加载

与当前 Task 无关的未来 Phase 设计、Historical 数据、未批准方案或大规模日志，不作为默认上下文。P1+ Milestone 只是路线，不是实施授权。

`scripts/check_docs.py` 会自动检查文档结构、注册 ID、Task 引用、逐根 traceability，以及 `--check-diff` 下 `Diff base..HEAD` 与 working tree 并集的 change-impact Rule ID/必审文档覆盖。Agent 必须在 Task 进入 `in_progress` 时先记录完整不可变 `Diff base`。校验器只能验证已经编码的治理规则；Agent 仍须完整读取当前 Task 引用的语义 Contract/Constraint/ADR，并对机器规则未表达的语义影响负责。
