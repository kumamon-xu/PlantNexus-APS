---
doc_id: DOC-RUNBOOK-INDEX
title: APS Headless 运维 Runbook 索引
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [65, 66, 91, 92, 95, 101, 102, 103, 106, 113, 114]
last_reviewed: 2026-09-07
---

# APS Headless 运维 Runbook 索引

TASK-P8-10已为隔离的`TEST/SIMULATION` Compose靶场形成首组可执行Runbook，并由`TEST-P8-OPERATIONS-001`逐页做结构检查、步骤映射和真实演练。它们适用于P8-09 exact Runtime的工程部署，不是Production值班手册，也不定义真实联系人、SLA、retention或上线authority。

- [Headless部署与双slot回退](headless-deployment-and-rollback.md)
- [备份与恢复](backup-and-restore.md)
- [依赖故障与readiness](dependency-outage-and-readiness.md)
- [Solver Worker停滞恢复](stalled-worker-recovery.md)
- [Extension装载与兼容失败](extension-load-and-compatibility-failure.md)
- [事件分诊与升级](incident-triage-and-escalation.md)

统一机器入口：

```powershell
uv run python scripts/p8_operations_check.py `
  --root . `
  --deployment-report build/validation/p8-10-deployment.json `
  --observability-report build/validation/p8-10-observability.json `
  --recovery-report build/validation/p8-10-recovery.json `
  --runbook-report build/validation/p8-10-runbooks.json
```

命令只允许创建项目名为`plantnexus-p8-10`的一次性容器、网络和volume。脚本自行生成临时密码、在`finally`中执行target-scoped清理，并只写sanitized JSON；失败时保留FAIL报告但不打印driver detail或credential。Raw database dump只存在于进程内/runner temp并随演练销毁。

P8-12～15后续负责Extension SDK、Registry、Enterprise Extension和Developer Kit。届时若运行组合、版本或故障模式改变，必须新增或修订对应Runbook并重新执行兼容演练；不得把本索引解释为允许当前Runtime加载Extension。
