---
doc_id: DOC-SIM-004
title: Scenario Library 与复杂度矩阵
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: true
source_sections: [43, 44, 45, 46, 56]
last_reviewed: 2026-08-28
---

# Scenario Library 与复杂度矩阵

## TASK-P4-10 formed continuous disruption row

| Scenario | Profile | Seed / stream | Evidence | Boundary |
| --- | --- | --- | --- | --- |
| `SIM-P4-DISRUPTION-REPLAY-001@1.0.0` | `PROFILE-P4-DISRUPTION-REPLAY-001@1.0.0` | `20260828` / 5 steps / 8 standard events | [`scenario-library.v1.json`](../../fixtures/synthetic/P4-DISRUPTION-REPLAY/scenario-library.v1.json)、[`calculation-note.md`](../../fixtures/synthetic/P4-DISRUPTION-REPLAY/calculation-note.md)、TEST-DISRUPTION-REPLAY-001 | continuous correctness only；`SIMULATION_NON_PRODUCTION` baseline advance；not probability/capacity/SLA |

五步顺序固定为Urgent Order→Machine Failure/Recovery→Material Delay/Ready→Processing Delay→Early Completion。每步保留raw event/replan/change evidence、fresh Validator PASS与completed/running/HARD/freeze invariants；same-seed须保持exact event stream与相同语义结果投影，raw runtime observation不丢弃。该row不创建PROFILE-A～E Production参数、不改变XS/S/M benchmark，也不提前形成P4-14 Gate。

## TASK-P4-09 core vector boundary

`SIM-P4-EXECUTION-CORE-001@1.0.0`只是在machine/unit/property evidence中使用的versioned correctness identity：固定3个标准ExecutionEvent、10/10/20秒offset、1秒virtual-clock resolution与seed `20260828`，验证同刻queue/replay/checkpoint/common ingress。它不进入正式disruption scenario catalog，不声明概率、故障持续量、事件分布、期望KPI、capacity或SLA；因此不替代下方TASK-P4-10连续场景。

## P4 continuous scenario requirement

TASK-P4-10现以同一deterministic run覆盖并可独立重放`URGENT_DEMAND_RECEIVED`、`MACHINE_UNAVAILABLE/MACHINE_RECOVERED`、`MATERIAL_DELAYED/MATERIAL_READY`、`PROCESSING_DURATION_CHANGED/PROCESSING_REMAINING_CHANGED`与`OPERATION_COMPLETED` early completion；每类都要求事实/锁保护、Validator PASS、ChangeReport completeness及tardiness/stability对比。P5 capabilities与Production profiles不得伪装成P4场景；完整Provider与P4-14/15 Gate仍是后继证据。

## 初始工厂画像

| Profile | 主要特征 | 验证目标 |
|---|---|---|
| PROFILE-A Flexible Job Shop | 多工序、多候选设备、多车间、设备速度不同 | V1 主模型 |
| PROFILE-B Bottleneck Factory | 关键设备高负荷、高交期压力、多订单竞争 | Weighted tardiness、scaling |
| PROFILE-C High-Mix Setup | 高频切换、Setup Matrix | 当前期望 `UNSUPPORTED_CAPABILITY` |
| PROFILE-D Assembly DAG | parallel branch、merge、secondary resource | DAG；Secondary Capacity 可明确拒绝 |
| PROFILE-E Cross-Workshop | Cutting→Machining→Treatment→Assembly 等 | precedence、transport lag、calendar |

## Scenario 矩阵

场景覆盖应组合 Factory Size、Routing Complexity、Candidate Resources、Bottleneck、Due Pressure、Calendar Fragmentation、Material Delay、WIP、Lock、Cross-workshop 和 Failure Frequency，而不是只扩大 operation count。

## Complexity Metrics

至少记录 order/lot/operation/edge/resource counts、avg candidates、optional intervals、routing depth、cross-workshop ratio、calendar fragments、WIP/lock/material-delay ratios、bottleneck utilization 和 horizon ticks。

## Profile 级别

XS/S/M/L/XL 在 `benchmarks/profiles.yaml` 中定义 operation/resource target、candidate/calendar density 和 routing complexity。它们只用于相对复杂度与回归，不代表生产容量。

## P0-05 status

ScenarioSpec v1 已固定上述矩阵所需的 factory size、routing complexity、candidate density、bottleneck、due pressure、calendar fragmentation、material/WIP/lock/cross-workshop ratios 和 failure frequency 字段；FactoryProfile v1 固定生成范围与 capability/rejection 边界。当前仅有 `SCHEMA-*` samples，五类 Profile、XS/S/M/L/XL baseline 与正式 Scenario catalog 尚未创建，不得把 sample 的单值范围写入本表作为批准参数。

TASK-P0-06 已创建下方 `SIM-MINIMAL-001` correctness fixture；未来 Profile/Scenario asset 必须各自升 version 并引用 SIM_ASSUMPTION。该资产没有关闭 OPEN-003/011/012，也没有产生容量或性能结论。

## P0 correctness catalog

