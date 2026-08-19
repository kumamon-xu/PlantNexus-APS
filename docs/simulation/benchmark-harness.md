---
doc_id: DOC-SIM-006
title: Benchmark Harness 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [45, 51, 52, 53, 54, 55, 56, 58, 89]
last_reviewed: 2026-08-19
---

# Benchmark Harness 合同

```python
BenchmarkRunner.run(
    scenario,
    solver,
    limits,
)
```

同一 Scenario 可运行 Reference Scheduler 与 GlobalCpSatStrategy，并使用同一 Validator/KPI 口径。

## BenchmarkReport

至少包含 scenario/profile/generator versions、Problem hash、Solver/version/parameters、status、model build/first solution/solve times、objective/bound/gap、memory、complexity metrics 和 validation result。

## 回归层级

- PR：XS；
- Nightly：XS + S + M；
- Release：XS + S + M + L + selected stress scenarios；
- XL：人工或专用环境。

## 结果解释

- correctness/Validator failure 一律阻止接受结果；
- CP-SAT 明显劣于简单 heuristic 产生 `BENCHMARK_WARNING`；
- runtime/memory/quality 显著退化阻止发布或要求 ADR；
- 报告必须注明硬件和环境；
- Synthetic 结果不能推导生产 SLA。
