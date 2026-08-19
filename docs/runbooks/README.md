---
doc_id: DOC-RUNBOOK-INDEX
title: Runbook 形成计划
status: planned
spec_version: 0.3.0
phase: P2-P7
normative: false
source_sections: [65, 66, 91, 92, 102, 103, 106]
last_reviewed: 2026-08-19
---

# Runbook 形成计划

Runbook 必须描述真实可执行操作、权限、验证、回滚和升级路径；没有实现与演练证据时不创建伪操作步骤。

计划路径：

- `planning-run-failures.md`；
- `stalled-worker-recovery.md`；
- `export-and-publish-retry.md`；
- `solver-upgrade.md`；
- `schema-migration.md`；
- `backup-and-restore.md`。

每份 Runbook 至少包含触发条件、诊断、影响范围、前置权限、安全保护、执行步骤、验证、回滚、升级联系人/责任和最近演练记录。
