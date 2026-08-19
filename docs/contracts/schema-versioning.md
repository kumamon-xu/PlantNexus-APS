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

## TASK-P0-04 additive set release

- Schema set：`1.1.0`，同步写入 `pyproject.toml`、`app.SCHEMA_VERSION` 与 data dictionary；
- 保留 `error.v1`、`validation-report.v1` 原文件和 URN；新增 `error.v2`、`validation-report.v2` 与 `state-transition.v1`；
- 新增四份 `*.v1` YAML rule/registry contract。它们的版本独立于 JSON document version；
- Set compatibility：添加新合同且保留全部 `1.0.0` artifact，属于 set-level additive；单个 v1/v2 document 仍不互换；
- Migration：没有数据库、持久化 Error/Validation consumer 或历史 run artifact，因此不执行数据迁移。v2 consumer 必须显式拒绝 v1；未来只能用 adapter/new artifact 迁移，不能 alias 或覆盖 v1；
- Validation：Draft 2020-12 `jsonschema==4.25.1`、PyYAML `6.0.2`、TEST-CONTRACT-001 与 TASK-P0-04 四项 contract tests；规则表 CLI 只验证完整性/一致性。

本次不修改 PlanningProblem、Snapshot、Import 或 KPI document version，不影响其 hash/serializer 语义。没有正式 sample/Fixture 可迁移；P0-04 tests 使用内联纯合同实例，不把它们声明为 Production 或 Scenario data。

## TASK-P0-05 additive Simulation set release

- Schema set：`1.2.0`，同步写入 `pyproject.toml`、`app.SCHEMA_VERSION` 与 data dictionary；
- 保留全部 `1.0.0/1.1.0` JSON/YAML artifact 与稳定 URN；新增 `factory-profile.v1`、`scenario-spec.v1`、`scenario-manifest.v1`；
- Set compatibility：只添加新 document types，属于 set-level additive；contract version（`*.v1`）、asset version（Profile/Scenario `1.0.0`）与 Generator version 相互独立；
- Migration：没有 DB、persisted consumer、正式 Fixture 或历史 run artifact，故 none；consumer 必须显式选择 Simulation v1，不通过 alias 吸收未来版本；
- Hash：`canonical-json.v1` 对 Standard Import envelope 稳定排序/编码并拒绝 NaN/Infinity，`dataset_hash=sha256(canonical_import_bytes)`；manifest `generated_at` 不参与 hash；
- Validation：Draft 2020-12 `jsonschema==4.25.1`、pure semantic precheck、TEST-CONTRACT-001、TEST-SCENARIO-REPLAY 与 TEST-SIM-ISOLATION。

本次不修改 `import-package.v1`、Snapshot/Problem、rule/state/error/capability artifact 内容。P0 empty package 的 `records={}` 是不猜生产字段的边界，不是 P1 canonical dataset 实现。
