---
doc_id: DOC-AGENT-005
title: Agent 审查清单
status: living
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [90, 97, 100, 111]
last_reviewed: 2026-08-27
---

# Agent 审查清单

只运行与 Task 类型匹配的清单。未命中的专项清单不要求调查或逐项填写 N/A。

## 所有 Task

- 目标、Requirement/NFR/ENG 和直接输入是否明确？
- authority、Production/Simulation 和 unsupported 边界是否明确？
- allowed/forbidden scope、错误行为和 rollback 是否明确？
- 直接 Contract/ADR 与实现是否一致？
- targeted positive/negative evidence 是否充分？
- 文档、traceability、OPEN/SIM 是否只更新真实变化？
- Validation profile 是否与风险匹配？

## Schema / Contract

检查 version、compatibility、migration、producer/consumer、canonical bytes/hash、positive/negative/round-trip 和旧版本保留。

## Planning / Solver / Constraint

检查 Problem/Policy、C-ID/OBJ、status semantics、int/tick边界、独立 Validator、Golden/Mutation/Property、Benchmark、exact dependency 和 rollback。

## Validator / Diagnostics

检查与 Backend 隔离、每个目标 C-ID、mutation construction 与判断公式分离、错误映射、deterministic replay 和 fail-closed。

## State / Persistence / Publication

检查允许与拒绝 transition、CAS/transaction、immutability、idempotency、audit、concurrency、migration、approved-only publish 和 partial failure。

## Import / Snapshot / Simulation

检查 authority、Standard Import common path、determinism、version/seed/hash、data plane isolation、unsupported capability 和 Production default-deny。

## Frontend / API

检查 wire contract、server authority、状态与 allowed actions、unknown/raw fallback、accessibility、idempotency/unknown outcome、无 Solver/Validator/KPI 复制。

## Security / Dependency / Operations

检查 exact lock、advisory/license、Secret/no-leak、least privilege、backup/restore、monitoring、rollback 和 Production 阻塞项。

## Phase Gate / Audit

检查 fresh replay、全部直接 Task manifest、失败历史保留、blocking gaps、Provider identity、总规合规和下一 Phase 授权。Audit 不得在内部修实现。
