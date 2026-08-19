---
doc_id: DOC-SIM-007
title: 性能与现实校准门
status: baseline
spec_version: 0.3.0
phase: P2-P7
normative: true
source_sections: [57, 58, 76, 80, 84, 85, 89, 105, 106]
last_reviewed: 2026-08-19
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
