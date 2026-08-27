---
doc_id: DOC-AGENT-003
title: Task 执行协议
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [6, 98, 99, 100, 111]
last_reviewed: 2026-08-27
---

# Task 执行协议

## 验证级别

每张 Task 必须选择一个验证级别。级别只决定执行范围，不降低直接受影响合同的质量要求。

| Profile | 适用范围 | 本地要求 | Provider 要求 |
|---|---|---|---|
| DOCS_ONLY | 仅文档、状态写回、证据索引，无代码/Schema/test/workflow/lock 变化 | links、full docs、Task diff、git diff check | 可使用轻量 docs/evidence gate |
| STANDARD | 局部业务实现，不改变高风险语义 | targeted tests、受影响 static/type、machine report、docs diff | exact SHA 上完整受影响技术栈回归一次 |
| HIGH_RISK | Schema compatibility、PlanningProblem/Constraint/Solver/Validator、状态机、migration、security、publication、dependency | targeted + full relevant suite、负例、回滚、必要 Benchmark/migration replay | non-skippable full required gate 与 artifact |
| PHASE_GATE | Vertical Gate、Exit Audit、Production readiness | fresh independent replay | exact provider + independent evidence manifest |

Frontend-only Task 不因仓库存在 Solver 而运行 Solver Benchmark；Backend-only低风险 Task 不因历史存在浏览器测试而在本地重复三轮 Chromium。跨栈 Contract 或 Phase Gate 明确要求时除外。

Provider 列指项目已配置的远程 Provider。治理基线明确为 local-only Git 时，使用绑定不可变 commit 的本地 machine manifest，不要求伪造远程 run/job/artifact；Provider 模式不得由普通业务 Task 临时降级。

## Before

1. 确认 Task 属于 current phase 且获得所需授权；
2. 记录完整 40 字符 Diff base；
3. 核验直接依赖 compact manifest，不递归重放完整历史；
4. 确认 Requirement/NFR/ENG、输入、allowed/forbidden scope；
5. 完整读取直接 Contract、Constraint、ADR；
6. 选择 Validation profile；
7. 从 change-impact matrix 选择最小语义所有者文档；
8. 明确错误、负向路径、回滚、Benchmark 和 excluded scope。

## During

- 先更新 Schema/Contract，再实现 consumer；
- 以最小有界变更完成目标；
- 新业务未知登记 PROD_OPEN；
- Simulation 数值登记 SIM_ASSUMPTION；
- 架构或语义改变先处理 ADR；
- 不修改测试期望掩盖实现缺陷；
- 新路径或新语义超出 scope 时先修订 Task；
- 不为了生成更多文档而复制相同状态、run、digest 或测试数字。

## Before implementation submission

所有 Profile 都必须：

- 运行目标测试及直接负向路径；
- 生成 Task machine report；
- 运行 full docs 和 Task diff governance；
- 运行 git diff check；
- 验证 forbidden scope。

STANDARD 及以上还必须运行直接受影响技术栈的静态检查和集成回归。HIGH_RISK 按 Task 风险运行完整相关 suite、Benchmark、migration、安全或浏览器回归。

本地已经完成的全量回归不需要在同一个 working tree 中无理由重复；代码、配置、依赖或环境变化后必须重跑受影响部分。

## Provider 与 closure

Implementation SHA 是业务证据主体。Provider artifact 至少绑定：

- Task ID、Diff base 和 exact code commit；
- Validation profile；
- required job conclusion；
- machine report、Task diff report；
- blocking issues。

Provider 已验证后，closure 只允许写回证据和状态。若 closure diff 仅包含 Task/Phase/Milestone/registry/evidence 文档，并且机器检查证明产品代码、Schema、test、workflow、dependency、migration、fixture/baseline 未变化，可运行轻量 closure gate。

若 closure 包含任何实现或测试语义变化，必须作为新的 implementation/corrective SHA 重新执行对应完整 Profile。失败 run 保留，不得用 rerun 或文档描述覆盖。

## Completion evidence

Task Card 只记录：

- 最终 implementation/closure SHA；
- Validation profile 与总体结论；
- machine report 和 Provider manifest 路径；
- 实际修改的语义文档；
- traceability/OPEN/SIM/ADR 变化；
- 未关闭问题与 rollback。

changed path 全表、每条命令 stdout、全部 artifact digest 和历史失败细节保存在机器报告、Provider manifest 或专用审计文档，不复制到 Current Phase、Task Index、README 和多个 registry。

没有文档变化时，记录 Documentation impact: none、命中的 Impact Rule 和简短理由即可；不要求逐份解释未修改候选文档。

## Phase

Task Done 不等于 Milestone Done。Phase Gate 必须独立执行；未获得用户阶段转换确认时不得进入下一 Phase。
