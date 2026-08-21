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

TASK-P0-05 的 ScenarioManifest v1 提供未来 report 需要引用的 Scenario/Profile/Generator/seed/dataset hash 边界，ScenarioSpec v1 提供复杂度维度输入；当前没有 `simulation/benchmarks/**` 实现、`benchmarks/profiles.yaml` baseline 变更、Problem/Solver/Validator result 或硬件采集。本 Task 不生成 BenchmarkReport，REQ-014 与 TEST-BENCHMARK 继续 `PLANNED`。

## TASK-P2-10 Reference input to future Benchmark

五个`reference-*.v1`算法及`reference-scheduler-report.v1`现已形成：七个P2-09 Problem各自产生五个完整Validator-PASS candidate，并记录weighted tardiness、makespan和single-run runtime。该报告证明Reference侧算法身份、determinism、hard-feasibility和metric carrier可用，但没有运行BenchmarkRunner，也没有把Global Strategy结果与Reference结果组成comparison row。

`simulation/benchmarks/**`、`benchmarks/profiles.yaml`、warm-up/repetition/percentile/hardware environment、quality warning与threshold继续零变化，REQ-014/TEST-BENCHMARK仍`PLANNED`。TASK-P2-12必须从相同Problem、formal Validator和KPI读取本版本Reference结果；不得把P2-10 tiny correctness timings追认为XS/S/M baseline。
