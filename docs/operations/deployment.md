---
doc_id: DOC-OPS-DEPLOY-001
title: APS Runtime 安装、预检与启动顺序
status: baseline
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [65, 93, 95, 97, 98, 99, 100, 101, 106, 107, 113, 114]
last_reviewed: 2026-09-07
---

# APS Runtime 安装、预检与启动顺序

本页定义P8-09工程候选的可重复安装与fail-closed启动顺序。它是未来部署Runbook的输入，不授予Production部署、签名或发布权限。

## 1. 固定输入并验证传输

操作者必须固定完整的content-addressed归档路径和旁置`.sha256`，记录期望的Runtime版本、40字符Git SHA、目标`linux/amd64`及数据库备份点。先用平台标准SHA-256工具核对sidecar，再调用Runtime preflight；不得只依赖文件名或容器tag。

Preflight只接收已配置的环境变量名称，不读取或输出secret value。下列名称必须由部署平台显式提供：

- `PLANTNEXUS_DATABASE_URL`
- `PLANTNEXUS_REDIS_URL`
- `PLANTNEXUS_CELERY_BROKER_URL`
- `PLANTNEXUS_CELERY_RESULT_BACKEND_URL`
- `PLANTNEXUS_RUNTIME_SCHEMA_DIRECTORY`
- `PLANTNEXUS_RUNTIME_PLANNING_POLICY_PATH`
- `PLANTNEXUS_RUNTIME_SOLVE_LIMITS_PATH`
- `PLANTNEXUS_RUNTIME_HTTP_POLICY_PATH`

此外，运行平台必须显式设置environment/data plane、`PLANTNEXUS_CODE_COMMIT`、`PLANTNEXUS_RUNTIME_COMPOSITION_ENABLED=true`及P8-08身份/授权policy adapter所需的外部配置。值不得写入归档、报告、命令历史或版本库。

在安装wheel后可执行：

```text
python -m app.infrastructure.release.preflight \
  --archive <content-addressed-runtime.tar.gz> \
  --expected-runtime-version 0.1.0 \
  --expected-code-commit <40-character-git-sha> \
  --configured <required-name> ... \
  --report <ignored-preflight-report.json>
```

任何checksum、manifest fingerprint、版本/commit/target、SBOM/license、migration、Extension边界或配置名称不一致必须返回非零且停止。

## 2. 解包与hash-locked安装

只允许使用拒绝绝对路径、`..`、反斜杠、重复成员、symlink/hardlink和超限展开的安全解包器。进入归档的`runtime/`目录后创建clean Python 3.12环境：

```text
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python --require-hashes \
  -r requirements/runtime-requirements.lock
uv pip install --python .venv/bin/python --no-deps wheels/*.whl
```

Windows命令仅用于工程复验时把解释器路径改为`.venv/Scripts/python.exe`；权威distribution target仍是Linux/amd64。安装后应在隔离模式import `app.api.app`、`app.jobs.planning_run_solver_worker`和独立`ProblemScheduleValidator`，并核对Runtime/Application/Core/Schema版本。

## 3. 数据库迁移

迁移前停止API写流量与Worker领取新任务，完成数据库备份并验证可恢复性。使用同一归档中的`alembic.ini`与`backend/migrations`：

```text
.venv/bin/alembic -c alembic.ini upgrade 0009_host_authorization_audit
```

必须确认数据库head恰好为release manifest声明值，然后才允许启动进程。禁止从其他checkout拼接migration、改写旧revision或在升级失败后继续启动。生产回退优先恢复备份和上一份获批artifact；直接downgrade会删除后继表/数据，只有显式审批、已验证备份和可接受数据损失时才可执行。

## 4. 启动顺序与健康检查

建议顺序为数据库/Redis/broker可用 → migration exact head → Worker → API → 宿主平台流量。进程入口为：

```text
.venv/bin/celery -A app.jobs.celery_app:celery_app worker
.venv/bin/uvicorn app.api.app:app --host 0.0.0.0 --port 8000
```

先检查`/health/live`，再检查依赖感知的`/health/ready`。只有readiness通过、Runtime resolution fingerprint与release identity一致、identity/authorization/audit adapter可用时，宿主平台才可通过统一Headless HTTP API提交canonical JSON。Extension集合必须保持`EXTENSION-SET-NONE`；当前release不得加载企业代码。

## 5. 失败与隔离

失败artifact继续保留在其content address中并标记禁止promotion，不得覆盖、改名冒充或删除报告。preflight失败、migration drift、依赖/VEX变化、secret/config缺失、Runtime fingerprint不一致、Worker/API角色不一致或readiness失败都必须保持服务不接收业务流量。诊断只记录稳定code、版本、fingerprint和配置名称，禁止记录DSN、token、claim、canonical payload、绝对部署路径或stack。

派生OCI镜像必须以同一归档/manifest作为输入并增加不可变image digest；仓库Dockerfile的label和build结果本身不构成Production签名镜像。远程registry、Kubernetes、HA、滚动/蓝绿、on-call、告警和retention仍由P8-10及后续具名工作形成。
