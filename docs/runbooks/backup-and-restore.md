---
doc_id: DOC-RUNBOOK-P8-BACKUP-001
title: PostgreSQL 备份与恢复演练
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [65, 91, 92, 95, 101, 103, 106, 113, 114]
last_reviewed: 2026-09-10
---

# PostgreSQL 备份与恢复演练

TASK-P8-10使用PostgreSQL custom-format dump验证migration head、完整schema及namespaced synthetic sentinel的恢复一致性；P8-18进一步要求Extension-enabled Runtime在备份点、恢复后API/Worker和rollback slot保持相同Extension set/config/Developer Kit identity。该机制是非Production工程证据，不定义真实backup产品、加密密钥、地域冗余、retention、RPO/RTO SLA或legal hold。

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
6. 三类数据库指纹全部相同后删除restore database、释放raw bytes，并重启API/Worker。
7. 分别读取重启后API与Worker descriptor，确认Extension set/config、Developer Kit version/fingerprint和composition identity与备份点逐字相同；任一漂移都视为恢复失败。

## 验证

恢复报告中的source/restored对象必须逐字相同，migration head=`0009_host_authorization_audit`，sentinel count=`1`，corruption detection=true，raw backup retained=false。P8-18报告还必须满足`extension_identity_at_backup_point == extension_identity_after_restore == rollback.extension_identity`且`extension_identity_match=true`。Elapsed只用于本次工程观察，不与SLA比较。

## 回退

恢复任一步失败即保留原数据库、停止promotion并隔离restore database；禁止覆盖唯一backup或用downgrade掩盖失败。若候选数据库已升级，恢复升级前已验证backup后才允许重新部署旧Runtime；无backup时只走具名审批的forward fix。

## 升级与责任

工程operator执行演练，database owner判断真实介质、加密与retention，security owner审批Production密钥/存储，incident authority决定真实恢复。P8-10没有为后三者具名或授权。

## 最近演练记录

2026-09-10由TASK-P8-18对一次性PostgreSQL 17.6、Alpha Extension和Kit-locked Runtime重新执行，数据库与Extension identity恢复检查本地PASS。exact Provider证据在Task Card闭环时登记；不覆盖真实数据量、并发写入、PITR、跨区恢复或Production RPO/RTO。
