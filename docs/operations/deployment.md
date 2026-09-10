---
doc_id: DOC-OPS-DEPLOY-001
title: APS Runtime 安装、预检与启动顺序
status: baseline
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [65, 93, 95, 97, 98, 99, 100, 101, 106, 107, 113, 114]
last_reviewed: 2026-09-10
---

# APS Runtime 安装、预检与启动顺序

本页定义P8-09起始、P8-13扩展后的Runtime工程候选可重复安装与fail-closed启动顺序，记录TASK-P8-10隔离Compose靶场对当前声明Runtime身份的真实部署结果，并说明P8-11可选Frontend的独立分发边界。它不授予Production部署、签名或发布权限。

P8-17 Exit只把本页既有部署、可观测、备份恢复、Runbook和Extension-enabled target证据作为fresh审计输入，不创建新的部署target或promotion。候选SHA的独立operations演练通过，但FULL中的第二次演练在broker恢复后依赖Celery进程自行重连并出现`WORKER_PROBE_FAILED`；TASK-P8-20因此固定为“Redis/API ready后显式restart同一exact image/config Worker，再等待具名pong”。该纠正不改变target或Runtime identity。即使后续Exit为`READY`，内部交付也只能标记为`TEST/SIMULATION`，不能省略真实环境preflight、身份/authority、数据备份责任或Production Gate。

## TASK-P8-18 Extension-enabled target

P8-18把`p8-operations-compose-v1`前移到纠正Runtime implementation `7369e9c1238bae36f278423edb1977124d07faa9`，归档SHA-256为`6ba13ea22b1032fdd1e67a09e1045dac9307f7597b71c5003fdf9fe680c92cee`，release fingerprint为`sha256:9c67fcfd3991d48acf4d05d3fae54ed7b82edddd4471b2642932c1faf71fac40`。目标锁定Alpha `1.0.0` artifact/config、Developer Kit `1.0.0` fingerprint及`runtime-http-policy.v2`，仍仅用于一次性`TEST/SIMULATION`。

非空Extension启动除catalog/key三元组外，还必须成组设置`PLANTNEXUS_DEVELOPER_KIT_VERSION`、`PLANTNEXUS_DEVELOPER_KIT_FINGERPRINT`和固定部署provider `PLANTNEXUS_RUNTIME_EXTENSION_ARTIFACT_PROVIDER=<module>:<callable>`。Provider由发布/部署方拥有，只能从本地read-only批准输入materialize精确artifact tuple；不能扫描entry point、联网、安装包、接受请求选项或hot reload。显式artifact与provider并存、provider超时/异常、集合未排序/重复、artifact/catalog/Kit不一致都必须在Runtime composition前失败。

API与Worker启动后必须读取descriptor并逐字比较Runtime、Kit、Extension set/config和composition fingerprint。备份点、恢复后进程与rollback slot还必须保留同一Extension identity；仅数据库恢复成功不足以promotion。本地完整演练已验证这些检查和10类告警/6份Runbook，仍不代表Production trust、签名、HA、容量或SLA。

## TASK-P8-15 Developer Kit policy隔离

P8-10保留靶场继续冻结其已验证Runtime代码、Schema、migration、镜像输入和两份既有Runtime release/vulnerability policy。`infra/release/developer-kit-release-policy.v1.json`只控制独立Developer Kit组装，不进入Runtime归档或Compose镜像，因此不属于该历史靶场的Runtime输入；运维checker以两份Runtime policy精确路径替代宽目录匹配。任一Runtime policy或其他既有输入漂移仍返回`RUNTIME_INPUT_DRIFT`，该收窄不更新P8-10 Runtime身份、不启用Extension，也不产生新的部署授权。

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

当且仅当启用企业Extension集合时，还必须由部署平台成组提供`PLANTNEXUS_RUNTIME_EXTENSION_CATALOG_PATH`、`PLANTNEXUS_RUNTIME_EXTENSION_VERIFICATION_KEY_ID`和SecretStr承载的`PLANTNEXUS_RUNTIME_EXTENSION_VERIFICATION_KEY`，并按上节提供精确Kit身份和唯一artifact provider。catalog缺失且无provider时保持default-empty；任一原子组不完整、catalog/manifest/config/artifact越界、digest/HMAC/版本/capability不一致均必须在数据库连接和业务调用前fail closed。禁止请求级上传、远程下载、hot load或运行时安装。

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

P8-10首次在PostgreSQL 17.6空库实际执行时发现：Alembic自动创建的`alembic_version.version_num varchar(32)`无法保存超过32字符的既有revision ID，裸升级在`0003→0004_schedule_versions_audit_export_jobs`处正确失败。P8-10不得改写已经发布的migration或Runtime，因此`p8-operations-compose-v1`在Alembic首次运行前幂等执行：

```sql
CREATE TABLE IF NOT EXISTS alembic_version (
  version_num VARCHAR(128) NOT NULL PRIMARY KEY
);
```

随后仍运行归档内未修改的线性chain到`0009_host_authorization_audit`。部署平台必须把该bootstrap作为可审计步骤并验证最终column/head；未来Runtime release应决定是否将其正式产品化。不得用手工截断revision、修改version row或忽略失败替代。

