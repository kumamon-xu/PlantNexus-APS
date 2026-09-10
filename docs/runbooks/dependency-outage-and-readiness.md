---
doc_id: DOC-RUNBOOK-P8-READINESS-001
title: API、数据库与 Broker 故障及 Readiness
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [59, 60, 61, 62, 65, 95, 101, 103, 113, 114]
last_reviewed: 2026-09-07
---

# API、数据库与 Broker 故障及 Readiness

TASK-P8-10验证liveness只表示进程存活，readiness才决定能否接收流量。PostgreSQL或Redis不可用时API必须返回sanitized 503，且不泄露driver、endpoint或credential。本Runbook不是Production负载均衡器或HA方案。

## 触发条件

- `APSApiUnavailable`、`APSReadinessDown`、`APSDatabaseUnavailable`或`APSBrokerUnavailable`告警；
- `/health/ready`为DOWN或Worker无法连接broker；
- fault drill要求验证依赖隔离与恢复。

## 影响与安全边界

只在Task Compose project内停止单个service。不得停止主机级Docker、删除非Task volume、修改业务terminal state或向Production注入故障。Health响应只能含稳定dependency code和build metadata。

## 前置权限

Operator需读取sanitized health/alert报告并能启动/停止`api`、`database`、`redis`服务。无需数据库内容读取权或业务审批权；不能通过将probe硬编码为PASS绕过故障。

## 执行步骤

1. 先记录live/ready基线及Runtime revision。
2. API故障：停止candidate API，确认live连接失败并触发`APSApiUnavailable`；重启后等待ready恢复。
3. Broker故障：停止Redis，确认live仍UP、ready=503且`redis/REDIS_UNAVAILABLE`，触发broker和readiness告警；重启Redis并等待API ready后，显式restart同一exact image/config Worker，再等待具名Celery `pong`和composition identity一致。不得依赖Worker进程是否自行重连。
4. Database故障：停止PostgreSQL，确认live仍UP、ready=503且`database/DATABASE_UNAVAILABLE`；重启并等待ready恢复。
5. 每次只注入一个故障，告警必须有fired和resolved两个状态；恢复前禁止切回traffic。

## 验证

`p8-10-observability.json`必须记录两次依赖故障期间liveness=`UP`、readiness=`DOWN`，对应四类alert全部fired/resolved。响应和报告不得出现URL、password、stack或canonical payload。

## 回退

依赖无法恢复时保持readiness DOWN、停止新流量和Worker，并按[事件分诊](incident-triage-and-escalation.md)升级。数据库可能损坏时不要反复重启，转到[备份与恢复](backup-and-restore.md)。API artifact异常时转到[部署回退](headless-deployment-and-rollback.md)。

## 升级与责任

工程operator负责单服务隔离；database/broker/runtime owner分别诊断对应依赖。Production on-call、云平台owner和业务影响通知链仍是OPEN，不得从本演练推断。

## 最近演练记录

2026-09-10由TASK-P8-20根据P8-17候选中保留的Worker probe失败，把broker恢复procedure确定为“Redis/API ready → 显式restart锁定Worker → 具名pong”。这不是产品自动恢复或HA；没有执行真实负载、网络分区、磁盘耗尽、多副本选主或Production failover。
