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
