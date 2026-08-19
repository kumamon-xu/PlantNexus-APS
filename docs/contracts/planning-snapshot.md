---
doc_id: DOC-CONTRACT-002
title: PlanningSnapshot 合同
status: baseline
spec_version: 0.3.0
phase: P0-P1
normative: true
source_sections: [23, 40, 62, 74, 101, 103]
last_reviewed: 2026-08-19
---

# PlanningSnapshot 合同

PlanningSnapshot 是某个 cutoff 的不可变计划事实集合，必须 immutable、deterministic、replayable、hashable。

## 最小元数据

```text
snapshot_id
cutoff_at
source_versions
rule_version
snapshot_hash
entity_counts
synthetic
scenario_id (synthetic only)
```

Synthetic Snapshot 还应能追溯 scenario/profile/generator/seed。Production Snapshot 必须 `synthetic=false`，且不得引用 synthetic-only source。

## 确定性

同一 canonical dataset、cutoff、规则版本和 Schema 版本必须得到相同 `snapshot_hash`。Hash 输入使用稳定排序和 canonical serialization，不包含随机 UUID、生成时间等非业务噪声。

## 不可变性

Snapshot 创建后不允许就地修改。输入事实变化、执行事件或规则版本变化必须产生新 Snapshot。删除/更正原始导入不得改写已被 PlanningRun 引用的 Snapshot。

## P0 Schema 骨架要求

Schema 应先固定元数据、实体集合、版本和 hash 语义；具体生产字段受 `PROD_OPEN` 影响时允许扩展占位，但不得填入猜测默认值。
