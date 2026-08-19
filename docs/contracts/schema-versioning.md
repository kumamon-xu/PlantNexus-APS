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