| Scenario | Profile | Size / features | Evidence | Scope boundary |
|---|---|---|---|---|
| `SIM-MINIMAL-001@1.0.0` | `PROFILE-SIM-MINIMAL-FJSP@1.0.0` | XS correctness；2 workshops、3 resources、3-operation DAG、alternative resources、calendar、cross-workshop | [`calculation-note.md`](../../fixtures/deterministic/SIM-MINIMAL-001/calculation-note.md)、TEST-GOLDEN-FJSP、TEST-SCENARIO-REPLAY | committed deterministic fixture only；不是 performance/production baseline |
| `SIM-P1-INGRESS-001@1.0.0` | `PROFILE-SIM-P1-INGRESS-001@1.0.0` | ingress correctness；2 workshops、4 resources、2 orders×3 operations、2 candidates、calendar/material/WIP/lock/cross-workshop | [`calculation-note.md`](../../fixtures/synthetic/SIM-P1-INGRESS-001/calculation-note.md)、TEST-SCENARIO-REPLAY、TEST-SIM-ISOLATION、TEST-P1-COMMON-INGRESS | Generator/Reference staging→Import/Snapshot/Problem correctness replay；不是 Solver/Benchmark/production baseline |

该 catalog 行实现 TASK-P0-06 的最小 Scenario；PROFILE-A～E 的正式参数集、XS/S/M/L/XL benchmark profiles、disruption/historical scenarios 仍未创建。`cross_workshop_ratio=0.5`、`material_delay_ratio=1/3` 等值只属于该 asset version，不外推到 Scenario Matrix 的默认分布。

P1 ingress行以`SIM-ASSUMPTION-010`逐项登记生成值；49条canonical records是correctness规模，不定义XS target或容量。PROFILE-A～E、performance baseline和broader catalog继续`PLANNED`。

TASK-P1-11只为该既有catalog row增加common-ingress machine evidence，没有新建Scenario/Profile、修改complexity或声称FEASIBLE/OPTIMAL已由Solver产生。

## P2 correctness catalog

| Scenario | Profile | Seed / correctness focus | Evidence | Scope boundary |
|---|---|---|---|---|
| `P2-GOLDEN-JSSP@1.0.0` | `PROFILE-P2-GOLDEN-JSSP@1.0.0` | `20260901` / opposite two-machine routes | [manual optimum](../../fixtures/deterministic/P2-GOLDEN-JSSP/calculation-note.md)、TEST-GOLDEN-JSSP | Solver/Validator correctness only |
| `P2-GOLDEN-FJSP@1.0.0` | `PROFILE-P2-GOLDEN-FJSP@1.0.0` | `20260902` / alternative-resource choice | [manual optimum](../../fixtures/deterministic/P2-GOLDEN-FJSP/calculation-note.md)、TEST-GOLDEN-FJSP | Solver/Validator correctness only |
| `P2-CROSS-WORKSHOP@1.0.0` | `PROFILE-P2-CORRECTNESS-MATRIX@1.0.0` | `20260903` / transport lag | [matrix note](../../fixtures/synthetic/P2-CORRECTNESS-MATRIX/calculation-note.md)、TEST-CROSS-WORKSHOP | shared matrix Profile；not distribution |
| `P2-CALENDAR@1.0.0` | `PROFILE-P2-CORRECTNESS-MATRIX@1.0.0` | `20260904` / unavailable interval | matrix note、TEST-CALENDAR | correctness only |
| `P2-MATERIAL-DELAY@1.0.0` | `PROFILE-P2-CORRECTNESS-MATRIX@1.0.0` | `20260905` / material gate | matrix note、TEST-MATERIAL | correctness only |
| `P2-RUNNING@1.0.0` | `PROFILE-P2-CORRECTNESS-MATRIX@1.0.0` | `20260906` / running remainder/resource | matrix note、TEST-RUNNING | correctness only |
| `P2-HARD-LOCK@1.0.0` | `PROFILE-P2-CORRECTNESS-MATRIX@1.0.0` | `20260907` / exact hard tuple | matrix note、TEST-INF-LOCK | correctness only |

全部七例由`PLANTNEXUS-P2-CORRECTNESS-ASSEMBLER@1.0.0`、approved Simulation Policy、exact Backend/Solver identity、manifest object/artifact hashes和SIM-ASSUMPTION-011固定，并已走正式Raw→Import→Snapshot→Problem→Strategy→Validator路径。`XS`仅表示可手算；PROFILE-A～E、XS/S/M performance baseline、Reference/Export与Production catalog仍未形成。

## TASK-P2-12 generated benchmark scenarios

| Scenario | Profile | Seed | Problem规模 | 用途 |
|---|---|---:|---|---|
| `P2-BENCHMARK-XS@1.0.0` | `P2-BENCHMARK-XS@1.0.0` | `20261201` | 4 orders / 8 operations / 3 resources | PR development benchmark |
| `P2-BENCHMARK-S@1.0.0` | `P2-BENCHMARK-S@1.0.0` | `20261202` | 8 / 24 / 6 | local/nightly-ready benchmark |
| `P2-BENCHMARK-M@1.0.0` | `P2-BENCHMARK-M@1.0.0` | `20261203` | 12 / 48 / 8 | local/nightly-ready benchmark |

三例由`benchmark-profile-set.v1`与`PLANTNEXUS-P2-BENCHMARK-GENERATOR@1.0.0`生成、经P2 correctness assembler进入正式pipeline，并以Problem hash和SIM-ASSUMPTION-013固定；它们是运行时可重建的versioned benchmark inputs，不新增或改写P2-09 correctness fixtures。PROFILE-A～E、L/XL、disruption/现实分布与Production catalog仍未形成。
