---
doc_id: DOC-RUNBOOK-P8-DEPLOY-001
title: Headless Runtime 部署与双 slot 回退
status: baseline
spec_version: 0.3.0
phase: P8
normative: false
source_sections: [6, 12, 65, 91, 92, 95, 101, 103, 106, 113, 114]
last_reviewed: 2026-09-07
---

# Headless Runtime 部署与双 slot 回退

本Runbook由TASK-P8-10建立，只适用于`p8-operations-compose-v1`和P8-09 exact Runtime `0.1.0`。它验证可重复工程部署及同一不可变artifact的last-known-good配置回退，不声称已经验证跨版本downgrade、零停机Production发布或流量网关。

## 触发条件

- 新建一次性P8-10靶场；
- candidate API/Worker启动失败、readiness持续DOWN或版本/组合指纹不一致；
- 需要验证回退slot在candidate停止前已经ready。

## 影响与安全边界

只能使用`TEST/SIMULATION`、synthetic payload和Task专用Compose project。不得指向Production endpoint、复用真实volume、加载Extension、上传raw dump或把演练耗时解释为SLA。回退不能修改PlanningRun、ScheduleVersion或append-only audit来伪造成功。

## 前置权限

Operator必须是`repository-engineer`或`github-actions:p8-operations`，能使用本地Docker、读取仓库和创建/销毁`plantnexus-p8-10`资源。无需也不得提供Production credential、registry promotion或业务审批权限。

## 执行步骤

1. 确认`git status --short`没有修改P8-09 Runtime输入，并核对target manifest中的40字符implementation SHA、release archive digest和release fingerprint。
2. 从仓库根运行索引中的`p8_operations_check.py`完整命令。脚本构建带P8-09 revision label的镜像，解析双Compose文件，启动PostgreSQL/Redis并执行`alembic upgrade head`。
3. 等待candidate API `/health/live`和`/health/ready`、Worker ping及Validator import全部PASS，再读取Runtime composition/Extension-set指纹。
4. 回退时先启动`rollback_api`和`rollback_worker`，确认`http://127.0.0.1:8001/health/ready`和Worker ping均PASS；随后停止candidate slot，并把工程探针选择切到rollback slot。
5. 由脚本在`finally`中对明确的Compose project执行`down --volumes --remove-orphans`。不要手工扩大清理路径。

## 验证

`p8-10-deployment.json`必须为PASS且包含8项检查；image revision必须等于P8-09 implementation、Runtime=`0.1.0`、live/ready=`UP`、Validator=`PASS`。`p8-10-recovery.json`必须记录rollback slot切换前后均ready，image和composition identity一致，且`cross_version_rollback=false`。

## 回退

若candidate启动或身份检查失败，不允许promotion；保留sanitized FAIL报告，启动/保留last-known-good slot并停止candidate。若数据库已发生变更，先按[备份与恢复](backup-and-restore.md)恢复冻结点，再重启旧slot。没有可验证备份时不得Alembic downgrade，应转交批准的forward fix。

## 升级与责任

工程operator负责停止演练和保存报告；runtime owner负责artifact/版本漂移；database owner负责恢复失败。真实on-call、发布经理和Production升级链仍未具名，任何真实上线必须单独补齐并授权。

## 最近演练记录

2026-09-07由TASK-P8-10在本地和exact-SHA Provider靶场执行；权威run/job/artifact在Task Card闭环时登记。当前记录只覆盖同artifact dual-slot配置回退，不覆盖未来Runtime或Developer Kit跨版本升级。
