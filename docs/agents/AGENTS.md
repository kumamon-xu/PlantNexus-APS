---
doc_id: DOC-AGENT-001
title: PlantNexus APS Coding Agent 规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [1, 2, 6, 12, 30, 59, 90, 98, 99, 100, 110, 111]
last_reviewed: 2026-08-19
---

# PlantNexus APS Coding Agent 规则

根目录 `AGENTS.md` 仅为自动发现入口；本文件是 Agent 规则正文。根入口不得复制或另行解释本文件的规范，避免出现两套规则。

## 开始任务

按顺序读取：

1. 本文件；
2. `../current_phase.md`；
3. 当前 Task Card；
4. Task 引用的 Schema/Contract、Constraint 和 ADR；
5. 相关代码和测试。

完成上述规范读取后，可以读取根 `README.md` 获取已落地的构建与本地检查命令；`README.md` 不高于 Task Card 或规范正文。

规格版本变化，或修改架构边界、PlanningProblem、SolverBackend、Constraint Catalog、状态机、发布规则或阶段 Exit Gate 时，完整重读 `../core/APS_IMPLEMENTATION_SPEC.md`。

## 执行边界

- 只修改 Task Card 的 `Files allowed to change`。
- 需要额外文件时停止，说明原因并先修订 Task Card。
- Task Card 必须显式填写 `Documentation impact`、`Documents to update` 和 `Traceability updates`；缺少任一字段不得开始实施。
- `Documents to update` 中的文件必须同时出现在 `Files allowed to change`，否则先修订任务卡。
- 不得提前实施当前 Phase 以后的能力。
- 不得把 SIM_ASSUMPTION 写入 Production Business Policy。
- 不得猜生产数据、班次、冻结窗口、运输时间、标准工时、库存、资源能力或目标权重。
- 不得删除硬约束、修改断言、静默忽略能力或把 Hint 当约束。

## 模块边界

- CP-SAT 逻辑只进入 `planning/backends/cp_sat/`。
- Domain、API Controller、React、ORM 不出现 CP-SAT 建模。
- Validator 不导入或复用 CpSatBackend 约束实现。
- Simulation 必须走 Standard Import → Snapshot → Problem → same Solver/Validator。

## 状态与措辞

- FEASIBLE 不称为最优；UNKNOWN 不称为无解。
- Synthetic Benchmark 不称为生产容量。
- Assumption conflict subset 不称为 minimal conflict set，除非有证明。
- 未支持能力返回 `UNSUPPORTED_CAPABILITY`。

## 完成任务

运行 Task 的 Acceptance Commands，记录真实结果；更新 traceability、开放问题、假设、文档和 artifacts。不能运行的命令必须明确说明原因，不得写成 PASS。

每个完成报告必须列出：

- 实际更新的文档；
- 实际更新的追踪关系；
- 若 `Documentation impact: none`，给出依据和审查结果；
- 与 `governance/change-impact-matrix.md` 的匹配结果。

代码、Schema、Constraint、状态机、Solver、Validator、Simulation、API 或发布行为发生变化，而完成报告没有文档影响结论时，Task 不得标记 Done。

未经阶段 Gate 和用户确认，不更新到下一 Phase。

当前仓库治理检查入口：

```text
uv run python scripts/check_docs.py
```

当前 Task 还必须运行：

```text
uv run python scripts/check_docs.py --task <task-card> --check-diff --report <report-path>
```

校验器检查 ID、Task 依赖、traceability 和实际 Git diff/change-impact 声明，但不代替业务 Contract、Schema、Solver/Validator correctness、Scenario 或 Phase Gate 验收。
