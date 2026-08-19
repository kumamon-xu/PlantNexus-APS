---
doc_id: DOC-CONTRACT-007
title: 标准成果包合同
status: baseline
spec_version: 0.3.0
phase: P0-P3
normative: true
source_sections: [4, 34, 36, 40, 55, 67, 93]
last_reviewed: 2026-08-19
---

# 标准成果包合同

成功 PlanningRun 的标准包：

```text
export_package/
├─ manifest.json
├─ schedule.json
├─ schedule_operations.csv
├─ order_summary.csv
├─ resource_load.csv
├─ kpi.json
├─ validation_report.json
├─ solver_report.json
├─ change_report.json
└─ import_quality_report.json
```

Synthetic Run 额外包含 `scenario_manifest.json` 和 `benchmark_report.json`。

## manifest

至少记录 package/schema version、ScheduleVersion、Snapshot/Problem hash、rule/solver/parameter/code versions、文件清单与 hash、生成时间和 synthetic 标识。

## 一致性

- 所有文件引用同一 ScheduleVersion 和 Problem；
- CSV/JSON 中 operation 数量与 manifest/entity counts 一致；
- KPI、validation、solver、change 和 quality report 不能来自其他 run；
- synthetic 包不可作为 production publish payload；
- 同一 ExportJob 幂等键重复执行得到逻辑等价成果，不能 double publish。
