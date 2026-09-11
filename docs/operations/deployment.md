---
doc_id: DOC-OPS-DEPLOY-001
title: APS Runtime 安装、预检与启动顺序
status: baseline
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [65, 93, 95, 97, 98, 99, 100, 101, 106, 107, 113, 114]
last_reviewed: 2026-09-11
---

# APS Runtime 安装、预检与启动顺序

## 企业双模式 Compose

`infra/enterprise/compose/docker-compose.enterprise.yml`只定义migrate、API、Worker与按需Validator，连接显式配置的外部PostgreSQL/Redis。`docker-compose.standalone.yml`是覆盖文件，增加`dependencies.v1.json`固定版本/digest的PostgreSQL、Redis和独立具名数据卷，不继承开发或历史operations Compose。两种模式仅用于TEST/SIMULATION。

部署前必须持有经Provider及SHA-256核验的镜像报告与已加载镜像。`control.py`使用宿主Python标准库和Docker/Compose；它检查approved report、local image ID、linux/amd64、UID和封装/Runtime labels，将四角色固定到同一`sha256:<image ID>`并禁止pull。输入可以是报告中的exact tag、本地image ID或已加载且RepoDigest一致的registry digest；tag指向错误镜像立即拒绝。没有registry推送时，不把本地image ID或tar digest称作registry digest。依赖镜像必须提前加载到本地，standalone不会隐式下载；版本未升级，不产生新的Production安全批准。

准备两个显式绝对目录：非敏感配置目录包含`deployment.env`、policy、TLS证书和可选Extension wheel/manifest/config/catalog/lock；独立Secret目录只通过只读挂载成为`/run/secrets`，包含`db_user/db_password`、`redis_user/redis_password`、`broker_user/broker_password`、`result_user/result_password`、`identity_token`、`tls_key`。Extension local模式另提供`extension_key`并在env引用该路径。bootstrap与配置也只读挂载，不传Docker socket、源码或宿主隐式目录。Linux文件权限必须允许容器UID 10001读取，Secret值不得经Compose插值；不要照搬测试fixture的公开合成文件权限处理真实密钥。

所有env路径按容器路径填写：配置根`/etc/plantnexus`、Secret根`/run/secrets`，`API_BIND=0.0.0.0`、`API_PORT=8000`、`DATA_VOLUME=/var/lib/plantnexus`、`BACKUP_VOLUME=/var/backups/plantnexus`。不匹配会被拒绝。资源限额取自同一env并作用于Compose，Worker并发仍由bootstrap传入。standalone要求DB host为`database:5432`，Redis/broker/result为`redis:6379`，三个不同Redis index，共用default用户与相同密码文件内容；enterprise可以显式分配不同既有实例/ACL。PostgreSQL与Redis不发布宿主端口，standalone网络禁止外部出口。

```text
python infra/enterprise/compose/control.py config --mode standalone --image-report <verified-image-report.json> --reference <exact-image-reference> --config-dir <absolute-config-dir> --secrets-dir <absolute-secret-dir> --project <isolated-project> --port <loopback-tls-port> --output <rendered-compose.json>
python infra/enterprise/compose/control.py up --mode standalone --image-report <verified-image-report.json> --reference <exact-image-reference> --config-dir <absolute-config-dir> --secrets-dir <absolute-secret-dir> --project <isolated-project> --port <loopback-tls-port>
```

企业已有依赖模式改为`--mode enterprise`。此控制入口只负责固定镜像与首次/停止后的Compose启动；运行中的API/Worker会拒绝直接重新部署，后续受控启停、安装、备份恢复及离线包分别由相邻运维任务交付。不要绕过身份门直接用可变tag执行up。

启动顺序为只读配置预检→依赖连通→执行已发布migration到`0009_host_authorization_audit`并复核exact head→具名Worker健康→API。新库预先建立VARCHAR(128)的Alembic版本表以容纳已发布长revision，沿用已验证部署方法，不改migration文件或业务Schema。未知revision、迁移异常、DB/Redis/broker/result不可用均非零；API/Worker入口自身再次检查head和依赖。Worker以`aps@aps-worker`运行，探针要求exact具名pong与本进程descriptor；API和Worker记录实际factory生成的相同Runtime/Kit/Extension组合身份。

