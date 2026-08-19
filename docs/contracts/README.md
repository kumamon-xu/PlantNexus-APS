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

本目录描述机器可执行 Schema 的人类语义。P0 文档基线不会创建实际 `/schemas` 文件；后续 Schema 必须与相应合同同版本、同 Task 更新。

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

## 等待实现事实后形成

- `api.md`：当前总规只有 endpoint inventory，payload/status/auth 尚未形成。
- `simulation-api.md`：需绑定环境开关、实际 job contract 和 OpenAPI。
- `external-adapters.md`：受 OPEN-002、OPEN-007、OPEN-013、OPEN-015 阻塞。

这些路径不创建空文档，避免被误认为已经批准的接口合同。
