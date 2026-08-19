---
doc_id: DOC-CONTRACT-INDEX
title: 合同文档索引
status: living
spec_version: 0.3.0
phase: P0
normative: false
source_sections: [24, 36, 38, 39, 63, 64, 67, 103]
last_reviewed: 2026-08-19
---

# 合同文档索引

本目录描述机器可执行 Schema 的人类语义。TASK-P0-03 已发布 schema set `1.0.0` 的 P0 skeleton；机器文件位于 `/schemas/json`，data dictionary 位于 `/schemas/data_dictionary.yaml`。Schema 与对应合同必须同 Task、同版本语义更新。

## 当前基线

- `import-and-normalization.md`
- `planning-snapshot.md`
- `planning-problem.md`
- `planning-policy-and-solve-limits.md`
- `planning-solution-and-schedule-version.md`
- `execution-events-and-replan-request.md`
- `export-package.md`
- `schema-index.md`
- `schema-versioning.md`

## 已形成的机器合同

- `import-package.v1`：只固定版本化 metadata envelope；Canonical records 字段仍由 P1 authority mapping 决定；
- `planning-snapshot.v1`：固定不可变快照元数据与 Production/Simulation provenance 分离；
- `planning-problem.v1`：固定 Solver-neutral 顶层、Operation/Option/Edge/Calendar interval skeleton；
- `kpi.v1`、`error.v1`、`validation-report.v1`：固定顶层 envelope；具体 KPI 计算、错误码规则表和 C-ID Validator 行为仍为后续 Task。

所有根对象拒绝未知字段且不声明业务默认值。`schemas/samples/` 只包含明确标识的 synthetic schema samples，不是正式 Scenario 或生产数据。

## 等待实现事实后形成

- `api.md`：当前总规只有 endpoint inventory，payload/status/auth 尚未形成。
- `simulation-api.md`：需绑定环境开关、实际 job contract 和 OpenAPI。
- `external-adapters.md`：受 OPEN-002、OPEN-007、OPEN-013、OPEN-015 阻塞。

这些路径不创建空文档，避免被误认为已经批准的接口合同。
