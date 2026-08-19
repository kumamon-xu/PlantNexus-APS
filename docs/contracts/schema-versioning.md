---
doc_id: DOC-CONTRACT-009
title: Schema 版本与兼容规则
status: baseline
spec_version: 0.3.0
phase: cross-phase
normative: true
source_sections: [23, 24, 40, 101, 103, 104]
last_reviewed: 2026-08-19
---

# Schema 版本与兼容规则

## 每次 Schema 修改必须

1. 增加对应 `schema_version`；
2. 说明 backward/forward compatibility；
3. 提供 migration 或明确拒绝旧版本；
4. 更新 human-readable contract；
5. 增加/更新 contract test；
6. 更新 sample/fixture；
7. 检查 Snapshot/Problem hash、replay 和 export 影响。

## 兼容分类

- Additive optional：可能向后兼容，但仍需 version 和测试。
- Required/semantic change：不兼容，必须迁移或明确拒绝。
- Rename/unit/time semantic change：视为不兼容，不能用 alias 静默吸收。
- Ordering-only serialization change：若影响 hash，必须作为版本变化治理。

Schema version、rule version、generator version 和 code commit 是不同维度，不能互相替代。

## 当前发布基线

- Schema set：`1.0.0`；`pyproject.toml` 与 `app.SCHEMA_VERSION` 一致；
- Contract IDs：`import-package.v1`、`planning-snapshot.v1`、`planning-problem.v1`、`kpi.v1`、`error.v1`、`validation-report.v1`；
- Dialect：JSON Schema Draft 2020-12，使用稳定 URN `$id`；
- Compatibility：这是从 `unassigned` 到首次 skeleton 的发布，此前没有已发布 consumer、历史 artifact 或数据库数据，因此 migration 为 none；
- Unknown/default policy：已定义根对象 `additionalProperties=false`，Schema 不含 `default`。Import 的 `records` 是明确标注的 P1 扩展点，不等于批准任何生产字段。

`*.v1` 的字段或语义后续变化必须分类为 additive/breaking；即使 schema set 版本提升，也不得无痕覆盖本目录下已经发布的 v1 artifact。