## 4. 启动顺序与健康检查

建议顺序为数据库/Redis/broker可用 → migration exact head → Worker → API → 宿主平台流量。进程入口为：

```text
.venv/bin/celery -A app.jobs.celery_app:celery_app worker
.venv/bin/uvicorn app.api.app:app --host 0.0.0.0 --port 8000
```

先检查`/health/live`，再检查依赖感知的`/health/ready`。只有readiness通过、Runtime resolution fingerprint与release identity一致、identity/authorization/audit adapter可用时，宿主平台才可通过统一Headless HTTP API提交canonical JSON。未配置catalog时Extension集合必须为`EXTENSION-SET-NONE`；配置catalog时只能装载服务端启动配置中allow-list且完整性、SDK/Runtime兼容性、capability和Registry逐值复核均通过的trusted in-process Extension。当前P8-10 Compose靶场仍保持空集合，不构成企业Extension认证或恶意代码沙箱。

## 5. 失败与隔离

失败artifact继续保留在其content address中并标记禁止promotion，不得覆盖、改名冒充或删除报告。preflight失败、migration drift、依赖/VEX变化、secret/config缺失、Runtime fingerprint不一致、Worker/API角色不一致或readiness失败都必须保持服务不接收业务流量。诊断只记录稳定code、版本、fingerprint和配置名称，禁止记录DSN、token、claim、canonical payload、绝对部署路径或stack。

派生OCI镜像必须以同一归档/manifest作为输入并增加不可变image digest；仓库Dockerfile的label和build结果本身不构成Production签名镜像。

## 6. P8-10可执行靶场与证据

[`../../infra/operations/non-production-target.v1.json`](../../infra/operations/non-production-target.v1.json)当前固定P8-13 Runtime输入SHA `9818d0b6686ff005d0ea48ae81f3a306a5b36172`、可复现archive digest `sha256:ee48bdd3245d83f7f87e1205c77aa69639b693120d13b6f80364a7dbecb1013f`、release fingerprint `sha256:1a06018df48a7a22cd434d8076c02768b09da4ef3dfed35dd45d1b34474c70cc`、digest-pinned PostgreSQL/Redis、operator、secret/storage及recovery边界；[`../../infra/operations/compose.p8-operations.yml`](../../infra/operations/compose.p8-operations.yml)只叠加到development Compose，不改变其默认行为。operations checker先验证当前checkout相对声明SHA的全部Runtime build inputs零漂移，再构建镜像；不能以新代码冒充旧release。内部`observer`通过Compose DNS执行health探针，无需开放外部ingress。

[`../runbooks/headless-deployment-and-rollback.md`](../runbooks/headless-deployment-and-rollback.md)规定部署与dual-slot顺序。机器演练必须验证8项deployment checks、API/Worker/Validator、Runtime/Extension descriptor及清理；rollback slot先ready后停止candidate，从而证明last-known-good配置切换。当前两个slot使用同一P8-13 exact Runtime输入且Extension为空，所以`cross_version_rollback=false`；Kubernetes、HA、真实企业Extension、真实流量网关和跨版本回退仍未验证。

## 7. P8-11可选Frontend独立分发

Frontend与Runtime是两个互不嵌套的工程制品。Runtime继续按第1～6节安装，并由P8-11 backend-only smoke从解出的wheel在隔离解释器内启动`app.api.app`，验证liveness、readiness、OpenAPI和5项Headless route，同时确认release inventory、wheel及HTTP route均不含Frontend。Frontend归档不进入Runtime archive、镜像、migration或进程启动条件。

在仓库固定Node/npm和exact lock下，从`frontend/`执行：

```text
npm run client:check
npm run build:headless
npm run package:headless
```

输出为`build/frontend/plantnexus-aps-frontend-0.1.0.tar.gz`、旁置`.sha256`和`frontend-distribution-manifest.v1.json`。构建入口为`headless.html`，相对asset base允许静态托管；无source map。打包器以固定tar metadata和gzip时间组装两次并要求byte-identical，manifest逐文件记录size/digest、OpenAPI digest、commit、认证/缓存配置、部署模式和`production_ready=false`。部署前必须核对sidecar与manifest，不得加入Backend/Core/Solver、Demo、Enterprise Extension、credential或运行数据。

首选部署模式是在Runtime/API同一origin提供静态文件，Frontend默认请求`/api/v1`。也可独立发布静态归档，但必须由获批gateway把公开API呈现为同源路径；P8-11未增加CORS，不能把任意cross-origin host视为已支持。宿主bootstrap只可在模块加载前注入内存`window.__PLANTNEXUS_APS_SESSION_PROVIDER__`，不能把token写入静态配置、URL、cookie或browser storage；未注入时保持不可用并fail closed。

Frontend可以晚于或早于兼容Runtime独立回退：停止提供当前静态归档并恢复上一份经同一OpenAPI/Chromium Gate验证的归档即可，不修改Runtime、数据库或业务状态。部署promotion仍需另行批准的TLS、gateway/SSO、CSP/WAF、浏览器矩阵、监控、UAT和支持责任；当前归档只是repository engineering candidate。
