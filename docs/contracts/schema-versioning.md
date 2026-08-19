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

## TASK-P0-08 engineering metadata review

Schema set 与 `app.SCHEMA_VERSION` 均保持 `1.2.0`；没有修改 `schemas/**`、JSON/YAML contract、sample、Fixture、hash 或 serializer。`engineering_job_records` 与 `engineering_idempotency_records` 是 Alembic 管理的通用关系型工程 metadata，不是 Business Schema set；其 compatibility 由 revision `0001_engineering_job_metadata` 的空库 upgrade/downgrade test 管理。

因此本 Task 的 JSON Schema compatibility/migration 为 none；新增 runtime dependencies/lock 和 build commit metadata 不能借机提升或覆盖 schema set。未来若 Job/health payload 成为跨系统产品合同，必须由单独 Task 建立 versioned Schema，而不能把本 P0 Python/DB skeleton 当作已发布业务合同。

## TASK-P1-02 canonical major set release

- Schema set：`2.0.0`，同步写入`pyproject.toml`、`app.SCHEMA_VERSION`与data dictionary；
- 新增`canonical-records.v1`、`import-package.v2`、`planning-snapshot.v2`及两份明确synthetic sample；所有`1.0.0/1.1.0/1.2.0` artifact、稳定URN和尤其Import/Snapshot v1文件逐字保留；
- Compatibility：从opaque Import v1/metadata-only Snapshot v1到strict required canonical payload属于set-level major与document-level breaking change。v1/v2前后均不互换，禁止alias、默认填充或静默upgrade；
- Migration：没有数据库或已发布v2 consumer，故无数据migration。v1 fixture/history保持只读；后续producer必须显式产出v2，旧consumer必须拒绝v2直到升级；
- Hash/replay：v2只固定`sha256:`格式、provenance和payload；dataset/Snapshot hash projection与builder仍由TASK-P1-05/08实现。Schema sample digest不构成hash evidence；
- Validation：JSON Schema Draft 2020-12/jsonschema `4.25.1`跨URN registry、positive/negative/round-trip、unknown/no-default、UTC/unit/duration/reference、synthetic isolation、v1 byte fingerprint及pure semantic precheck均由TEST-CONTRACT-001覆盖。

本release落实ADR-0007/0008/0009既有决定，不改变PlanningProblem、rule/state/error/capability/Simulation artifact，也不引入dependency、DB migration、Adapter、DataValidation、Builder或Solver。`uv.lock`依赖图因此保持不变。

## TASK-P1-04 metadata review

本Task只在`pyproject.toml` runtime dependencies增加exact openpyxl/defusedxml并更新`uv.lock`，没有修改`[tool.plantnexus-aps.versions]`、`app.SCHEMA_VERSION`、`schemas/**`、data dictionary、sample、serializer或hash projection。Schema set继续`2.0.0`，JSON/YAML compatibility与migration均为none；Reference Adapter`1.0.0`是独立code-level transport version，不能替代或提升Schema version。

未来改变三列Reference transport或opaque row serialization必须发布新的adapter version并提供replay/compatibility规则，但只有修改machine Schema时才按本文件提升schema set。Dependency lock变化不能无痕改写Import/Snapshot document版本。

## TASK-P1-05 additive normalization-rule release

- Schema set：`2.1.0`，同步更新`pyproject.toml`、`app.SCHEMA_VERSION`和data dictionary；新增`unit-conversion-registry.v1`，不新增或重写JSON document version；
- Preservation：`canonical-records.v1.schema.json`与`import-package.v2.schema.json`SHA-256继续分别为`fd13b188b7317eb92f14489fdc6c7976cc24b5b03cfcb2fa9d9f1eabdd4b3f9e`、`166514c8ea40702c7b42b27956809619396c90d10b1b0cab4c2bd57dd4a75f56`；Import v2 document内固定`schema_set_version=2.0.0`；
- Compatibility：set-level只添加独立rule type，属于additive；mapping profile、unit registry与canonicalization version必须显式组合进入normalization rule version，禁止按`latest`重解释历史staged rows；
- Migration：无数据库迁移、无历史canonical package改写。旧rule version继续只读，consumer rollback必须显式选择旧版本；
- Validation：unit registry contract、Schema/data-dictionary同步、stable ID/UTC/integer seconds、same-input replay、mapping-version mutation和负向DATA_ERROR均由TEST-CONTRACT-001/TEST-NORMALIZATION-001覆盖。

`pyproject.toml`本次只改版本metadata，没有dependency或lock graph变化；`uv.lock`保持不变。规则版本变化必须发布新registry文件并回放canonical hashes，不能原地更改v1语义。
