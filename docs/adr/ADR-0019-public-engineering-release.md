---
doc_id: ADR-0019
title: Public Engineering Release and Independent Artifact Provenance
status: accepted
spec_version: 0.3.0
phase: P8
normative: true
source_sections: [95, 97, 101, 106, 114]
last_reviewed: 2026-09-14
---

# ADR-0019 — Public Engineering Release and Independent Artifact Provenance

## Context

项目需要通过 GitHub 分发离线部署包、Runtime、Developer Kit 和公共接口文档。既有 Kit 的 Runtime 已落后于独立验证的 Runtime；同版本覆盖会破坏企业锁定与回放。项目所有者明确批准公开未签名工程发行及相应规则，尚未提供外部签名 authority。

## Decision

GitHub tag 标识整组发行，各组件内部版本独立。新 Kit 使用独立版本和追加式 registry；保留 Kit 1.0.0，Kit 1.0.1 精确嵌入已验证 Runtime 0.1.0。Kit 的组装提交与 Runtime 的来源提交分别记录；独立来源必须同时锁定完整提交、归档 SHA-256 和 Runtime fingerprint，并由验证器检查嵌套原字节。既有 Kit 1.0.0 同源规则继续执行。

新增显式 `public-engineering` 校验 channel，仅接受新 Kit 中的 `UNSIGNED_PUBLIC_ENGINEERING` distribution 声明。该声明允许公开下载，明确 `signature_present=false`、`production_authorized=false`。原 `public` 与 `production` 信任提升路径继续以 `KIT_SIGNATURE_REQUIRED` 拒绝缺少外部签名的制品；SHA-256 只证明内容身份。

发布须绑定成功的 exact Provider、四类资产逐文件摘要与内部版本。默认工程 verifier 仍可核验旧 Kit；旧资产元数据不追写公开授权。外层发行清单准确说明冻结 Runtime 和离线包的历史工程元数据及其来源。

新 Kit 必须完成重复构建、clean install、两份独立 Extension conformance、旧 Kit 回放、显式升级/回滚、兼容负例和供应链检查。企业升级仍需自己显式选择，公开可下载不授予运行时 Extension 信任，也不构成业务 UAT 或 Production 就绪。

## Consequences

纠正后的 Runtime 可进入新 Kit，无需为文档或组装变化重发相同 Runtime bytes。消费者需同时核对发行 tag、组件版本和摘要。发行工程负责人维护资产与兼容记录；企业负责代码、配置、运行 authority、升级与业务验收。发现已发布问题应撤回或另发新版本，禁止静默替换。

## Alternatives

覆盖 Kit 1.0.0 会破坏不可变性；把所有内部版本改为 tag 版本会混淆兼容维度；自签名冒充外部信任不可接受。等待外部签名不符合已批准的公开工程分发目标。

## Validation

旧 Kit 合同回归、新 Kit 双构建和锁定/来源篡改负例、公开工程与 Production channel 区分、clean install 双 Extension、升级回滚、SCA/license、资产与 GitHub 上传摘要核对。

新公开 Kit 使用 `aps-developer-kit-release-manifest.v2`，在 v1 字段上增加必需的 distribution 声明。读取器保留 v1 精确字段检查；不允许给旧 v1 清单静默添加字段。业务 Schema Set 不变。
