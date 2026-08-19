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

## TASK-P1-02 v2 payload contract

[`planning-snapshot.v2`](../../schemas/json/planning-snapshot.v2.schema.json)要求schema/source/rule/normalization/expansion/canonicalization versions、Import v2 dataset hash、`import-quality-report.v1` PASS reference、严格entity counts、canonical records、expanded `operation_instances`与`operation_precedence_edges`。实例显式保留DemandOrder→ProductionOrder→ProductionLot→RoutingVersion/Operation lineage、release/material/due、required capabilities、candidate级duration/source version、execution fact和lock引用；COMPLETED可作为Snapshot事实保留。

Synthetic v2必须携带scenario/profile/generator/version/seed，Production v2禁止该provenance。Schema中的`sha256:`字段只固定格式；本Task的contract sample digest是形状占位，不是hash builder证据。canonical serialization、hash projection、deterministic snapshot ID、insert-only repository与immutability测试仍由TASK-P1-08实现，不能从v2 Schema存在推断REQ-002已完成。
