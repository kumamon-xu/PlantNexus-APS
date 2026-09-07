---
doc_id: DOC-RUNBOOK-P8-BACKUP-001
title: PostgreSQL 备份与恢复演练
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [65, 91, 92, 95, 101, 103, 106, 113, 114]
last_reviewed: 2026-09-07
---

# PostgreSQL 备份与恢复演练

TASK-P8-10使用PostgreSQL custom-format dump验证P8-09 migration head、完整schema及namespaced synthetic sentinel的恢复一致性。该机制是非Production工程证据，不定义真实backup产品、加密密钥、地域冗余、retention、RPO/RTO SLA或legal hold。

## 触发条件

- 部署/升级前需要冻结恢复点；
- 数据库故障后需要验证backup可读及恢复身份；
- 例行P8-10恢复演练或backup指纹告警。

## 影响与安全边界

备份前必须停止API写流量及全部Worker。只允许`plantnexus_dev`和一次性`plantnexus_restore_drill`；synthetic sentinel位于`p8_operations_drill` schema。Raw dump不上传、不写仓库，恢复完成即销毁。不得在Production数据库创建演练schema或执行本Runbook。

## 前置权限

Operator需要Task靶场内的`pg_dump`、`pg_restore`、`createdb`、`dropdb`权限和target-scoped Docker权限，不需要外部对象存储或Production DBA权限。密码由脚本每次生成且不得复制到报告。

## 执行步骤

1. 由完整P8-10演练器停止`api`与`worker`，确认备份点处于`QUIESCED_API_AND_WORKERS`。
2. 创建namespaced synthetic sentinel，读取Alembic head及排序后的`public`/演练schema元数据指纹。
3. 使用`pg_dump --format=custom --no-owner --no-acl`获取内存中的raw backup并计算SHA-256。
4. 对副本翻转一个byte并确认checksum mismatch在restore前被拒绝，触发`APSBackupOrRestoreFailed`。
5. 创建一次性restore database，使用`pg_restore --no-owner --no-acl`恢复，再复算migration head、schema fingerprint和sentinel fingerprint。
6. 三类指纹全部相同后删除restore database、释放raw bytes，并重启API/Worker。

## 验证

`p8-10-recovery.json`中的source/restored对象必须逐字相同，migration head=`0009_host_authorization_audit`，sentinel count=`1`，corruption detection=true，raw backup retained=false。Elapsed只用于本次工程观察，不与SLA比较。

## 回退

恢复任一步失败即保留原数据库、停止promotion并隔离restore database；禁止覆盖唯一backup或用downgrade掩盖失败。若候选数据库已升级，恢复升级前已验证backup后才允许重新部署旧Runtime；无backup时只走具名审批的forward fix。

## 升级与责任

工程operator执行演练，database owner判断真实介质、加密与retention，security owner审批Production密钥/存储，incident authority决定真实恢复。P8-10没有为后三者具名或授权。

## 最近演练记录

2026-09-07由TASK-P8-10对一次性PostgreSQL 17.6靶场执行。exact Provider证据在Task Card闭环时登记；不覆盖真实数据量、并发写入、PITR、跨区恢复或Production RPO/RTO。
