---
doc_id: DOC-OPS-RELEASE-001
title: APS Runtime 发布、版本与回退合同
status: baseline
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [59, 60, 61, 65, 95, 97, 98, 99, 100, 101, 106, 113, 114]
last_reviewed: 2026-09-07
---

# APS Runtime 发布、版本与回退合同

## GitHub 工程发行

GitHub tag 标识一组可下载资产，不替代 Runtime、SDK、Kit、Schema 或数据库版本。发行提供离线部署包、Runtime 包、Developer Kit、公共接口与文档包及 SHA-256 清单。Runtime/离线包复用已验证的不可变原字节；其历史工程元数据保留，外层发行清单记录公开下载授权、来源和当前验证。

依据 [ADR-0019](../adr/ADR-0019-public-engineering-release.md)，`UNSIGNED_PUBLIC_ENGINEERING` 仅授权工程下载，不声明外部签名或 Production 就绪。新 Kit `1.0.1` 精确嵌入纠正后的 Runtime `0.1.0`；SDK 为 `1.0.0`。以下早期 Runtime 章节中的未发布 SDK/Kit 占位描述历史组合，实际使用须以下载资产的 lock/manifest 为准。

## 发布身份不是单一“APS 版本”

首个Headless Runtime工程候选的兼容矩阵如下。每个维度独立升级和判断，禁止用Runtime版本覆盖Schema、API、Core、Application或数据库版本。

| 维度 | 当前值 | 兼容要求 |
|---|---|---|
| Runtime distribution | `0.1.0` | distribution与运行载体版本 |
| Application package | `0.0.0` | Python wheel的研发占位版本 |
| APS Core | `0.0.0` | Solver/Validator核心实现版本 |
| Headless HTTP API | `headless-http.v1` | 只按既有v1 additive规则演进 |
| Schema set | `2.10.0` | document自身版本和immutable bytes仍为权威 |
| Database | `0009_host_authorization_audit` | 必须是完整、线性的Alembic链 |
| Extension SDK | `0.0.0-not-published` | 当前未发布，不允许加载企业Extension |
| Developer Kit | `0.0.0-not-published` | P8-15前不得宣称形成 |
| Plugin Registry | `plugin-registry.v1` | 只有协议占位，默认Extension集合为空 |

版本来源由`app`包常量、`pyproject.toml`和发布policy交叉校验。版本任一不一致，构建或preflight必须失败；企业项目不会因Core/Runtime发布而自动升级。

## 权威发布物

P8-09的权威distribution是面向`CPython 3.12.13 / linux / amd64`的确定性`tar+gzip`，不是本地Compose、未固定digest的容器镜像或Frontend bundle。归档包含：

- application wheel、`uv.lock`、带hash的runtime requirements与Python pin；
- 完整Alembic脚本、`alembic.ini`、全部已发布Schema和当前/兼容基线OpenAPI；
- canonical release/compatibility/migration manifest、CycloneDX 1.5 SBOM、许可证报告和逐文件checksums；
- 当前release与vulnerability policy，以及default-empty Extension边界；
- 受控Dockerfile副本，作为派生镜像输入，不是Production镜像身份。

归档明确排除`demo/**`、Frontend、第三方connector、Enterprise Extension、凭据和运行数据。输出只写`build/release/sha256/<archive-digest>/`，同一内容地址只能重放相同bytes；不同bytes不得覆盖。归档旁的`.sha256`是外层传输校验，归档内manifest fingerprint和逐文件checksum是内层内容校验。

## 构建与机器验证

从clean checkout运行：

```powershell
uv run python -m app.infrastructure.release.check `
  --root . `
  --release-output build/release `
  --report build/validation/p8-runtime-release.json `
  --compatibility-report build/validation/p8-runtime-release-compatibility.json `
  --migration-report build/validation/p8-runtime-release-migration.json `
  --security-report build/validation/p8-runtime-release-security.json `
  --benchmark-report build/benchmarks/p8-runtime-release.json
