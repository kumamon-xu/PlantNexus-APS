---
doc_id: DOC-AGENT-005
title: Agent 审查清单
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [90, 97, 100, 111]
last_reviewed: 2026-08-19
---

# Agent 审查清单

## 任意功能

- 对应哪个 REQ/NFR/ENG？
- 输入权威从哪里来？
- Production 与 Simulation 如何区分？
- PlanningProblem 如何表达？
- SolverBackend 如何实现？
- Validator 如何独立验证？
- 正/反 Fixture 和 Scenario 是什么？
- 性能如何变化？
- 是否新增 PROD_OPEN/SIM_ASSUMPTION？
- 是否需要 ADR？
- 哪些文档必须更新？路径是否明确？
- 哪些追踪矩阵行、Requirement、Test 或 Artifact 关系会变化？
- 如果声明无文档影响，理由能否由 change-impact matrix 支持？

任何无法回答的问题都不能进入生产代码。

## Solver 变更

检查 C-ID、Objective phase、status semantics、Validator、Golden/Mutation/Property、Benchmark、exact version 和 rollback。

## Schema 变更

检查 version、migration、compatibility、contract test、fixture、hash/replay、producer/consumer 和 export。

## Release

检查 approved-only publish、immutability、idempotency、manifest/provenance、security、monitoring、backup/restore、UAT 和 PROD_OPEN closure。
