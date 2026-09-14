---
doc_id: DOC-RUNBOOK-P8-BACKUP-001
title: PostgreSQL 备份与恢复演练
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [65, 91, 92, 95, 101, 103, 106, 113, 114]
last_reviewed: 2026-09-14
---

# PostgreSQL 备份与恢复演练

TASK-P8-10使用PostgreSQL custom-format dump验证migration head、完整schema及namespaced synthetic sentinel的恢复一致性；P8-18进一步要求Extension-enabled Runtime在备份点、恢复后API/Worker和rollback slot保持相同Extension set/config/Developer Kit identity。该机制是非Production工程证据，不定义真实backup产品、加密密钥、地域冗余、retention、RPO/RTO SLA或legal hold。

## P8-26 企业脚本备份与隔离恢复

本节适用于新的企业Compose脚本，后续P8-10/P8-18旧靶场步骤保持其历史范围。参数前七项与[部署入口](../operations/deployment.md#p8-26-shell-运维入口)一致；仅使用已校验预构建镜像、明确TEST/SIMULATION目标和只读配置/Secret。

```text
<bundle>/infra/enterprise/scripts/backup.sh <bundle> <manifest-sha256> <sha256:image-id> <source-slot> <source-project> <port> standalone <new-absolute-backup-directory> QUIESCE-<source-project>
<bundle>/infra/enterprise/scripts/restore.sh <bundle> <manifest-sha256> <sha256:image-id> <restore-slot> <new-project> <new-port> standalone <backup-directory> <backup-manifest-sha256> TARGET-<new-project>
<bundle>/infra/enterprise/scripts/rollback.sh <bundle> <manifest-sha256> <sha256:image-id> <verified-slot> <new-project> <new-port> standalone <backup-directory> <backup-manifest-sha256> TARGET-<new-project>
```

备份前由operator停止外部写入并确认没有其他共享数据库的Worker。QUIESCE参数授权停止本project API/Worker；脚本先取得并比较健康进程descriptor和已验证slot的完整配置文件摘要，然后停止二者、检查exact head，用锁定PostgreSQL客户端生成custom-format dump。备份成功仍保持API/Worker停止，operator决定何时用start恢复。新目录在同文件系统临时目录完成后原子发布；已有目录绝不覆盖。失败可保留私有`.p826-backup-*`候选供诊断，未完整生成并校验SHA256SUMS的候选不能用于恢复。

备份包括database.dump、API/Worker安全descriptor、`enterprise-backup.v1` metadata与SHA256SUMS。metadata绑定image ID、source project、数据库exact head、Runtime/Kit/Extension/config身份、完整非敏感配置文件集合摘要及dump SHA-256。backup输出的manifest摘要须与备份分开保管；restore同时要求该期望摘要和TARGET确认，任一缺失或不符在数据恢复前拒绝；当前配置文件字节必须与备份一致，不能靠保留旧validated.json冒充已验证slot。文件默认0700目录/0600备份，不进入Provider、交付包或公开日志；介质加密、retention、密钥和真实RPO/RTO仍由环境责任方审定。

恢复仅面向不同于source project的停止中隔离目标及空数据库和空Redis/broker/result索引，拒绝任何已有业务表的数据库；不提供overwrite、dropdb、删卷或downgrade选项。外部依赖模式还须由operator提供专属隔离DB/Redis并确认无其他使用者。pg_restore使用single-transaction/exit-on-error；失败不删除原数据库或备份，API/Worker不放行。恢复后检查head，启动同image/config，验证TLS readiness、具名Worker pong和完整descriptor与备份一致，任何漂移都停止API/Worker。

rollback使用相同隔离恢复流程，额外要求slot保留先前成功安装生成的validated.json，且image ID和组合身份逐字等于备份。它恢复已验证的同版本配置slot，不做原地跨版本回退、不切换外部流量、不改Core/Kit或旧migration。原目标保留，由operator核对恢复结果后另行决定路由。Redis作为新broker恢复，备份不声称保存或重放队列中的任务；真实恢复前仍需审定在途任务处置策略。

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