```

该命令必须完成两次wheel和两次归档字节比较、内容地址/sidecar、clean venv的hash-locked依赖安装、API/Worker/Validator import smoke、preflight正负例、完整migration replay、SBOM/license与SCA/VEX检查。`SOURCE_DATE_EPOCH`取Git commit timestamp且不得早于wheel ZIP支持的1980-01-01；时间、路径、owner、tar顺序和gzip header均固定。工程size/timing只作为无阈值baseline，不能推导Production SLA或容量。

## 签名、SCA与许可证

当前状态必须写成`UNSIGNED_ENGINEERING_CANDIDATE`。canonical manifest和外层SHA-256是可签名输入，但仓库没有获批signing key、Production release authority或远程registry credential，因此不能生成伪签名、push或promotion。

SBOM覆盖锁定runtime graph的51个组件（包含application和`psycopg[binary]`选择），许可证表达式必须逐组件出现在reviewed policy中，unknown或未允许identifier直接失败。`uv audit`的每条当前finding必须恰好匹配一个VEX assessment；dependency lock、advisory集合或受影响源码使用变化时必须重新审查。`NOT_AFFECTED`只描述当前Headless Runtime使用边界，不是依赖无漏洞或Production安全认证。

## Upgrade与rollback

`0.1.0`没有声明可自动升级的前置Runtime，`upgrade_from=[]`。未来Runtime/Core升级必须发布新版本、新兼容矩阵和新Developer Kit候选；已验证企业项目可继续锁定旧Runtime/SDK/Kit，不得静默替换。

数据库升级前必须完成备份、停止写入并验证目标artifact；升级只允许执行归档中的线性chain到其exact head。所有现有downgrade均按“可能破坏数据”处理。工程回放明确证明`0009 → 0008`会删除append-only授权审计表和其中记录，因此Production不能把Alembic downgrade当作无损回退。受支持的回退顺序是：停止新流量和Worker、保留失败证据、恢复升级前数据库备份并重新部署上一份获批不可变artifact；若无可验证备份，则走经批准的forward fix。禁止覆盖旧版本、重写migration或删除历史审计来“回滚”。

## 支持与Production边界

Runtime归档自身继续保留`P8_ENGINEERING_CANDIDATE`channel元数据；P8最终内部交付保证该exact artifact可重建、重哈希和回放，直到新的Runtime release以独立版本和兼容证据显式取代。该内部支持边界不是Production SLA。

TASK-P8-10在`TEST/SIMULATION`靶场补充了真实PostgreSQL/Redis、API/Worker/Validator、依赖故障、备份恢复及same-artifact dual-slot配置回退证据，同时保持所有Runtime构建输入相对P8-09 SHA零变化。该演练发现并显式处理Alembic version column长度bootstrap；因此不能把P8-09原“裸PostgreSQL迁移”叙述外推为已验证。P8-18/19随后补充了synthetic Enterprise Extension组合兼容与恢复证据；最终成果仍没有Production部署、真实企业UAT、容量、SLA、retention、signing、release authority或跨版本rollback结论。

## P9 内部交付候选

P9-10 使用独立 Runtime `0.2.0`、Developer Kit `1.1.0` 与部署归档 `0.2.0`；Application/Core `0.0.0`、SDK/Tooling/Template `1.0.0`、Schema Set `2.11.0` 和 database `0010_runtime_replan` 分别记录。新组合只属内部未签名工程候选，不继承 v0.1.0 的公开下载授权。

新增 `runtime-release-policy-0.2.0.v1.json` 与 `developer-kit-release-policy-1.1.0.v1.json`。候选 builder 从 clean committed input 构建原 wheel，再按 `p9-runtime-version-materialization.v1` 只生成 wheel 中的 Runtime metadata 常量与归档 pyproject 的 Runtime 版本。`app/p9-build-provenance.json` 保存源 wheel、policy、原/生成 metadata SHA-256 和完整 source commit；其余应用源码不变，wheel RECORD 重新生成。不能把源 wheel 与生成 wheel 混为同一字节身份。历史默认 builder 保持原语义。

交付 Gate 双构建 Runtime/Kit，验证干净安装的实际 Runtime 版本和 P9 人工修改、事件、重排、读取与输出链；回放已发布 Kit 1.0.1 的固定摘要，显式升级并通过停机备份恢复旧组合。新制品与报告随 exact Provider 保留，禁止同版本覆盖、自动升级和未经授权的外部发布。

## P9 readiness 合同 patch 候选

当前 P9 builder 形成 Runtime `0.2.1` / Kit `1.1.1`，使用新增精确版本 policy；仅为已有 readiness 503 补充 OpenAPI 声明。原 `0.2.0` / `1.1.0` policy 与制品字节保留，验证器仍能核对旧版本 provenance。Application/Core、SDK/Tooling/Template、Schema Set、database 和依赖均沿用既有版本。候选仍为内部未签名工程制品；交付后独立安装复审，不构成外部发行或阶段 Exit。
