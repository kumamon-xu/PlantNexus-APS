---
doc_id: DOC-SIM-007
title: 性能与现实校准门
status: baseline
spec_version: 0.3.0
phase: P2-P7
normative: true
source_sections: [57, 58, 76, 80, 84, 85, 89, 105, 106]
last_reviewed: 2026-08-21
---

# 性能与现实校准门

## Gate A — P2 Synthetic Solver

完整验证 Snapshot → Problem → Solver → Validator → Export，至少运行 Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock 和 XS/S/M，并记录 build、first feasible、runtime、gap、memory、model size 和 validator result。

## Gate B — P4 Dynamic Replanning

通过 ExecutionSimulator 连续注入异常，确认 Execution Facts/HARD_LOCK 不变、新 Version Validator PASS、ChangeReport 完整。

## Gate C — P7 Reality Calibration

```text
Historical Snapshot
→ Replay
→ Synthetic Comparison
→ FactoryProfile Calibration
→ Production Capacity Boundary
```

Reality Gap Report 比较 routing depth、candidate density、calendar fragmentation、bottleneck 和 solver runtime 等真实/合成分布。

## 禁止承诺

在 OPEN-011/012 未关闭前，禁止“5 分钟一定排完”“秒级排程”“99% 最优”“任意规模”等表述。P7 不能成为第一次性能测试。

TASK-P0-05 只形成可供未来 Gate 引用的 versioned Scenario manifest 和 dataset hash；empty Import replay 不包含 operations/resources，不是 XS profile 或性能运行。Gate A/B/C、TEST-BENCHMARK、runtime/memory/quality baseline 和 OPEN-012 production threshold 均未改变。

TASK-P0-06 的 `SIM-MINIMAL-001@1.0.0` 使用 XS 标签只表示三道工序可手算 correctness；验收记录测试通过与 hash，不采集 Solver runtime、gap、memory/model size，也不进入 `benchmarks/**`。因此 Gate A/B/C、TEST-BENCHMARK、OPEN-012 和任何 performance baseline 均未改变。

TASK-P1-10的`SIM-P1-INGRESS-001@1.0.0`同样只验证49条canonical record的生成/Normalization/Data Validation replay；没有调用Problem/Solver、采集runtime/gap/memory/model size或修改`benchmarks/**`。因此它不是Gate A的XS run，也不改变Gate A/B/C、TEST-BENCHMARK、OPEN-011/012或任何容量/SLA结论。

## TASK-P2-08 tiny objective evidence boundary

`objective-strategy-report.v1`开始记录真实build/first-feasible/solve/validation/total、objective/bound/gap、model size与memory，并以4个至多3-operation的in-memory vectors证明OBJ-001数值/状态/Validator correctness。它没有使用`benchmarks/profiles.yaml`、正式Scenario Library、Reference Scheduler、warm-up/repetition/percentile或XS/S/M，因此不是Gate A/B/C performance run。

CI新增该correctness report只为防止objective/strategy/status回归；任何runtime或memory单值不得转成threshold、capacity或SLA。P2-12仍独占XS/S/M Benchmark，OPEN-011/012继续OPEN。

## TASK-P2-09 performance boundary

七个新Scenario均标记`XS`只是表达可手算correctness，报告虽透传model size/timing/memory，但不执行warm-up、repeat、percentile、Reference comparison或`benchmarks/profiles.yaml`。CI中的`ci-p2-correctness.json`只是一致性Gate，不能形成Gate A/B/C baseline、threshold、capacity或SLA；P2-12与OPEN-011/012保持不变。

## TASK-P2-12 Gate A scale slice

XS/S/M三个versioned profile现已各自在正式source→Problem链上运行Global和五Reference，并记录build/first feasible/solve/validation/total、objective/bound/gap、memory、model/Problem complexity与Validator结果。每个scheduler执行1次warm-up和3次measured repetition；本地三份`benchmark-report.v1`均8/8 PASS且无warning，CI PR slice真实执行XS。

这只关闭Gate A的XS/S/M scale-measurement子项，不替代P2-09 Golden/Cross/Calendar/Material/Running/Hard Lock evidence整合，也不形成完整Gate report。TASK-P2-13仍须把所有子项、exact provider artifact与phase trace组合后判定；TASK-P2-14才可审计。Development ceiling和same-environment factor不是Production SLA，OPEN-011/012继续OPEN。

## TASK-P2-13 Gate A aggregate evidence

`p2-vertical-slice-report.v1`现把Golden JSSP/FJSP、Cross Workshop、Calendar、Material Delay、Running、Hard Lock与XS/S/M组合为两次完整replay；每个XS/S/M再次运行Global+五Reference的1 warm-up/3 measured、fresh Validator、共享KPI和internal Export，并保留build/first/solve/validation/total、objective/bound/gap、memory、model/Problem scale、environment及package hashes。两次versioned business projection一致且11/11 aggregate checks PASS。

这构成TASK-P2-13本地Gate A aggregate evidence，不是TASK-P2-14 Exit audit或Production performance Gate。Run-specific SolverReport/KPI/package hash包含时间证据并逐次保留，不错误要求相等；Problem/candidate/业务投影必须一致。OPEN-011/012、L/XL、Nightly schedule、Production capacity/SLA仍未形成。
