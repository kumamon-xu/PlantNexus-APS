---
doc_id: DOC-SIM-007
title: 性能与现实校准门
status: baseline
spec_version: 0.3.0
phase: P2-P7
normative: true
source_sections: [57, 58, 76, 80, 84, 85, 89, 105, 106]
last_reviewed: 2026-08-20
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
