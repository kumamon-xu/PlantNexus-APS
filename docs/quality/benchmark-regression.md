---
doc_id: DOC-QUAL-005
title: Benchmark Regression 规则
status: baseline
spec_version: 0.3.0
phase: P2-P7
normative: true
source_sections: [53, 55, 56, 57, 58, 89, 102]
last_reviewed: 2026-08-19
---

# Benchmark Regression 规则

Solver 升级、Constraint 修改、PlanningProblem 修改和影响模型规模的 preprocessing 修改都必须回放固定 Scenario Set。

比较维度：correctness、objective quality、runtime、memory、model size、first feasible、bound/gap 和 Validator result。

## 判定顺序

1. Validator/contract correctness；
2. feasibility/status semantics；
3. objective quality 与 Reference Scheduler；
4. runtime/memory；
5. 其他诊断指标。

Correctness 退化不能用更快运行时间抵消。显著质量或性能退化需要阻止发布或提交 ADR；“显著”的生产阈值受 OPEN-012 约束，当前使用版本化 Benchmark baseline 和明确环境作相对比较。

报告和 baseline 是版本化 artifacts，不手工覆盖历史结果。

## TASK-P0-03 review

本 Task 首次发布 `planning-problem.v1` skeleton，因此已审查 ADR-0003 与本规则。P0-03 没有 Problem builder、Solver、固定 Scenario Set 或历史 baseline，无法产生有意义的 correctness/quality/runtime/memory comparison；不得伪造零值 Benchmark。P2 首次 vertical slice 必须把该 schema version/problem hash 纳入固定 Scenario replay，并建立真实 baseline。

## TASK-P0-04 review

P0-04 将总规已有 C-001～C-018 semantics 固定为 `constraint-rule-sheet.v1`，没有修改 `planning-problem.v1`、Solver、constraint builder、目标或 Scenario baseline；状态/error/capability contract 也不改变模型规模。因此当前没有可运行的 Solver/Golden/Scenario benchmark，不生成零值或 synthetic 性能结论。

P2 首次 baseline 必须记录 rule sheet/ValidationReport version；以后任何公式、C-ID 语义或 capability 从 UNSUPPORTED 变为支持，都重新匹配本规则并执行 correctness/quality/runtime/memory replay。
