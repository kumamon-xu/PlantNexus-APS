---
doc_id: DOC-SIM-006
title: Benchmark Harness 合同
status: baseline
spec_version: 0.3.0
phase: P0-P2
normative: true
source_sections: [45, 51, 52, 53, 54, 55, 56, 58, 89]
last_reviewed: 2026-08-31
---

# Benchmark Harness 合同

## TASK-P5-01 qualification profile

`capability-qualification-profile.v1`把九项候选、五项`ALL_TRUE`选择事实、XS/S/M replay集合、四个必报维度和P5/P6/Production排除边界固定为机器合同；`evidence-manifest.v1`逐字绑定profile、九份candidate record及既有registry/rule-sheet/Simulation/Benchmark源文件SHA-256。hash、version、source type、candidate identity或声明决定漂移均fail closed。

本Task复用既有BenchmarkRunner和baseline，不修改runner、profile set、threshold或expected。report中的runtime/memory/model-size/quality为raw development observation，不是新基线或Production承诺。

## P4 planned harness impact

TASK-P4-10/14将把五类连续重排场景接入可重放Gate，记录event count、replan count、solver/validator status、tardiness、stability和ChangeReport coverage；任何性能数据仅为Simulation evidence，不是Production SLA/capacity。现有XS/S/M benchmark baseline、threshold与runner不变。

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

## TASK-P2-12 BenchmarkRunner implementation

`benchmark-profile-set.v1`只注册XS/S/M；每项固定Profile/Scenario/generator/assembler/version/seed、60秒tick、horizon、订单/资源/工序/候选/日历/material参数、1次warm-up、3次measured run及不可覆盖baseline路径。XS=`4 orders/3 resources/8 operations/16 options/1 fragment/180 ticks`，S=`8/6/24/48/2/480`，M=`12/8/48/96/4/900`。L/XL不被loader或CLI接受。

`benchmark-report.v1`为strict exact-key internal machine contract，记录source→Problem与KPI/Export耗时、Problem/Snapshot hashes、全部复杂度指标、环境签名、Global exact solver/parameters/status/model counts、build/first/solve/validation/total raw samples/median/nearest-rank p95、objective/bound/gap/memory、五Reference的相同统计、formal Validator、共享schedule KPI、deterministic fingerprints、comparison、baseline checks和phase boundaries。任何correctness/KPI/determinism失败hard fail；Global weighted tardiness高于最佳Reference产生`BENCHMARK_WARNING`但不得篡改结果。

三个`benchmark-baseline.v1`绑定固定Problem hash/complexity和一次真实Windows AMD64/Python 3.12.13/OR-Tools 9.15.6755观测。跨环境仍执行宽松development ceiling，但跳过相对性能结论；同环境才使用2.5倍diagnostic regression factor。历史v1不得覆盖，变化必须发布新版本。命令为`uv run python scripts/run_benchmark.py --profile <xs|s|m> --report <path>`；PR CI只执行XS并上传报告，Nightly S/M调度仍未创建。全部结果synthetic-only，OPEN-011/012保持OPEN。

## TASK-P2-13 aggregate replay consumer

Gate不修改Profile/Report/Baseline、threshold或runner；它用public `run_benchmark`在每个full replay内按XS/S/M各调用一次，所以`repeat=2`产生6份完整BenchmarkReport、18个Global measured runs与90个Reference measured runs。每份报告仍独立执行strict validation、baseline comparison与warning规则，任何warning或FAIL均阻断Gate。

Aggregate report完整嵌入六份原始报告并另算`p2-gate-semantic-projection.v1`：比较Profile/Problem/environment/candidate/model/quality/Validator/Reference/baseline语义，排除本来就会变化的time/memory和由SolverReport timing派生的KPI/package identity。此投影不替换原Benchmark合同或原始测量；L/XL、Nightly与Production threshold继续不在范围。

Provider artifact `9440650646`精确包含六份nested XS/S/M BenchmarkReport、全部108次Validator PASS及同SHA Gate aggregation；required Gate step success。Profile/Baseline/runner仍无变化，L/XL、Nightly和Production threshold继续未形成。
