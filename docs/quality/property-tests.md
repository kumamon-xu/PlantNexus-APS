---
doc_id: DOC-QUAL-004
title: Property Test 规范
status: baseline
spec_version: 0.3.0
phase: P1-P4
normative: true
source_sections: [45, 86, 87]
last_reviewed: 2026-08-19
---

# Property Test 规范

Property Test 随机生成合法 V1 PlanningProblem 或合法 canonical input，检验跨大量组合保持的不变量。

## 核心性质

- 任何被接受的 Schedule 必须 `validator_passed=true`；
- 每个未完成 Operation 恰排一次；
- 同 resource interval 不重叠且尊重 calendar；
- precedence、material/release、lock、duration 和 horizon 均成立；
- 同 canonical input 和版本产生相同 hash；
- unsupported capability 被明确拒绝；
- 序列化 round-trip 不改变语义。

## 非性质

不要求相同 schedule ordering、相同 Solver search path 或相同 runtime，因为多个同质量解可能正确。

随机失败必须保存最小化 example、seed、Schema/Generator/Problem version 和 Problem hash，确保可回归。

TASK-P0-03 已对两个明确 synthetic sample 执行 JSON serialization round-trip，并验证 UTC/duration/reference 的确定性 helper；这只是 `TEST-CONTRACT-001` 的固定样例证据，不是随机 Property Test、Snapshot/Problem hash replay 或 TEST-PROPERTY 完成。完整性质测试仍为 P1/P2 `PLANNED`。
