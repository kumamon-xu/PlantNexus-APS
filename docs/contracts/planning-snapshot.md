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

[`planning-snapshot.schema.json`](../../schemas/json/planning-snapshot.schema.json) 已固定 `snapshot_version=planning-snapshot.v1`、最小元数据、严格 UTC `Z`、根对象未知字段拒绝和 synthetic/scenario 条件。Production (`synthetic=false`) 禁止携带 `scenario_id`；synthetic Snapshot 必须携带。

P0 sample 明确标记 synthetic，且 hash/builder 值标明不是生产结果。Snapshot builder、canonical serialization、hash 计算和 entity payload 仍为 P1 `PLANNED`；当前 skeleton PASS 不等于 REQ-002 实现完成。
