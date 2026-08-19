---
doc_id: DOC-PLAN-006
title: 无解与失败诊断
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [29, 57, 91, 92, 93]
last_reviewed: 2026-08-19
---

# 无解与失败诊断

## 诊断管道

```text
1. Precheck
2. Pure Feasibility Solve
3. Assumption Groups
4. Conflict Explanation
```

## Precheck

在构建/求解前检测 route cycle、missing candidate resource、非法 duration、明显 horizon/lock 冲突、unsupported capability、引用错误和单位问题。这些错误不能错误归类为 Solver INFEASIBLE。

## Pure Feasibility

当带目标运行失败时，可在相同硬约束下执行纯可行性诊断，以区分目标配置、求解预算与真实无解。不能为诊断删除硬约束。

## Assumption Groups

可将 locks、calendar、material gate、precedence、horizon 等分组用于 conflict explanation。输出的是已发现的 conflict subset；除非算法证明，不使用“最小冲突集”措辞。

## 报告

诊断应包含 Problem hash、Constraint IDs、entity IDs、assumption groups、limits、Solver status/version 和下一步建议。UNKNOWN 只报告未在预算内得到认证结论。
