---
doc_id: DOC-RUNBOOK-P8-WORKER-001
title: Solver Worker 停滞与恢复
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [59, 60, 61, 62, 65, 95, 101, 103, 113, 114]
last_reviewed: 2026-09-07
---

# Solver Worker 停滞与恢复

本Runbook沿用P8-05的lease、heartbeat、late ACK、retry与dead-letter合同，并由TASK-P8-10验证容器级Worker停止可被探测和恢复。它不会手工把PlanningRun改成COMPLETED，也不是Production容量或并发调优指南。

## 触发条件

- `APSWorkerUnavailable`告警；
- Celery ping无`pong`、heartbeat过期或队列深度持续增加；
- Worker进程丢失、broker重连失败或部署回退需要排空/替换Worker。

## 影响与安全边界

只操作Task靶场Worker。Late ACK与repository lease仍是业务一致性边界；禁止直接更新PlanningRun/attempt表、伪造heartbeat、清空broker队列或删除dead-letter证据。Production Worker扩缩容必须另行授权。

## 前置权限

Operator需要读取Worker ping、broker depth、sanitized job/run/correlation reference并能停止/启动指定Compose service。不需要读取canonical payload或数据库credential。

## 执行步骤

1. 记录Worker ping、broker depth、Runtime composition fingerprint和当前slot。
2. 停止`worker`并确认ping失败、`APSWorkerUnavailable` fired；API是否ready必须单独判断，不能用API liveness替代Worker健康。
3. 检查broker是否可用；若broker故障先按依赖Runbook恢复，不要连续重启Worker制造重投。
4. 启动相同exact image/config Worker，等待ping出现`pong`并确认composition fingerprint与API一致。
5. 若执行dual-slot回退，先启动`rollback_worker`并通过ping，再停止candidate Worker。

## 验证

`p8-10-deployment.json`的Worker检查为PASS；`p8-10-observability.json`记录告警fired/resolved及broker queue depth。任何API/Worker Runtime、Core、SDK、Extension-set或Validator identity不一致都必须拒绝领取/发布结果。

## 回退

新Worker不能恢复时保留失败attempt/audit，切回last-known-good Worker slot；不要回滚业务状态。若数据库/queue一致性无法证明，停止所有Worker并升级，不允许以ack或删除消息换取绿色。

## 升级与责任

runtime owner负责镜像与composition，queue owner负责broker，planning owner负责业务重试语义。Production on-call、重试预算和capacity阈值仍未批准。

## 最近演练记录

2026-09-07由TASK-P8-10执行candidate Worker stop/start和rollback Worker preflight。该演练无真实PlanningRun负载，不替代P7容量或Production长任务恢复验证。
