---
doc_id: DOC-OPS-013
title: APS Developer Kit 发布、升级与回滚
status: active
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [4, 5, 9, 12, 93, 95, 97, 98, 101, 103, 106, 107, 113, 114]
last_reviewed: 2026-09-10
---

# APS Developer Kit 发布、升级与回滚

## 当前公开工程发行

Developer Kit `1.0.1` 使用 `infra/release/developer-kit-release-policy-1.0.1.v1.json`，独立于 GitHub tag `v0.1.0`。Runtime 仍为 `0.1.0`，SDK/Tooling/Template 仍为 `1.0.0`。新 Kit 直接包含来源 `39149091859b35b1303002a237a3cf1344572773` 的 Runtime，归档 SHA-256 为 `7c90ba63b0ba950eb256488c5647e9463760eb01c720b69a744bff1a3ce742fc`。Kit 自身 source commit 记录组装代码身份，不能替代上述 Runtime 身份。

[ADR-0019](../adr/ADR-0019-public-engineering-release.md) 允许经所有者授权的 `UNSIGNED_PUBLIC_ENGINEERING` 下载。验证器使用 `channel="public-engineering"`，要求包内明确声明；旧 Kit 不能自动获得此声明。`public` 和 `production` 继续拒绝没有外部签名的信任提升。SHA-256 和清单不是数字签名。

Kit `1.0.0` 是保留的正式前代，不覆盖其 registry/归档。升级到 `1.0.1` 时显式修改项目 Kit 锁，重建 Extension，再用新包 conformance CLI 验证单项目及共同部署集合；API/Worker 必须使用同一新 Kit fingerprint。回滚恢复保留的旧项目锁、旧 Kit/Runtime/Extension/config 原字节，不混搭，不降级数据库。无数据库或 Runtime bytes 变化的 Kit 组装更新不新增 migration。

离线部署包保留其已验收的 Kit `1.0.0` provenance 基线，不包含企业 Extension。新 Kit 的工程 conformance 不自动批准在该离线部署组合中运行新 Extension；企业仍需对自己选定的完整部署集合验证。以下章节中“当前/首个”均指历史 `1.0.0` 发行，旧组装命令不可用于重发该版本。

## P8 Exit与内部交付

TASK-P8-17已核验Kit `1.0.0`的Provider lineage、六层不可变合同、两个独立Extension重放、Runtime动态兼容与no-auto-upgrade边界，没有重新运行assembler或改变registry。P8 Exit通过后形成的最终内部交付把冻结Kit `1.0.0`、P8-18后独立Runtime artifact及二者的binding/compatibility evidence并列打包；该外层交付索引不是新的Developer Kit版本，也不声称纠正Runtime已经嵌入Kit `1.0.0`。

冻结Kit内部继续保留`UNSIGNED_ENGINEERING_CANDIDATE`元数据；外层最终成果标记为`UNSIGNED_INTERNAL_ENGINEERING_DELIVERY`并明确省略外部PKI步骤。SHA-256、manifest和checksum仍保留以识别内容。外部/Production promotion继续要求独立签名authority和发布审批，不能从“内部可交付”反推信任结论。

## 1. 当前工程发行

首个正式编号的Developer Kit为`1.0.0`，仅通过repository/CI内的append-only、content-addressed工程channel交付。它精确绑定Runtime `0.1.0`的归档digest与code commit、Extension SDK `1.0.0`、Extension Tooling `1.0.0`、Enterprise Extension模板`1.0.0`、Alpha/Beta synthetic示例、兼容矩阵、锁文件、文档、CycloneDX SBOM和许可证报告。

该Kit的签名状态是`UNSIGNED_ENGINEERING_CANDIDATE`。SHA-256、逐文件checksum和canonical manifest用于内容身份及待签输入，不等于PKI签名。当前没有获批外部key或签名authority，因此public/Production promotion必须以`KIT_SIGNATURE_REQUIRED`拒绝；不得生成自签名文件冒充信任。

## 2. 组装与验证

P8-15发布候选CI先生成同一exact SHA的P8-09 Runtime release，再运行：

```powershell
uv run python -m aps_developer_kit.check `
  --root . `
  --release-output build/release `
  --kit-output build/developer-kit `
  --report build/validation/p8-developer-kit.json `
  --security-report build/validation/p8-developer-kit-security.json `
  --upgrade-report build/validation/p8-developer-kit-upgrade-rollback.json `
  --benchmark-report build/benchmarks/p8-developer-kit.json
