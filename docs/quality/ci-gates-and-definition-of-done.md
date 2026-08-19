---
doc_id: DOC-QUAL-006
title: CI Gate 与 Definition of Done
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [58, 72, 74, 76, 78, 80, 89, 100, 101]
last_reviewed: 2026-08-19
---

# CI Gate 与 Definition of Done

## 常规验收命令目标

Backend：Ruff、type check、unit/contract/integration tests。Frontend：test 和 production build。P2 后增加 golden/simulation；涉及 Solver 的任务增加 PR Benchmark。

具体命令以仓库脚本和 lockfile 落地为准；在这些文件不存在前不宣称已运行。

文档/traceability 本地检查由 `scripts/check_docs.py` 实现，合同见 `documentation-consistency-checks.md`。Task 进入 `in_progress` 时记录完整 `Diff base`；acceptance 至少运行全仓检查、带 `--check-diff` 的当前 Task 基线范围检查和 `TEST-TRACEABILITY-VALIDATOR`，并确认提交前后均可复验。把它接入 PR/Release CI 属于 TASK-P0-08。

P0-07 增加可本地复验的 fixture Validator gate：

```text
uv run python -m app.planning.validation.mutation_check --root . --report build/validation/TASK-P0-07-validator-mutations.json
```

该 gate 必须同时得到 positive PASS、13 negative FAIL、C-001～C-011/required mutation 无缺口、exact v2 report/error、deterministic replay 和无 backend/OR-Tools 依赖；它尚未接入 CI，仍由 TASK-P0-08 负责自动化。

## Task Done

任务完成至少满足：

- Task Card 的目标、允许范围和明确排除项均遵守；
- Requirement/NFR/ENG 追踪已更新；
- Schema/Contract/ADR 影响已处理；
- Task Card 已填写文档影响、明确文档路径和追踪更新；
- change-impact matrix 要求的文档均已更新，或存在经审查的 `Documentation impact: none` 理由；
- 成功、错误、边界和回滚行为有测试证据；
- 没有新增未登记 PROD_OPEN/SIM_ASSUMPTION；
- 文档与实现一致；
- 文档一致性检查通过；
- 验收命令实际通过并记录结果。

## Phase Done

只有对应 Milestone 的全部 Exit Gate 有真实 Artifact 证明时才能更新 `current_phase.md`。任务全部关闭不自动等于 Phase 通过，未经确认不得进入下一阶段。
