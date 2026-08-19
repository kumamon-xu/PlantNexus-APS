---
doc_id: DOC-QUAL-001
title: 测试策略与 Test Matrix
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [31, 57, 72, 74, 76, 78, 80, 86, 87, 88, 89, 100]
last_reviewed: 2026-08-19
registry_version: 1.0.0
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

| Test ID | Purpose | Earliest phase | Evidence status |
|---|---|---|---|
| TEST-TRACEABILITY-VALIDATOR | Registry、reference、Task、diff/impact，以及 clean-tree committed range regression | P0 | [`backend/tests/unit/test_check_docs.py`](../../backend/tests/unit/test_check_docs.py) |
| TEST-OBS-001 | 日志、运行标识与 Observability 关联 | P0 | PLANNED（TASK-P0-08） |
| TEST-CONTRACT-001 | 基础 Contract 结构与兼容性 | P0 | PLANNED |
| TEST-GOLDEN-JSSP | 人工可验证 JSSP | P2 | PLANNED |
| TEST-GOLDEN-FJSP | 人工可验证 FJSP | P2 | PLANNED |
| TEST-INF-NO-RESOURCE | 无候选资源明确拒绝 | P0-P2 | PLANNED |
| TEST-INF-LOCK | Lock 导致的不可行性 | P0-P2 | PLANNED |
| TEST-INF-HORIZON | Horizon 不允许静默截断 | P0-P2 | PLANNED |
| TEST-CALENDAR | 设备日历约束 | P0-P2 | PLANNED |
| TEST-MATERIAL | material_ready_at gate | P0-P2 | PLANNED |
| TEST-RUNNING | 运行中事实保护 | P0-P2 | PLANNED |
| TEST-CROSS-WORKSHOP | 跨车间 precedence/transport lag | P0-P2 | PLANNED |
| TEST-MAX-LAG | max_lag 不被忽略 | P0-P2 | PLANNED |
| TEST-VALIDATOR-MUTATION | 独立 Validator 拒绝人工错误计划 | P0-P2 | PLANNED |
| TEST-REPLAN | Replan 事实、锁与变化报告 | P4 | PLANNED |
| TEST-OUTPUT | 标准成果包合同 | P2-P3 | PLANNED |
| TEST-IDEMPOTENCY | Import/Planning/Export/Publish/Event 幂等 | P0-P3 | PLANNED |
| TEST-SCENARIO-REPLAY | Scenario/Profile/Generator/seed 重放 | P0-P2 | PLANNED |
| TEST-SIM-ISOLATION | Synthetic/Production 隔离 | P0-P1 | PLANNED |
| TEST-REFERENCE-SCHEDULER | Reference Scheduler baseline | P2 | PLANNED |
| TEST-BENCHMARK | BenchmarkReport/profile 回归 | P2 | PLANNED |
| TEST-PROPERTY | 合法 Problem 的通用不变量 | P2 | PLANNED |
| TEST-SOLVER-UPGRADE | Solver 升级 replay/status contract | P2+ | PLANNED |

Test ID 一经分配不得复用。链接到真实测试路径才是已形成证据；`PLANNED` 只登记合同。表结构或状态语义变化必须提升 `registry_version`。

## 原则

- 测试失败不能通过删除硬约束或修改断言规避；
- Solver 与 Validator 必须有不同实现路径；
- Golden 关注 feasibility、objective 和约束，不比较完整 Gantt JSON；
- 多个同质量解可能都正确，Property/Golden 不固定无意义排序；
- Benchmark 正确性失败优先于性能结果。

实际测试路径和结果在文件创建后写入追踪矩阵，当前只登记合同 ID。