API直接使用配置的TLS证书/私钥，仅发布宿主loopback端口。健康探针验证证书信任、有效期与`API_DOMAIN`主机名，并访问既有`/health/ready`；内部模板proxy不作为此栈的额外服务。真实入口域名、受信证书、代理、企业网络与SSO仍需环境责任方提供，不由本次合成演练证明。认证仍为显式LOCAL_TEST_TOKEN，不能外推Production。

Validator默认不启动，独立profile使用同一镜像、`network_mode: none`及全只读输入挂载。把既有canonical Problem/Candidate放在配置目录的`validation/problem.json`与`validation/candidate.json`，用经身份门生成的Compose执行`docker compose -p <same-project> -f <rendered-compose.json> run --rm --no-deps validator`。原独立Validator真实判定，失败非零；部署日志只保留状态与违例计数，不输出业务payload。

普通`down`保留PostgreSQL/Redis具名卷，重新up后复核exact head与readiness。只有明确一次性合成靶场才允许`down --volumes`；实际数据卷和备份不得按演练清理。该持久化重建证明不是备份恢复、跨版本回退、完整离线安装或容量/SLA结论。

## 企业配置与 Secret 预检

`infra/enterprise/config/`提供`.env.example`、Planning Policy/Solve Limits、Runtime HTTP policy、authorization policy、Extension catalog/lock、reverse-proxy TLS和Docker Secret/资源接线模板；`configuration-matrix.v1.json`逐项列出必填条件、值的来源、注入位置与验证责任。占位符不构成可运行配置；JSON中的数值占位符须替换为原合同要求的数值类型，不能删除硬约束或猜测业务值。资源值仅为操作者评审的TEST/SIMULATION限额，不代表容量或SLA。

外层bootstrap以只读挂载消费既有镜像，应用wheel与Core不变。把bootstrap目录挂载为`/opt/enterprise/bootstrap:ro`，非敏感配置与policy挂载为只读文件，Secret挂载为独立只读文件；工作目录为`/opt/enterprise`。启动前执行：

```text
python -m bootstrap.run --config /etc/plantnexus/deployment.env --check
python -m bootstrap.run --config /etc/plantnexus/deployment.env --role api
```

`--role`支持api、worker、migration和validator。前两者经既有Runtime factory运行，migration执行已发布Alembic链到head；validator仅验证既有独立函数入口，不新增业务输入协议。全部角色先执行相同预检，错误非零且仅输出稳定code/field；不使用shell source、dotenv隐式加载或请求选择配置。必须使用Linux只读rootfs/挂载，非Linux预检不宣称已验证只读性。`secrets.example.yml`只演示禁网预检接线，不是P8-25完整部署栈。

DB、Redis、broker和result backend的host/port/database非敏感字段与username/password Secret分离；bootstrap在内存中进行URL编码，传入显式Settings与进程环境，不把凭据放入命令行或Compose插值。`DATA_VOLUME/BACKUP_VOLUME`必须为不重叠绝对路径；CPU/内存由Compose实施，Worker并发由Celery参数实施，TLS域名/上游由操作者填写proxy模板。SSL预检验证证书/私钥可加载且匹配，域名、证书信任/有效期与代理部署仍需后续环境验收。

唯一已形成认证适配为`IDENTITY_PROVIDER=LOCAL_TEST_TOKEN`，且`ENVIRONMENT=test`、`DATA_PLANE=simulation`；Issuer/Audience与授权policy必须相同，Subject须有具名exact scope。`IDENTITY_CLIENT_ID`必须是`not-applicable-local-test`，真实OIDC Client ID/认证Provider继续未支持，不能把环境变量当作真实SSO实现。测试Bearer从只读Secret加载，不是JWT；原HostAuthorizationAdapter仍负责严格身份、scope、revocation及append-only audit。

