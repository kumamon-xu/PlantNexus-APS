---
doc_id: DOC-OPS-INDEX
title: Operations 文档形成计划
status: planned
spec_version: 0.3.0
phase: P0-P7
normative: false
source_sections: [65, 66, 93, 94, 95, 101, 106]
last_reviewed: 2026-08-19
---

# Operations 文档形成计划

当前只固定要求，不编造尚不存在的部署事实。实现形成后分别建立：

- `security.md`：import、secret、auth、dependency 和 threat controls；
- `observability-and-audit.md`：PlanningRun metrics、trace、audit events 和 retention；
- `worker-reliability-and-idempotency.md`：heartbeat、lease、attempt、STALLED、retry；
- `release-and-versioning.md`：code/spec/schema/solver version 和 promotion；
- `production-readiness.md`：Historical replay、UAT、backup/restore、monitoring、runbook 和 PROD_OPEN closure。

这些文档必须引用真实部署配置、监控指标、测试和责任人后才能从 `planned` 转为 `baseline/living`。