```

发布前必须满足：tracked input clean；Runtime归档和sidecar绑定当前提交；相同输入双构建逐字相同；manifest、lock、checksum和嵌套Runtime lineage通过；Kit在clean Python环境安装；包内CLI对两个独立Extension完成Runtime conformance；兼容正负例、旧项目重放、显式升级、SBOM/license/SCA和回滚证据全部PASS。

输出位于`build/developer-kit/registry/versions/1.0.0/sha256/<digest>/`，registry index把Kit版本唯一映射到digest、release fingerprint和code commit。同一版本出现不同bytes必须以`KIT_REGISTRY_CONFLICT`拒绝；修复需要新Kit版本，不能覆盖旧目录或index记录。CI artifact只是工程交付面，不创建GitHub Release、tag、外部registry或Production批准。

### P8-18之后的不可变基线

Kit `1.0.0`以P8-15 final `87e2f1e814c75fbc25e82a89288f14b80831209b` / Provider run `34320622291`及fingerprint `sha256:ee2a3a407337e595ca724ed2a92540e911c5fad7272e472f2d3ef3297a14a361`冻结。P8-18修改Runtime执行链，但不发布或重新组装Kit；因此后继CI不得把变化后的Runtime传给`aps_developer_kit.check`并写入相同`1.0.0` registry位置。该操作应以`KIT_BOUNDARY_VIOLATION`或`KIT_REGISTRY_CONFLICT`拒绝，而不是通过放宽assembler范围解决。

P8-18 CI改为重跑Kit的contract、unit、property、integration、security和validation六层不可变合同，并在后续Runtime产品步骤生成Developer Kit binding证据，验证Extension仍锁定上述Kit version/fingerprint且API、Worker和work item一致。这只是当前Runtime消费既有Extension开发基线的兼容证据，不是新的Kit artifact。若需要在Developer Kit中交付纠正后的Runtime，必须创建独立发布Task、分配新Kit版本、追加registry记录并重跑完整组装/clean-install/兼容/安全/升级/回滚流程；既有企业项目可继续使用已验证版本，不自动迁移。

## 3. 企业项目安装和开发

解包后使用Kit内的Runtime依赖锁、Runtime wheel、SDK wheel、工具依赖锁和tooling wheel建立clean环境。Extension项目必须保留`enterprise-extension-project.v1.json`与`pyproject.toml`中的五项精确版本锁，并使用包内`tools/aps_extension_conformance.py`、SDK wheel和Core source hash inventory进行检查。宿主仍只调用Headless HTTP API；Extension不在宿主或浏览器执行。

当前支持矩阵只有：Kit `1.0.0` + Runtime `0.1.0` + SDK `1.0.0` + Tooling `1.0.0` + Template `1.0.0`。任何unknown、mixed、floating或自称“latest”的组合必须在安装或Runtime装载前拒绝。Kit内示例是synthetic参考，不是客户规则、行业认证或Production配置。

## 4. 显式升级

Core、Runtime、SDK或Kit发布新版本不会修改企业仓库、lock或已部署artifact。升级必须由企业owner显式选择目标Kit，在独立变更中更新精确锁，重建Extension artifact，并对单项目及共同部署Extension set重跑全部conformance和业务UAT。SDK breaking change必须提升major；Runtime/Core即使保持SDK API不变，也必须发布新兼容矩阵并重放企业项目。

P8-14的`0.0.0-not-published`只是一份synthetic/unpublished predecessor fixture，不是曾承诺支持的正式Kit。它可用于证明旧项目仍能重放及不会自动升级；从该fixture迁移到`1.0.0`仍需explicit opt-in和重新验证，不能在Runtime启动时隐式改写。

## 5. 回滚与撤回

升级失败时停止新Kit promotion，保留失败报告和全部不可变bytes，并恢复企业仓库中上一组明确锁定的Runtime/SDK/Kit/Extension/config组合。首个正式Kit没有可宣称的上一正式Kit，因此当前工程回滚只可恢复P8-14 synthetic项目锁或撤回`1.0.0`候选；它不是Production回滚证明。

如果Runtime migration或数据状态发生变化，必须另按Runtime release政策使用备份恢复或获批forward-fix，不得仅替换wheel。Extension配置、artifact、catalog和Runtime必须作为一个已验证集合回退，不能从请求临时关闭Validator或混合新旧版本。

## 6. 支持与责任边界

`PlantNexus APS Release Engineering`只负责repository/CI工程发行、兼容证据和候选撤回。企业Extension owner负责业务语义、代码审查、配置、artifact批准、UAT和升级选择；Production release/operations/security authority、外部PKI、SLA和支持窗口仍须具名形成。后续Kit只能在新版本的support policy中显式deprecate旧版本，且不得删除旧bytes或强制现有项目迁移。

## P9 候选组合与验证命令

内部候选为 Kit `1.1.0` + Runtime `0.2.0` + SDK/Tooling/Template `1.0.0`。支持矩阵精确锁定五项版本，Kit lock 进一步锁定 Runtime source commit、archive digest、fingerprint，以及所有 wheel、模板、文档与依赖摘要。SDK 接口未增加，不能把 Runtime 的 P9 功能称为新 SDK 功能。

```text
uv run python -m app.infrastructure.release.p9_check --root . --out build/p9-delivery --predecessor <retained-kit-1.0.1.zip>
```

输出目录必须未存在，输入 checkout 必须 clean committed。前代归档必须匹配已发布 SHA-256 `e45cc42ba4ee0e9ee032a8b7e7eae9c23db7bbbe6012e5f66d6cc46bb3d00a04`，不能在当前源码上重构同名旧版本代替。Gate 保留双构建候选、安装后 JUnit、数据库迁移/恢复、供应链及组合报告；失败目录原样保留，修正后使用新目录。

示例和模板仅在组装临时副本显式 relock；原 P8 源项目不变。对企业项目的升级仍需 owner opt-in、相同新组合上的项目及完整 Extension-set conformance。未知/浮动 Runtime、混搭 SDK/tool/template、来源不符和缺少外部签名的 public/Production promotion 均拒绝。

从 0009 升级至 0010 前先停止写入并保存可恢复数据库。回退必须恢复原数据库备份和旧 Runtime/Kit/Extension/config 整组身份；不能将删除后继数据表的 downgrade 称为无损回退。P9 Gate 用保留的旧 wheel/migrations 建立含 audit 数据的 0009 库，新包升级后核对保留数据，再以旧包恢复备份并复核 head/完整性。此证据限 synthetic SQLite 工程环境。
