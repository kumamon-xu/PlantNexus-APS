---
doc_id: DOC-OPS-INDEX
title: Operations 索引与形成边界
status: baseline
spec_version: 0.3.0
phase: P0-P7
normative: false
source_sections: [65, 66, 93, 94, 95, 101, 106]
last_reviewed: 2026-08-19
---

# Operations 索引与形成边界

P0-08 已形成工程骨架可验证的前三份 Operations baseline：

- [`security.md`](security.md)：environment-only config、Secret/log redaction、dependency/SQL/shell 边界；Import/auth/threat-model controls 仍待真实功能。
- [`observability-and-audit.md`](observability-and-audit.md)：structured log context、OpenTelemetry ID 注入、health/build metadata；PlanningRun metrics/audit persistence/retention 仍待实现。
- [`worker-reliability-and-idempotency.md`](worker-reliability-and-idempotency.md)：business-neutral heartbeat、lease、attempt、STALLED、idempotency 与 migration；distributed repository/scanner/business retry 仍待实现。

后续仍只保留计划：

- `release-and-versioning.md`：code/spec/schema/solver version 和 promotion；
- `production-readiness.md`：Historical replay、UAT、backup/restore、monitoring、runbook 和 PROD_OPEN closure。

现有三份 baseline 只引用仓库内配置、tests 与 machine report，不能被解释为 Production Runbook。Release/Production 文档必须引用真实部署配置、监控指标、backup/restore、平台 run 和责任人后才能创建并转为 `baseline/living`；P0-08 未猜测这些事实。
