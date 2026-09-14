# 离线企业部署候选 — TEST/SIMULATION

本包未签名，仅供内部工程使用。P8-28 独立 clean Linux 验收与 P8-29 最终封存尚未完成，不能作为 Production、UAT 或最终权威交付。Runtime、镜像封装与本包封装分别记录完整 SHA；Developer Kit 只记录已验证兼容身份，不包含 Kit 或企业源码。

## 校验与解包

从可信交付记录取得归档 SHA-256、SHA256SUMS 文件 SHA-256 和 Runtime image ID。旁置文件证明传输完整性，不是签名或可信来源。先比较可信期望值，再执行 `sha256sum -c <归档名>.sha256`。由交付方的安全校验器验证归档成员后，在新建的空目录解包：`tar --no-same-owner -xzf <归档名>.tar.gz`。不要解包到已有安装目录。进入顶层目录执行 `sha256sum --strict -c SHA256SUMS`；任何失败均停止。

MANIFEST.json 枚举普通成员的路径、大小、SHA-256、权限、镜像来源和工具要求。它不包含自身及 SHA256SUMS；SHA256SUMS 覆盖 manifest 和所有 payload，排除自身。最后产生归档及包外 sidecar。追加 evidence 必须重新封存；payload_fingerprint 变化必须重新验收。

## 系统和配置准备

需要 Linux x86_64、Docker Engine 27+、Compose 2.30+、POSIX sh、GNU coreutils、awk、find、tar 和 gzip。无需宿主 Python、uv、npm、Git、构建工具或网络下载。Docker 数据目录须预留三个 tar 展开及持久化数据的空间；slot 至少 1 GiB，备份另行按实际数据预留容量。

安装目录及 slot 均使用不含空格的规范绝对路径，所有父级和成员禁止符号链接。slot 位于包外，包含 config/ 与 secrets/。用 config/.env.example 和 configuration-matrix.v1.json 准备完整 deployment.env、policy、证书和资源配置，替换全部 __REQUIRED__，并按 JSON 合同恢复数值类型。包内模板不能直接启动。Secret 保存在独立 secrets/，只读挂载；权限须让业务 UID 10001 可读，不把值放入 argv、报告、Compose 插值或包内。

仅支持 ENVIRONMENT=test、DATA_PLANE=simulation、LOCAL_TEST_TOKEN。Runtime/Kit 的精确源 SHA 和指纹由 manifest 提供；它们不是包封装 SHA。TLS、identity issuer/audience/subject/scope、policy、CPU、内存及 Worker 并发由操作者明确配置，不猜业务策略。API_BIND=0.0.0.0、API_PORT=8000、DATA_VOLUME=/var/lib/plantnexus、BACKUP_VOLUME=/var/backups/plantnexus；配置路径使用 /etc/plantnexus，Secret 路径使用 /run/secrets。

standalone 使用 database:5432 和 redis:6379，三个 Redis index 必须不同，使用 default 用户及同一密码。enterprise 使用明确的既有隔离 PostgreSQL/Redis/broker/result endpoint，包内 PostgreSQL 镜像供备份客户端使用；不创建企业外部服务。API 自带 loopback TLS，无额外 proxy 容器；外部 ingress 和真实认证是环境前提，未在本包实现。

Extension none/local 二选一。local 需要服务器只读的已批准 wheel/catalog/lock/key/config，原 Runtime 执行完整性、兼容和 API/Worker 同身份检查；不允许下载、pip 安装或动态发现。包内不携带可运行企业 Extension 或密钥。

## 四步安装

以下尖括号全部替换为审核后的值，各次调用使用相同七参数：

```text
docker load --input <bundle>/images/runtime.tar
<bundle>/scripts/preflight.sh <bundle> <checksums-sha256> <sha256:runtime-image-id> <slot> <project> <port> standalone
<bundle>/scripts/install.sh <bundle> <checksums-sha256> <sha256:runtime-image-id> <slot> <project> <port> standalone
<bundle>/scripts/start.sh <bundle> <checksums-sha256> <sha256:runtime-image-id> <slot> <project> <port> standalone
```

preflight 验证包和配置，不要求依赖镜像已加载。install 在配置门通过后从包内导入缺失 PostgreSQL/Redis 镜像，以实际 config image ID 核验，不依赖 docker save/load 可能丢失的 RepoDigest。manifest 保留导出时固定 registry digest 与 tar/image ID 的映射；Compose 使用对应 ID，pull_policy=never。其他动作缺镜像即失败。enterprise 将末参数改为 enterprise，也离线导入所需客户端镜像。

install/start 均受控停止 API/Worker，检查依赖并执行已发布 migration 到 0009_host_authorization_audit，再重建具名 Worker、等待 TLS API readiness，并核对 Runtime/Kit/Extension descriptor。重复 start 是受控重启。失败非零，不绕过前置门。status.sh 使用相同参数验证实际健康和配置 receipt；logs.sh 只输出允许的错误码计数；stop.sh 保留容器及数据卷。

## 备份、恢复和回滚

backup.sh 的七参数后加 `<新的绝对备份目录> QUIESCE-<project>`，调用前必须静默所有共享数据库写入者。成功留下 API/Worker 停止，需显式 start。备份包含数据库 dump、安全身份及配置文件摘要，Secret 仍由环境单独保存。

restore.sh/rollback.sh 的七参数后加 `<备份目录> <备份SHA256SUMS的可信摘要> TARGET-<目标project>`。只允许异于源 project 的隔离、停止、空数据库与空 Redis 目标；完整配置和原镜像/Runtime/Kit/Extension 身份必须一致。rollback 额外需要已有 validated.json 的同版本 slot。拒绝覆盖已有数据、自动 downgrade、删除卷或流量提升。Redis 使用新队列，不声称恢复未完成任务。

## 证据与风险

evidence/ 保存镜像报告、原输入映射与依赖安全清单；SBOM/ 分列三个镜像的 CycloneDX 清单。Runtime 的既有漏洞评估保持原结论；固定 PostgreSQL/Redis 的漏洞和许可证枚举是透明的库存记录，不是 Production 安全批准。缺失扫描、Secret 发现、镜像身份或完整性异常均禁止候选通过。无真实配置、备份、日志或客户数据随包分发。

## 工作区身份与审计

必须配置 WORKSPACE_AUTHORIZATION_POLICY_FILE；对应只读 JSON 采用 enterprise-workspace-authorization.v1，固定 TEST/SIMULATION、production_binding=false。示例 principals=[] 拒绝全部工作区身份。每个 principal 显式提供 actor_ref、token_file、capabilities、allow_all_synthetic_resources 和 planning_run_scope/schedule_version_scope/export_job_scope；token 文件与 Headless 身份独立，禁止复用。能力不相互继承，资源范围默认精确 ID；仅隔离 synthetic 库的显式 allow_all_synthetic_resources=true 允许单独的通配字符串。配置变化要求受控重启。

API 的独立 ingress bridge 支持 Docker 27 下的 loopback TLS；内部依赖不发布端口。该 bridge 不提供宿主出口防火墙，应按实际环境配置出口限制。

工作区拒绝审计追加到独立 workspace_audit 卷，标识仅保留散列，写入失败拒绝业务。新备份 enterprise-backup.v2 在 API/Worker 静默后保存数据库与 workspace-audit.jsonl，两者均被摘要绑定。恢复要求目标审计为空；旧 v1 不作为 v2 自动升级。成功业务 audit 仍在数据库事务内。
