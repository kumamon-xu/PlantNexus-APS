---
doc_id: DOC-QUAL-001
title: 测试策略与 Test Matrix
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [31, 57, 72, 74, 76, 78, 80, 86, 87, 88, 89, 100]
last_reviewed: 2026-08-19
---

# 测试策略与 Test Matrix

## 测试层

| 层 | 目的 |
|---|---|
| Unit | 局部纯逻辑和错误边界 |
| Contract | Schema、状态、API/adapter 语义 |
| Integration | DB/queue/import/export 和模块协作 |
| Golden | 小规模、人工/暴力可验证 correctness |
| Mutation | 证明 Validator 能拒绝人工错误计划 |
| Property | 随机合法 Problem 的通用不变量 |
| Simulation | 可重放场景、覆盖与动态异常 |
| Benchmark | correctness、quality、runtime、memory regression |

## 必需 Test IDs

`TEST-CONTRACT-001`、`TEST-GOLDEN-JSSP`、`TEST-GOLDEN-FJSP`、`TEST-INF-NO-RESOURCE`、`TEST-INF-LOCK`、`TEST-INF-HORIZON`、`TEST-CALENDAR`、`TEST-MATERIAL`、`TEST-RUNNING`、`TEST-CROSS-WORKSHOP`、`TEST-MAX-LAG`、`TEST-VALIDATOR-MUTATION`、`TEST-REPLAN`、`TEST-OUTPUT`、`TEST-IDEMPOTENCY`、`TEST-SCENARIO-REPLAY`、`TEST-SIM-ISOLATION`、`TEST-REFERENCE-SCHEDULER`、`TEST-BENCHMARK`、`TEST-PROPERTY`、`TEST-SOLVER-UPGRADE`。

## 原则

- 测试失败不能通过删除硬约束或修改断言规避；
- Solver 与 Validator 必须有不同实现路径；
- Golden 关注 feasibility、objective 和约束，不比较完整 Gantt JSON；
- 多个同质量解可能都正确，Property/Golden 不固定无意义排序；
- Benchmark 正确性失败优先于性能结果。

实际测试路径和结果在文件创建后写入追踪矩阵，当前只登记合同 ID。