`EXTENSION_MODE=none`时移除其他Extension字段；`local`时lock/catalog/key ID/key Secret须成组提供。lock固定Runtime源SHA、Kit 1.0.0/fingerprint和完整有序wheel集合；只读取已有、只读且摘要匹配的wheel，验证catalog/HMAC后加载批准模块，并调用原Runtime loader再次验证manifest/config/compatibility/resolution。bootstrap不签发catalog、不写配置、不安装或下载、不扫描entry points、不热更新。API与Worker使用同一配置、Secret和已批准集合，变更需重启和重新核验；可信同进程Extension并非安全沙箱。

## 企业 Runtime OCI 镜像

`infra/enterprise/image-inputs.v1.json`固定已验证P8-17 Runtime归档、wheel、requirements、源SHA与基础镜像digest。`scripts/enterprise_image_build.py`验证归档全部payload后，仅以wheel、锁定依赖、Schema、OpenAPI、migration和metadata生成context。原发行Dockerfile因缺少COPY源不能在发行包内独立构建；构建报告保留实际失败摘要，新Dockerfile安装原wheel，不复制仓库应用源码。

在clean实施SHA运行：

```text
uv run python scripts/enterprise_image_build.py --output build/enterprise-container/staging/<unique-build> --report build/validation/ci-enterprise-image.json
```

默认只下载清单指定的Provider artifact并核验摘要；过期或缺失立即失败。已保留相同归档可显式传`--archive <path>`，摘要要求不变。构建侧需要Docker、gh及联网依赖安装/漏洞数据库；消费侧使用导出的tar与SHA-256，不需要uv、npm、pip或开发源码。`--candidate`仅用于本地未提交验证，不作为最终镜像。

交付tag为`plantnexus-aps-runtime:0.1.0-<40位封装SHA>`，不使用latest。镜像固定linux/amd64、UID/GID 10001，OCI labels区分封装SHA与Runtime源SHA `39149091859b35b1303002a237a3cf1344572773`；Runtime 0.1.0、Application/Core 0.0.0、Schema 2.10.0不被重新解释。未推registry时RepoDigest为空，以实际image ID及tar SHA-256验收。

同一image ID验证API `uvicorn app.api.app:app`、Worker `celery -A app.jobs.celery_app:celery_app worker`、migration `alembic -c alembic.ini heads`及独立Validator函数入口。验证在禁网、只读、无capabilities容器执行，migration head须为`0009_host_authorization_audit`。这些是入口/import检查；实际配置、数据库升级、readiness及业务闭环归后续部署验收，不能借用旧operations镜像PASS。

镜像仅限未签名内部TEST/SIMULATION。SBOM、许可证及未关闭系统漏洞见[安全说明](security.md#企业镜像扫描与未关闭风险)；构建PASS不等于Production安全批准。

本页定义P8-09起始、P8-13扩展后的Runtime工程候选可重复安装与fail-closed启动顺序，记录TASK-P8-10隔离Compose靶场对当前声明Runtime身份的真实部署结果，并说明P8-11可选Frontend的独立分发边界。它不授予Production部署、签名或发布权限。

P8-17 Exit只把本页既有部署、可观测、备份恢复、Runbook和Extension-enabled target证据作为fresh审计输入，没有创建新的部署target或promotion。先前候选SHA的独立operations演练通过，但FULL中的第二次演练因依赖Celery自行重连而出现`WORKER_PROBE_FAILED`；TASK-P8-20已固定“Redis/API ready后显式restart同一exact image/config Worker，再等待具名pong”，并在新SHA的独立operations及FULL内重复演练中同时通过。最终P8-17精确Provider再次通过这两条演练并得到`READY`。该纠正不改变target或Runtime identity；内部交付仍只能标记为`TEST/SIMULATION`，不能省略真实环境preflight、身份/authority、数据备份责任或Production Gate。

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
